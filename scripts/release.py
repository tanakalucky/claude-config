#!/usr/bin/env python3
"""設定リポジトリの版を検証し、検証済みコミットのタグだけを作成する。"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = Path("plugins/workflow-kit/.claude-plugin/plugin.json")
MARKETPLACE_PATH = Path(".claude-plugin/marketplace.json")
VERSION_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


class ReleaseError(ValueError):
    """曖昧な版、整合性の不一致、変更できないタグを表す。"""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseError(f"JSON のキーが重複しています: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ReleaseError(f"JSON に使用できない値です: {value}")


def read_manifest(path):
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"manifest を読み込めません: {path}") from exc
    if not isinstance(value, dict):
        raise ReleaseError(f"manifest は JSON オブジェクトである必要があります: {path}")
    return value


def validate_release(root=ROOT):
    """版の正本と README 表示、および単一プラグインの参照を照合する。"""
    plugin = read_manifest(root / PLUGIN_PATH)
    version = plugin.get("version")
    if not isinstance(version, str) or VERSION_PATTERN.fullmatch(version) is None:
        raise ReleaseError("plugin.json の version に明示的な X.Y.Z 形式の版が必要です")
    if plugin.get("name") != "workflow-kit":
        raise ReleaseError("plugin.json の name は workflow-kit である必要があります")

    marketplace = read_manifest(root / MARKETPLACE_PATH)
    if marketplace.get("name") != "workflow-kit-marketplace":
        raise ReleaseError("marketplace の name が一致していません")
    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
        raise ReleaseError("marketplace は単一の workflow-kit プラグインを参照してください")
    entry = entries[0]
    if entry.get("name") != plugin["name"] or entry.get("source") != "./plugins/workflow-kit":
        raise ReleaseError("marketplace の name / source が同梱プラグインと一致していません")
    metadata = marketplace.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ReleaseError("marketplace の metadata は JSON オブジェクトにしてください")
    if "version" in entry or "version" in marketplace or "version" in metadata:
        raise ReleaseError("版の正本は plugin.json です。marketplace に version を重複させないでください")

    try:
        readme = (root / "README.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReleaseError("README.md を読み込めません") from exc
    displayed = re.findall(r"^バージョン:([^\n]*)$", readme, flags=re.MULTILINE)
    if displayed != [f" {version}"]:
        raise ReleaseError("README の「バージョン: X.Y.Z」を1つだけ記載し、plugin.json と一致させてください")
    return version


def git(root, *args):
    """値はシェルへ展開せず、Git の独立した引数として渡す。"""
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, text=True, capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReleaseError(f"Git コマンドに失敗しました: git {args[0]}") from exc
    return result.stdout.strip()


def remote_tag_commit(root, tag):
    """通信失敗とタグ未作成を区別し、注釈付きタグは対象コミットまで解決する。"""
    ref = f"refs/tags/{tag}"
    output = git(root, "ls-remote", "--tags", "origin", ref, f"{ref}^{{}}")
    refs = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 2 or fields[1] not in (ref, f"{ref}^{{}}"):
            raise ReleaseError("リモートタグの応答を解釈できません")
        sha, name = fields
        if COMMIT_PATTERN.fullmatch(sha) is None or name in refs:
            raise ReleaseError("リモートタグの応答が不正です")
        refs[name] = sha
    if refs and ref not in refs:
        raise ReleaseError("リモートタグの参照が不完全です")
    return refs.get(f"{ref}^{{}}", refs.get(ref))


def create_release_tag(root, expected_commit):
    """既存タグを動かさず、検証対象と同じコミットに軽量タグを追加する。"""
    version = validate_release(root)
    if COMMIT_PATTERN.fullmatch(expected_commit) is None:
        raise ReleaseError("検証済みコミットの完全な SHA が必要です")
    commit = git(root, "rev-parse", "--verify", "HEAD^{commit}")
    if commit != expected_commit:
        raise ReleaseError("チェックアウトしたコミットと検証済みコミットが一致していません")
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ReleaseError("作業ツリーに変更があります。未変更の検証済みコミットを使ってください")
    tag = f"v{version}"
    existing = remote_tag_commit(root, tag)
    if existing == commit:
        return tag, False
    if existing is not None:
        raise ReleaseError(f"{tag} は別のコミットを参照しています。既存タグは変更しません")

    # 明示した1本だけを送る。競合しても force、タグ削除、付け替えは行わない。
    try:
        git(root, "push", "--porcelain", "--no-follow-tags", "origin", f"{commit}:refs/tags/{tag}")
    except ReleaseError:
        # 同時実行で同じコミットのタグが作成された場合だけ、成功済みとして扱う。
        if remote_tag_commit(root, tag) == commit:
            return tag, False
        raise
    if remote_tag_commit(root, tag) != commit:
        raise ReleaseError(f"{tag} の作成結果を確認できません")
    return tag, True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="manifest と README の整合性を読み取り専用で検証する")
    tag_parser = subparsers.add_parser("tag", help="検証済みコミットのリリースタグを origin に作成する")
    tag_parser.add_argument("--commit", required=True, help="同じ実行で検証した完全なコミット SHA")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            print(f"版と manifest の整合性を確認しました: {validate_release()}")
        else:
            tag, created = create_release_tag(ROOT, args.commit)
            print(f"リリースタグを作成しました: {tag}" if created else f"同じコミットのタグが既にあります: {tag}")
    except ReleaseError as exc:
        print(f"リリースの検証に失敗しました: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
