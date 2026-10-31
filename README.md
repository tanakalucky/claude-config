# Claude Code / Codex 共通設定

アプリのリポジトリへコピーして使う設定一式。生成処理や外部の設定リポジトリへの参照は不要。
共通の指示は`AGENTS.md`、規約・認識合わせ・レビュー本文は`.ai-config/`で一元管理する。

```text
AGENTS.md                      共通の作業指示
CLAUDE.md -> AGENTS.md          相対symlink
.ai-config/
  rules/coding.md              コーディング規約
  workflows/clarify.md         認識合わせ
  review/
    policy.md                 制約・重大度・完了条件・出力形式
    workflow.md               base確定・収集・3観点・統合
    reviewer.md               観点担当の共通手順
    correctness.md            正確性/安全性
    tests.md                  テスト
    design.md                 設計/可読性
.agents/
  review-runtime.md           Codex固有のモデル・権限・委譲条件
  skills/config-*/SKILL.md     Codexの薄い入口5本
.claude/skills/*/SKILL.md       Claude Codeの薄い入口5本
```

## アプリへの配置

`AGENTS.md`、`CLAUDE.md`、`.ai-config/`、`.agents/`、`.claude/`をセットでコピーする。
`.git/`やこのREADMEは配布に不要。隠しディレクトリとsymlinkを保持できる方法を使う。
既存の同名ファイル・ディレクトリがある場合は、上書きせず差分を確認して統合する。
空の配置先なら、たとえば`cp -R`で上記5つをコピーできる(macOS/Linux)。
`CLAUDE.md`のリンク先は常に同じルートの`AGENTS.md`。
Windows等でsymlinkが通常ファイルになってしまう環境は、そのまま使えるとはみなさずリンクを確認する。

```sh
# コピー後のルートで確認
readlink CLAUDE.md
python3 -m unittest discover -s .ai-config/tests -v
```

`readlink`の期待値は`AGENTS.md`。テストはPython 3.9以上の標準ライブラリのみを使い、
リンクと全Markdown参照が配置先の内部で解決することを確認する。
ユーザー領域へのインストール、既存設定の切替、権限変更は自動で行わない。
前の`commands/`・`skills/`・`rules/`配置から採用する場合は、アプリ側の既存入口との重複を確認する。
Claudeの`/clarify`・`/review`・3観点のskill名は維持し、配置は`.claude/skills/`へ統一した。

## 利用方法とツール固有部分

配置後に新しいセッションを開始し、規約と入口を認識していることを確認する。
Markdownリンクは自動includeとして扱わず、入口に明示的な読取指示を記載している。
各リンクはそのMarkdown自身の場所を基準に解決する。

| 用途 | Claude Code | Codex |
| --- | --- | --- |
| 認識合わせ | `/clarify 依頼内容` | `$config-clarify 依頼内容` |
| レビュー | `/review <比較元またはcommit> <要件>` | `$config-review <比較元またはcommit> <要件>` |
| 3観点 | Skill呼出で`review-correctness`・`review-tests`・`review-design` | 独立した子agentが`config-review-correctness`・`config-review-tests`・`config-review-design`を読む |

Claudeの観点担当には従来の`model: sonnet`、`context: fork`、`background: false`を保存した。
レビュー入口と観点担当は`disallowed-tools: Write, Edit`を維持し、`allowed-tools`は追加しない。
これらはClaude固有の設定であり、shellや外部サービスへの書込まで防ぐ完全なsandboxではない。

Codexのモデル・推論量はユーザー指定、未指定なら実行セッションの設定を継承する。
利用できない指定は黙って置き換えず未完了とする。モデル名は固定しない。
レビュー専用セッションを読取専用sandbox、承認要求ありで起動する例:

```sh
codex --sandbox read-only --ask-for-approval on-request
```

指定する場合は`--model <モデル名>`と`-c 'model_reasoning_effort="<推論量>"'`を追加する。
変更可能な外部ツールも実行側で無効化し、子agentへ同じ条件を引き継ぐ。
`.agents/review-runtime.md`は指示であり、skillの読込だけでモデル・権限・子agent起動が設定されるわけではない。
実行条件を確認できない場合や独立した委譲ができない場合は、未完了と報告する。

## 共通方針の編集

共通本文は`.ai-config/`だけを編集する。ツール固有の呼出やモデル設定は各ツールの入口で変更する。
テストはAAA(Arrange・Act・Assert)で準備・実行・検証を分け、形式だけの複雑化は避ける。
正確性/安全性・テスト・設計/可読性を各1回行い、報告のみで統合する。
固定baseからの全差分、機密除外、行番号・根拠・最小修正案、実行と読取の区別、
未完了の明記、再試行ループ禁止は共通方針に定義している。
生成スクリプトや生成物の再生成は不要。

## 互換性と検証

公式仕様は[Codex AGENTS.md](https://developers.openai.com/codex/agent-configuration/agents-md)、
[skills](https://developers.openai.com/codex/build-skills)、
[subagents](https://developers.openai.com/codex/agent-configuration/subagents)、
[Claude skills](https://code.claude.com/docs/en/skills)、
[Claude memory](https://code.claude.com/docs/en/memory)を参照した。

実動作試験は同一base・同一合成差分を持つ隔離コピーで行い、モデル・権限条件・結果・
ファイル不変を[検証記録](.ai-config/validation/README.md)に記録する。
静的な参照検証とCLIの実行結果を区別し、未実施・認証失敗を成功と扱わない。
