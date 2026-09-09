# M2は未完了 — 採用候補は未確定

2026-09-09 12:19 JST / default board・pda-improvement・t_ec4c52b9

## 判断

M3へ進める候補はまだ確定できません。Hermes最小構成とLettaローカル構成は、今回の試験条件ではM2要件に届きません。管理型・混成は認証と利用条件の境界で未検証です。これは全製品のNO-GOでも、M2完了でもありません。

旧「Hermesを限定M3候補に選定」「Lettaは通常読取り不成立のため不採用」は撤回済みです。この再開資料が現在の判定です。旧報告・添付27の結論は採用根拠に使いません。

推奨する次の実機候補はLetta Cloudの管理sandboxです。状態だけでなく実行環境の管理責任も移せる方式を先に確かめ、ローカルで残った「停止中の本体を誰が復元するか」を比較します。ただし、管理型でこの問題が解決すると判定したわけではありません。

## 候補を同じ軸で比較

共通要求は、保存済み状態を失わず単純な標準復帰で応答・修復へ戻り、停止・不明結果を保留できることです。

| 候補 | 要求に対応する標準能力 | 実測・証拠水準 | 残る保守・退出責任 | 採否 |
| --- | --- | --- | --- | --- |
| Hermes 0.21.1 最小標準構成 | native Runs・停止・idempotency、標準backup/import、Docker再起動 | 実プロセス停止・資源故障・依存障害後の読取り、実ツール修復、保存状態を含む外部復元を確認。停止受理直後の状態保持に反例。 | 正常版・互換データ・復元を起動する主体、永続領域の保護は自分側に残る。今回のread-only本体では自己更新も未実証。 | 今回構成は未達。M3へ進めない |
| Letta Code 0.31.13 ローカル | 公式App Server/local backend、MemFS、標準Docker監督 | 4B最小設定で保存状態を読める。読取り専用の故障試験と、別試験の実Bash修復が成立。破損indexでは起動不能。 | ローカル推論と保存データ、正常版・保存データの復元主体、永続領域保護が残る。 | 今回構成は未達。旧「読取り不成立」を理由にしない |
| Letta Cloud 管理sandbox | 状態はCloud、ツールは管理sandboxで実行。[1] | 一次資料・認証境界まで。管理sandbox・履歴照会・復元の実機試験は未実施。 | 管理先の可用性・費用・保持/復元・export、送信後の不明結果の照会が必要。[1] | 認証・利用条件待ち。未検証 |
| Letta Cloud＋自前runner | 状態はCloudに置き、ツール実行環境を自己管理できる。[1] | 一次資料のみ。自前runner消失とCloud状態の再接続は未試験。 | Cloudだけでなくrunnerの復帰責任も残る。管理型と同じ保証ではない。 | 認証・利用条件待ち。未検証 |
| Cloudflare Agents | Durable Objectsの保存・PITR、durable fiber。復帰フックは利用側コード。[2][3] | PITRはローカル非対応。fiberのローカル動作は検証可能だが、クラウド復元の代替証拠にはならない。[2][3] | 復帰フック・作用照合等のアプリ責任、Cloudflare依存と退出の検証が残る。 | 実機未検証。枠組みを完成済み本体と扱わない |
| OpenAI保存API＋自前実行機 | Conversationsで会話・tool call/output等の状態を保持できる。[4] | 会話保存の資料確認のみ。提案した実行機・復元主体は未構築。 | 本体実行・停止・照合・復帰の接続を新規に保守する案であり、保存API自体の保証と区別する。 | 参考案。本体候補としては未成立 |

## 元の完了条件との照合

状態表示120秒、正常版復帰300秒を変更していません。HTTP正常だけでは合格にしません。外部試験者による復元を、候補自身の無人復帰や「救出0」に読み替えません。

| 条件 | Hermes最小構成 | Lettaローカル |
| --- | --- | --- |
| 状態表示120秒 | プロセス停止・依存/資源障害では限定確認。DB破損はHTTP200でも保存状態を読めず未達。 | 読取り専用6ケースは閾値内。index破損では120秒後も起動不能。 |
| 正常版復帰300秒 | 外部試験側のimport＋正常版起動なら閾値内。無人復帰は未実証。 | 読取りの復帰は成立。破損/不良更新の復元試験は観測中断を含み、無人RTO合格に使わない。 |
| 依頼・記憶・停止・未確定記録 | 最新の静止点backupから論理状態を保持。任意の古いbackupからの無損失ではない。 | nativeメモリを前後一致。静止点コピーの復元も一致。 |
| 停止の保持 | 停止受理直後はstopping→interrupted。取消完了後のcancelled保持と分ける。 | 事前保存した停止印の読取りのみ。実際の停止要求の競合・継続実行は未実証。 |
| 不明結果・盲目的再送の抑止 | 実ツールのfsync済み模擬作用で、同じIDの再送は元runを返し追加作用なし。実業務APIではない。 | 未確定印を返せた。読取り専用呼出しのため実行可能状態での非再送保証ではない。 |
| 作業による資源侵食の防止 | 作業用一時領域とOOMの限定試験は成立。永続HOMEへ上限を超えて書けるため保護は未達。 | 作業領域上限では読取り可。永続HOMEは同様に上限を超えて書ける。 |
| オーナー救出・複雑な独自復旧を不要にする | 試験者の外部復元を、停止したPDA自身の無人復帰へ読み替えない。未達。 | 同左。モデル依存の解除も試験側が実施。未達。 |
| 応答だけでなく修復へ戻る | 実ツールによる模擬ファイル修復は成立。本体自己更新は今回構成で未実証。 | 実Bashによる模擬ファイル修復は成立。自己更新・安全な実仕事再開は未実証。 |

## Lettaで確認できたことと限界

公式Letta Code 0.31.13、Ollama qwen3.5:4b・CPU推論を使用しました。標準設定で不要なskillを外し、読取り試験ではツールを禁止した最小入力構成です。診断用fetch hookは採否に使う試験から外しています。旧2B構成の不成立をLetta全体へ一般化しません。

| 故障・条件 | native状態読取りまで | 故障からモデル読取りまで | 結果 |
| --- | --- | --- | --- |
| 作業領域容量枯渇 | 0.129秒 | 71.227秒 | 読取りのみ成立 |
| 作業領域inode枯渇 | 0.091秒 | 74.426秒 | 読取りのみ成立 |
| モデル停止→試験側が再起動 | 0.789秒 | 78.899秒 | 読取りのみ成立 |
| コンテナ内OOM | 0.798秒 | 99.170秒 | 読取りのみ成立 |
| 主プロセス強制終了 | 1.574秒 | 53.519秒 | 読取りのみ成立 |
| 模擬worker消失 | 1.760秒 | 82.429秒 | 読取りのみ成立 |

この6ケースは保存された試験状態を読めたことの確認です。読取り専用なので、誤再開・再送が起きなかったことを、ツール付きの仕事を安全に再開できる証明には使いません。模擬workerも実業務ではありません。モデル停止試験では、試験側がOllamaを再起動しています。

別の実ツール試験では、Bashを通して壊した模擬ファイルを所定内容へ修復できました（157.425秒）。これは実ファイルの内容で確認した結果であり、本体の自己更新ではありません。

一方、保存済みagent indexの破損では121.224秒後も起動できませんでした。正常版と静止点コピーの復元後にはファイル一致・native状態一致・モデル読取りが戻りましたが、試験者の外部操作であり、中断した観測を含むため無人RTO合格にはしません。

永続HOMEへ64MiBを書け、作業領域の48MiB上限を超えました。ホストを満杯にはしていません。これは「今回の永続領域に同じ保護がない」証拠であり、すべての公式構成で保護不能という判定ではありません。

## Hermesで確認できたことと限界

公式0.21.1のアーカイブに含まれる12195ファイルを照合し、不一致なしを確認しました。実モデルはgpt-6-astraです。LettaのCPU小型モデルと性能同条件ではないため、応答時間で製品の優劣を決めません。

主プロセス停止からの復帰は3.780秒。容量・inode・OOMの限定試験後にも保存状態を読みました。記憶読取り不可・モデル通信不可の試験では、実在する取消済み仕事のnative状態をそれぞれ3.941秒・4.357秒で表示できました。依存解除後のモデル読取りも成立しましたが、依存解除は試験側の操作です。

停止受理直後の試験では、HTTP200・stopping受理後の実プロセス停止により、復帰後のnative状態がinterruptedになりました。取消完了後の試験ではcancelledが残ります。両者を置き換えて合格にしません。対象の停止/取消済み/結果不明の3ケースでは、同じidempotency keyの再送が元runを返し、模擬のfsync済み作用は増えず、遅延workerも残りませんでした。実業務APIに対する保証ではありません。

DB破損ではhealthがHTTP200でも、保存DBは読めない状態が120秒を超えました。次の数値は、その後に外部試験側が標準importと正常版起動を行った試験です。

| 故障 | 外部復元後の状態復帰まで・故障起点 | モデル読取りまで・故障起点 | 復元主体 |
| --- | --- | --- | --- |
| DB破損 | 130.260秒 | 144.750秒 | 試験側が標準import・正常版起動を実施 |
| 起動不能更新＋非互換DB | 130.183秒 | 142.640秒 | 試験側が標準import・正常版起動を実施 |

保存DBの論理内容・記憶・模擬作用receipt・native run状態・同じIDの再送結果は保持しました。ただし、受付を止めた直近backupからの復元に限定します。不良更新試験は起動不能版と非互換DBの複合故障であり、起動不能版だけの独立測定とは区別します。

実ツールでの模擬ファイル修復は10.061秒で成立しました。永続HOMEへ64MiBを書け、作業用/workの32MiB上限を超えた点は未達です。本体はread-onlyマウントで自己更新を書込み拒否しましたが、これは試験構成の境界であり、Hermes製品自体の自己更新不能を示しません。

## 管理型の実際の境界

この実行環境の環境変数・Hermes .env・標準Letta/Wrangler設定を調べた範囲では、利用できるLetta Cloud/Cloudflare/OpenAI APIの試験認証はありません。ユーザーが別の場所にアカウントやブラウザログインを持たないという意味ではありません。認証なしのCloudflare APIはAuthorization欠落、OpenAI APIは401、Letta APIはWAFの403でした。Lettaの403を認証失敗と断定しません。

CloudflareのPITRはローカル非対応で、変更のdurable logがローカルにはないことが公式に明記されています。[2] fiberのローカル復帰は検証可能ですが、PITRやクラウド障害を再現したことにはなりません。[3] 今回はそのローカルデモも未実施です。復帰フックを自作して完成品の標準保証と呼び替えません。

再開に必要なのは、まずLetta Cloud管理sandboxを試せる認証・利用枠・許可済み送信範囲です。試験データは合成に限定し、本番データや本番構成を持ち込みません。認証情報はチャットや報告に貼らず、安全な設定先で用意する必要があります。新規契約・課金条件・権限は勝手に追加していません。

## 観測誤りを合格根拠から除外

- Letta model-unavailableのraw verdictにあるrestoration_observer_calls_after_fault=0は誤り。別の実行記録どおり試験側がOllamaを1回startした。依存解除を含む限定試験として扱い、無人復帰のゼロ介入根拠から除外する。
- 旧Hermes依存障害probeは存在しない旧run IDに404を返した。保存状態の合格根拠から除外。memory-v3/model-v4では実在する取消済みIDのHTTP200を要求して再確認した。
- Letta requires_approvalはクライアントturn終端ではない。元の早期終了判定を撤回し、native終端まで追跡。
- LettaのPID1 signal成功だけでは実停止していなかった試行を復帰合格から除外。採用したread-only試行では世代・再起動数変化を要求。
- 有効なJSONが通常文に包まれた応答を誤って失敗とした試行は観測側のparse不備。訂正履歴を残し、再試験と区別。
- 再起動中のExitCodeサンプリング、ConnectionResetError、restoreではなくimportを使うCLI差で中断した元試行は通算RTO合格に使わない。Hermesは別名の再試験、Lettaは外部継続復元の証拠として扱う。
- Hermes model-v3ではComposeのunhealthy判定で観測を早く打ち切った。元の120秒条件を変えず、v4でnative healthを有限時間追跡して再確認。

生の失敗記録は履歴として保存し、上記の訂正をassessment.jsonへ併記しています。スクリプトの終了コードだけで候補の合格を決めていません。

## 残る仕事と再開地点

- M3へ渡せる実証済み本体候補が未確定。M2全体は未完了。
- Letta Cloud管理型/混成の試験用認証、利用枠、許可済み送信条件。
- Cloudflareの実クラウドPITR・復帰責任・退出検証。ローカルfiberだけでは代替不能。
- 本体停止中に誰が正常版と互換データを戻すかを、ユーザー救出も複雑な独自復旧も要さない形で実証する。
- 永続状態を作業侵食から守りつつ、必要な本体更新ができる構成の実証。
- 実業務APIの作用照合、注意/忘却/skill・UI・退出、独立レビュー・本番反映は後続段階で未実施。

実験用m2proof/m2r2コンテナは停止・除去済みです。試験データと再現情報は隔離worktreeに保持しています。M3着手・本番反映・旧scope control v2/dispatcherの再開は行っていません。独立レビューも未実施です。

カード本文の「新候補の実証は未実施」は古い実行状況の表記で、本文へは今回の状況を反映できていません。導入済みCLIのeditは完了済みtaskの結果編集専用です。blockedへの変更もCLIに拒否されたため、未割当triageを維持し、今回の実行状況と認証待ちは添付・コメントへ記録します。本文更新案も保存します。状態を動かすための強制変更やready昇格は行わず、古い未着手表記を再実行の指示にしません。

再開時はこの比較表、assessment.json、CHECKPOINT.mdとカードの現行本文を読み、実行中資源と認証境界を確認します。失敗した旧試行を盲目的に繰り返さず、未検証の管理型へ進みます。

## 生証拠への対応

相対パスの起点はこの資料のフォルダです。assessment.jsonに採否・完了条件・訂正・証拠ファイル名を保存しています。

- evidence/final-dependency-retest-cleanup.json
- evidence/hermes-resumed-live-repair-verdict.json
- evidence/hermes-resumed-resource-permission-boundary.json
- evidence/hermes-resumed-restore-bad-update-unattended-observation.json
- evidence/hermes-resumed-restore-bad-update-verdict.json
- evidence/hermes-resumed-restore-data-corruption@verified-unattended-observation.json
- evidence/hermes-resumed-restore-data-corruption@verified-verdict.json
- evidence/hermes-source-reverification.json
- evidence/letta-candidate-summary.json
- evidence/letta-data-corruption-120s-verdict.json
- evidence/letta-fault-byte-full@read-only-verdict.json
- evidence/letta-fault-inode-full@read-only-verdict.json
- evidence/letta-fault-model-unavailable@read-only-dependency-restored-by-injector.json
- evidence/letta-fault-model-unavailable@read-only-verdict.json
- evidence/letta-fault-oom@read-only-verdict.json
- evidence/letta-fault-process-death@read-only-verdict.json
- evidence/letta-fault-worker-disappearance@read-only-verdict.json
- evidence/letta-live-bash-repair-verdict.json
- evidence/letta-persistent-home-bounded-probe.json
- evidence/letta-restore-bad-update-continued-verdict.json
- evidence/letta-restore-data-corruption-continued-verdict.json
- evidence/managed-auth-boundary-current.json
- evidence/r2-hermes-baseline-semantic-verdict.json
- evidence/r2-hermes-memory-outage-v3.json
- evidence/r2-hermes-model-outage-v4.json
- evidence/r2-hermes-resumed-bytes.json
- evidence/r2-hermes-resumed-crash.json
- evidence/r2-hermes-resumed-inflight-v2-orphan.json
- evidence/r2-hermes-resumed-inflight-v2-settled-stop.json
- evidence/r2-hermes-resumed-inflight-v2-stop.json
- evidence/r2-hermes-resumed-inodes.json
- evidence/r2-hermes-resumed-memory-limit.json

## Sources

[1] https://docs.letta.com/agent-sdk/deployment/index.md — letta-deployment
[2] https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api — cloudflare-sqlite
[3] https://developers.cloudflare.com/agents/runtime/execution/durable-execution — cloudflare-fibers
[4] https://platform.openai.com/docs/guides/conversation-state — OpenAI Conversation state
