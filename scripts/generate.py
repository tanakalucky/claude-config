"""共通本文からClaude CodeとCodexの配布用入口を生成する。"""

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
NAMES = ("clarify", "review", "review-correctness", "review-tests", "review-design")
TOKEN = re.compile(r"\{\{([a-z_]+)\}\}")
CLAUDE = {
    "tool_boundary": "`disallowed-tools: Write, Edit` で編集ツールを除外している。",
    "request_input": "$ARGUMENTS または直前の会話",
    "orchestration": "- 親のinlineコンテキストで実行する。子agentを直接起動せず、3つのskillをSkill呼出で使う。\n- `allowed-tools` は使わない。",
    "review_execution": "次の3つをSkill呼出で実行し、結果を待つ(各skillは `context: fork`、`background: false`、会話履歴を持たない)。",
    "reviewer_context": "会話履歴は引き継がれない。呼出側が渡した要件・base・対象範囲・差分・適用規約だけを前提にする。",
    "skill_prefix": "",
}
CODEX = {
    "tool_boundary": "このMarkdown自体は権限を変更しない。実行側で読取専用sandboxと承認なし(never)を設定し、変更可能な外部ツールも無効化する。設定できない場合はレビューを開始せず未完了と報告する。",
    "request_input": "skillとともに渡された依頼、または直前の会話",
    "orchestration": """- 親は対象の確定と統合を担当する。3観点は独立した子agentに各1回だけ委譲し、全結果を待つ。同じ観点を3周しない。
- 実行側のモデル・推論量・読取専用条件を確認して報告する。ユーザー指定があればその指定を使い、なければ実行セッションの設定を継承する。指定モデルや推論量が使えない場合は勝手に別の値へ置き換えず未完了とする。不明な実効値は不明と書く。
- 子agentにも同じモデル・推論量と読取専用条件を適用する。skillの読込だけでは子agent起動や権限制御にならない。委譲機能や読取専用条件が用意できなければ該当観点を未完了とし、親による代行を独立レビューと数えない。""",
    "review_execution": "次の3つのskillを、独立した子agentが1つずつ読んで実行する。呼出側は会話履歴に依存しない入力を渡し、結果を待つ。",
    "reviewer_context": """独立したレビュー担当として、このskillを読んで実行する。呼出側が渡した要件・base・対象範囲・差分・適用規約だけを前提にし、会話履歴には依存しない。

モデル・推論量はユーザー指定、未指定なら実行セッションの設定を使う。実効値と読取専用条件を報告し、不明な値は不明とする。Claudeの `model` / `context` / `background` / `disallowed-tools` はCodexの設定ではない。""",
    "skill_prefix": "config-",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="書き込まず生成物の一致を検証する")
    args = parser.parse_args()
    mismatches = []
    for relative, content in render_all().items():
        target = ROOT / relative
        if args.check:
            if not target.is_file() or target.read_text(encoding="utf-8") != content:
                mismatches.append(str(relative))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    if mismatches:
        print("生成物が一致しません:\n" + "\n".join(mismatches))
        return 1
    print("生成物の一致を確認しました。" if args.check else "入口を生成しました。")
    return 0


def render_all() -> dict:
    outputs = {}
    for name in NAMES:
        metadata, body = read_source(ROOT / "shared" / f"{name}.md")
        for host, adapter in (("claude", CLAUDE), ("codex", CODEX)):
            is_command = name in ("clarify", "review")
            entry_name = f"/{name}" if host == "claude" else f"$config-{name}"
            values = dict(adapter, entry_name=entry_name)
            rendered = TOKEN.sub(lambda match: values[match.group(1)], body)
            header = make_header(name, metadata, host, is_command)
            notice = f"<!-- 自動生成: shared/{name}.md と scripts/generate.py を編集してください。 -->"
            if host == "codex":
                relative = Path(f".agents/skills/config-{name}/SKILL.md")
            elif is_command:
                relative = Path(f"commands/{name}.md")
            else:
                relative = Path(f"skills/{name}/SKILL.md")
            outputs[relative] = f"---\n{header}\n---\n\n{notice}\n\n{rendered.strip()}\n"
    return outputs


def read_source(path: Path) -> tuple:
    opening, header, body = path.read_text(encoding="utf-8").split("---", 2)
    if opening:
        raise ValueError(f"frontmatterがありません: {path}")
    metadata = dict(line.split(": ", 1) for line in header.strip().splitlines())
    if metadata["name"] != path.stem:
        raise ValueError(f"名前がファイル名と一致しません: {path}")
    return metadata, body


def make_header(name: str, metadata: dict, host: str, is_command: bool) -> str:
    fields = []
    if host == "codex" or not is_command:
        fields.append(f"name: {'config-' if host == 'codex' else ''}{name}")
    fields.append(f"description: {metadata['description']}")
    if host == "claude":
        if is_command:
            fields.append(f"argument-hint: {metadata['argument-hint']}")
        else:
            fields.extend(("context: fork", "model: sonnet", "background: false"))
        if name != "clarify":
            fields.append("disallowed-tools: Write, Edit")
    return "\n".join(fields)


if __name__ == "__main__":
    raise SystemExit(main())
