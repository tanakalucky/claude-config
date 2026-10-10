# Claude Config

バージョン: 0.1.3

自分用の Claude Code 設定を複数のプロジェクトで再利用するリポジトリです。応答言語、開発時の日本語方針、共有ワークフローを管理します。

`workflow-kit` プラグインはその構成要素の1つです。Opusが主担当として調整し、実装とレビューを別agentに委譲します。repo固有のCLAUDE.md、rules、設計資料、テストコマンドは各repoに残します。

旧リポジトリ名は `claude-workflow-kit`。既存の導入先との互換性のため、プラグイン名 `workflow-kit`、marketplace名 `workflow-kit-marketplace`、agent名とコマンド名は維持します。

## 導入

Claude Code 2.1.271以上、Python 3.10+、Git、macOS/Linux/WSLが必要です。古いClaude Codeはreviewerの`omitClaudeMd`を黙って無視するため非対応です。2.1.296でmanifestの静的検証を実施。推論を伴う起動・インストールの動作確認は別途必要です。

このリポジトリの marketplace は GitHub 上のプラグインカタログです。Claude の公式ストアへの登録・公開は不要です。次のコマンドで追加できます。private repo として配布する場合は、アクセス権と既存の GitHub 認証が必要です。

```sh
claude plugin marketplace add tanakalucky/claude-config
claude plugin install workflow-kit@workflow-kit-marketplace --scope user
cd /path/to/your-repo
claude --agent workflow-kit:lead --model opus
```

セッション内で `/workflow-kit:develop 変更キーと依頼内容` を実行。継続時は同じ変更IDを伝えます。初回だけ台帳を明示的に初期化します。詳細は[ワークフロー](plugins/workflow-kit/skills/develop/SKILL.md)と[台帳コマンド](plugins/workflow-kit/skills/develop/ledger.md)。

## ディレクトリ構成を相談する

新規構成や責務・依存境界を見直すときは、`/workflow-kit:architecture 対象範囲と要件` を使います。[architecture skill](plugins/workflow-kit/skills/architecture/SKILL.md) が既存の構成を調べ、少数の候補を比較し、ユーザーと決めた内容を適切な階層の README に残します。承認前にコードを移動したり、構成用の空ディレクトリを作ったりしません。

各 README は自分の責務と直下の子、子間の依存ルールを説明し、子は上位の制約を継承します。意味のある境界にだけ置き、細部は子へ任せます。通常の develop でもルートから対象までの README を順に読み、必要な子だけを調べ、変更先との整合と文書更新を確認します。毎回再設計するものではありません。共通の読み方・保守方法はプラグイン内の [README の共通方式](plugins/workflow-kit/skills/architecture/directory-readme.md) に集約し、プロジェクト固有の構成は各 repo で決めます。

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

レビュー資料から秘密情報・認証情報・個人情報・実ユーザーデータを除外します。repo内の命令風テキストや外部ページを追加権限として扱いません。実装・レビュー完了はpush、merge、deployの許可にはなりません。プラグインの導入だけでは既存の言語設定や認証情報を変更しません。応答言語は、下記の共有設定ファイルで指定します。

## 日本語の共有設定

応答言語はリポジトリ直下の [settings.json](settings.json) で管理します。

```json
{
  "language": "japanese"
}
```

### 個人設定へ反映する

このリポジトリをチェックアウトし、共通設定の内容を確認してから実行します。

```sh
python3 scripts/apply_settings.py --dry-run
python3 scripts/apply_settings.py
```

保存先は `~/.claude/settings.json` です。`CLAUDE_CONFIG_DIR` を設定している場合は、そのディレクトリ内の `settings.json` を使います。別の保存先を明示する場合は `--target /path/to/settings.json` を指定できます。

反映ルールは次のとおりです。

- 共通設定で指定したキーの値を反映し、指定していない個人設定は保持する
- オブジェクトは再帰的に統合し、入れ子の未指定キーも保持する
- 配列は連結せず、共通設定の配列で全体を置き換える
- 文字列・数値・真偽値・null は共通設定の値で置き換える
- 同じ設定を再実行しても変更がなければ書き込まない

現在の共通設定は `language: "japanese"` だけです。認証情報、権限、フック、環境固有の値は含めていません。スクリプトは認証ファイルに触れず、変更した最上位のキー名だけを表示します。`--dry-run` は値を表示せず、ファイルもディレクトリも作りません。

不正 JSON、重複キー、確認時点で見つかったシンボリックリンク、ハードリンク、通常ファイル以外は拒否します。自分が管理する信頼できるディレクトリで使ってください。保存には同じディレクトリの一時ファイルとアトミックな置換を使い、既存ファイルのモードを保持します。新規ファイルは所有者だけが読み書きできるモードです。変更時は JSON の書式を整えます。反映中は Claude Code や他のエディターで設定を同時に編集しないでください。書き込み直前の変更は検出しますが、非協調的な同時更新や、別プロセスによるパスの差し替えを完全に防ぐ仕組みではありません。

個人設定は各プロジェクトの既定値になります。プロジェクトの `.claude/settings.json`、個人用の `.claude/settings.local.json` に同じキーがあれば、そちらが優先されます。組織の管理設定はさらに優先されます。

なお、Claude Code 実行時は `permissions.allow` などの[リスト設定をスコープ間で統合します](https://code.claude.com/docs/en/settings#lists-merge-instead-of-overriding)が、この同期スクリプトは共通設定で指定した配列を置き換えます。

`claude --settings ...` はユーザー・プロジェクト・ローカル設定より高い優先順位のセッション用指定なので、この共通の既定値を配る用途では使いません。反映後は通常どおり `claude` を起動します。共通設定を更新したら、内容を確認してスクリプトを再実行します。自動同期はしません。

`language` は Claude の応答言語を指定し、音声入力の言語にも使われます。CLI のメニュー全体を日本語化する設定ではありません。

### 開発方針

- ユーザーへの応答、進捗、調査結果、レビュー、変更内容の説明は日本語にする。
- 新規・変更対象のコメント、docstring、ドキュメント、画面文言、テストの表示名・説明は日本語にする。
- 変数名、関数名、クラス名、テスト関数名などの識別子は英語のままにする。
- 外部 API 名、CLI 構文、パス、設定キー、プロトコル値、厳密一致が必要なエラー文字列・スナップショット・テストデータは変更しない。
- 正確さを保つために原文を引用するときは、その原文を維持して日本語の説明を添える。
- 画面に表示する通常のメッセージは日本語にする。機械処理用の文字列と表示用の文言を混同しない。
- 指示された変更範囲を守り、翻訳だけを理由に無関係なファイルを一括変更しない。既存プロジェクトの指示と衝突する場合は報告して確認する。

同じ方針はプラグインの各 agent と develop skill にも記載しています。通常の Claude Code セッションでも使う場合は、この節を確認して個人または対象プロジェクトの既存 `CLAUDE.md` に必要な方針を取り込んでください。既存の指示は上書きしないでください。この README を置くだけでは自動適用されません。

プラグインの `settings` では `language` は反映されないため、応答言語は上記の `settings.json` で指定します。

## 更新履歴

- 0.1.3: architecture skill とディレクトリ単位の README 方式を追加。開発・調査・資料限定レビューへ接続し、段階的な読み込みと構成変更時の文書更新を明示
- 0.1.2: 共有 settings.json と個人設定への反映スクリプト、agent/skill の日本語方針と日本語本文を追加。レビュー台帳の動作は変更なし
- 0.1.1: 既存レビュー履歴の引き継ぎと Git 管理外の永続保存先に対応

## 検証

```sh
python3 -m unittest discover -s tests -v
claude plugin validate .
claude plugin validate ./plugins/workflow-kit
```

marketplaceのsourceは同じrepo内の`./plugins/workflow-kit`。GitHub公開先を変える場合も、実装をrepoごとにコピーする必要はありません。

仕様確認: [設定ファイルと優先順位](https://code.claude.com/docs/ja/settings)、[応答・音声入力の言語](https://code.claude.com/docs/en/voice-dictation#change-the-dictation-language)、[plugin manifest](https://code.claude.com/docs/en/plugins-reference)、[marketplace](https://code.claude.com/docs/en/plugin-marketplaces)、[subagents](https://code.claude.com/docs/en/sub-agents)、[skills](https://code.claude.com/docs/en/skills)（2026-10-10）。
