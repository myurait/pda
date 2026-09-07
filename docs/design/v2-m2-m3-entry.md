# V2 M2/M3 entry — M1で具体化した一括境界

状態: entry提案。M1開始指示はこの新しいinstall/runtime/model接続を許可したことにはしない。M2=`t_ec4c52b9`、M3=`t_0a0c6ad7`。この文書は本番承認ではない。

## 1. 今回M1の範囲と次の判断

M1実行開始は2026-09-07 11:23:55 JST、今回の上限は16:23:55 JST。ownerの「可能な限り並行して効率的に自走」を受け、無作用再現、証拠回収、入力fixture、制御/比較契約、独立review、隔離branchへのcommit、Kanban review記録まで行う。重いruntime、候補install、provider新規利用、本番変更はM1では0件とする。

次に求める判断はM2の隔離復帰実証のentryだけ。以下のallowlist、費用/資源上限、停止・後始末をまとめて示し、一部の小コマンドごとにownerを呼び戻さない。実装の限定変更はstage内裁量、範囲・資源・送信先・credentialの拡大は新しい判断とする。

## 2. M2で許可を求める実験境界

目的: 壊れたworkerの代わりに、独立監督が状態・stop・承認・仕事・残予算を保持して限定活動を復帰できることを、実プロセスと実sinkで測る。PDA本番を壊す試験ではない。

### 対象と既存primitive

- 独立task worktree: `/home/user/projects/pda-autonomous-tasks/t_ec4c52b9`、branch `pda-auto/t_ec4c52b9`。作業開始時に未使用/正しいtask所属を確認し、他threadの既存領域を上書きしない。
- runtime root: `/home/user/.hermes/workspaces/pda-v2-m2` の新しいrun専用subdirectory。versioned managed-root markerを確認する。ここ以外のデータを削除しない。
- host側独立control service: 実験専用systemd user unit `pda-v2-m2-control-<runid>`、別cgroup。現gatewayとは別のOS監督経路で起動・再起動し、現gatewayの停止/再起動はしない。
- worker: 既存の `python:3.11-bookworm` imageをローカルimage digestで固定し、Docker namespaceで非root、read-only rootfs、cap-drop、no-new-privileges、host PID/socket/home/production volumeを渡さない。新しい実験imageへ依存を足す場合はlock/hashを固定してから実行する。
- durable workflow候補: `dbos==2.31.0`（既存の公開source snapshot `7a35952040dc5e30b1fe178ffdd8f3c86ddef3100c`）。DBOS system DBはworkflow continuationだけ、control正本は別のSQLiteに分離。DBOSの再試行が外部exactly-onceを単独保証するとは扱わない。
- control正本: [state custody](v2-state-custody.md)の単一writer SQLite、owner/worker別endpoint、stable ID、receipt、fencing。薄いadapter/fixture/sink/観測の本体上限800行（tests除外）。超える場合は独自基盤へ拡大せずNO-GO/再設計。
- 複数writer・異なるUID・権限境界を説明だけで済ませず、workerがcontrol DB、owner socket、host Docker socket、正常artifactを書けないnegative probeをM2 bootstrapの最初に行う。別cgroupだけで権限独立と称さない。

### 許可する作用

新規実験venv/imageへのpin済み依存install、実験unit/containerのcreate/start/stop/kill、実験root内のsnapshot/replay/restore、ローカルfixture sinkへのidempotent append、実験worker/監督のfault注入。scope control v2のsourceはread-onlyで反例として使用するだけ。

パッケージ取得先はPyPI/その配布CDN、npm/その配布CDN、GitHubの当該公開repo、Docker Hubの当該base imageに限る。送るのは通常のpackage/公開source取得要求だけ。telemetryは無効化可能なものを無効化し、私的PDA state/secretを送信しない。実行中はworkerのnetworkを閉じ、必要ならcontrol/model relayだけへ限定する。公開listen/Funnel/Tailscale設定変更はしない。

許可しない作用: 既存gateway/Open WebUI/backup/dispatcher/scope gateの変更や再起動、既存profile/config/authの変更、私的memory移行、新accountの認証、課金、外部通知/メール/公開投稿、remote Git push、既存DB restore。

### model/credential

bootstrapは0 model callsの決定的workerで実施する。ここを通らない間はLLMに試行を消費させない。

M2後半の実Hermes worker再試験に限り、既存PDA-localの`openai-codex` provider・現main model/effortというaliasを使用するentry承認を求める。最大32 model calls、入力/出力/reasoning累計100,000tokens、実fixtureの合成情報だけ。本proposalの固定値はprovider=`openai-codex`、model=`gpt-6-astra`、reasoning=`max`。entry記録へ値として保存し、後のprofile変更へ追随しない。first-party Hermesのmodel-onlyなhost側relayを介し、workerの実験用tool executorとは分ける。relayは固定template/モデル/上限のみを受理し、host commandや任意tool実行を委譲できないことをnegative probeで確認する。

実Hermes再試験の割当はF1/F2/F5/F6/F8の各1screen+5confirm、各trialに新規推論1callを行ってからfaultを注入する。計30call、残り2callだけを課金され得る再送に留保する。fault後にcommit済み推論stepを再利用した部分は機械的replayであり、新規推論の追加試験数に数えない。追加推論が必要な実装なら総32callを超えて黙って試験を増やさずINCONCLUSIVE。100,000tokensは別の累積hard capであり、全30trialの完走を保証しない。F9のtimeout/quota負例はbootstrapの障害注入であり、本物のprovider全停止/課金境界を実証したとは呼ばない。

raw auth/tokenをcandidateのファイル・gold・export・logsへcopyしない。model-only経路とproduction tool/config非到達を実物で制限できなければM2はINCONCLUSIVE/NO-GOで止める。別account、開発PCのcorporate Claude、Claude個人残額、API keyへ自動fallbackしない。新しいログインが必要ならcredentialsを推測せず、その一点を追加entryとしてまとめる。

既存`hermes proxy providers`ではanthropic/claude_code/xaiのみが表示され、proxy自体も停止中だった。これをCodex対応bridgeが動作済みとの証拠にはしない。新しい汎用proxyやcore forkをM2の隠れた前提へ足さない。

### 上限・報告・後始末

M2全体最大24時間、1attempt最大6時間、同型実装retry2回、candidate重処理1つ、実験合計CPU≤2core/RAM≤2GiB/追加disk≤5GiB、新規課金0。ownerが今回の5時間枠内での続行を選ぶ場合は、当日16:23:55 JSTがこれらより先に作用するdeadlineとなり、未完了はcheckpointして停止する。

statusを5分ごと/phase境界にcheckpointする。2分間新しいprogressが無い場合は観測器でPID/claim/queue/receiptを確認し、許可済み復帰を最大2回、未知receiptは再送せず照会する。owner stop受理を復帰で解除しない。停止で実験worker/unitを止めてもcontrol/証拠を消さない。

rollback対象は当該runのunit/container/image tagと実験rootの可逆設定だけ。shared service、old gate、既存activityへ触らない。temporary process停止後もevidence/snapshotを保存し、managed marker付き生成データの明示清掃は判定後の別stepとする。正常サービス稼働のread-only確認を行って閉じる。

## 3. M3へ渡す固定候補

M2の全必須caseが実物でPASSし、独立reviewとowner M3 entryが揃うまでM3は開始しない。候補順位は投資順位であり採用決定ではない。

| 役割 | pin / 取得した根拠 | 扱い |
|---|---|---|
| 実行基盤先頭 | Letta Code `0.22.2`, source `324164556a5a5e994903e34f8d2f99b2722e93653`。既存9/6 upstream snapshot | local backend/App Serverを対象。Letta旧Python serverを同じ製品と混同しない |
| 注意・memory重点 | OpenViking source `b73108dabd1df080dae728406b63d442020aeabc`、9/7 public GitHub API lookup | lifecycle/検索/skill/情報区分を実driverで確認する。repo metadataのlicenseはAGPL-3.0だったため、採用/配布前に当該LICENSE本文と提供形態の義務を確認する |
| 対抗 | Hindsight source `424601520456a6d06a81b2fdc709a0d023d800af`、9/7 public GitHub API lookup | 同じfixture/送信条件で比較。metadataのlicenseはMIT。OpenVikingとの初手両積みはしない |
| 対照 | 現Hermes + 既存運用。pinは実行前にhead/configの非secret digestを固定 | 今の利用便益と復帰能力の証明を分離。主状態をコピーせず合成stateで試す |
| 最小memory対照 | Letta native MemFS + 簡素な抽象索引 | 索引サイズ/全件列挙の負担まで計上。新しいmemory engineを必須と決めない |
| managed | 既存比較資料のCloudflare/Temporal等 | 資料対照のみ。account/課金/外部state送信が未承認なのでruntime実測へ自動進出しない |

新しいcommitへ追従してから比較することはせず、pinがinstall不可ならその事実を残し、変更する版/理由/影響を一度に再提示する。lockfileとimage digestはM3 preflightで採取するが、採取前にはmodel実測へ進めない。

## 4. M3 model経路の実際の未決定点

Letta公式はlocal backend/App Serverではagent state・memory・provider接続がon-deviceに残り、Letta accountは不要と説明する。外部modelを選べばpromptはそのproviderへ送られる。[2]

Letta公式にはlocalでChatGPT Plus/Pro Codex subscriptionを接続する機能とdevice-code loginの経路がある。[1] したがって「Lettaは従量API keyしか使えない」は誤りである。しかし、機能が存在することと、現在のPDAのOAuth tokenが無操作で適法/安全に再利用できることは別であり、後者は未実証である。

M3 entryでまとめて決める対象は、PDA-localの同じ定額accountをLetta localへ正式に接続すること、合成fixtureをそのproviderへ送ること、embedding/summarizationのrouteと上限である。新login/device confirmationが必要ならowner操作を求める。Hermes authを他runtimeのcredential形式へ勝手に変換・copyしない。Cloudバックアップ/Letta Cloud gatewayへのstate転送はこのlocal許可に含めない。[1][2]

OpenViking/Hindsightのembedding/summarization routeが同じ情報/費用条件を満たさない場合はM3の該当candidateがINCONCLUSIVE/NO-GOとなる。新有償endpointを黙って加えない。不要な自作互換proxyを作って『既存製品で成立』と採点しない。

## 5. 実測順とownerへ返す単位

M2: isolation/bootstrap → 実control/fixture sinkのF1〜F10 → 実Hermesを含む再試験 → 独立review → M3に必要な変更点だけを一括提示。

M3: no-model preflight → 最大4構成screen → 最有力/対抗2構成confirm → [acceptance](v2-acceptance-contract.md)に従うF11〜F20とUI/maintenance/exportの観測 → 採否/理由/残費用を提示。上位candidateに必須未確認があれば条件付き採用しない。

各stage内で通常のバグ修正/再試験/解析を小刻みに承認依頼しない。stage境界、費用/送信/資格情報/対象拡大、全候補失格、時間上限、owner stopだけを判断点として残す。

## Sources

[1] https://docs.letta.com/configuration/models/index.md
[2] https://docs.letta.com/self-hosting/index.md
