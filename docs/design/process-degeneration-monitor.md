# 二値判断プロセスの形骸化検知

- Status: owner-approved v2 implementation contract（2026-09-01）。実装正本は`integrations/hermes-scope-gate/`に置き、稼働状態は本書ではなくruntime read-backで確認する。
- 適用先: 最初の適用はPDAのスコープ制御。以後、同じ契約で任意の二値判断プロセスを登録できる。
- 関連: `task-scope-admission-gate.md`、`improvement-orchestrator.md`、`self-improvement-governance-adr.md`

## 1. 目的

AIまたはゲートが形式上は判断を返していても、実際には常に`true`または常に`false`へ倒れ、判断工程として機能しなくなることがある。この失敗を、判断内容を再解釈せず、施行結果の分布から決定論的に検知する。

検知器は、どちらの値が「正しい」か、望ましい比率が何%かを決めない。直近3日間に有効な施行が10件以上あり、一方の値が95%以上を占めた事実を「仕組みの失敗疑い」として起票し、人または後続の改善工程へ渡す。

## 2. 適用範囲と非目標

適用できるのは、各施行について`true`または`false`を一つ返し、期待される施行母集団を別のライフサイクルイベントから特定できる判断プロセスである。モデル判断、決定論ゲート、承認判定のいずれにも使える。

本機構は次を行わない。

- 元の判定を反転、補正、再試行、上書きしない。
- 50対50を正常値として強制しない。
- 偏りだけを理由に作業、承認、最終反映を許可または拒否しない。
- 欠測や不正イベントを`true`または`false`へ丸めない。
- 自動修復や自動割当を開始しない。

アラートの作用は、未割当Triageタスクの作成または既存episodeへの追記だけに限定する。

## 3. 共通登録契約

監視対象は、実装コードへの個別分岐ではなく登録レコードで追加する。登録には少なくとも次を含める。

| 項目 | 契約 |
|---|---|
| `monitor_id` | 監視の安定識別子。実装版やモデル名が変わっても、同じ意味の判断なら維持する。 |
| `display_name` | Triageで人が理解できる判断工程名。 |
| `expected_event_type` | 判断が一件存在すべき母集団を表すライフサイクルイベント。 |
| `decision_event_type` | 二値判定イベントの型。 |
| `join_key` | 期待イベントと判定イベントを一対一に結ぶ施行識別子。 |
| `verdict_field` | JSON booleanだけを受理する欄。文字列の`"true"`等は不正とする。 |
| `expected_occurred_at_field` | 判断が必要になった時刻。pendingと欠測の期限判定に使う。 |
| `decision_occurred_at_field` | 判定が完了した施行時刻。72時間の偏向集計はこのevent timeを使う。 |
| `event_time_authority` | event timeを付与するcontrol planeまたは認証済みsource。実行主体の自由記述時刻を使わない。 |
| `decision_due_rule` | 期待eventがpendingからmissingへ変わる時刻またはライフサイクル境界。processごとに必須。 |
| `event_id_field` | 再送を除くための一意なイベントID。 |
| `diagnostic_dimensions` | evaluator、model、policy version等。原因分析用であり、主集計を分断して閾値をリセットしない。 |
| `task_destination` | 既定はHermes default board、tenant `pda-improvement`、未割当Triage。 |
| `authority_source` | この登録と閾値を承認した統治文書またはオーナー決定。 |

### 3.1 新しい二値判断工程を追加する手順

1. 判断工程の意味と`monitor_id`を決め、統治文書（本書または該当ADR）に閾値の出所を1行で記す。
2. `integrations/hermes-scope-gate/process_monitor.py`の`MonitorDefinition`で登録レコードを作り、`ProcessMonitorStore.register_monitor()`で登録する。初期登録は同ファイルの`INITIAL_MONITORS`に並べれば、storeの初期化時に自動登録される。
3. 判断が必要になった時点で`record_expected(monitor_id, join_key, event_id, occurred_at, due_at)`を、判定が確定した時点で`record_decision(monitor_id, join_key, event_id, verdict: bool, occurred_at, accepted_at)`を、それぞれcontrol plane側から呼ぶ。時刻は呼び出し側（control plane）が付与し、実行主体の自由記述時刻を渡さない。
4. `pda-scope-gate monitor-reconcile --no-delivery`で期待どおりに`N`と比率が集計されることを確かめ、その後は毎時のtimer（`pda-process-monitor.timer`）が起票まで行う。
5. 既存登録の閾値や窓を変える場合は`register_monitor()`が差分を拒否するため、新しい`monitor_id`と移行記録を作る（同じIDのまま条件を緩めることはできない）。

`monitor_id`は意味的に同じ工程を版ごとに分割してはならない。モデルやpolicy versionを主キーにすると、頻繁な版上げだけで72時間窓を空にできるためである。版情報は同じ監視内の診断軸として保持する。判断の意味自体が変わる場合だけ、新しい`monitor_id`と移行記録を作る。

control plane全体には予約済みの`monitor_id = process-monitor.ingress-integrity`を常設する。raw eventに`monitor_id`が無い、registryに存在しない、またはmonitor IDとして不正な値しかない場合は、元の主張値を`claimed_monitor_id`という診断欄へ隔離し、この予約IDの`unattributed-invalid-event`として扱う。未知IDを動的にregistryへ追加したり、raw eventを捨てたりしない。

## 4. 判定イベントと母集団の完全性

全てのraw eventは内容検証より前にcontrol event storeへ受け入れ、変更不能なenvelopeを付ける。envelopeは`source_stream_id`、stableな`source_position`、`raw_payload_digest`、`ingress_id`、`accepted_at`、単調増加の`control_sequence`を持つ。`ingress_id = sha256(source_stream_id || source_position || raw_payload_digest)`とする。sourceがstable positionを供給できない場合は、control storeがcommit前に払い出すdurable ingress sequenceを`source_position`として使う。再送で既存`ingress_id`が見つかった場合は、最初の`accepted_at`と`control_sequence`を維持する。

有効な判定イベントは、このenvelopeに加え、登録済み`monitor_id`、一意な`event_id`、`join_key`、event time、JSON boolean verdictを持つ。raw prompt、reasoning、tool引数、秘密は複製しない。

期待母集団との照合は必須である。

1. `expected_event_type`一件につき、同じ`join_key`の判定イベントがちょうど一件必要である。
2. 同じ`event_id`と同じpayloadの再送は一件として扱い、最初に受理したenvelopeを維持する。
3. 同じ`join_key`へ同じverdictが別`event_id`で複数届いた場合は、永続化順を表す`(control_sequence, event_id)`の昇順で最小のeventをcanonical survivorとする。wall clockの逆行や再送順序でsurvivorを変更しない。canonical eventだけを比率の分母・分子へ入れ、その`decision_occurred_at`を72時間窓に使う。残りは`duplicate-decision`として別途可視化する。
4. 同じ`event_id`または`join_key`に異なるverdictが届いた場合、どちらかを採用せず`conflicting-duplicate`とする。
5. 欠損、不正、未実施、評価不能、中断による未判定はbooleanへ変換しない。
6. 期待イベントの取得自体ができない場合、母集団をゼロと仮定しない。

3項から6項は通常の偏向比率とは別の`telemetry failure`である。比率の分母には有効で一意なboolean判定だけを入れるが、除外した事実を黙らせず、同じ評価周期で必ず別起票する。これにより、判定を出さないことや重複送出で見かけの比率だけを正常化する経路を残さない。

期待eventだけが存在しても、登録済み`decision_due_rule`を満たす前は`pending`でありfailureにしない。期限判定には自己申告のevent timeを使わず、decision eventのcontrol-stamped `accepted_at`を使う。時刻deadlineとの比較は`accepted_at <= decision_due_at`、ライフサイクル境界との先後は`control_sequence`の小さいeventを先とする。期限または必須境界を越えた時点で初めて`missing-decision`とする。期限後に届いた判定は、その`decision_occurred_at`が期限前を主張していても通常の母集団へ遡及投入せず`late-decision`として記録し、既に起票した欠測episodeへ関連付ける。これにより、正当に評価中の処理を即時欠測扱いせず、未実施を無期限にpendingへ置くことも、時刻の自己申告で遅着を隠すこともない。

## 5. 72時間の偏向判定

各`monitor_id`について、判定イベントの永続化直後と毎時のreconcileで同じ集計を行う。評価時刻を`cutoff`とし、次を満たすevent timeの有効イベントを対象とする。

```text
cutoff - 72 hours < occurred_at <= cutoff
```

集計は次のとおりである。

```text
true_count  = verdict == true  の件数
false_count = verdict == false の件数
N           = true_count + false_count

dominance = max(true_count, false_count) / N
trigger   = N >= 10 AND dominance >= 0.95
```

比較は「95%以上」なので`>= 0.95`であり、丸めた表示値ではなく整数件数の比で判定する。件数下限は10件である。`N < 10`では比率を記録しても偏向episodeを開始せず、10件目以降だけtriggerを評価する。

異なる`monitor_id`を合算しない。診断軸ごとの内訳は記録するが、主判定は安定した`monitor_id`全体で行い、version変更による窓のリセットを許さない。

## 6. episodeと冪等起票

triggerが`false`から`true`へ変わった時点をepisode開始とする。monitor登録時の永続状態は`last_trigger=false`、`episode_generation=0`であり、初回の有効評価がtriggerなら通常のfalse→true遷移として扱う。状態遷移とdurable outbox書込は一つのcontrol-side transactionで行う。

- event直後のevaluation IDは`event/<monitor_id>/<source_event_id>`、毎時reconcileは`reconcile/<monitor_id>/<UTC hour bucket>/<event high-watermark>`とする。同じ入力の再実行は同じIDになる。
- false→trueを最初にCASで確定した評価だけが`episode_generation`を1増やす。episode IDは`sha256(monitor_id || episode_generation || dominant_value)`とし、競合したevent評価、reconcile、再起動の順序で変わらない。
- idempotency keyは`process-degeneration/<monitor_id>/<episode_id>`とする。
- 同じepisode中の再評価は新しいカードを作らず、既存カードへ最新の窓、件数、比率、完全性状態を追記する。
- dominanceが95%未満へ戻ったらepisodeを`recovered`として記録する。原因調査カードを自動完了にはしない。
- recovered後に再び閾値へ達した場合は、新しいepisodeとして新規起票し、前episodeへ関連付ける。

同じtransactionに、episode ID、idempotency key、payload digestを持つoutbox行を一件だけ作る。Kanbanへの起票が失敗してもepisodeを通知済みにせず、起票先からtask IDをread-backできるまで同じoutbox行を再送する。再試行中も元の判断・作業・承認を止めたり変更したりしない。outbox自体の書込または再送が失敗した場合は、独立した運用アラートへ送る。

起票するカードは未割当Triageとし、少なくとも次を含める。

- 判断工程名と`monitor_id`
- 優勢値
- 72時間窓の開始・終了
- `true_count`、`false_count`、`N`、dominance
- 期待母集団件数とtelemetry failure件数
- evaluator/model/policy versionの内訳
- 根拠イベントへの非秘密参照
- 「元判定は変更していない」「自動修復・自動割当はしていない」という作用境界

カード名は「判定プロセス失敗疑い: <display_name>」とする。起票自体を仕組みの正常性の証明には使わない。

## 7. telemetry failure

次は偏向とは独立した失敗episodeとして、同じく未割当Triageへ冪等起票する。

- `missing-decision`: 期待された施行に判定イベントがない。
- `late-decision`: 登録済み期限または必須境界を越えて判定が届いた。
- `invalid-verdict`: 登録済みprocessのboolean以外のverdict、またはmonitor ID以外の必須欄欠落。
- `unattributed-invalid-event`: monitor IDが欠落・不正・registry非所属で、個別processへ帰属できないraw event。
- `duplicate-decision`: 同じ施行・同じverdictが別eventとして複数届いた。
- `conflicting-duplicate`: 同じ施行に相反する判定がある。
- `expected-population-unavailable`: 母集団を取得・照合できない。
- `monitor-evaluation-failed`: 母集団照合または偏向集計自体が失敗した。
- `sink-delivery-failed`: Triageの作成・更新、またはtask IDのread-backが失敗した。
- `outbox-persist-failed`: monitor状態とoutboxを作るcontrol transactionを永続化できなかった。

failureの冪等単位は次の二種類に固定する。

1. 施行単位: `missing-decision`、`late-decision`、`invalid-verdict`、`unattributed-invalid-event`、`duplicate-decision`、`conflicting-duplicate`。subject keyは有効な`join_key`、それが無ければ`event_id`、両方が欠ける不正eventはcontrol envelopeの`ingress_id`とする。個別processへ帰属できない場合は必ず予約ID`process-monitor.ingress-integrity`をmonitor IDとして使い、subject keyを`ingress_id`とする。episode IDは`sha256(monitor_id || failure_type || subject_key)`、idempotency keyは`process-telemetry/<monitor_id>/<failure_type>/<episode_id>`とする。別のjoin keyを同じepisodeへ集約しない。同じ施行の追加証拠は同じepisodeへ追記する。missing後にlate decisionが届いた場合はmissing episodeを`resolved-late`へ更新し、late-decision episodeを同じsubject keyで関連付ける。施行自体は一回限りなのでgenerationを持たない。
2. 継続障害単位: `expected-population-unavailable`、`monitor-evaluation-failed`。subject keyは`monitor_id`とfailure typeである。永続状態を`active=false`、`generation=0`から開始し、最初の失敗でCASしてgenerationを増やす。episode IDは`sha256(monitor_id || failure_type || generation)`とする。母集団照合または評価が一回正常完了した時点でrecoveredとし、その後の再発は次generationにする。

delivery障害は配信対象に結び付ける。`sink-delivery-failed`のsubject keyはprimary outbox ID、`outbox-persist-failed`のsubject keyはcontrol invocation IDであり、episode IDは`sha256(failure_type || subject_key)`とする。sink-delivery episodeは同じidempotency keyのtask IDをread-backできた時点でrecoveredとする。outbox-persist episodeは、後述のhealth eventを次の正常reconcileがcontrol ledgerへ取り込み、元のpayloadをoutboxへ再構成できた時点でrecoveredとする。新しいoutboxまたはinvocationの失敗は別episodeであり、同一subjectの再試行は同じepisodeへ追記する。

primary Triage sinkをdelivery障害の唯一の可視化先にはしない。PDA実装は、primary outboxと同じcontrol storeに`process_monitor_health` ledgerと、Kanbanを経由しない`owner_alert_outbox`を持つ。`sink-delivery-failed`はこの二つへ同じtransactionで記録し、所有者status/alert surfaceがACKするまで再送する。Kanban復旧後には同じepisodeをTriageへもread-back付きで作成し、control alertと相互参照する。

control transaction自体が失敗して`outbox-persist-failed`を同じstoreへ書けない場合は、監督processが`pda.process-monitor.health/v1`の構造化eventをsystem journalへ書いてnon-zeroで終了する。event IDは`sha256("outbox-persist-failed/v1" || control_invocation_id || payload_digest)`とする。service healthと所有者statusはjournal未取込eventを異常として表示し、次の正常reconcileがevent IDで冪等にhealth ledgerとTriageへ取り込む。この最終fallbackまで失敗した状態はmonitor service unhealthyであり、正常運転を主張しない。

telemetry failureがある場合でも、有効イベントが一件以上あれば偏向集計は併記する。どちらか一方だけを報告してもう一方を隠さない。

## 8. 最初の登録

### 8.1 Terra事前評価の追加保証フラグ

- `monitor_id`: `scope.prework.additional-assurance-required`
- `expected_event_type`: `pda.scope.prework-review-requested/v1`。control planeがTerraを起動する前に永続化する。
- `decision_event_type`: `pda.scope.prework-review-completed/v1`。別sessionのTerra verdictを受理した時だけ永続化する。
- `join_key`: `review_request_id`。ScopeFrameまたは計画を改訂して再提出する場合は新しいIDを払い出し、旧要求を上書きしない。
- expected event ID: `sha256("scope-prework-request/v1" || review_request_id || scope_frame_digest || plan_digest)`。
- decision event ID: `sha256("scope-prework-completed/v1" || review_request_id || canonical_verdict_digest)`。同じ結果の再送は同じIDになる。
- expected time: `requested_at`。decision time: `completed_at`。72時間の偏向集計には`completed_at`を使う。
- time authority: どちらもcontrol planeが対応eventを永続化する時に付与し、Terraまたはexecutorの自由記述値を受理しない。期限判定はdecision envelopeの`accepted_at`を使う。
- verdict: JSON booleanの`additional_assurance_required`。
- `decision_due_rule`: expected eventが持つcontrol-policy由来の`decision_due_at`、または同じ`scope_frame_id`を参照する`pda.scope.work-started/v1`の発生のうち早い方。期限前はpending、期限経過または未評価のまま作業開始なら`missing-decision`とする。作業開始の強制可否はスコープ実行境界が別途扱う。
- 完全性条件: 一つの`review_request_id`に有効な完了eventが一件だけ存在する。評価不能、出力欠落、executorによる値の書換え、期限後の完了はtelemetry failureであり、通常施行として数えない。

### 8.2 最終スコープ監査ゲート

- `monitor_id`: `scope.final.final-scope-conformant`
- `expected_event_type`: `pda.scope.final-audit-required/v1`。正常経路ではrunを成功、partial、blocked、failedの終端へ確定するcontrol transaction内で一件作る。crash経路ではterminal runを検出したreconcileが同じ決定論IDで補う。
- `decision_event_type`: `pda.scope.final-audit-completed/v1`。実作用を現在指示由来のScopeFrameへ照合した最終監査が完了した時だけ永続化する。
- `join_key`: `final_audit_request_id`。一つの`run_id`と最終`scope_frame_digest`に対して一つだけ払い出す。
- expected event ID: `sha256("scope-final-audit-required/v1" || run_id || scope_frame_digest)`。crash reconcileでも同じIDを再構成する。
- decision event ID: `sha256("scope-final-audit-completed/v1" || final_audit_request_id || canonical_audit_digest)`。
- expected time: `required_at`。decision time: `audited_at`。72時間の偏向集計には`audited_at`を使う。
- time authority: どちらもcontrol planeが対応eventを永続化する時に付与する。期限とowner-response境界との先後はdecision envelopeの`accepted_at`と`control_sequence`で判定する。
- verdict: JSON booleanの`final_scope_conformant`。
- booleanの意味: 観測できた全作用に現在スコープ上の根拠があり、作用の帰属が未解決でなければ`true`。一件でもoverreachまたは作用未解決があれば`false`。要求未達は別のcompletion状態であり、作用が範囲内ならそれだけで`false`にはしない。
- `decision_due_rule`: expected eventが持つcontrol-policy由来の`decision_due_at`、または同じ`run_id`の`pda.scope.owner-response-finalized/v1`発生のうち早い方。期限前はpending、期限経過または未監査のままowner responseを確定した場合は`missing-decision`とする。
- 完全性条件: 全ての終端runに有効な完了eventが一件だけ存在する。Terraが追加保証を要求した場合、完了eventは予約済み別主体の`independent_audit_id`とaudit digestを参照しなければ不正とする。

この二件は同じ共通集計器へ登録し、個別のif文で特別扱いしない。

## 9. 実装境界と受入条件

本書の実装正本は`integrations/hermes-scope-gate/process_monitor.py`、event producerは同integrationの`scope_v2.py`、Triage sinkとreconcile CLIは`pda-scope-gate`、定期実行は同integrationのsystemd templateである。実装と稼働状態を混同せず、次をfocused testとruntime read-backで固定する。

- event time境界の直前・一致・直後
- 94.99%相当と95%以上
- `N=0`、`N=9`、`N=10`の件数境界
- 同一event再送、同値duplicate、相反duplicate
- control envelope、遅着判定、同値duplicateのcanonical survivorが再送・順序違いでも不変であること
- monitor ID、event ID、join keyが全て欠けたraw eventも`process-monitor.ingress-integrity`と`ingress_id`で一件だけ起票され、主張された未知IDは診断値にしかならないこと
- 判定欠損中にも偏向とtelemetry failureの双方が見えること
- 同一episodeの重複起票0、回復後の再発は新episode
- model/policy version変更で主窓がリセットされないこと
- アラート経路が元の判定値、作業可否、承認可否を変更しないこと
- 本番Kanbanを試験データで汚染しないこと

本機構の登録、閾値、起票先の変更は統治変更であり、通常workerが自己正当化して緩和できない。
