# PDA改善タスクの自動捕捉と日次振り返り

## 目的

PDA改善の依頼を会話に埋没させず、Hermes Kanbanを唯一の正本として捕捉し、隔離worktreeで実装・検証し、最終反映だけをオーナー承認へ送る。オーナーは「Kanbanへ追加」や「このカードへ着手」と毎回明記する必要がない。

カード登録だけではmain統合、push、デプロイ、再起動、外部送信の許可にはならない。一方、停止条件のない具体的なReadyカードは、専用workerが隔離branch内で実装・テスト・local commitまで自動実行する。承認リストでdigest-boundな最終承認が記録されて初めて、表示済みの反映手順だけを実行できる。

## 正本と既定値

- 正本: `~/.hermes/kanban.db` のdefault board
- 対象tenant: `pda-improvement`
- 新規カード: 未割当 `triage`
- 重複防止: 意図を正規化した安定idempotency key
- 出典: 要求が生じたHermes session
- 自動分解: 無効のまま維持する

## 即時捕捉

通常会話では、次のいずれかを満たすPDA固有の依頼を同じターンで登録または既存カードへ統合する。

- 改善、機能追加、不具合、再発防止
- 運用・構成・安全境界の変更
- 後続作業を伴う調査や判断待ち
- 中断、延期、依存関係により次ターン以降へ残る作業

作成前にopen cardを検索し、同じowner outcomeが存在すれば新規作成せず、そのカードへ新しい要求・証拠・判断だけを追記する。新規カードには目的、現状、完了条件、次の一手、停止・判断ゲート、出典を含める。

次は自動登録しない。

- 挨拶、純粋なQ&A、状況報告・停止要求そのもの
- 合成probe、タイトル生成、テスト用会話
- 後続成果が残らない日常的な一回操作
- 既存カードと同一の依頼
- オーナーが「一時」「保存不要」「登録不要」と指定したもの

## 日次サイクル

実機のローカル時刻 `Asia/Tokyo` を基準に、毎日06:00 JSTに実行する。05:00 JSTの継続バックアップとは重ねない。

1. 直近のowner request-bearing sessionと`pda-improvement`のopen cardを読む。
2. 即時捕捉から漏れた持続的な依頼を、未割当`triage`として追加する。
3. 重複候補は削除せず、正本候補と差分をコメントに残す。
4. 最大3件の`triage`をHermes specifierで具体化し、目的、受入条件、非目標、検証方法、最終反映対象が十分で停止・価値判断ゲートがなければ`ready`へ進める。
5. `running`の停滞、繰り返し失敗、`review`の承認待ち、branch衝突を抽出する。明示的な停止中カードは再開しない。
6. その日の変更、実行中、承認待ち、未解決リスク、次候補を監査カードへJST日付付きで1コメントだけ残す。

同一日の再実行は既存の日次コメントを読み、カードとコメントを重複させない。

## 二段階実行契約

### Phase 1: 承認前に自動実行する

- 依頼捕捉、重複抑止、Triage具体化、依存・停止ゲート整合、Ready化、日次監査。
- 30分周期の決定論的routerが、WIP上限2件で優先度順に1件ずつ選ぶ。空queueの確認にmodel turnを使わない。
- task ID固有の`pda-auto/<task_id>` branchと専用worktreeを作り、`default` profileのfresh Kanban workerへ割り当てる。
- workerはforced skill `pda-autonomous-improvement`に従い、当該worktree内の実装、focused test、local commit、承認handoffを行う。
- `pda_approval`にはbase/head SHA、exact non-symlink linked-worktree path、canonical Git common-dir/worktree git-dir identity、`pda-auto/<task_id>` branch、変更ファイル、実際に通った検証、影響、残存リスク、反映対象・手順・rollbackを含める。検証失敗やdirty worktreeは承認可能にしない。

### Phase 2: 最終承認後だけ実行する

- Dashboardの「承認」タブはKanban `review`カードから一覧を導出し、別タスクDBを持たない。
- APIは現在のbasic-auth owner sessionだけに承認・差戻しを許し、最新review handoffのcanonical SHA-256 digest、task ID、full approval contract、exact non-symlink linked-worktree path、canonical Git common/worktree identity、`pda-auto/<task_id>` branch、base/diff、cleanな実Git HEADをtransaction内でも再照合する。不一致ならfail closedでカードを動かさない。
- 承認時は同じKanban DB内のplugin専用ledgerへowner identity、task/run/digest、base/head、worktree/Git identityをatomicに記録し、author `pda-owner-approval`のコメントはworkerへの通知だけに使って同じカードをReadyへ戻す。installerは汎用commentを承認証拠として受理しない。activationは事前生成nonceでledger rowを排他claimし、共有変更前後にfull contractを再検査して成功時だけ一度消費する。rollbackまたはclaim解放の競合時はtimerを再停止してclaimを保持し、15分経過後の明示recoveryだけを許す。
- 差戻しはauthor `pda-owner-changes`で記録し、新しいcommitとdigestによる再承認を要求する。

### 承認があっても暗黙には拡大しない

- 承認payloadにない認証・秘密・課金・外部送信、データ削除、履歴破壊、不可逆操作。
- 他の進行中worktreeの変更、reset、stash、無関係なmerge・repair・audit。
- 明示的に停止中のカードの再開。
- 承認後に必要と判明した追加変更。これは新しいhead/digestで再承認する。

## WIPと失敗時の扱い

- 自動具体化は1日3件まで、実装WIPは2件、1回のrouter tickで新規割当は1件までとする。
- 同一操作を2回失敗したら戦略を変え、反復しない。
- 日次処理が完遂できない場合も、確認できた事実と障害だけを監査カードへ残す。
- 日次処理の失敗は既存カードを完了・削除する根拠にしない。routerの衝突・profile欠落は未割当のままfail closedにする。

## 検証条件

- 通常会話の継続ルールに即時捕捉基準が存在する。
- 日次Cronがenabledで、次回実行時刻が06:00 JSTとして計算される。
- 手動試験で、同じ日付の再実行がカードまたは日次コメントを重複生成しない。
- 新規捕捉カードは未割当triageで、具体化されReadyになるまでworkerが起動しない。
- 毎日の結果がKanban監査カードから追跡できる。
- 承認前workerが他worktree、main、runtimeへ書かないことを回帰試験で証明する。
- digestまたはGit HEADが変わった承認要求が拒否され、正しい承認だけが専用workerへ再割当される。
- stage導入ではruntime configが`enabled=false`で、承認後activationだけが`enabled=true`にする。
