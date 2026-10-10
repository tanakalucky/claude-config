# Claude Config

バージョン: 0.1.5

## 導入
Claude Code 2.1.271以上、Python 3.10+、Git、macOS/Linux/WSLが必要です。

```sh
claude plugin marketplace add tanakalucky/claude-config
claude plugin install workflow-kit@workflow-kit-marketplace --scope user
cd /path/to/your-repo
claude --agent workflow-kit:lead --model opus
```

## 共通設定
`settings.json` を確認して反映します。既定の保存先は `~/.claude/settings.json`。`CLAUDE_CONFIG_DIR` と `--target` にも対応します。

```sh
python3 scripts/apply_settings.py --dry-run
python3 scripts/apply_settings.py
```

未指定の設定は保持し、オブジェクトは再帰的に統合、配列は置き換えます。反映中は同じ設定を他で編集しないでください。

## 使い方・方針
- 開発: `/workflow-kit:develop 変更キーと依頼内容`。継続時は同じ変更IDを使います。
- Opus が短い計画を作り、ユーザーとホストが確認。承認後は実装・テスト修復・最大 3 回のレビューを完了かエスカレーションまで進めます。
- 呼び出し側は工程ごとの停止を指示せず、同じ計画・変更 ID で継続。ホストは依頼された承認済み操作の実行と結果返却を担います。段階限定はユーザーが求めた場合だけです。
- 構成の相談: `/workflow-kit:architecture 対象範囲と要件`
- 詳細: [開発手順](plugins/workflow-kit/skills/develop/SKILL.md)・[台帳](plugins/workflow-kit/skills/develop/ledger.md)・[README の方式](plugins/workflow-kit/skills/architecture/directory-readme.md)

応答・進捗・レビュー・文書・コメント/docstring・画面文言・テスト説明は日本語。識別子、API/CLI、設定キー、厳密一致の機械処理用文字列は維持します。
原文引用に日本語の説明を添え、変更範囲と既存規約を守ります。通常セッションにも適用する場合は、既存の `CLAUDE.md` に必要な方針を取り込みます。
配置: `plugins/` はワークフロー、`.claude-plugin/` はカタログ、`settings.json` は共通設定、`scripts/` は反映・リリース、`tests/` は検証、`.github/workflows/` は CI の条件・権限。repo 固有の規約は各 repo に置きます。

## 更新・リリース
1. 版は手動で決め、[plugin.json](plugins/workflow-kit/.claude-plugin/plugin.json) の `version` と README 冒頭を PR で揃えます。形式は `X.Y.Z`。marketplace に版は重複させません。
2. 検証後に `main` へマージし、Actions の「設定の検証とリリース」で `main` を選んで `Run workflow` を実行します。初回は現行の未タグ版を使えます。
3. 同じ実行で再検証したコミットに `vX.Y.Z` を付けます。同名タグが同じコミットなら変更せず成功、別コミットなら失敗。自動採番やタグの付け替えはしません。

PR・push は検証だけ、自動化の公開処理は手動実行時の Git タグ作成だけです。追加 secret は不要です。
導入先は別途更新します。プラグインは Claude Code 側で更新（第三者 marketplace の自動更新は既定で無効）、共通設定は確認後に反映スクリプトを再実行します。

## 検証
```sh
python3 scripts/release.py check
python3 -m unittest discover -s tests -v
```

CI はテストと参照・版の整合性を確認します。Claude CLI の schema 検証・インストール・推論は含めません。必要時は導入済み CLI で `claude plugin validate .` と `claude plugin validate ./plugins/workflow-kit` を実行します。
