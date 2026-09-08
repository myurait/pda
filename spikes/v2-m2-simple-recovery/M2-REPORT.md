# M2 判定：単純に復帰できる本体候補

2026-09-08 JST / default・pda-improvement・t_ec4c52b9

## 結論

Hermes 0.21.1のクリーンな最小構成を、M3へ渡す限定候補に選びます。現行PDAの採用継続を追認したのではなく、ローカル改変を含まない公式ソースを別環境で実行した結果です。故障時にAI診断や独自復旧サービスを追加せず、標準Dockerの再起動、事前に固定した正常版・互換データの復元で、応答と保存状態の読取りが戻りました。

今回のM2選別・隔離実証は終了です。本番採用、現行PDAの更新、M3の実行、自己完全性全体の達成ではありません。主PDA単独・直列の自己点検であり、独立レビューは未実施です。旧DBOS/control試作品のNO-GOと追加修正停止、旧scope control v2停止を維持します。

Lettaの今回のローカル構成はM3候補に採りません。導入、API、停止操作、再起動、保存ファイル保持までは成立しましたが、Letta経由の保存状態のモデル読取りを成立させられませんでした。管理型／混成は利用条件を確認できていないため未検証です。これらをHermesに性能で負けた製品とは扱いません。

## 候補比較：要求 → 標準能力 → 実測 → 保守責任 → 採否

| 候補 | 要求に対応する標準能力 | 今回の実測・証拠水準 | 残る独自保守責任と退出 | 採否 |
|---|---|---|---|---|
| Hermes最小構成 | native session/run、メモリ、API停止・idempotency、公式backup/import、標準Docker監督 | 実モデル、反復故障、互換データ復元、復帰後の状態分類・限定修復まで実測 | バージョン・設定・保存先・backup互換性・配置手順を管理する。業務状態機械や復旧daemonは追加しない。native DB/Markdown/backupを保持できるが他製品への意味的移行は未検証 | 限定M3候補 |
| Letta Code 0.31.13 / local App Server + Ollama | 公式CLI/App Server、local backendの会話・MemFS、abort、Docker監督 | 公式npm導入、Ollama単独応答、API agent保持、abort ACK、主process強制終了後1.733秒でready、保存5ファイルのcommitted prefix保持。Letta経由の通常読取りは未成立 | App Serverとローカル推論の両方、モデル設定、ファイル型保存・MemFS、クライアント再接続を運用する。未成立の接続を独自proxyや本体patchで救わない。完全なbackup/import・退出は未試験 | この構成は不採用／基礎読取りINCONCLUSIVE |
| Letta Cloud管理sandbox | agent状態はCloud、実行sandboxは管理側。期限切れsandboxを再取得する公式方式 | 一次資料のみ。新規Letta認証・利用契約・データ送信条件の許可を取得しておらず未実行 | 自前常駐運用は減る一方、Cloud状態・課金・export契約に依存。send後の通信断は履歴確認が必要で、無条件再送は公式にも推奨されない | 利用条件不足で未検証 |
| Letta Cloud + BYOM | 状態をCloud、実行機を自前に分ける公式混成方式 | 一次資料のみ。上記利用条件に加え、自前機との接続・復帰は未実測 | Cloudと自前実行機の境界を保守。単純な部品数だけでは低保守と判断できない | 未検証 |
| Cloudflare Agents / Durable Objects | 標準状態保存、hibernation、AIChatAgentの会話保存・stream再開、Workers rollback、SQLite PITR | 一次資料のみ。Cloud部署・実アカウントは未使用。PITRは公式にlocal development非対応で、ローカル試験による代用不可 | Agentを拡張するアプリ、tool実行・停止の意味、binding/migration、退出・外部exportを所有する。rollbackにはDO lifecycle/binding制限がある | 管理型候補として未検証 |
| OpenAI Responses / Conversations + 自前実行機 | 長期conversation IDとmessage/tool-call/tool-output保持 | 一次資料のみ。Codex購読認証を一般OpenAI API権限とみなさず、API deploymentは未実行 | 保存APIだけでPDA本体が完成するわけではない。実行・停止・作用照合・UI等のアプリ責任が残るため、今回はその本体を新規製作しない | 完成本体の対抗として採らず、混成参考／未検証 |

モデル条件は同一ではありません。Hermesは既存の公式OpenAI Codex経路でgpt-6-astra、Lettaは新規認証を避けたqwen3.5:2bのローカルCPU推論です。速度・応答品質の製品間ランキングは作りません。

## Hermes実証の範囲と結果

固定した最終判定対象は14ケースです。各ケース、生のAPI結果、注入失敗、前提修正をevidence/へ分離保存しています。verify_evidence.pyが件数・重複・注入成立・状態保持・native replay・モデル読取り・時間を再照合し、VERDICT.jsonを生成します。途中の同種試行を最終宣言の合格数へ水増ししていません。

| 故障・確認 | 対象試験の実測 | 状態・モデル確認 |
|---|---|---|
| 主process SIGKILL ×4 | 3.735〜3.911秒で標準restart policyが復帰。観測者はstart/restartを発行していない | 保存済み依頼・memory・停止・結果不明の保持とモデルによる継続／保留分類 |
| 一件の作業出力のbyte/inode、container memory上限 | /workは67,108,864 byte、2,046空ファイルでENOSPC。memory注入はexit137、oom_kill=1 | 本体は応答継続し、状態hash・session・モデル読取りを保持。永続home全体の上限試験ではない |
| native停止後／担当消滅中の再起動 | 3.804／3.787秒。遅延tool processは消滅 | cancelled／interruptedを保持。同じidempotency keyで同一runを返し、receiptはそれぞれ1件。復帰モデルも開始済み作用を取消済みと偽らず、盲目的再送を拒否 |
| 起動不能更新 | 故意のstartup RuntimeErrorを拒否し、事前固定した正常版へ7.694秒で復元 | 状態保持と実モデル読取り。schema変更を伴わないcode-only不良更新 |
| 不正形式DBから互換データ復元 | 公式の静止backup→import --force→標準起動で8.616秒。その後のモデル読取り14.445秒 | native停止／中断・replay ID・receipt・依頼・memoryを保持。追加の保存照合では復元前87メッセージすべてが内容一致、欠落0・改変0 |
| memory読取り不可 | PermissionErrorを実際に確認。制御表示3.890秒。事前固定した権限復元・再起動3.939秒 | native中断状態は読め、モデルは欠落memoryを捏造しない。解除後のhashとモデル読取り一致 |
| モデル経路断 | internal networkでrouted egressを除去。制御表示6.353秒。実provider要求は27.207秒で接続失敗 | モデル不在でもnative保存状態は取得できた。経路復元6.311秒後に実モデル読取り成功。元のhost公開ポートはこのfixtureでは維持されない |
| 復帰後の修復能力 | 実モデルが限定ファイルを修復 | 観測者が実ファイルのrepaired-violet-739を確認。runtime/host自体を更新できる権限の証明ではない |

記録された制御復帰／標準復元区間の最大は8.616秒です。制御・保存状態読取り・native作用評価の記録区間をケース内で足した最大は32.805秒ですが、これは別計測区間の合計で、観測者の細かな処理を含む全drillの連続wall clockではありません。2分／5分の目標は変更していません。モデル依存が止まっている期間のnative表示を、自然言語応答の完全復旧とは数えません。

対象試験内で、ownerの救出要求、保存済み状態の観測された喪失、停止済み仕事の自動再開、結果不明操作の盲目的再送による追加作用は0でした。これは合成receiptを用いた限定結果で、実業務API全般のexactly-once保証ではありません。

## 単純復帰として何が成立し、何が未成立か

主process故障の再起動はDockerが自動で行いました。更新・データ復元・依存障害の解除は、故障前に選んだ固定コマンドを主試験者が発行しました。その復帰経路にLLM診断はありませんが、任意の本番破損を自動検知し、適切なbackupを選び、無人で全復元する運用を実装・実証したわけではありません。

復元では受付を止め、直前の正常世代をbackupし、その間に新規依頼を受理していません。古いbackup後の任意の書込みを失わないzero-RPO、破壊的migration、host/disk全損、外部provider全断は対象外です。正常版の選定・互換性・導入権限は試験者側にあり、候補本体の自己更新権限と現行PDA自身の独立復帰を今回のPASSへ混ぜません。

作業tmpfsと永続stateを分けたことで、指定の/workの膨張は本体へ波及しませんでした。一方、永続state bind自体にhard byte/inode quotaはありません。任意の出力をhomeへ向ける挙動まで封じたとは言えず、この制限を隠して自己完全性完成とはしません。

停止と結果不明は保持できましたが、native idempotencyの保持期間は有限です。長時間経過後の再送、実際の送信先での結果照会、停止競合、永続保留からの安全な継続はM3の必須評価として残します。

## Lettaで確認できなかったこと

公式npm 0.31.13を非rootのread-only-root containerへ導入し、公式local backendとOllama接続を使用しました。Ollama単独は実応答を返しましたが、Letta経由の基礎読取りは150秒、設定変更後90秒、接続を切り直したclean restart後180秒の観測で完了応答を得られませんでした。短い入力でcontext圧縮へ入る記録があり、max_tokens=384・reasoning_effort=none・context_window=8192の保存はnative APIで確認しました。abortはACKを返しましたが、推論側に計算が残った観測も保存しています。原因は断定していません。

この180秒を5分目標への性能FAILとは扱いません。通常応答という前提が未成立なので、起動不能更新・全依存故障・全state復元の完全matrixは進めず、モデル読取りINCONCLUSIVE・今回構成不採用として閉じました。最後にguard付きSIGKILLとnative API再取得で1.733秒のready復帰、agent IDと保存5ファイルのprefix保持を実測しましたが、HTTP／ファイル保持だけでM3候補へ格上げしていません。

参照ソース2f0fb7cと、実行したnpmのgitHead a501f8cは別でした。最終照合で区別し、npm tarballのSHA-512 integrityと公開gitHeadの存在を検証しました。実測対象は一貫してnpm 0.31.13であり、参照ソースだけから因果関係を断定しません。Hermesの主要state/API/backupソースは固定commitとbyte一致しました。

## 失敗を合格へ混ぜない処置

Hermes初期のon-failure:3は累積4回目で停止したため、標準unless-stoppedへ変更して影響する試験をやり直しました。初期のPID選別失敗、venv mountとmessaging extra不足、非存在API endpoint、internal networkのNAT誤認は前提／観測器の訂正として残しています。オンラインbackupのexit0でも「不完全」と表示された世代は合格に使わず、静止して完成したbackupを復元しました。

Letta導入で不足したbuild prerequisiteとOllamaの非root保存先は標準packaging内で修正しました。PID2固定の誤った注入はguardが拒否した無効試験として保存し、実node processを照合した注入だけを最終結果に採りました。製品ソースのpatch、汎用復旧proxy、独自業務状態機械、旧control延命は実装していません。低保守負担という指示は、ここで追加開発を採らない判断に使用しました。

## M3への引継ぎと保全

M3はこの限定Hermes候補について、注意切替・部分的忘却・休眠skill再発見、活動UI、実仕事の停止／結果照合／引継ぎ、更新権限、保存量の境界、長期continuity、移行・退出を同じ活動で評価する段階です。本体の復帰と仕事の再開資格を分けつつ、永久保留を完成形にしません。独立レビューと正式反映の承認を自己点検で代替しません。今回M3は開始していません。

試験containerとnetworkは停止・除去し、試験state、正常／隔離世代、source、venv、モデルcacheは私有の.runtimeに保全します。実認証やbackupを含む.runtimeはGit・添付に含めません。配布するのは最小宣言、試験器、合成観測、判定書です。mainと他worktreeの変更、現行gateway／Open WebUI、旧停止状態は変更していません。

再開時の入口はCHECKPOINT.mdです。旧試験を盲目的に再実行しないでください。候補設定・認証・保存先・バージョン・前提条件を再確認し、新しい名前と状態で行う場合だけ再試験します。probeは一回限りの試験器であり、本番へ常駐配置する成果物ではありません。

## 一次資料と証拠

- Hermes固定ソース：https://github.com/NousResearch/hermes-agent/tree/fef0e16fe19b79ded929209f87c7434270b03825
- Hermes session仕様：https://hermes-agent.nousresearch.com/docs/user-guide/sessions/
- Letta self-hosting：https://docs.letta.com/self-hosting
- Letta公式managed／local／BYOM区分：https://docs.letta.com/agent-sdk/deployment
- Letta App Server：https://docs.letta.com/platform/app-server/quickstart
- 実行npm：https://registry.npmjs.org/@letta-ai/letta-code/0.31.13
- 実行npmの公開gitHead：https://github.com/letta-ai/letta-code/commit/a501f8c4557e49812d66c7b801eff0ade5516343
- Cloudflare Agent class：https://developers.cloudflare.com/agents/concepts/agent-class/
- Durable Objects SQLite/PITR：https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Workers rollback制限：https://developers.cloudflare.com/workers/configuration/versions-and-deployments/rollbacks/
- OpenAI conversation状態：https://platform.openai.com/docs/guides/conversation-state

数値の正本はVERDICT.jsonとevidence/。ソース照合はsource-pins.json、evidence/source-pin-reverification.json、evidence/artifact-provenance-self-check.json。保存照合はevidence/hermes-message-custody-self-check.json。最小設定はcompose.yaml、hermes-config.yaml、try-release.sh、restore-data.sh、compose-letta.yaml、Letta.Dockerfileです。
