# 台帳のコマンド

Python 3.10+ と POSIX 環境（macOS/Linux/WSL）が必要。依存関係やモデル推論は不要。
対象の Git リポジトリから実行する。`GATE` はインストール済みヘルパーの絶対パスに
置き換え、パスと不透明な値はシェルで適切に引用する。タスクやリポジトリの文章を
評価・実行しない。`--repo /path` はグローバルオプションである。
既定の状態ディレクトリは `git rev-parse --git-common-dir` に `/workflow-kit` を
加えた場所であり、リンクされた worktree 間で共有される。
代わりに、毎回同じ絶対パスの `--state-dir /trusted/path` を指定してもよい。
その親ディレクトリは存在していなければならない。プラグインのキャッシュ内や
追跡対象のソース内には決して置かない。明示した状態ディレクトリは Git のメタデータが
なくても利用できる。このヘルパーのためだけに Git を初期化しない。

```sh
# 本当に新しい状態の場合だけ使用する。使用済みの台帳の復旧には使わない。
python3 "GATE" setup --ack-new-ledger
python3 "GATE" list
python3 "GATE" new --key feature-opaque-001
# 返された change_id を保存する。同じキーを繰り返し使うと同じ ID が返る。
python3 "GATE" status --change CHANGE_ID
python3 "GATE" start --change CHANGE_ID --snapshot PACKET_SHA256
python3 "GATE" claim --change CHANGE_ID --round 1 --perspective security
# claim が成功した後にだけ security-reviewer を呼び出し、そのトークンを保持する。
python3 "GATE" record --change CHANGE_ID --round 1 --perspective security \
  --token CLAIM_TOKEN --result complete --p0 0 --p1 0 --p2 1 --report REPORT_SHA256
# 同じラウンドで test-adequacy と design-rules-docs も claim・呼び出し・record する。
python3 "GATE" check --change CHANGE_ID --snapshot PACKET_SHA256
```

## 台帳外でレビュー済みの変更の取り込み

`new` を使う前に、この論理的な変更がすでにレビューラウンドを消費していないか確認する。
初回の移行時に限り、既存の根拠と照合してその回数を確定する。変更、実際に消費した
ラウンド数（中断を含む）、根拠への参照を明示した、機密情報を除去した履歴概要を保持する。
ローカルでハッシュを計算し、レビュー結果を捏造したり未解決の指摘を捨てたりしない。
回数や履歴が不確かな場合は中止し、人に確認する。

```sh
# Git 管理外のチェックアウトでは、ソース外に永続的な非公開ディレクトリを 1 つ選ぶ。
# この台帳が本当に一度も初期化されていない場合だけ実行する。
python3 "GATE" --state-dir /trusted/state/workflow-kit setup --ack-new-ledger
python3 "GATE" --state-dir /trusted/state/workflow-kit list
python3 "GATE" --state-dir /trusted/state/workflow-kit adopt \
  --key existing-change-001 --rounds-consumed 1 \
  --evidence HISTORY_SHA256 --ack-history
# 返された change_id を保持する。次の start はラウンド 1 ではなくラウンド 2 を予約する。
```

`adopt` が受け付けるのは、過去に消費した 1～3 ラウンドと未使用の変更キーだけである。
処理はアトミックであり、繰り返しの取り込みや、ラウンドがないものも含む既存の変更への
上書きを拒否する。同じ根拠ハッシュを別のキーで取り込むことはできない。
応答が不確かな場合は `list`/`status` を使い、新しいキーを作らない。
取り込まれたラウンドにはステータス `adopted` と `evidence_sha256` があり、
レビュー担当の行、claim、指摘件数、コードのスナップショットはない。
編集や、後から完了済みとすることはできない。承認済みとはせずに枠だけを消費するため、
`check` は失敗する。ステータスは `historical_unverified`、3 ラウンドすべてを
消費済みなら `human_required` となる。次の通常ラウンドでも 3 観点すべてが必要である。
ヘルパーが検証するのはハッシュの形式であり、根拠の真実性ではない。照合は lead が行う。
これは、失われた既存の台帳を復旧・リセットする仕組みではない。

## 結果と復旧

すべてのダイジェストは小文字の SHA-256（16 進数 64 文字）とする。
`sha256sum` や Python hashlib などを使い、機密情報を除去した成果物からローカルで
計算する。資料にはベース・リビジョン、関連する未コミット変更と未追跡の変更、
テストの根拠を明示する。機密情報の除去によって関連する動作が隠れることがある。
生の秘密情報を送ったりレビューが完了したふりをしたりせず、安全な合成データによる
根拠を求める。

`claim` は各観点につき一度だけ成功し、重複する claim は失敗する。
開発の引き継ぎには、秘密情報を含めず、変更 ID とともにエージェントの識別子を保持する。
セッション中断後は `status` で claim トークンを復元できる。可能なら元のエージェントを
再開する。起動や結果が不確かな場合は、確認せずに再起動しない。

```sh
python3 "GATE" record --change CHANGE_ID --round 1 --perspective security \
  --token CLAIM_TOKEN --result failed
# または、完了した観点を保持したまま、中断したラウンド全体を終了する。
python3 "GATE" interrupt --change CHANGE_ID --round 1
```

リセット・削除・上書きのコマンドは存在しない。完了済みの同一記録は冪等であり、
矛盾する記録は失敗する。エージェントが起動しなかった場合でも、開始したラウンドは
枠を消費する。SQLite トランザクションが並行プロセスを直列化し、コミット済みの予約は
クラッシュ後も保持される。中断した claim に有効期限はない。
3 観点すべてが complete で P0/P1 が 0 件なら passed となり、P2 は妨げにならない。
阻害要因あり・失敗のラウンドが 3 回に達すると、ステータスは `human_required` となる。
`check` は、スナップショットがない、失敗している、進行中である、または一致しない場合に
拒否し、マージ・デプロイの権限を与えない。

状態に含まれるのは不透明なキー・ID、ハッシュ、件数、ステータスだけである。
非公開で保持し、セッションをまたいで引き継ぐ。Git にコミットしない。
バックアップ時は書き込みを停止し、信頼できるツールで状態ディレクトリ全体をコピーする。
状態の欠落、不完全さ、破損、未対応バージョン、安全でない状態を検出すると、安全側に停止する。
削除したり別の場所で setup を実行したりせず、既知のバックアップを復元するか、
人に照合を依頼する。新しい clone・マシンでは、変更を続行する前に同じ履歴を転送する
必要がある。このローカル台帳は、ディレクトリ全体の削除、捏造した入力、意図的に変更した
キー・パス、直接の Agent 呼び出しを検出できない。
