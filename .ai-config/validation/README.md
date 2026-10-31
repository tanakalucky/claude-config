# CLI比較の検証記録

2026-10-31。**両CLIで同じ振る舞いを確認できた、という合格判定はまだ出していない。**
Claudeは既存OAuthの期限切れ、Codexの3観点レビューは下記の実行条件で未完了。
認証新設、ユーザー設定の切替、sandbox解除、危険なバイパスは行っていない。

## 構成と静的検証

- `AGENTS.md`を正本とし、`CLAUDE.md`は`AGENTS.md`への相対symlink。
- 共通本文は`.ai-config/`、両ツールの入口は`.claude/skills/`と`.agents/skills/`。
- 5項目を別ディレクトリへコピーし、配布物のリンク・Markdown参照がコピー先内部で解決することを検証。
- `python3 -m unittest discover -s .ai-config/tests -v`: 7件成功。テスト自身もAAAで記述。
- 独立したCodex担当3人が新構成を正確性/安全性・テスト・設計/可読性で各1回静的レビュー。
  P0/P1なし。P2の実行条件本文の回帰検知、配置先の既存skillとの共存を実装担当が修正した。
  AAA追加はその後のユーザー指定として共通規約・テスト観点・検証テストへ反映。
- 静的な参照確認は、実際のCLI探索・委譲・権限制御を証明しない。

## 同じ小さな変更を持つ隔離repo

公開`claude-config`のcommit `0fcec775605609af99bca9df90e8a9a1ce5f0b23`を起点に、
今回の配布物と正常な送料計算を検証専用のローカルcommitへまとめ、2つの独立cloneを作成した。
テスト用コードや不具合はPR branchへcommit/pushしていない。

AAA反映後の共通base: `adaeb06cad28f6f90f9e29c5a0e58dd63908bb9a`。
両cloneの差分は`shipping.py:2`の`>= 5000`を`> 5000`にした1行だけ。
要件は「合計5000円以上は送料無料、未満は500円」。
既存のAAAテストは4999・5000・5001円に対して500・0・0円を期待する。
検証担当が`python3 -B -m unittest test_shipping`を実行し、正常baseは成功、不具合入りは失敗を確認した。
これは検証担当の実行であり、レビューagentがテストを実行したという意味ではない。

共通のレビュー入力(入口名だけ各toolに合わせる):

```text
合意した起点commitはadaeb06cad28f6f90f9e29c5a0e58dd63908bb9aです。
要件: 送料は合計5000円以上で0円、5000円未満で500円。既存テストもこの境界をAAAで検証する。
タスク変更全体を3観点各1回で独立レビューし統合してください。報告のみで修正しないでください。
各観点の独立実行・完了状況、行番号・根拠・最小修正案を示し、実行した検証と読取判断を区別してください。
実行側では読取専用と承認要求を設定し、変更可能な外部連携を無効にしています。
この隔離repo内のファイルだけを対象にしてください。
```

期待する結果は、独立した3観点の完了状況と、`shipping.py:2`の5000円ちょうどで送料500円になる
不具合・根拠・`>=`へ戻す最小修正案。文章の完全一致は求めない。

## CLI・モデル・実際の結果

| 項目 | Codex | Claude Code |
| --- | --- | --- |
| 使用CLI | ChatGPT同梱0.166.0-alpha.5.1 | 既存ネイティブ2.1.278 |
| 指定モデル/推論 | `gpt-6-astra` / `xhigh` | `sonnet` / `high` |
| 既存認証の状態 | ChatGPTログイン、短いAPI疎通成功 | claude.aiログインを認識するが、APIは401 |
| 規約・clarify | 共通規約/手順を読取、4項目と入口名を回答 | 認証失敗のため未実施 |
| 独立3観点レビュー | 開始条件を満たせず、3観点とも未実行と報告 | 認証失敗のため未実施 |
| 既知不具合 | clarifyで行番号と最小修正案を回答。レビューとしての検出は未検証 | 未検証 |
| 比較全体の判定 | 未完了 | 未完了 |

Codexのclarifyと非対話レビューはAAA追加前の共通base
`85f4810dbd401eeb7eb9844f473ff7ac84d18630`で実行した。送料差分と期待する境界結果は同じ。
AAA反映後の両repoも準備済みだが、3観点の比較完走とは数えていない。
ClaudeはAPI失敗のため実際に応答したモデルIDは確認できていない。

Codex非対話起動の主な条件:

```text
codex exec --ignore-user-config --ephemeral --sandbox read-only
  -c approval_policy="on-request" -c model_reasoning_effort="xhigh"
  --model gpt-6-astra --disable apps --disable plugins
  --disable memories --disable shell_snapshot --disable hooks
```

実効approvalはCLI側で`never`になった。現在のadapterは承認要求を表示できる条件を要求するため、
レビューは正しく「未完了」と返した。対話CLIも試したが、フォルダの信頼情報をユーザー設定へ
保存する確認で終了し、保存は承認していない。公式には
[read-onlyとneverの組合せ](https://developers.openai.com/codex/agent-approvals-security)もあるが、
今回の承認制約を勝手に緩めて採用してはいない。

Claudeの小さなAPI疎通は`--model sonnet --effort high --tools '' --restricted`
`--strict-mcp-config --no-session-persistence --permission-mode manual`で実行した。
追加のOS sandboxで既存設定領域への書込を拒否し、認証値は表示していない。
結果は`401 OAuth access token has expired`。本人による再認証後の試験が必要。
認証失敗をコード・モデル・skillの不具合と断定していない。

## ファイル不変と残る確認

実行前後に、隔離repo内の全通常ファイルのSHA-256とsymlink先を比較する。
Git内部領域は別管理とし、レビュー前後の`git diff`も照合する。
これまで実行したCodexのclarify/未完了レビュー後はファイル不変。
未実行のClaudeやAAA反映後のrepoが変わっていないことは、動作試験成功の根拠にしない。

残る確認は、Claude本人再認証、Codexの承認条件の確定、同一AAA反映済みbaseでの
両CLIの入口読込・独立3観点・期待不具合/出力形式・ファイル不変である。
生の会話ログ・認証情報・個人情報はこの記録へ含めていない。
