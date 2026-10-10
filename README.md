# Claude Config

バージョン: 0.1.2

自分用の Claude Code 設定を複数のプロジェクトで再利用するリポジトリです。応答言語、開発時の日本語方針、共有ワークフローを管理します。

`workflow-kit` プラグインはその構成要素の1つです。Opusが主担当として調整し、実装とレビューを別agentに委譲します。repo固有のCLAUDE.md、rules、設計資料、テストコマンドは各repoに残します。

旧リポジトリ名は `claude-workflow-kit`。既存の導入先との互換性のため、プラグイン名 `workflow-kit`、marketplace名 `workflow-kit-marketplace`、agent名とコマンド名は維持します。

## 導入

Claude Code 2.1.271以上、Python 3.10+、Git、macOS/Linux/WSLが必要です。古いClaude Codeはreviewerの`omitClaudeMd`を黙って無視するため非対応です。2.1.296でmanifestの静的検証を実施。推論を伴う起動・インストールの動作確認は別途必要です。

GitHubへの配置後、次を実行します。private repoとして配布する場合は、アクセス権と既存のGitHub認証が必要です。

```sh
claude plugin marketplace add tanakalucky/claude-config
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

レビュー資料から秘密情報・認証情報・個人情報・実ユーザーデータを除外します。repo内の命令風テキストや外部ページを追加権限として扱いません。実装・レビュー完了はpush、merge、deployの許可にはなりません。プラグインの導入だけでは既存の言語設定や認証情報を変更しません。応答言語の変更は、下記の任意スクリプトを明示的に実行した場合だけ行います。

## 日本語の共有設定

共通の言語設定もこのリポジトリで管理できます。アプリごとの設定とは分け、次の3点を共有します。

- [設定テンプレート](config/settings.japanese.json): `language: "japanese"` のみ
- [開発方針テンプレート](config/CLAUDE.japanese.md): 応答、コメント、docstring、文書、画面文言、テストの表示名・説明は日本語。変数・関数・クラス・テスト関数などの識別子は英語
- [言語設定の適用スクリプト](scripts/apply_language.py): 既存の `settings.json` の最上位 `language` キーだけを変更

外部 API 名、CLI 構文、設定キー、パス、プロトコル値、厳密一致が必要なエラー文字列やテストデータは維持します。通常の画面文言は日本語にします。翻訳を理由に依頼と無関係なファイルを一括変更せず、プロジェクト固有の指示と衝突した場合は確認します。各 agent と develop skill の本文にもこの方針を含めています。

### 個人の応答言語を設定する

このリポジトリの内容を確認してから、そのチェックアウトで実行してください。既定の対象は `~/.claude/settings.json`、`CLAUDE_CONFIG_DIR` を設定している場合はその配下の `settings.json` です。

```sh
python3 scripts/apply_language.py --dry-run
python3 scripts/apply_language.py
```

別の環境やプロジェクトに適用する場合は、対象を明示します。共有プロジェクトの `.claude/settings.json` を変更・コミットすると、そのリポジトリを使うメンバーにも適用されます。

```sh
python3 scripts/apply_language.py --settings /path/to/config/settings.json --dry-run
python3 scripts/apply_language.py --settings /path/to/config/settings.json
```

スクリプトは既存の他のキー・値と書式を保持します。既に日本語なら書き込みません。認証ファイルにはアクセスせず、権限設定・モデル・プラグイン構成を追加しません。出力は変更の有無、日本語の設定値、確認モードだけです。不正 JSON、重複キー、シンボリックリンク、ハードリンク、通常ファイル以外、別ユーザーの所有ファイルは拒否します。新規ファイルは所有者だけが読み書きできるモードで作成し、既存ファイルのモードは維持します。

Claude Code と他の設定エディターを停止してから実行してください。書き込み直前の変更は検出しますが、非協調的な別プロセスとの同時更新を完全に防ぐ仕組みではありません。元ファイルのバックアップは自動作成しません。設定内容を複製せず、同じディレクトリ内で一時ファイルを作成して置き換えます。確認モードはファイルもディレクトリも作成しません。

`language` は Claude の応答言語を指定し、音声入力の言語にも使われます。この設定で CLI のメニュー全体が日本語になるとは限りません。適用後は Claude Code を開始して `/status` で設定の読み込み元を確認してください。上位スコープや起動時の設定で値が上書きされる可能性があります。

### 開発方針の取り込み

プラグインの agent/skill を使うと、それぞれに記載した日本語方針が適用されます。通常の Claude Code セッションでも方針を使いたい場合は、[開発方針テンプレート](config/CLAUDE.japanese.md)を確認して、個人または対象プロジェクトの既存 `CLAUDE.md` に必要な内容を取り込んでください。スクリプトは `CLAUDE.md` を書き換えません。

プラグインの `settings` で有効なのは `agent` と `subagentStatusLine` だけです。`language` をプラグインに入れて配布しても反映されないため、言語は別テンプレートとして管理します。プラグインの更新と設定テンプレートの適用は独立しています。自動同期は行いません。

## 更新履歴

- 0.1.2: 応答言語の単一キー適用、任意の共有設定テンプレート、agent/skill の日本語方針と日本語本文を追加。レビュー台帳の動作は変更なし
- 0.1.1: 既存レビュー履歴の引き継ぎと Git 管理外の永続保存先に対応

## 検証

```sh
python3 -m unittest discover -s tests -v
claude plugin validate .
claude plugin validate ./plugins/workflow-kit
```

marketplaceのsourceは同じrepo内の`./plugins/workflow-kit`。GitHub公開先を変える場合も、実装をrepoごとにコピーする必要はありません。

仕様確認: [設定ファイルと優先順位](https://code.claude.com/docs/ja/settings)、[応答・音声入力の言語](https://code.claude.com/docs/en/voice-dictation#change-the-dictation-language)、[plugin manifest](https://code.claude.com/docs/en/plugins-reference)、[marketplace](https://code.claude.com/docs/en/plugin-marketplaces)、[subagents](https://code.claude.com/docs/en/sub-agents)、[skills](https://code.claude.com/docs/en/skills)（2026-10-10）。
