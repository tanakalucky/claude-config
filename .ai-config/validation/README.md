# CLI比較の検証記録

2026-10-31。**Codexの入口・独立3観点・既知不具合の検出・ファイル不変を確認した。
Claudeは本人の再ログイン後もAPIが401のため、両CLI比較は未完了。**
認証新設、ユーザー設定の切替、sandbox解除、危険なバイパスは行っていない。

## 構成と静的検証

- `AGENTS.md`を正本とし、`CLAUDE.md`は`AGENTS.md`への相対symlink。
- 共通本文は`.ai-config/`、両ツールの薄い入口は`.claude/skills/`と`.agents/skills/`。
- 5項目を別ディレクトリへコピーし、リンク・Markdown参照がコピー先内部で解決することを検証。
- `python3 -m unittest discover -s .ai-config/tests -v`: 7件成功。テスト自身もAAAで記述。
- Codex 5入口のskill形式検証、`git diff --check`: 成功。
- GPT-6 Astra / xhigh指定の独立担当3人が新構成を正確性/安全性・テスト・設計/可読性で各1回静的レビュー。P0/P1なし。P2の実行条件本文の回帰検知と既存skillとの共存を実装担当が修正した。
- AAA追加を共通規約・テスト観点・検証テストへ反映。後述のCodex実行条件の最終差分も独立した正確性担当が静的確認し、指摘なし。
- 静的な参照確認だけでは、CLIの探索・委譲・権限制御を証明しない。

## 同じ入力を持つ隔離repo

公開`claude-config`のcommit `0fcec775605609af99bca9df90e8a9a1ce5f0b23`を起点に、
配布物と正常な送料計算・AAAテストをローカルcommitへまとめ、独立cloneを2つ作成した。
最終fixture baseは`6b6ff85ddbc07a431c806cd91a3bdaef5aba1fa8`。
両cloneの差分は`shipping.py:2`の`>= 5000`を`> 5000`にした1行だけ。
テスト用コードや不具合はPR branchへcommit/pushしていない。

要件は「合計5000円以上は送料無料、未満は500円」。
既存AAAテストは4999・5000・5001円に対して500・0・0円を期待する。
検証担当が`python3 -B -m unittest test_shipping`を実行し、正常baseは成功、
不具合入りは`[500, 500, 0] != [500, 0, 0]`で失敗した。
これは検証担当の実行であり、レビューagentによるテスト実行ではない。

両ツールへ渡す共通のレビュー依頼:

```text
合意した起点commitは6b6ff85ddbc07a431c806cd91a3bdaef5aba1fa8です。
要件: 送料は合計5000円以上で0円、5000円未満で500円。既存テストもこの境界をAAAで検証する。
タスク変更全体を3観点各1回で独立レビューし統合してください。報告のみで修正しないでください。
各観点の独立実行・完了状況、行番号・根拠・最小修正案を示し、実行した検証と読取判断を区別してください。
この隔離repo内のファイルだけを対象にしてください。
```

入口名と実行側の権限説明は各ツールに合わせる。Codexへは実際の`read-only / never`と
外部連携無効・MCP未読込を伝えた。ClaudeへCodexの設定名を適用したとは説明しない。
clarifyの共通依頼は、同じ要件に対する完了条件・スコープ・最小案・未確定点と、
規約の配置ルール・認識した入口名の整理。文章の完全一致は求めない。

## 実際の結果

| 項目 | Codex | Claude Code |
| --- | --- | --- |
| 使用CLI | ChatGPT同梱0.166.0-alpha.5.1 | 既存ネイティブ2.1.278 |
| 指定モデル/推論 | `gpt-6-astra` / `xhigh` | `sonnet` / `high` |
| 規約・clarify | 共通本文を読み、4項目、caller→callee、AAA、両ツールの入口名を回答 | API認証失敗により未実施 |
| 独立3観点 | 正確性/安全性・テスト・設計/可読性を各1回完了 | 未実施 |
| 既知不具合 | 正確性とテストの同一P1を統合。`shipping.py:2`、5000円で500円になる根拠、`>=`への最小修正案 | 未検証 |
| 報告契約 | 固定base・全範囲・観点別完了状況・行番号・根拠・最小案を明記。実行したGit読取と、テスト失敗の読取予測を区別 | 未検証 |
| 無理な指摘の抑止 | 設計固有の指摘なし。AAA違反・テスト不足・形式的分割の指摘を根拠不足として除外 | 未検証 |
| ファイル不変 | 全通常ファイル・symlink・Git差分が不変 | fixtureは不変だが、レビュー成功の証拠には数えない |

Codexの親と独立した3つの子sessionについて、実行記録の`turn_context`がすべて
`gpt-6-astra / xhigh / read-only / never`であり、各子の完了記録が1件ずつあることを照合した。
agent自身は確認できないモデル実効値を「不明」と報告しており、検証担当が実行記録で補っている。
匿名化した条件・完了数・ハッシュは[検証サマリー](codex-evidence.json)に保存した。
生の会話ログ・認証情報・個人情報は含めていない。

## Codexの実行条件

実際に使った実行ファイルは`/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`。
最終レビューは次の条件で起動した(出力ファイル名は検証用に指定)。

```sh
codex exec --ignore-user-config --sandbox read-only \
  -c 'approval_policy="never"' -c 'model_reasoning_effort="xhigh"' \
  -c 'web_search="disabled"' --model gpt-6-astra --json \
  --disable apps --disable plugins --disable memories --disable shell_snapshot \
  --disable hooks --disable computer_use --disable browser_use \
  --disable browser_use_external --disable image_generation \
  '$config-review <上記の依頼と実行条件>'
```

`--ephemeral`では履歴をforkする子の起動に`no rollout found`が出たため、
最終レビューは通常のsession記録を使った。ユーザーの設定・trust情報は保存していない。
`clarify`は子agent不要のため`--ephemeral`を追加して実行した。

元mainの規約に`on-request`必須条件はなかった。今回のadapterが追加した過剰条件を取り除き、
読取専用・外部変更ツール無効・昇格不可(`never`)または本人承認(`on-request`)を受け入れる。
書込を許可する承認は禁止したまま。これは公式の
[read-only非対話実行](https://developers.openai.com/codex/agent-approvals-security)に沿う。
同じ`read-only / never`設定の`codex sandbox /usr/bin/touch <検証marker>`が
`Operation not permitted`で終了し、markerが作られないことも確認した。

Codexの専用読取ツールがない場合に備え、許可済みの`git diff --no-index -- /dev/null <path>`で
現在の本文を取得する方法をadapterへ明記した。`HEAD`本文で未commit変更を代用しない。
最終実行でも、規約本文を読み込む前の入口探索には`pwd`・`rg`・`cat`が使われた。
読込後の親の収集はGit読取に限定されたが、起動からすべてのshellコマンド名を技術的に
制限できたという検証ではない。技術的な書込拒否はsandbox、Git限定は運用上の指示として区別する。

## Claudeの残るブロッカー

対象は`~/.local/bin/claude`(2.1.278)の既存claude.aiログインを使う、小さなAPI疎通。
`--model sonnet --effort high --tools '' --restricted --strict-mcp-config`
`--no-session-persistence --permission-mode manual`を使い、追加のOS sandboxで既存設定領域への書込を拒否した。

本人の再ログイン完了という新しい情報を受け、既知の401を1回再試行したが、
再び`401 OAuth access token has expired. Re-authenticate to continue.`でAPIに拒否された。
通常起動と追加sandbox内の`auth status`はいずれもログインを認識したが、API成功は確認できなかった。
実際に応答したモデルIDも不明。認証値の取得・表示、再ログイン操作、認証設定の変更、追加API再試行はしていない。

本人側で同じ実行ファイルのAPI疎通が成立する状態を確認した後、準備済みの同一fixtureで
Claudeの入口・共通本文読込・独立3観点・期待不具合/報告形式・ファイル不変を確認する必要がある。
認証失敗を設定内容やモデルの不具合と断定していない。

## 不変確認と判定範囲

最終実行の前後で、隔離repo内の全通常ファイルのSHA-256とsymlink先を比較し、一致した。
Git内部領域は対象外とし、`git diff`の合成差分も前後・両cloneで同一だった。
Codexのユーザーconfigも実行前後のSHA-256が一致した。

静的な構成レビューとCodexの合成ケースは確認済み。Claudeの実レビューと両CLI比較は未完了。
Draft PRを維持し、mainへのmerge・端末globalへの適用・既存設定の切替は行わない。
