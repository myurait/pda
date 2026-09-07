# V2 state custody — M1で固定する制御・情報の所有契約

状態: M1設計契約。実装・復帰・独立権限の実証ではない。revision: `v2-custody-2`。
追跡: V2-M1 / `t_bb976fc1`。規範は[PDA憲章](../../pda_charter.md)と[v2-01](../roadmap/v2-01-whole-system-reassessment.md)。停止したscope control v2をpatch/再有効化しない。

## 1. 対象と責任分界

同じ論理objectの正本は一つとする。複製、UI、search index、agentの会話、checkpoint、Kanbanコメントは権威の代用品ではない。障害時に多数決・最終更新時刻・LLM判断で正本を選ばない。

M2の実験活動は `experiment/<entry-id>/<activity-id>` という実験専用namespaceを用いる。現行Kanbanのowner作業カードとは別objectであり、productionカードをコピーして同じIDの実行正本を二重化しない。M2/M3の実験成績は現行Kanbanカードへ記録する。将来実仕事を移管する場合、M4 migration契約で旧側をfenceしてからauthority handoffを行い、本書だけで移管しない。

M2実物候補は、既存systemd user managerによる専用監督、既存Dockerで隔離したworker、DBOS Python 2.31.0によるworkflow/step継続、SQLiteによる限定したcontrol authorityである。これは汎用workflow engineの自作ではない。DBOSのcheckpointをstop/承認/receiptの代用品にしない。DBOSとcontrol DBを跨ぐatomic transactionが存在するとは主張しない。各境界でoperation IDを安定させread-backとholdにより整合をとる。

control実装はsuccessを返すstubではなく、SQLite transaction・一意制約・revision CASを使う実物をM2で実装して試験する。実物が完成する前にM1へ実証済みという条件を逆流させない。独自code上限は後述し、上限内で実現できなければ既製制御候補へ戻してM2をINCONCLUSIVEとする。

## 2. 現在の保存先・所有者・可搬性

値やcredential本体は本書へ写さない。所在は論理aliasで表す。絶対locatorと取得時のdigestはprivate entry/checkpointへ保存する。

| object | 現在の唯一の正本 / 書込主体 | export・backup・消去上の注意 | M2/M3での扱い |
|---|---|---|---|
| owner要求・承認境界 | 憲章・owner明示決定。認証済みowner入力 | publicな規範とprivateな原会話を区別 | 合成のowner入力だけを実験authorityへ登録。本物の承認をfixtureへコピーしない |
| 改善task・関係・コメント | default board、tenant pda-improvementのKanban DB / 正規Kanban surface | DBの整合backupとattachments。コメントはapprovalではない | 実験外の追跡正本のまま維持 |
| 既存artifact最終承認 | shared Kanban DB内 `pda_owner_approvals` / owner認証されたapproval plugin | task/run/digest、Git identity、失効・消費を保持。実験の認可へ流用しない | production ledgerはread-only。将来adapter照合をM4で別途承認 |
| 実行履歴・会話 | Hermes state DB / Hermes runtime | 会話はprivate。抽出summaryは正本ではない。削除指示とbackup復帰の整合が必要 | raw会話の候補runtime移行なし |
| 現行記憶・好み | Hermes memory/user profile / 明示owner訂正と許可されたmemory操作 | token制限・出典・訂正/削除を別扱い。旧値をbackupから復活させない | 合成のみ。semantic memoryをstop/承認の正本にしない |
| 公開知識 | public PKBのsource/note + Git / 既存PKB運用 | publicのみ。索引は再生可能projection | 既存raw私有データを混ぜず、fixture内の公開/合成objectを利用 |
| skill | 現行skill package/sourceと必要な実環境条件 | package本文、抽象索引、validity、依存版、権限を分離 | 名前なし発見→検証→loadを試す。読んだだけで常設catalogへ戻さない |
| code/release | task worktreeのGit artifact、承認対象release / 実装者と承認済みfinalizer | 同一disk Gitのみでhost喪失に備えたとしない | 未承認merge/pushなし。実験releaseのみ |
| credentials/課金 | 現行providerの認証store / provider認証経路 | private。Git・PKB・candidateへの値コピー禁止。aliasだけを契約に記載 | M2 bootstrapはcredential/model利用0。ownerが明示承認したM2後半の実Hermes再試験だけ、entryで固定した既存alias/model/effortと累積上限をhost側model-only relayで利用する。workerへ認証値を渡さない。M3の利用経路は別entryで制限 |
| backup | 現行local-backupの成功generation/manifest / 既存timer | 同一disk保護。停止/失効を古いsnapshotへ戻さない。オフホストHAではない | 実験専用storeのtemp復元だけ。現行backupやretentionは変更しない |

既存approval schemaの確認源: `integrations/hermes-pda-approvals/dashboard/plugin_api.py:113-188`。既存scope sourceは失敗の証拠としてのみ利用し、制御正本に昇格させない。

## 3. M2実験controlのauthority matrix

全APIはtrusted transport由来のprincipal/roleを検査する。payload中の `actor=owner`、task名、UUIDらしい文字列は認証にならない。workerにはowner socket、control DB、Docker socket、host homeを渡さない。実験のowner入口とworker入口を物理的に分け、namespaceとobject所有をget/readにも適用する。

| objectと不変ID | 正本・唯一の書込主体 | 遷移 / linearization point | CAS・冪等key / 復帰規則 | primitiveと後段接続 |
|---|---|---|---|---|
| activity `namespace,activity_id` | control DB activity row / control service | created→ready→running→waiting/held/stopped→completed。失敗/停止を完了へ読み替えない。row transaction commitが確定点 | revision CAS。create request IDとactivity IDを分離。現在のrowとeventを同一transactionで記録 | SQLite `BEGIN IMMEDIATE` + PK + revision条件。DBOS workflow IDはこのactivityに紐付く別ID |
| stop `activity_id,stop_epoch` | control DB / owner stop ingressのみがepochを増加 | 未開始作用の受付を停止commitで閉じる。再起動/rollback/古い承認ではclearしない。resumeは現在epochを指定した別のowner許可 | stop request IDはidempotent。control row revisionとepoch照合。owner停止は学習/忘却対象外 | owner専用UDSとtransaction。worker deny/予算枯渇から独立。M3 adaptersは作用前照合 |
| approval `approval_id,scope_digest` | control DB / owner認証入口のみ | proposed→approved→activation-claimed→consumed または revoked/expired。artifact/entry/scope変更で失効 | approval ID + activity + entry digest + artifact + effect class + limit + expiry + stop_epoch。activation nonceはCASで一つだけ。rollbackで未消費へ戻さない | SQLite制約とauth境界。M3/4は同一verification APIに結線し、runtimeの内部Yesで代替しない |
| claim `activity_id,run_id,fencing_token` | control DB / scheduler-controlだけ | lease取得/更新/失効。新claimでfenceを単調増加。lease時刻確認不能は新規作用hold | active claimのsingleton、revision CAS、renew request ID。old runのheartbeatを新runへ流用しない | SQLite CAS + trusted clock。DBOS worker開始前・各作用前にcontrolで確認。worker時計は非権威 |
| effect intent `activity_id,operation_id` | control DB intent / control service | planned→authorized→dispatched→confirmed または uncertain→held/reconciled。intent commitを先行し、通信成功/例外だけでconfirmedにしない | 同じlogical operationの全retryは同じID。payload digest相違はconflict。attempt IDで新作用へ化けさせない | control DB PK(activity,operation)。effect service/sinkのread-after-writeとfence検証へ結線 |
| effect実現の事実 `operation_id,receipt_id` | 実作用先のreceipt / 実作用先のみ | downstream側commitが作用の確定点。control内receiptは検証済みmirror | downstreamのidempotency keyとreceipt query。receipt不明時は再作用しない。mutationにCAS/冪等/照会が無いtargetは自動replay不可 | M2は隔離した実HTTP/UDS試験sink。M3 adapterを変えたらF4/F6再実行。controlとsinkを同一stubで成功させない |
| budget `entry_id,activity_id` | control DB累積ledger / control service | 課金され得る各dispatch attemptの予約をcommitしてから送信。timeout/receipt不明の旧予約は消去しない。settlementは二重精算しない | stable logical operation IDとchargeable dispatch-attempt reservation IDを分離。再送は新しいreservationでentryとactivityのcapを同transactionで再照合する。過去累積を下回るcap変更はdeny。同一requestを再送せず観測/復元するだけなら旧reservationを参照する。run再作成で累積をゼロに戻さない | SQLite transaction + unique attempt reservation。DBOSが同じoperation IDでretryしても、別のprovider requestには別予約が必要。downstream冪等keyは追加課金がない証拠ではない。M3 token/料金brokerへ接続 |
| workflow continuation `workflow_id,step-id` | DBOS system DB / DBOS runtime | DBOSがcommitしたstepだけ再利用。activity/stop/approvalを別権威へ移さない | workflow/operation IDをcheckpointに保存。control現況をread-backし再開資格を判定。DBOS復帰成功だけでjob resume不可 | DBOS 2.31.0、adapter code/version/digestを固定。M3/M4で変える場合は関係するM2試験を再実行 |
| artifact/evidence `content digest` | Git/immutable evidence manifest / producer、verifierは別 | 内容変更は新digest。review targetは固定snapshot | byte hash、base/head、fixture/entry/control revisionを束縛。旧reviewを新artifactへ流用しない | Git + SHA256。Kanbanはlocator/検証結果を表示 |

## 4. 故障・競合の決定規則

1. DB rowとevent ledgerは同一SQLite transactionで書く。どちらかだけ更新された疑い、schema/hash不整合なら当該活動をholdし独立診断へ出す。バックアップを多数決で選ばない。
2. control DBとDBOS DBと外部sinkは別transaction領域である。intent先行、安定operation ID、sink照会、holdにより境界の第三状態（commit済みだが応答消失）を表現する。
3. 新claim/stopと作用が競合した場合、downstreamがfence・operation IDを検査するcommitが作用のlinearization point。stopより前にcommitした作用は歴史から消えない。stop後の新規dispatchは0。既にdispatch済みの作用はreceipt照合まで未確定と表示する。取消可能性を保証せず、非取消targetは事前entryで明示する。
4. lease期限とstop受理の境界ではcontrol接続不能のworkerをfail closedにする。接続確認と作用の間のraceは、downstream/server-side条件と短命permitの照合で防ぐ。workerによるcheck-then-actだけでfencingを主張しない。
5. effect sinkはpermit取得時のstop epoch/fenceだけを永遠に信頼しない。M2ではcontrol admissionとsink commitを一つの直列化されたbroker経路に限定し、stop/claim更新とcommitの順序をbarrier試験で検査する。このbroker契約を満たせない外部targetはM3で自動作用対象から外す。
6. control DB喪失/破損時は作用停止。releaseだけrollbackして古いstop/approval/budgetへ戻さない。新しいstop/失効を含まないsnapshotを復元した場合、外部保管した最新control epochの照合ができるまで再開不可。M2は同一hostのprocess/DBアクセス故障だけを必須範囲とし、host/disk全損の救援なし復帰は未実証として残す。
7. 監督喪失は正常/進行中と表示しない。独立statusは最終観測時刻、観測主体、unknown/stopped/recoveringを返す。authority到達不能でも説明・stop受付のreceiptまたは受付不能の応答まで通常作業予算に連座させない。『受け付けた』と表示するのはstopが永続commitされた場合だけ。
8. 作業budgetと安全なcontrol budgetを分ける。control requestはサイズ/頻度/認証で別に制限するが、普通のtool拒否回数/再review回数でstop/report/receipt照会を封鎖しない。無限のmodel retryをdiagnosticと呼ばない。

## 5. 記憶・注意・寿命は制御authorityと別

memory recordは `source_id,source_revision,validity,scope,classification,locator,lineage,status` を持つ。statusは active/abstracted/dormant/superseded/revoked/deletedを区別する。sourceの訂正/削除がprojectionより優先され、検索結果を返す時も有効性を確認する。projection未更新はstale/holdであり、LLMが古い要約をcurrent truthへ昇格させない。

回収可能な休眠と明示削除は別である。休眠詳細のlocatorは保持し、通常catalogには抽象的能力と適用範囲だけを載せる。削除tombstoneはindex rebuild/backup/importに先行して適用し、削除内容をsummary-of-summaryから再生成しない。stop/approval/未完了義務はsemantic similarityや経過時間で失効させない。

M3でmemory候補を交換してもcontrol authorityは移さない。OpenViking/Hindsightのどちらか一つで足りるかを評価し、両方の常駐を前提にしない。F11/F13〜F20のtraceは取得、注入、回答言及、作用の4段を区別する。

## 6. 実装責任・独立性・維持費上限

M2 control実装/adapterの責任はPDA、検証は別verifier。専用systemd unit・sandbox worker・control・sink・observerは実PID/cgroup/UID/mount/permissionを記録する。名前だけ違うprocess、同じhost UID、containerの存在、unit fileの存在だけで独立としない。workerからcontrol DB/owner入口/host socketへのアクセス失敗と、worker破損中のowner stop/status成功を実行証拠にする。

本番gatewayはこの実験のkill/restart対象にしない。現会話はgatewayと同cgroupであり、既に独立監督役があるとは主張しない。M2 bootstrapで専用経路の親会話終了・worker停止・監督再起動を先に検証する。これが失敗した場合、長時間比較を追加しない。

M2で新作するcontrol/adapter/fixture driver/sink/observerの実行コードは合計800 logical Python lines（testsだけ除外）、常駐専用control serviceは1、固有state storeはcontrol DB + DBOS system DBまでを初期投資上限とする。logical lineは空行・コメントを除くPython tokenのNEWLINE数で同じscriptにより集計する。controllerに汎用query engine、独自queue engine、全履歴移行を追加しない。超過時はM2 NO-GO/再設計とし、範囲を密かに拡大しない。line数だけで良否は決めず、更新/復元/退出の手動操作と実時間を合わせて比較する。

## 7. M1 exitから後段への結線

M1 exit manifestが本書の実byte SHA256を固定し、独立レビュー結果とともにM2 entryへ渡す。M2は各行についてimplementation path/version/config/adapter digest/試験ID/実結果を埋める。M3とM4は同じidentityの結線を引き継ぐか、変更した範囲のF1〜F10を再試験する。M5〜M7は各実観測窓の前半/後半でworker/監督の複数再起動、重複停止、通知断、checkpoint前後、receipt不明、旧claimを試し、同じactivity・stop・残予算を維持する。

本書の文書レビューPASSはM2の実装PASSでもowner entry承認でもない。制御primitiveを成功前提stubへ置換した測定、現行Kanban done、別taskへの再投入、cloneだけの観測は後段依存を解放しない。
