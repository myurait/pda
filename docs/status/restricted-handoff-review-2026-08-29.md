# tool budget 超過後の完了合図免除の反証レビュー（2026-08-29）

- Status: review complete / findings recorded（コミット前の反証記録）
- 対象: 未コミット差分（`integrations/hermes-scope-gate/scope_gate.py`、`integrations/hermes-scope-gate/tests/test_artifact_change_scope.py`、`docs/operations/adversarial-suite.md`）
- レンズ: 例外の引数検査の穴（別task・別board・複合形）／1回限りの数え方のリセット経路／deny_ceiling との相互作用／run-signal 以外のツールの滑り込み／turn 境界を跨いだ再取得／`docs/operations/adversarial-suite.md` の既存の閉じた迂回クラスとの矛盾
- 照合した一次資料: 上記実装と `docs/operations/adversarial-suite.md`。実測は当該ワークツリーの `./tmp/venv-scope/bin/python` で当該実装を直接呼び出して取得（`integrations/hermes-scope-gate/tests/test_artifact_change_scope.py` の `_seeded_store` / `_admit` を利用）

## 件数

- major 2 件 / minor 3 件（計 5 件）。既存の閉じた迂回クラスとの矛盾は M2 に該当する。

## major

### M1. 対象欄の綴り列挙は「宛先の一致」を強制していない（複合形が通過する）

- 実装の主張: `artifact_run_signal_targets_bound_task()` の docstring が「A call that names no target, names a target in an unrecognized shape, or carries any target other than the bound task is not covered」と述べ、`ARTIFACT_RUN_SIGNAL_TARGET_FIELDS` のコメントが「whichever listed field is present, its value has to be the bound task id」と述べる。
- 実装が実際に強制していること: 列挙 5 綴り（`task_id`/`task`/`card_id`/`card`/`id`）のうち **1 つ以上が存在して一致すること**、および **列挙内のどれも不一致でないこと**。列挙外のキーは走査対象に入らないため、値が何であっても判定に影響しない。
- 実測（tool budget を上限値に固定した locked ターンで `kanban_complete` を投入。いずれも `allowed=True` / `action=complete-past-budget`）:

```
{"task_id": "task-change", "target":   "task-other"}          -> allow
{"task_id": "task-change", "task_ids": ["task-other"]}        -> allow
{"task_id": "task-change", "to":       "task-other"}          -> allow
{"task_id": "task-change", "payload":  {"card_id":"task-other"}} -> allow
```

- 具体形: 束縛タスク id を列挙内の綴りに置き、実効の宛先を列挙外の綴り（`target` / `task_ids` / `to` / 入れ子コンテナ）に置いた 1 呼出。ゲートは通過し、呼出は元の引数のまま実行される。実効果は稼働 Hermes 側 kanban ツールが列挙外キーをどう扱うか（無視するか、宛先として採用するか）に依存し、本リポジトリにスキーマが無いため確定できない。すなわち「他カードの状態遷移に到達しないこと」は現状 **ゲート側では保証されていない**。
- 既存決定との関係: `docs/operations/adversarial-suite.md` の「引数分類の網羅漏れによる計上先の誤り」の項は、3 巡の独立検証の結論として「開放的な引数空間の双方向分類は列挙では原理的に閉じない」を記録し、同種の失敗形（束ね末尾の値取り形、宣言義務の欠落）を列挙している。本変更の対象欄列挙はその結論と同型の構造を、今度は allow 側の必要条件として導入している。
- 是正方向: 綴りの列挙で宛先を認識するのではなく、引数集合そのものを閉じる（許可キー集合を定め、未列挙キーが 1 つでもあれば例外不適用）。列挙は「認識だけを広げる」と説明されているが、未列挙キーは認識されないまま通過するため、その説明は allow 判定には当てはまらない。

### M2. 現行の run signal は locked ターンで引数無検査であり、adversarial-suite が閉じたと記録する類型に該当している

- 文書の主張: `docs/operations/adversarial-suite.md`「**引数無検査カテゴリへの宛先の持ち込み**（許可カテゴリのツール引数にパス・URL・他カードの宛先を運ぶ）」を、`test_the_work_record_catalogue_is_a_closed_explicit_set` / `test_tools_outside_the_work_record_catalogue_stay_denied`（宛先を運ぶツールをカタログ外へ出すことで固定）で閉じたと記録する。
- 検証事実: その固定は `ARTIFACT_WORK_RECORD_TOOLS` に対するもの（`kanban_link` / `kanban_attach` / `kanban_attach_url` を除外理由付きでカタログ外に置く）。一方 `ARTIFACT_RUN_SIGNAL_TOOLS`（`kanban_complete` / `kanban_request_review`）はカード id を宛先として運ぶが、`_admit_artifact_change_locked` の該当分岐は `GateDecision(True, "signal-run-outcome", ...)` を無条件に返し、引数を一切見ない。
- 実測（tool budget 未消尽の通常状態、locked ターン）:

```
kanban_complete       {"task_id": "task-other"}                 -> allow / signal-run-outcome
kanban_request_review {"card_id": "task-other", "reviewer": "x"} -> allow / signal-run-outcome
```

- 具体形: 予算超過を待たず、locked ターンの通常経路で他カードを宛先にした完了・レビュー要求を 1 回以上（回数上限は tool budget のみ）発信できる。M1 の複合形はこの上位集合の一部でしかない。
- 文書上の帰結: 今回追記された迂回クラスは「他カードを宛先にした呼出」を閉じたと読める記述を持つが、閉じているのは例外レーンのみで、同一ツールの通常レーンは無検査のまま隣に残る。表を読む側は宛先の束縛が一般に成立していると受け取る。追記の際は、束縛が例外レーン限定であること（または通常レーンも同時に束縛したこと）を明示する必要がある。

## minor

### m1. 例外が契約有効性の検査より前に返る

`_admit_artifact_change_locked` の例外は `exceeded` 判定の直後に return するため、後続の `artifact_contract_scope(contract)`（`PathRejected` を投げ得る）と `if not root or not write_patterns: -> contract-invalid` を通らない。すなわち例外は、この関数の allow のうち唯一「契約が write scope を持つこと」の下流に無い。到達性は低い（`_lock_artifact_change` は空 write scope の lock を `ValueError` で拒否し、seed 経路は検証済みレコードから契約を組むため、locked かつ write scope 空の状態は通常成立しない）。順序の脆さとして記録する。

### m2. 予算理由コードをリテラルで比較している

`exceeded.action == "tool-budget"` は、同ファイルが既に持つ `ARTIFACT_BUDGET_DENY_ACTIONS` の要素を裸のリテラルで再掲している。綴りが変われば例外は無効化される（fail-closed 方向なので安全側）が、`docs/operations/adversarial-suite.md`「理由コードの綴り共有による計上写像の不健全化」の項が扱う結合のしかたと同じ形であり、定数参照へ寄せるのが一貫する。

### m3. 1回限りの計数が action 綴り単位のため、permit レーンは数に入らない

`_run_signal_exception_spent()` は `verdict='allow' AND action='complete-past-budget'` の行のみを見る。`artifact-change` の `EXPANSION_REVIEW_BUDGET` は 2 で、permit を消費した allow は `expansion-permit` で記録されるため、予算超過後に発信し得る run signal は最大 3 回（permit 2 + 例外 1）になる。permit は独立審査必須・審査者不在時 fail-closed なので迂回ではないが、「予算超過後の run signal は 1 回」を監査で数えるには当該 action 1 種では足りない。

## 反証して閉じていることを確認した経路

いずれも当該実装を直接呼び出して確認した。

- **1回限りの数え方のリセット**: 同一ターンで `tool_count` / `denied_count` を減算・ゼロ化する経路は実装に存在しない（更新は加算のみ）。`purge_expired()` は `decisions` を削除するが対象は `started_at` が 30 日より古いターンで、同時に `turns` 行も削除するため、当該ターンは wall budget 超過かつ `admit_without_turn` の fail-closed 側へ落ちる。再 lock（`_lock_artifact_change` の locked 分岐）は契約を冪等に返すだけでカウンタを触らない。
- **綴り違いでの二度取り**: 消費後に `{"card": <束縛id>}`（別の列挙内綴り）および引数を変えた同一ツール呼出を投入 → いずれも `tool-budget` で拒否。
- **deny_ceiling との相互作用**: deny 上限のみ消尽 → `deny-budget` 拒否。deny 上限と tool 予算の両方を消尽 → `tool-budget` が先行するが `denied_count < max_denied_calls` が偽のため例外不適用で拒否。座礁は維持される。
- **wall budget との順序**: wall と tool の両方を消尽 → `wall-budget` 拒否（例外に到達しない）。
- **run-signal 以外の滑り込み**: 予算超過後の `write_file` / `terminal`（`git add`）/ `read_file` / `kanban_comment` はいずれも `tool-budget` 拒否。例外消費後の `kanban_comment` も拒否。
- **G3 経路からの消費**: 予算超過後に `request_expansion()` を `judge=None` で投入 → `deny` / `fail-closed`。stage 2 の「既に許可済み」判定は `run_signal_exception_unspent` を既定 False の位置引数で呼ぶため例外を答えず、決定行も書かれない。
- **turn 境界を跨いだ再取得**: seed 付きタスクの次ターンは `state='locked'` / `tool_count=0` で開始するため例外も新品になる。これはターン単位予算の設計どおりで、ターン行は host 側の user message 単位で作られ、`scope_gate` ツールの action は `lock` / `review` / `complete` に限られるため、agent 側からターンを増やす経路は無い。

## 実行事実

`./tmp/venv-scope/bin/python -m pytest integrations/hermes-scope-gate/tests -q --ignore=integrations/hermes-scope-gate/tests/test_hermes_integration.py` → 685 passed（実装報告の件数と一致）。追加テスト 5 本は `_admit` が呼出ごとに一意の tool_call_id を発行するため冪等キャッシュに吸われておらず、`test_the_second_run_signal_past_the_budget_is_denied` の別ツール名ケースは `_run_signal_exception_spent()` に実際に到達している。負例のパラメータ列には M1 の複合形（列挙外の綴りに宛先を置き、列挙内の綴りに束縛 id を置く形）が含まれていない。

## 処置記録（2026-08-29）

- **M1（修正）**: 免除の適用条件を対象欄の綴り列挙から引数キーの閉じた集合へ変えた。対象欄（`ARTIFACT_RUN_SIGNAL_TARGET_FIELDS`。存在する欄はすべて束縛タスク id と一致必須）と報告欄（`ARTIFACT_RUN_SIGNAL_REPORT_FIELDS`）のどちらにも属さないキーが 1 つでもあれば免除は不適用となり、tool budget が変更前と同じく拒否する。指摘のとおり列挙で宛先を認識する形は閉じないため、閉じるのは引数集合そのものにした。報告欄の入れ子に現れた対象欄にも同じ一致を要求する（承認 metadata が対象タスク id を持つため）。負例に実測された複合形 4 種（`target` / `task_ids` / `to` / 入れ子 `payload`）、`board`、宛先を運ばない未列挙キー、報告欄の入れ子に置いた他カード id を追加。宛先を運ぶ既知の欄（`board` / `created_cards` / `artifacts`）は理由付きで報告欄から除外した。免除が狭すぎる方向の失敗は変更前の座礁（自動再試行で回収）に留まる。
- **M2（文書是正）**: 通常レーンが引数無検査であることは事実で、免除レーンはその部分集合にすぎない。ただし通常レーンへ同じ対象一致検査を広げると、host anchor の無いターン（`resolve_task_binding` の実測どおりターンの task_id がカード id ではなく session id になる形）で正規の完了合図まで拒否されるため、実装上の束縛は免除レーンに限った。`docs/operations/adversarial-suite.md` は 3 点を是正: 「引数無検査カテゴリへの宛先の持ち込み」へ run 終端シグナルの残余を明記、今回の追記へ束縛が免除レーン限定であることと閉じた引数集合を明記、未カバー節へ通常レーンの宛先束縛を追加。
- **m1（修正）**: 免除の判定に契約の write scope 検証（`_artifact_locked_write_scope_is_declared`）を加え、write scope を持たない契約では免除が成立しないようにした。設計 §8 が案 (a) の必須条件に挙げる run 終端シグナルの契約検証に対応する。`test_the_run_signal_exception_needs_a_contract_with_a_write_scope` で固定。
- **m2（修正）**: `ARTIFACT_TOOL_BUDGET_ACTION` を導入し、予算判定・`ARTIFACT_BUDGET_DENY_ACTIONS`・免除条件が同一定数を参照するようにした。
- **m3（棄却・注記追加）**: expansion permit 経由の run signal は独立審査を必須とし審査者不在で fail-closed の別権限で、`expansion-permit` として別 action に記録される。1 回限りは免除そのものの回数であって予算超過後の run signal 総数ではないため、計数の実装は変更しない。監査で総数を数えるには両 action の合算が必要である点を `_run_signal_exception_spent` の docstring に明記した。
- 報告欄の一覧（`summary` / `result` / `metadata` / `reviewer`）は本開発PCからは稼働ツールの引数スキーマと突き合わせられない。列挙が実キー名を取り落としている場合の帰結は免除不適用（= 変更前と同じ tool budget 拒否）であり、許可側は広がらない。実キー名は拒否された合図の audit 記録に残るため、追加はその記録に基づく明示的な編集で行う。
- テスト: `./tmp/venv-scope/bin/python -m pytest integrations/hermes-scope-gate/tests -q --ignore=integrations/hermes-scope-gate/tests/test_hermes_integration.py` → 706 passed（処置前 685）。

## 処置記録（2026-08-29）

- Status: 処置完了（M1・m1・m2 は実装修正、M2 は文書是正、m3 は棄却）
- テスト: `./tmp/venv-scope/bin/python -m pytest integrations/hermes-scope-gate/tests -q --ignore=integrations/hermes-scope-gate/tests/test_hermes_integration.py` → 706 passed（追記前 685）。`test_hermes_integration.py` は稼働 Hermes ランタイムを import するため開発 PC では成立せず、レビューと同じく除外している。

### M1（修正）

免除の適用条件を、対象欄の綴り一致から引数キーの閉じた集合へ変更した。`ARTIFACT_RUN_SIGNAL_TARGET_FIELDS`（5 綴り。存在する欄の値は束縛タスク id と一致必須）と `ARTIFACT_RUN_SIGNAL_REPORT_FIELDS`（`summary` / `result` / `metadata` / `reviewer`）のいずれにも属さないキーが 1 つでもあれば免除不適用となり、tool budget が拒否する（免除導入前と同じ挙動）。報告欄の入れ子に現れた対象欄の綴りにも同じ一致を要求する（`_run_signal_report_names_another_task`。走査ノード数に上限を置き、未完走のときは免除を与えない）。

宛先の束縛は対象欄の一致ではなく集合の閉じ方が担う。報告欄の綴りは稼働 kanban ツール（`kanban_complete` / `kanban_request_review`）の引数スキーマから取り、`board`（束縛 id を別盤面で解決させる）・`created_cards`（完了に付随するカード新規作成）・`artifacts`（パス・URL を運ぶ）は宛先を運ぶため理由付きで除外した。集合を広げるときはスキーマに基づく明示的な編集とし、狭すぎる側の失敗は免除不適用（座礁は再試行で回収）へ倒れる。

負例に、指摘された 4 形（`target` / `task_ids` / `to` / 入れ子 `payload`）と、`board` を伴う形・宛先を運ばない未列挙キーを伴う形・報告欄の入れ子に他カード id を置いた形を追加した。正例は実際に送られる報告（`summary` / `result` / `reviewer` / 承認 metadata）で固定した。

### M2（文書是正。コード変更なし）

指摘のとおり、予算内の通常レーン（`signal-run-outcome`）は引数を読まない。これを `docs/operations/adversarial-suite.md` の「引数無検査カテゴリへの宛先の持ち込み」項に残余として明記し、宛先の束縛が効くのは予算超過後の免除レーンのみであることを追記した。同項の未カバー一覧にも通常レーンの宛先束縛を追加した。

通常レーンへ同じ対象一致検査を広げる処置は採らない。ターンの束縛 id は host anchor（盤面のカード id）だが、anchor が無い経路ではターンの task_id が session id になるため（`host_task_binding` / `resolve_task_binding`）、正規の完了合図が全て拒否される false deny が生じる。これは免除レーンでの不適用（座礁のまま＝従来挙動）と違い、動作しているレーンを壊す変更になる。束縛の形は設計 §8 の handoff 契約と併せて決める。

### m1（修正）

免除を契約の write scope 検証に従属させた（`_artifact_locked_write_scope_is_declared`）。設計 §8 が案 (a) の必須条件に挙げる「run 終端シグナルの契約検証」に対応する。契約を空にしたターンで免除が下りないことをテストで固定した。

### m2（修正）

`ARTIFACT_TOOL_BUDGET_ACTION` を新設し、予算判定の理由コード発行・`ARTIFACT_BUDGET_DENY_ACTIONS`・免除の適用条件が同一定数を参照するようにした。

### m3（棄却。注記のみ追加）

permit を消費した allow は `expansion-permit` として記録され、独立審査（審査者不在時は fail-closed）を経た別権限であり、expansion review budget で別に上限が付く。免除の「1 回限り」は免除自身についての性質であり、permit レーンを同じ計数に入れると 2 つの権限が区別できなくなるため、計数の変更は行わない。監査が「予算超過後に発信された run signal の総数」を数えるときは両 action を合算する必要があるため、その旨を `_run_signal_exception_spent` の docstring に明記した。
