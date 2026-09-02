# scope制御v2 運用runbook

## 目的と安全境界

このrunbookは、scope制御v2が稼働しているかを読み取り、Terraによる事前評価と必要な最終監査が実行されたかを確認し、監視が作るTriageカードと障害を切り分けるための手順です。

通常確認は読み取りだけで行います。installerの再実行、timerの有効化・停止、Hermesのreload、Git revertは稼働状態を変えます。障害対応またはrollbackとして承認されたときだけ実行してください。確認のために判定を作り直したり、state DBやoutboxを直接編集したり、Triageカードを手動で複製したりしません。

以下はPDAの正本checkoutから実行します。

```bash
cd ~/projects/pda
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN="$HERMES_HOME/plugins/pda-scope-gate"
GATE="$PLUGIN/pda-scope-gate"
```

## 1. 稼働中の状態を確認する

### 1.1 pluginの版と読込元

```bash
hermes plugins list
readlink -f "$PLUGIN"
grep -E '^(name|version):' "$PLUGIN/plugin.yaml"
grep -E '^(name|version):' integrations/hermes-scope-gate/plugin.yaml
```

次を確認します。

1. `hermes plugins list`に`pda-scope-gate`があり、無効または読込失敗になっていない。
2. `readlink -f`の結果が、承認済みの正本checkoutにある`integrations/hermes-scope-gate`を指している。
3. 稼働plugin側と正本側の`version`が一致している。v2導入時のmanifestは`0.2.0`です。以後は固定値だけで判断せず、承認されたreleaseのmanifestと照合します。

symlinkとmanifestが一致していても、更新前から動き続けているHermes processが新しいコードを読んだ証明にはなりません。plugin変更後は承認されたreloadを行い、新しいturnが後述のv2 stateへ記録されるところまで確認します。

### 1.2 plugin、hook、gate DB

```bash
hermes plugins doctor integrations/hermes-scope-gate --ci
hermes hooks doctor
"$GATE" doctor
```

`pda-scope-gate doctor`はJSONを返します。正常時は少なくとも次を満たします。

- `ok`が`true`。
- `schema`が`pda.scope-control/v2`。
- `integrity`が`ok`。
- `state_path`が、現在のprofileで使うscope gate DBを指す。
- `monitors`に登録済み監視が存在する。

`doctor`が確認する中心はscope/monitor DBの整合性です。pluginの有効化、shell hook、timer、Kanban配信までを単独で保証するものではないため、前後の確認を省略しません。

### 1.3 process monitorの状態

```bash
"$GATE" monitor-status
echo "exit=$?"
```

主な欄は次のように読みます。

| 欄 | 意味 | 判断 |
|---|---|---|
| `ok` | `process_monitor_health`にactiveな障害がないか | `true`が必要です。ただし、これだけで全体正常とは判断しません。 |
| `pending_outbox` | 未配信、または内容更新後に未反映のTriage outbox行数 | 通常は`0`です。正数なら次回配信待ちか、Kanban配信失敗を切り分けます。 |
| `telemetry_failures` | DBに記録された判定telemetry failure episodeの総数 | 現行statusは履歴を含む件数です。正数だけで現在障害とは断定せず、カード、`last_seen_at`、後続reconcileを確認します。 |
| `active_health_failures` | 現在activeなmonitor運用障害数 | 通常は`0`です。正数なら`ok`は`false`になり、service journalとoutboxを確認します。 |
| `unacknowledged_owner_alerts` | owner alert経路で未ACKの件数 | 正数なら、Kanban以外の警報経路も未解消です。 |
| `monitors` | 登録済み二値判断processの定義 | 少なくとも事前評価の追加保証判定と最終scope監査が登録されていることを確認します。 |

`ok=true`でも、`pending_outbox`が正数、timerが停止、または古いpluginを長時間processが保持している場合があります。日常確認では、版、doctor、hook、timer、monitor-statusを一組として読みます。

## 2. Terra事前評価と最終監査が実際に動いたか確認する

現行CLIにはgate stateを表示する専用subcommandがありません。`doctor`が返した`state_path`のSQLite DBを読み取り専用で確認します。raw promptやtool出力を取り出さず、必要な状態欄だけを表示します。

```bash
STATE_DB="$("$GATE" doctor | python3 -c 'import json,sys; print(json.load(sys.stdin)["state_path"])')"
TASK_ID="<確認するKanban task id>"

python3 - "$STATE_DB" "$TASK_ID" <<'PY'
import json
import sqlite3
import sys

state_db, task_id = sys.argv[1:]
connection = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
connection.row_factory = sqlite3.Row
row = connection.execute(
    """
    SELECT turn_id, task_id, state, review_json,
           additional_assurance_required, audit_json,
           completion_status, completion_summary
    FROM scope_v2_turns
    WHERE task_id = ?
    ORDER BY updated_at DESC, rowid DESC
    LIMIT 1
    """,
    (task_id,),
).fetchone()
if row is None:
    raise SystemExit(f"scope v2 turn not found for task {task_id}")

review = json.loads(row["review_json"]) if row["review_json"] else {}
audit = json.loads(row["audit_json"]) if row["audit_json"] else {}
independent = audit.get("independent") or {}
effects = [
    dict(item)
    for item in connection.execute(
        """
        SELECT kind, target, result
        FROM scope_v2_effects
        WHERE turn_id = ?
        ORDER BY created_at, tool_call_id, kind, target
        """,
        (row["turn_id"],),
    )
]
print(json.dumps({
    "turn_id": row["turn_id"],
    "state": row["state"],
    "completion_status": row["completion_status"],
    "scope_verdict": review.get("scope_verdict"),
    "review_id": review.get("review_id"),
    "reviewer_model": review.get("reviewer_model"),
    "reviewer_process": review.get("reviewer_process"),
    "additional_assurance_required": bool(row["additional_assurance_required"]),
    "final_scope_conformant": audit.get("final_scope_conformant"),
    "audit_reviewer_model": independent.get("reviewer_model"),
    "audit_verdict": independent.get("audit_verdict"),
    "audit_scope_conformant": independent.get("scope_conformant"),
    "observed_effects": audit.get("observed_effects", effects),
}, ensure_ascii=False, indent=2))
PY
```

Kanban外のturnを確認する場合は、task IDではなく、`scope_gate`の戻り値で得た正確な`turn_id`を使って同じ表を検索します。

### 2.1 turnの状態を読む

| `state` | 意味 | 運用判断 |
|---|---|---|
| `inference-pending` | ScopeFrame/計画の事前評価前 | 変異を始めません。 |
| `reviewed` | Terraの事前評価はpassしたがlock前 | `reviewer_model`等を確認し、lockが成功するまで変異を始めません。 |
| `review-blocked` | Terraが`revise`/`block`を返したか、呼出失敗でfail closed | 現在指示からframe/計画を直して再評価します。迂回してlockしません。 |
| `locked` | 事前評価とlockが通り、評価済みcontainment内の作業中 | 完了状態ではありません。 |
| `completed` | 最終scope監査がpassした | `final_scope_conformant`と実作用も照合してから完了扱いにします。 |
| `audit-blocked` | 最終scope監査がpassしなかった | 完了報告、Kanban終端遷移、追加作用を行いません。現在指示へ戻って再評価します。 |

### 2.2 Terra事前評価の実行事実

次がそろって初めて、事前評価が実際に完了したと判断します。

1. `reviewer_model`が空でなく、現在承認されているTerra modelを示す。v2導入時は`gpt-5.6-terra`です。
2. `reviewer_process`が`fresh-safe-mode-session`。
3. `review_id`があり、`scope_verdict`が記録されている。
4. 作業を開始したturnなら、`scope_verdict=pass`を経て`state`が`locked`以降になっている。

`state=review-blocked`だけでは、Terraが意味上の修正を求めたのか、process不達だったのかを区別できません。直前の`scope_gate(action=review)`戻り値を確認します。再評価失敗時には古い`review_json`が残り得るため、古い`reviewer_model`だけを新しい評価の証明にしません。

### 2.3 最終監査と実作用

作用を伴うturnでは次を確認します。

1. `observed_effects`に、実際に起きた作用の種類、対象、結果が入っている。計画したtool名の一覧ではありません。
2. `state=completed`かつ`final_scope_conformant=true`である。
3. `completion_status`が実際の成果（`success`、`partial`、`blocked`等）と一致する。scope内の作用だったことと、要求を完遂したことは別に判断します。
4. `additional_assurance_required=true`なら、`audit_reviewer_model`がTerra modelを示し、`audit_verdict=pass`かつ`audit_scope_conformant=true`である。

`additional_assurance_required=false`なら、独立Terra最終監査がないこと自体は正常です。この場合もexecutorの作用監査と機械的containment照合は必要です。作用のないread-only turnでは`observed_effects=[]`が正常ですが、作用があったturnで空なら完了の証拠にしません。

## 3. 形骸化監視のTriageカードを読む・閉じる

対象はdefault board、tenant `pda-improvement`の未割当Triageです。

```bash
hermes kanban list --status triage --tenant pda-improvement
hermes kanban show <card_id>
```

監視カードは元の判定を変更せず、自動修復・自動割当もしません。カードが存在すること自体を、monitorまたは判定工程が正常である証明にしません。

### 3.1 「判定プロセス失敗疑い」

タイトルは`判定プロセス失敗疑い: <判断工程名>`です。直近72時間の有効なboolean判定が10件以上あり、一方が95%以上になったepisodeを表します。「優勢側が誤り」という意味ではなく、判断工程が実質的に固定値化していないかを調べる入口です。

カードと最新コメントで次を読みます。

1. どの判断工程か。
2. 集計窓、`true`/`false`件数、`N`、`dominance`。
3. 同時にtelemetry failureがあるか。
4. 同一episodeの更新か、回復後に始まった新episodeか。

現在の回復状態はcardだけで推測せず、gate DBの`pm_state`を確認します。

```bash
python3 - "$STATE_DB" <<'PY'
import datetime
import sqlite3
import sys

connection = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
connection.row_factory = sqlite3.Row

def local_time(value):
    if value is None:
        return None
    return datetime.datetime.fromtimestamp(value).astimezone().isoformat()

for row in connection.execute(
    """
    SELECT monitor_id, last_trigger, episode_id,
           recovered_at, last_evaluated_at
    FROM pm_state
    ORDER BY monitor_id
    """
):
    item = dict(row)
    item["recovered_at"] = local_time(item["recovered_at"])
    item["last_evaluated_at"] = local_time(item["last_evaluated_at"])
    print(item)
PY
```

`last_trigger=0`と`recovered_at`は偏向episodeが閾値未満へ戻った証拠ですが、原因調査カードは自動完了しません。次をすべて満たしたときだけ人が閉じます。

- 対象episodeが回復済みで、後続の定期評価も成功している。
- 固定値化、入力母集団の偏り、または正当な業務上の偏りのどれかを根拠付きで判断した。
- 必要な修正を別の承認済み変更として完了したか、変更不要の判断と再発時の扱いをカードへ記録した。

比率が一度95%未満になっただけ、またはカードが起票できただけでは閉じません。

### 3.2 「判定テレメトリ失敗」

タイトルは`判定テレメトリ失敗: <failure_type>`です。期待した判定が無い、遅い、形式不正、重複・競合している、母集団または評価を取得できない、といった「判定内容とは別の観測経路の失敗」を表します。同じmonitorとfailure typeは1枚へ集約され、個々のsubject episodeはDBに残ります。

カードでは`monitor_id`、`failure_type`、最新コメントの更新時点を読みます。個々のepisodeが必要な場合は読み取り専用で確認します。

```bash
python3 - "$STATE_DB" <<'PY'
import datetime
import sqlite3
import sys

connection = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
connection.row_factory = sqlite3.Row
for row in connection.execute(
    """
    SELECT monitor_id, failure_type, subject_key, active,
           first_seen_at, last_seen_at
    FROM pm_failures
    ORDER BY last_seen_at DESC
    LIMIT 50
    """
):
    item = dict(row)
    for field in ("first_seen_at", "last_seen_at"):
        item[field] = datetime.datetime.fromtimestamp(
            item[field]
        ).astimezone().isoformat()
    print(item)
PY
```

`monitor-status.telemetry_failures`は履歴を含むため、ゼロへ戻ることを閉鎖条件にしません。次をすべて満たしたときだけ人が閉じます。

- failure typeに対応する入力、期限、重複、母集団取得、評価処理の原因を特定した。
- 修正後または一過性障害解消後の定期reconcileが成功し、同じ原因の新しいepisodeが増えていない。
- 関連するoutbox更新が配信済みで、必要な調査・修正・受容判断をカードへ記録した。

有効な偏向集計とtelemetry failureは同時に存在できます。片方の回復をもう片方の解消とみなしません。

閉鎖条件を満たした後は、Dashboardで根拠を記録してDoneへ移すか、権限のあるoperatorが次を実行します。

```bash
hermes kanban complete <card_id> --summary "原因、回復確認、修正または受容判断を記録"
```

## 4. 障害時の切り分け

最初に、作用を増やさず次を採取します。

```bash
"$GATE" doctor
"$GATE" monitor-status
systemctl --user status pda-process-monitor.timer pda-process-monitor.service --no-pager
systemctl --user list-timers pda-process-monitor.timer --all --no-pager
journalctl --user -u pda-process-monitor.service -n 100 --no-pager
```

### 4.1 Terraへ到達できない

典型的な見え方は、`scope_gate(action=review)`が`ok=false`となり、turnが`review-blocked`のまま、今回の評価に対応する`reviewer_model`または`review_id`が得られない状態です。戻り値には、Hermes executable不在、timeout、不正JSONなどのfail-closed理由が出ます。

```bash
command -v hermes
hermes doctor
```

- 変異を始めず、review結果を手書きでDBへ入れたり、過去の`review_json`を流用したりしません。
- Hermes executable、provider/auth、Terra fresh-session経路のうち、戻り値が示す箇所を復旧します。
- 復旧後は、現在の認証済み指示から同じScopeFrame/計画を`review`へ再提出します。gate外でTerraを呼んだ結果は正式なreview eventの代用になりません。

### 4.2 追加監査が必要だが監査経路がない

事前評価は`scope_verdict=pass`で`additional_assurance_required=true`ですが、`scope_gate(action=lock)`が`independent audit is required but no audit path is available; blocked before effects`で止まります。turnは`reviewed`のままで、`observed_effects`は空であるべきです。

- これはscope外判定ではなく、必要な保証経路が無いexecution blockerです。
- lockを迂回せず、Terra reviewer/auditor adapterを利用可能にします。
- 復旧後に同じturnの`lock`を再実行し、`state=locked`を確認してから作業します。
- この状態なのに作用が記録されている場合は通常復旧を続けず、統制逸脱として別途エスカレーションします。

### 4.3 monitor timerまたはserviceが失敗している

`monitor-status`はDBの現在値を読めても、timerが定期実行されたことまでは保証しません。正常時はtimerが`active (waiting)`で、`list-timers`に直近実行と次回実行が見え、直近のoneshot serviceが成功しています。timerはboot後およそ2分、以後およそ1時間ごと（最大30秒のrandom delay、persistent）にserviceを起動します。

- timerがinactive、次回時刻が無い、serviceがfailed、またはjournalのreconcileが古い場合はmonitor経路の障害として扱います。
- journalの最初の非zero終了を読み、DB整合性、unit読込、実行interpreter、Kanban配信のどこで止まったかを分けます。
- unitをその場で手編集しません。承認された復旧ではREADMEの「Install and activate」に従い、正本installerから再配置します。

```bash
~/.hermes/hermes-agent/venv/bin/python integrations/hermes-scope-gate/install.py
systemctl --user daemon-reload
systemctl --user enable --now pda-process-monitor.timer
```

復旧後はtimer/service、journal、`doctor`、`monitor-status`を再確認します。installer実行とsystemd操作は変更作用なので、読み取り切り分けとは分けて承認を得ます。

### 4.4 Kanbanへの起票または更新が失敗している

典型的な組合せは次です。

- `pending_outbox`が正数のまま。
- `active_health_failures`が正数で`ok=false`。
- `unacknowledged_owner_alerts`が正数。
- service journalに`pda.process-monitor.health/v1`と`sink-delivery-failed`がある。
- 対応するTriage cardが無い、または最新payloadのcommentが反映されていない。

`pending_outbox>0`だけなら、`--no-delivery`評価後や次回timer前の待機でも起こります。healthとjournalを合わせて判断します。journalが`outbox-persist-failed`ならKanban sinkではなくcontrol storeへの永続化失敗なので、DB正常に見えることを根拠に無視しません。

- outbox行、delivery task ID、health rowを直接削除・書換しません。
- 同じepisodeを人手で新規起票しません。outboxとKanban idempotency keyが再送時の重複を防ぎます。
- Kanban DBまたはAPI経路を復旧した後、通常は次回timerに再送させます。即時再送が承認されている場合だけoneshot serviceを起動します。

```bash
systemctl --user start pda-process-monitor.service
```

再送後に、`pending_outbox=0`、`active_health_failures=0`、`ok=true`、owner alertのACK、および実際のTriage task IDまたは更新commentをread-backします。これらがそろう前に「起票済み」と報告しません。

## 5. rollbackの要約

正本は`integrations/hermes-scope-gate/README.md`の「Rollback」節です。実行前に、戻す承認済みcommit、対象環境、timerを残すか、Hermesをどの面でreloadするかをfinalization contractへ固定します。

v2の通常rollbackは次の順序です。

1. PDA mainで、対象変更を履歴破壊ではなく通常のGit revertとして作る。
2. Hermes venvのPythonでinstallerを再実行し、active plugin symlink、hook、managed unitをrevert後の正本へ合わせる。
3. v2より前へ戻す場合だけ、monitor timerを停止・無効化する。v2内の版戻しでは承認契約にないtimer停止を追加しない。
4. 稼働形態に合わせてHermes processをreloadする。gatewayなら`hermes gateway restart`、CLIなら終了して新しいprocessを起動する。
5. このrunbookの第1節と第2節を再実行し、実際のversion、hook、doctor、timer方針、state schemaをread-backする。

```bash
cd ~/projects/pda
git revert <承認された対象commit>
~/.hermes/hermes-agent/venv/bin/python integrations/hermes-scope-gate/install.py
systemctl --user daemon-reload

# v2より前へ戻す契約に含まれる場合だけ実行
systemctl --user disable --now pda-process-monitor.timer

# gateway稼働の場合。別の稼働面では対応するHermes processをreload
hermes gateway restart
```

v2はv1のSQLite tableを削除・書換しません。rollback時にstate DBのtableを手動削除する必要はなく、legacy runtimeはv2 tableを無視できます。またinstallerは、自分が配置した内容から並行変更された設定を上書きせず、conflictとして停止します。その場合は強制上書きせず、差分と所有者を確認して新しい承認を取ります。

rollback後の確認が失敗した場合は、元の判定や承認を手で補正して正常に見せません。実version、process、hook、timer、stateのどこが目標と違うかを記録し、rollback未完了として扱います。

## 参照正本

- `docs/design/task-scope-admission-gate.md` の「0. 現行決定（v2）」
- `docs/design/process-degeneration-monitor.md`
- `integrations/hermes-scope-gate/README.md`
