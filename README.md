# Claude Workflow Kit

複数repoで再利用するClaude Code plugin。Opusが主担当として調整し、実装とレビューを別agentに委譲します。repo固有のCLAUDE.md、rules、設計資料、テストコマンドは各repoに残します。

## 導入

Claude Code 2.1.271以上、Python 3.10+、Git、macOS/Linux/WSLが必要です。古いClaude Codeはreviewerの`omitClaudeMd`を黙って無視するため非対応です。2.1.296でmanifestの静的検証を実施。推論を伴う起動・インストールの動作確認は別途必要です。

GitHubへの配置後、次を実行します。private repoとして配布する場合は、アクセス権と既存のGitHub認証が必要です。

```sh
claude plugin marketplace add tanakalucky/claude-workflow-kit
claude plugin install workflow-kit@workflow-kit-marketplace --scope user
cd /path/to/your-repo
claude --agent workflow-kit:lead --model opus
```

セッション内で `/workflow-kit:develop 変更キーと依頼内容` を実行。継続時は同じ変更IDを伝えます。初回だけ台帳を明示的に初期化します。詳細は[ワークフロー](plugins/workflow-kit/skills/develop/SKILL.md)と[台帳コマンド](plugins/workflow-kit/skills/develop/ledger.md)。

## 動き

- 主担当: Opus。判断・分担・進捗管理を担当し、コードは書かない
- 実装: Sonnet。repoの指示に従い、実装とテストを行う
- 調査: 必要時だけ。外部の技術選定は最大3候補・5ページ・5分。コードベース調査は問い・範囲・終了条件を決め、必要なローカルファイル数は一律制限しない
- レビュー: security、test-adequacy、design-rules-docsの3観点で1ラウンド。読み取り専用のSonnet agentが匿名化済み資料を確認
- P0/P1は修正必須、P2は任意。レビューは開発工程に含め、1変更につき最大3ラウンド。3回後の未解決点は人に返す

モデル設定は組織の制限や環境設定で上書きされ得ます。実際のモデルがOpusでない場合は報告して止めます。agentのツール制限は最小限ですが、主担当のBash利用などは指示上の制約も含み、OSレベルの隔離ではありません。

## 上限と安全性

標準ライブラリだけの`review_gate.py`が変更ID、ラウンド、3観点のclaimと結果をSQLiteに保存します。標準の保存先は共通Gitディレクトリ配下の`workflow-kit`で、PR・push・セッションをまたいでもリセットしません。中断も1回に数え、同時実行と結果の上書きを制御します。状態にソースやレビュー本文は保存しません。

Git管理外の作業には、ソース外の永続保存先を`--state-dir`で明示できます。導入前にレビュー済みの変更は、根拠のハッシュと実際の消費回数を`adopt`で引き継ぎます。過去分は未検証の消費済み枠として記録し、合格や架空のレビュー結果にはしません。既存キーの上書きと回数リセットは拒否します。

上限を強制できるのはこのhelper経由の開始・claimだけです。直接のAgent呼び出し、状態削除、虚偽の結果、別キー作成までは防げません。未検証のhookや「絶対に4回目を防ぐ」という保証はありません。別cloneや別PCで同じ変更を続ける際は台帳を引き継ぎます。

レビュー資料から秘密情報・認証情報・個人情報・実ユーザーデータを除外します。repo内の命令風テキストや外部ページを追加権限として扱いません。実装・レビュー完了はpush、merge、deployの許可にはなりません。既存の`.claude`設定や認証情報を上書きする仕組みは含みません。

## 検証

```sh
python3 -m unittest discover -s tests -v
claude plugin validate .
claude plugin validate ./plugins/workflow-kit
```

marketplaceのsourceは同じrepo内の`./plugins/workflow-kit`。GitHub公開先を変える場合も、実装をrepoごとにコピーする必要はありません。

仕様確認: [plugin manifest](https://code.claude.com/docs/en/plugins-reference)、[marketplace](https://code.claude.com/docs/en/plugin-marketplaces)、[subagents](https://code.claude.com/docs/en/sub-agents)、[skills](https://code.claude.com/docs/en/skills)（2026-10-10）。
