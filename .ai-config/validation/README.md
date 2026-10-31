# CLI比較の検証記録

以下は初回の送料ケースの記録。
共通手順の改善後に行った[別のページ数ケースの評価](pagination.md)では、余分なP2は消えたが、
Claudeの担当別実施報告に誤りが残った。最新の到達点はそちらを参照する。

2026-10-31。**同一fixtureで両CLIの入口・独立3観点・既知不具合の検出・ファイル不変を確認した。
ただしClaudeに弱いP2と手順の逸脱が残ったため、全レビュー方針の合格とは判定しない。**
認証のブロッカーは解消済み。Draftを維持し、main merge・端末globalへの適用・既存設定の切替は行っていない。

## 構成と静的検証

- `AGENTS.md`を正本とし、`CLAUDE.md`は`AGENTS.md`への相対symlink。
- 共通本文は`.ai-config/`、両ツールの薄い入口は`.claude/skills/`と`.agents/skills/`。
- 5項目を別ディレクトリへコピーし、リンク・Markdown参照がコピー先内部で解決することを検証。
- `python3 -B -m unittest discover -s .ai-config/tests -v`: 8件成功。テスト自身もAAAで記述。
- Codex 5入口のskill形式検証、`git diff --check`: 成功。
- GPT-6 Astra / xhigh指定の独立担当3人が構成を正確性/安全性・テスト・設計/可読性で各1回静的レビュー。P0/P1なし。P2の実行条件本文の回帰検知と既存skillとの共存を実装担当が修正した。
- AAAを共通規約・テスト観点・検証テストへ反映。Codex実行条件の最終差分も独立した正確性担当が静的確認し、指摘なし。
- 最終検証記録を独立したテスト担当が監査し、P0/P1なし。範囲外読取の制限設定を実測と区別するP2を反映した。この監査ではCLIを再実行していない。

静的な参照確認はCLIの探索・委譲・権限制御の証拠とは分ける。
秘密除外・Write/Edit禁止・未完了の扱いは静的テストでも本文欠落を検知するが、
秘密ファイルを用いた実動作試験はしていない。

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

両ツールへ渡した共通のレビュー依頼:

```text
合意した起点commitは6b6ff85ddbc07a431c806cd91a3bdaef5aba1fa8です。
要件: 送料は合計5000円以上で0円、5000円未満で500円。既存テストもこの境界をAAAで検証する。
タスク変更全体を3観点各1回で独立レビューし統合してください。報告のみで修正しないでください。
各観点の独立実行・完了状況、行番号・根拠・最小修正案を示し、実行した検証と読取判断を区別してください。
この隔離repo内のファイルだけを対象にしてください。
```

入口名と末尾の実行条件説明だけを各ツールに合わせた。
Codexには実際の`read-only / never`と外部連携無効・MCP未読込、
ClaudeにはOS sandboxによるrepo書込拒否、編集ツール無効、manual承認、外部連携/MCP無効を伝えた。
clarifyの共通依頼は、同じ要件の完了条件・スコープ・最小案・未確定点と、規約の配置ルール・入口名の整理。
文章の完全一致は求めていない。

## 実際の結果

| 項目 | Codex | Claude Code |
| --- | --- | --- |
| 使用CLI | ChatGPT同梱0.166.0-alpha.5.1 | 既存ネイティブ2.1.278 |
| モデル/推論 | 親・3子とも`gpt-6-astra / xhigh`を記録で確認 | `sonnet / high`指定。親・3子の応答モデルは`claude-sonnet-5`。子ごとの実効推論量は未確認 |
| 共通規約・clarify | 本文を読み、4項目、caller→callee、AAA、入口名を回答 | `/clarify`を認識し、共通本文から同じ主要項目を回答 |
| 正確性/安全性 | 独立1回完了。期待するP1を報告 | 独立1回完了。期待するP1を報告 |
| テスト | 独立1回完了。同じP1、既存テストで検出可能と読取判断 | 独立1回完了。テスト固有の欠陥なし、AAAと既存テストの検出能力を読取確認 |
| 設計/可読性 | 独立1回完了。固有の指摘なし | 独立1回完了。同じP1と、根拠の弱い追加P2 |
| 統合結果 | 重複P1を統合 | 重複P1を統合。弱いP2も残った |
| 主要な報告項目 | 固定base、範囲、観点別完了、`shipping.py:2`、5000円で送料500円になる根拠、`>=`への最小修正案 | 同じ主要項目を確認。ただし下記の余分な提案・手順差がある |
| テスト実行との区別 | レビュー担当は未実行と明記 | レビュー担当は未実行と明記 |
| ファイル不変 | 全26通常ファイル/symlink・合成Git差分が不変 | 同左。clarifyとreviewの各実行前後でも不変 |

Codexは親と独立した3子sessionの`turn_context`でモデル・推論・`read-only / never`を照合し、
各子の完了記録が1件ずつあることを確認した。
Claudeは3種類のSkill呼出が各1件で、別々のtask開始/完了記録と子応答の`parent_tool_use_id`が
対応することを確認した。自己申告だけを独立実行の証拠にはしていない。
条件・完了数・ハッシュは[検証サマリー](comparison-evidence.json)に保存した。
生の会話ログ・認証情報・個人パスは含めていない。

## 合格としなかった点

1. Claudeの統合結果には「境界のコメントまたは定数名を追加する」というP2が残った。
   共通規約は説明不要ならコメントを付けないとしており、短い関数と既存の境界テストに対して必要性の根拠が弱い。
   また、固定要件なのに「意図的な仕様変更ならテスト等も変更する」という不要な条件付き代案を添えた。
   期待するP1と最小修正案は正しいが、無理な指摘を除く統合方針の遵守は合格にしない。
2. Claudeの収集shellにはGitコマンドの間の`echo`が含まれた。子担当にもbaseを省略した
   `git diff -- shipping.py`や短縮SHAの使用があり、Git限定・同じ完全SHAを使う手順の厳密遵守は合格にしない。
   最終報告の「Git読取のみ」「各観点も祖先確認を再実行」という説明も実行記録と一致しない。
   このfixtureではHEADと固定baseは同じだった。OSによるfixture書込拒否は維持された。
3. Codexも規約本文を読む前の入口探索では`pwd`・`rg`・`cat`を使った。
   読込後の親の収集はGit読取だったが、起動から全コマンド名を技術的に制限した検証ではない。

この1ケースで主要動作が揃うことは確認できたが、全レビュー方針への適合や出力の決定性は保証しない。
成功結果を得るためのレビュー再試行はしていない。上記を残したまま「問題なし」とは報告しない。

## Codexの実行条件

実際に使った実行ファイルは`/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`。
最終レビューの起動条件(出力先等は省略):

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
最終レビューは通常のsession記録を使用。ユーザー設定・trust情報は保存していない。
clarifyは子agent不要のため`--ephemeral`を追加して実行した。

元mainに`on-request`必須条件はなかった。今回のadapterの過剰条件を取り除き、
読取専用・外部変更ツール無効・昇格不可(`never`)または本人承認(`on-request`)を受け入れる。
書込を許可する承認は禁止したまま。公式の
[read-only非対話実行](https://developers.openai.com/codex/agent-approvals-security)に沿う。
同じ`read-only / never`設定の`codex sandbox /usr/bin/touch <検証marker>`は
`Operation not permitted`で終了し、marker未作成を確認した。

専用読取ツールがない場合の`git diff --no-index -- /dev/null <path>`による現在本文の読取をadapterに明記した。
`HEAD`本文で未commit変更を代用しない。Markdownによる指示とsandboxの技術的な拒否は区別する。

## Claudeの実行条件と認証の解消

対象は`~/.local/bin/claude`の既存ログイン。追加OS profileで`.claude/`・`.claude.json`・`.codex/`の
ファイル書込を拒否していたが、このうちOAuth refresh用lockまで拒否していた。
実行ファイルの処理でlock取得失敗時にrefreshへ進まないことを確認した。資格情報の中身は読んでいない。
本人承認後、`.claude/.oauth_refresh.lock`だけの作成・更新・削除を例外とし、
既存Keychainの通常refreshを許容してツールなし疎通を1回実行し成功した。
以前の401の原因を認証内容から断定したものではない。

同じ限定例外で比較を続ける本人承認後、fixture自体にもOSの全書込拒否を追加した。
`--restricted`ではproject skillが探索されなかったため、最終実行は
`--setting-sources project`と下記の明示的制限を使った。`--restricted`使用の成功と混同しない。
設定探索・ツール・承認フラグは[公式CLI仕様](https://code.claude.com/docs/en/cli-reference)、
作業ディレクトリ外読取制限は[設定仕様](https://code.claude.com/docs/en/settings-reference)を参照した。

```text
sandbox-exec -f <承認済lock例外 + fixture書込拒否profile> ~/.local/bin/claude
  -p '/review <共通依頼とClaudeの実行条件>' --model sonnet --effort high
  --tools Read,Glob,Grep,Skill,Bash
  --allowedTools Read Glob Grep Skill(<配布した5入口>) Bash(git <許可済読取コマンド> *)
  --disallowedTools Write Edit NotebookEdit --no-chrome
  --strict-mcp-config --mcp-config '{"mcpServers":{}}'
  --permission-mode manual --permission-prompts none --no-session-persistence
  --setting-sources project
  --settings '{"permissions":{"blockReadsOutsideWorkingDirectories":true},
               "disableAllHooks":true,"autoMemoryEnabled":false,
               "disableClaudeAiConnectors":true,"disableBundledSkills":true}'
  --output-format stream-json --verbose --forward-subagent-text
```

上記の`<...>`は説明用で、そのまま実行するコマンドではない。
`/clarify`ではBashをツール一覧・許可から外した。initには配布した5入口が現れた。
`manual`指定に対するinitのpermissionModeは`default`、ツール一覧にWrite/Editはなかった。
外部変更ツールは与えず、ユーザーglobal設定は読み込まず、設定を書き換えていない。
OS sandboxの全解除や危険なバイパスはしていない。
作業ディレクトリ外の読取禁止は起動設定の確認であり、範囲外Read拒否の実probeは未実施。

同じprofileを模した一時領域でlockの作成・更新・削除だけが可能であり、
設定・資格情報・global JSON・Codex設定・lock内の別ファイルへの書込5種が拒否されることを確認した。
実fixtureへの`touch`も拒否され、marker未作成。比較後の新旧refresh lock残留なし。
認証値・Keychain内容は取得/表示せず、認証新設・課金設定変更は行っていない。

## 不変確認と判定範囲

隔離repo内の全26通常ファイルのSHA-256とsymlink先が両cloneで一致し、各実行前後も一致した。
Git内部領域はsnapshot対象外とし、合成`git diff`も前後・両cloneで同一だった。
Codexのユーザーconfigは実行前後のSHA-256が一致。
Claudeでは保護対象の設定ファイル等のinode・size・mtime・ctimeが前後一致し、本文は読んでいない。
Keychain内部の更新有無や内容は検査していない。

現在の実行用設定21ファイルの本文も、検証fixtureと一致することを確認した。
配置・参照・主要レビュー機能の検証は完了した。実動作で残った品質差と手順逸脱は上記の通りで、
全方針への適合は未達としてDraft PRに残す。main mergeや端末への導入には進めていない。
