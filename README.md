# Claude Code / Codex 共通設定

コーディング規約と、正確性/安全性・テスト・設計/可読性の3観点レビューを共有する。
対象はClaude CodeとCodex。設定の配布用ファイルを管理するリポジトリであり、
cloneや生成スクリプトの実行だけでは端末の設定を変更しない。

## 構成と編集場所

| 正本 | 用途 | 配布用の入口 |
| --- | --- | --- |
| `rules/coding.md` | 共通コーディング規約 | Claudeのrules / Codexの`AGENTS.md`から明示的に読む |
| `shared/clarify.md` | 実装前の認識合わせ | `commands/clarify.md` / `.agents/skills/config-clarify/SKILL.md` |
| `shared/review.md` | 対象の確定、3観点実行、統合 | `commands/review.md` / `.agents/skills/config-review/SKILL.md` |
| `shared/review-*.md` | 各観点のレビュー本文 | `skills/review-*/SKILL.md` / `.agents/skills/config-review-*/SKILL.md` |
| `scripts/generate.py` | ツール固有のfrontmatter・呼出方法・権限の説明 | 上記10個の入口を生成 |

生成物もcommitする。共通本文を手で二重管理せず、配布先では外部参照の解決や生成処理を不要にする。
既存のClaudeの入口パス・frontmatter・本文の意味は維持する。
Codex用は組込みコマンドと区別するため`config-`を付ける。
symlinkの可否や読み込み元を基準とする相対参照に依存しない、小さな生成方式を選んだ。
共通テンプレートのfrontmatterは1行の`name` / `description` / `argument-hint`のみを扱う。

```sh
python3 scripts/generate.py
python3 scripts/generate.py --check
python3 -m unittest discover -s tests -v
```

Python 3.9以上の標準ライブラリだけを使う。`--check`は書き込まず、不一致・欠落で終了コード1を返す。
本文の方針変更は`shared/`、ツール差分は生成スクリプト、規約変更は`rules/coding.md`を編集する。
生成された入口を直接編集しない。

## 配置と利用

このリポジトリにはinstaller、plugin manifest、hooks、ユーザー設定ファイルはない。
既存端末でコピー・リンクのどちらが使われているかはリポジトリだけでは分からないため、
採用前に配置先を確認する。以下は手動で採用する場合の対応表であり、自動適用はしない。
同名の既存ファイルやsymlinkがあれば上書きせず内容を比較し、必要な変更だけを統合する。

### Claude Code

| リポジトリ内 | プロジェクトだけに適用 | 全プロジェクトに適用する場合 |
| --- | --- | --- |
| `commands/clarify.md`, `commands/review.md` | `<対象repo>/.claude/commands/` | `~/.claude/commands/` |
| `skills/review-correctness/`, `skills/review-tests/`, `skills/review-design/` | `<対象repo>/.claude/skills/` | `~/.claude/skills/` |
| `rules/coding.md` | `<対象repo>/.claude/rules/coding.md` | `~/.claude/rules/coding.md` |

レビューにはcommandだけでなく3つのskillも必要。配布用入口は本文を内包するので`shared/`の配置は不要。
既存の配置を継続でき、新しい設定ファイルの追加や権限変更は必須にしない。
採用先のClaude Codeで`/clarify 依頼内容`、`/review <比較元またはcommit> <要件>`を使う。
`/review`は親のinlineコンテキストから3つのSkillを各1回呼び、結果を待つ。

各観点の`model: sonnet`、`context: fork`、`background: false`、
commandと各観点の`disallowed-tools: Write, Edit`を保存している。
`allowed-tools`による権限付与は追加しない。Write/Editの除外はBashや外部ツールの
全書込を防ぐsandboxではなく、本文のGit読取限定・秘密除外と合わせて使う。
実行環境がfrontmatterに対応しているか、モデルが利用可能かは採用先で確認する。

### Codex

このリポジトリを作業対象として開くと、ルート`AGENTS.md`と`.agents/skills/`が入口になる。
他の対象repoに採用する場合は、`.agents/skills/config-*`の5フォルダを対象repoの
`.agents/skills/`へ配置する。`AGENTS.md`の指示を既存AGENTSに統合し、
`rules/coding.md`も同じルートに配置する(衝突する場合は規約の配置先と参照を一緒に調整する)。
規約リンクは自動includeではなく、AGENTSに明示的な読取指示を記載している。
全端末向けのインストール・`~/.codex`等への切替はこの手順では扱わない。

`$config-clarify 依頼内容`で認識合わせ、`$config-review <比較元またはcommit> <要件>`でレビューする。
`/skills`で5つのskillが見えることを確認する。AGENTSの読込はセッション開始時なので、
配置後は新しいセッションで規約とskillを認識しているか確認する。

レビューを始める**実行セッション側**で、モデル・推論量・読取専用条件を設定する。
ユーザー指定があればそれを使用し、未指定なら既存セッションのモデル・推論量を継承する。
このリポジトリはCodexのモデル名や推論量を固定しない。利用できない指定を黙って置き換えず、
未完了として報告する。実効値を確認できなければ不明と報告する。

CLIで指定を省略して既存設定を使う例:

```sh
codex --sandbox read-only --ask-for-approval never
```

モデル・推論量を指定する場合は、使用可能な値をユーザーが選び、同じ起動に
`--model <モデル名>`と`-c 'model_reasoning_effort="<推論量>"'`を追加する。
アプリ等では同等の設定を実行側で行い、子agentにも引き継がれることを確認する。
変更可能なMCP・Apps等の外部ツールも実行側で無効化する。ファイルsandboxだけで
外部サービスへの書込まで防げるとはみなさない。

親が入力と3観点の結果をまとめ、独立した子agentが各skillを1回ずつ実行する。
skill本文やClaudeのfrontmatterはCodexのモデル・権限・子agent起動を自動設定しない。
子agent用ファイルに`sandbox_mode`等を書くだけでも親の権限を上書きできないため、
レビュー専用セッションを読取専用で開始する。委譲や読取専用条件が使えない場合は、
該当観点を未完了と報告する。実装担当が自分で読み直すことを独立レビューに数えない。

## レビューで共通に守ること

3観点を各1回実施して統合する。報告のみで修正は実装担当が行う。
合意したbaseを固定SHAにし、全taskコミット・staged・unstaged・未追跡を対象にする。
先にファイル名を列挙し、機密・ignoredを除いてから明示パスの差分を読む。
P0/P1/P2の意味、行番号・根拠・最小修正案、不足や失敗を未完了とする扱いは共通本文にある。
再試行ループや根拠の弱い指摘の水増しは行わない。テストは実行と読取判断を区別する。

## 互換性の根拠と確認範囲

2026-10-31に確認した公式資料:

- [Codex AGENTS.md](https://developers.openai.com/codex/agent-configuration/agents-md): ルートから作業ディレクトリまでの指示読込。
- [Codex skills](https://developers.openai.com/codex/build-skills): `.agents/skills`、name/description、`$`での明示呼出。
- [Codex subagents](https://developers.openai.com/codex/agent-configuration/subagents): 独立した委譲と親セッションの設定境界。
- [Codex CLI](https://developers.openai.com/codex/cli/reference): 起動時のモデル・sandbox・承認設定。
- [Claude skills](https://code.claude.com/docs/en/skills): 既存commands互換、fork、model、background、ツール制限。
- [Claude rules](https://code.claude.com/docs/en/memory): `.claude/rules`とユーザー規約。

自動テストは生成の再現性、欠落・手編集の検出、共通本文変更の両入口への反映、
移行前Claude入口との互換性、3観点の参照先、規約参照、ツール固有設定の分離を確認する。
frontmatterを実行環境が守るか、モデルが使えるか、LLMが各観点を完走するかを証明するテストではない。
手元のCLIはCodex 0.42.0 / Claude Code 2.0.55。現行公式仕様のskill探索・委譲・権限制御の
実動作確認には使わず、端末の更新や設定変更も行っていない。採用先での起動・実レビューは別途確認する。
