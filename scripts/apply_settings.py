#!/usr/bin/env python3
"""共通 settings.json を個人設定へ反映し、未指定の設定は保持する。"""

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


SOURCE = Path(__file__).resolve().parents[1] / "settings.json"


class SettingsError(Exception):
    """安全に設定を反映できない場合のエラー。"""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SettingsError("重複キーがあるため変更しません。")
        result[key] = value
    return result


def reject_constant(value):
    raise SettingsError("JSON で許可されない定数があるため変更しません。")


def parse_settings(raw):
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError) as error:
        raise SettingsError("有効な UTF-8 JSON ではないため変更しません。") from error
    if not isinstance(data, dict):
        raise SettingsError("設定の最上位はオブジェクトである必要があります。")
    return data


def merge_settings(existing, shared):
    """オブジェクトは再帰的に統合し、配列と他の値は共通設定で置換する。"""
    result = existing.copy()
    for key, value in shared.items():
        if isinstance(value, dict):
            current = result.get(key)
            result[key] = merge_settings(current if isinstance(current, dict) else {}, value)
        else:
            result[key] = value
    return result


def check_path(path):
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise SettingsError("シンボリックリンクを含むパスは使えません。")


def read_file(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SettingsError("通常ファイル以外やハードリンクは使えません。")
    if info.st_uid != os.getuid():
        raise SettingsError("別のユーザーが所有するファイルは使えません。")
    return path.read_bytes(), info


def apply_settings(target, dry_run=False):
    target = Path(os.path.abspath(target))
    if target.name != "settings.json":
        raise SettingsError("対象ファイル名は settings.json に限定しています。")
    check_path(SOURCE)
    check_path(target)
    shared_raw, _ = read_file(SOURCE)
    if shared_raw is None:
        raise SettingsError("共通 settings.json が見つかりません。")
    shared = parse_settings(shared_raw)
    original, info = read_file(target)
    existing = parse_settings(original) if original is not None else {}
    merged = merge_settings(existing, shared)
    # true と 1 など、Python では等しくても JSON の型が異なる値を区別する。
    changed_keys = sorted(key for key in shared if key not in existing or
                          json.dumps(merged[key], sort_keys=True) != json.dumps(existing[key], sort_keys=True))
    result = {"changed_keys": changed_keys, "dry_run": dry_run}
    if not changed_keys or dry_run:
        return result

    target.parent.mkdir(parents=True, exist_ok=True)
    check_path(target)
    descriptor, temporary = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode) if info else 0o600)
            json.dump(merged, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        check_path(target)
        current, current_info = read_file(target)
        if current != original or bool(current_info) != bool(info):
            raise SettingsError("読み取り後に設定が変わったため変更しません。")
        if info and (current_info.st_ino, current_info.st_mtime_ns) != (info.st_ino, info.st_mtime_ns):
            raise SettingsError("読み取り後にファイルが更新されたため変更しません。")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return result


def main():
    parser = argparse.ArgumentParser(description="共通設定を個人の Claude Code 設定へ反映します。")
    parser.add_argument("--target", type=Path, help="対象の settings.json。未指定時は個人設定")
    parser.add_argument("--dry-run", action="store_true", help="変更する最上位キーだけを表示し、保存しない")
    args = parser.parse_args()
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    try:
        result = apply_settings(args.target or config_dir / "settings.json", args.dry_run)
    except (SettingsError, OSError) as error:
        # パスや設定値を含み得る OS エラーの詳細は表示しない。
        message = str(error) if isinstance(error, SettingsError) else "ファイル操作に失敗したため処理を停止しました。"
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
