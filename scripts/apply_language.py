#!/usr/bin/env python3
"""応答言語だけを日本語に変更する。認証情報や権限設定は操作しない。"""

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "config/settings.japanese.json"


class SettingsError(Exception):
    """既存設定を安全に保持できない場合のエラー。"""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SettingsError("重複キーがあるため変更しません。")
        result[key] = value
    return result


def reject_constant(value):
    raise SettingsError("JSON で許可されない定数があるため変更しません。")


def parse_object(raw):
    try:
        value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise SettingsError("有効な UTF-8 JSON ではないため変更しません。") from error
    if not isinstance(value, dict):
        raise SettingsError("設定の最上位がオブジェクトではないため変更しません。")
    return value


def update_text(raw):
    """他の値と既存の書式を保持し、最上位の language だけを置き換える。"""
    value = parse_object(raw)
    if value.get("language") == "japanese":
        return raw
    decoder = json.JSONDecoder()
    cursor = len(raw) - len(raw.lstrip()) + 1
    open_end = cursor
    last_end = None
    while True:
        while raw[cursor].isspace():
            cursor += 1
        if raw[cursor] == "}":
            break
        key, cursor = decoder.raw_decode(raw, cursor)
        while raw[cursor].isspace():
            cursor += 1
        cursor += 1  # 検証済みのコロンを越える。
        while raw[cursor].isspace():
            cursor += 1
        start = cursor
        _, cursor = decoder.raw_decode(raw, cursor)
        if key == "language":
            return raw[:start] + '"japanese"' + raw[cursor:]
        last_end = cursor
        while raw[cursor].isspace():
            cursor += 1
        if raw[cursor] == ",":
            cursor += 1
    if last_end is not None:
        return raw[:last_end] + ',\n  "language": "japanese"' + raw[last_end:]
    return raw[:open_end] + '\n  "language": "japanese"\n' + raw[open_end:]


def check_path(path):
    for part in (path, *path.parents):
        if part.is_symlink():
            raise SettingsError("シンボリックリンクを含むパスには書き込みません。")


def read_existing(path):
    """通常の settings.json だけを読み、内容を出力しない。"""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SettingsError("通常ファイル以外、またはハードリンクには書き込みません。")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise SettingsError("別のユーザーが所有するファイルには書き込みません。")
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            return stream.read(), info
    except UnicodeError as error:
        raise SettingsError("有効な UTF-8 ではないため変更しません。") from error


def apply_settings(path, dry_run=False):
    """単一キーの変更を同じディレクトリ内の一時ファイルから置換する。"""
    path = Path(os.path.abspath(path))
    if path.name != "settings.json":
        raise SettingsError("対象ファイル名は settings.json に限定しています。")
    check_path(path)
    if parse_object(TEMPLATE.read_text(encoding="utf-8")) != {"language": "japanese"}:
        raise SettingsError("共有テンプレートが単一の日本語設定ではないため変更しません。")
    original, info = read_existing(path)
    changed = update_text(original) if original is not None else '{\n  "language": "japanese"\n}\n'
    if original == changed:
        return {"changed": False, "language": "japanese", "dry_run": dry_run}
    if dry_run:
        return {"changed": True, "language": "japanese", "dry_run": True}
    path.parent.mkdir(parents=True, exist_ok=True)
    check_path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".language-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode) if info else 0o600)
            stream.write(changed)
            stream.flush()
            os.fsync(stream.fileno())
        check_path(path)
        current, current_info = read_existing(path)
        if current != original or bool(current_info) != bool(info):
            raise SettingsError("読み取り後に設定が変わったため変更しません。再確認してください。")
        if info and (current_info.st_ino, current_info.st_mtime_ns) != (info.st_ino, info.st_mtime_ns):
            raise SettingsError("読み取り後にファイルが更新されたため変更しません。")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"changed": True, "language": "japanese", "dry_run": False}


def main():
    parser = argparse.ArgumentParser(description="Claude Code の応答言語だけを日本語にします。")
    parser.add_argument("--settings", type=Path, help="対象の settings.json。未指定時はユーザー設定を使用")
    parser.add_argument("--dry-run", action="store_true", help="書き込まず、変更の有無だけを確認")
    args = parser.parse_args()
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    try:
        result = apply_settings(args.settings or config_dir / "settings.json", args.dry_run)
    except (SettingsError, OSError) as error:
        # OS エラーにはパスが含まれ得るため、詳細を表示しない。
        message = str(error) if isinstance(error, SettingsError) else "ファイル操作に失敗したため処理を停止しました。"
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
