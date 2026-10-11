# 収集方法と制約

- OpenClaw 2026.10.1 の公式 CLI と設定を使った。配布元の README、common.md、agents/*.md、製品本体のコードは変更していない。
- protocol 4、client.id=cli、mode=cli、displayName="PDA roles check 2026-10-11" の WebSocket クライアント。今回生成した単一の Ed25519 device identity と返された device token を、リポジトリ外の0600ファイルで再使用した。既存の Claude/Codex/TypeSafe の秘密ファイルは読んでいない。
- 同じ依頼を各回1回だけ chat.send し、各回は別のセッション・接続。親の最後の応答と全関連セッションの非稼働を確認し、関連する更新が15秒間無い状態を経て接続を閉じた。途中の final 通知のあとにも継続処理があるため、通知だけでは終了しない。
- A1 の初回 collector は sessionKey に大文字の A1 を含めた。Gateway は小文字に正規化したため、collector がイベントと sessions.list の結果を除外してしまった。依頼そのものは受理されており、再送していない。元のソケットを保持したまま、同じ identity の読み取り専用接続から履歴・後続イベントを1回の回復処理で収集した。履歴から初期の tool call の時刻を得た。最終報告の受信と非稼働を確認した後だけ、元の collector を SIGTERM で終了し、回復用接続を閉じた。元の終了時刻はプロセス終了を観測した時刻。A1.jsonl を保持し、補完は A1-recovery.jsonl に分けた。A2/A3 は生成時にセッション名を小文字にした。
- 初回の補助 inspection (00-api-a1-recovery.json) も同じ identity を使う読み取り専用接続であり、依頼の再送は無い。元の A1 接続は、この inspection と回復処理の全期間で保持した。A1 の補完接続が2本あるという測定上の制約を明記する。
- 各回の前に hello.py だけを初期コミット c2c680a68fa41598b377d449dadeadb898a6944c から復元した。この初期ファイルは print("hello") の1行で、関数定義は無い。依頼には scratch の絶対パスだけを補足した。特定の相手や道具を使うよう追加誘導していない。
- before/after の models.list(agentId=worker)、WebSocket、親子の chat.history、同時間帯の journal と Gateway ファイルログを保存した。API時刻と本文の時刻はUTC、Gatewayログ本文は元のJST表記を保持する。
- sessions_spawn と Codex 内蔵 spawn_agent を区別する。内蔵の task_name="auditor" は、OpenClaw の本番 auditor に sessions_spawn したことの証拠にはしない。
- 指定の authority エラーは、異なる toolCallId の件数で数え、stream と履歴の重複を除く。終了状態のエラーは同じ事象の journal とファイルログを足し合わせない。各媒体の検索結果も解析JSONに残す。
- plugin の単体検証は一時ファイルで、全5エージェント名、ファイル内容の変更、削除後の読込失敗を確認する。配布元や本番 common.md を試験用の内容に変えていない。実際の hook 呼出しは Gateway ログの agent/session/run とSHA-256を照合する。
- 機密値・device鍵・device token は証拠に保存しない。device ID は別名に置換する。今回の identity/token は登録解除後に削除する。chat.history の native spawn 引数の一部は製品自身により伏せ字になっており、復号は行っていない。
- A1 の回復用 stream を解析器に追加した際、data が配列の履歴補完レコードで解析器が AttributeError となった。配列レコードを tool event として解釈しないよう修正し、解析を1回やり直した。保存済みの履歴・受信イベントは変更せず、モデルへの依頼は増やしていない。
- 片付けの最初の device 一覧比較は、既存2件が保持されているという採取側の仮定により AssertionError になった。Gateway ログで公式 plugin install 時の CLI 登録と既存2件の自動整理を確認した。今回作成の CLI 登録を追加で解除し、残るファイルの片付けを再開した。採取用 device の削除やモデル依頼は繰り返していない。
