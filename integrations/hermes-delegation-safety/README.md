# Hermes delegation safety recovery series

このディレクトリは、委任上限だけで親agentが停止する問題、structured-output retryのchild context欠落、子の端末識別情報が共有shell snapshotから親へ漏れる問題の修復資産です。

適用基点はHermes commit `5112f51749ac744923a702900730149dfc8634da`です。現在のlive Hermes checkoutは未変更です。2026-09-06の追加調査で、従来の0001だけでは通常端末の漏洩を直せないことを実再現しました。旧0001と`manifest.json`は保存し、現在の結合seriesの正本を`recovery-manifest.json`とします。古い承認を新しいseriesへ流用してはいけません。

## 影響

結合seriesが変更する実行時sourceは次の3ファイルだけです。

- `agent/tool_guardrails.py` (0001): 上限を越えるspawn要求だけを実行前の`reject`として返し、親loopをhaltさせません。cap値、control action、web-search cap、repeated-failure hard stopは変更しません。
- `tools/delegate_tool.py` (0001): 初回child turnとschema retry turnを同じcontext helper経由にし、各経路で親contextを復元します。
- `tools/environments/base.py` (0002): `HERMES_DELEGATED_CHILD_CONTEXT`をsnapshotへ書き出す専用subshellだけで除外します。実行中の子の環境印・Kanban guardは維持し、後続の親が古い子の識別情報をsourceしないようにします。環境印の手動解除、DB直接更新、guard無効化はしません。

scope制御v2、自律改善timer、profile設定、既存の並行worktree、資格情報は変更対象外です。

## 検証

PDA task worktreeから、実際の親プロセスで実行します。

```bash
python -B -m pytest -q integrations/hermes-delegation-safety/tests
python -B integrations/hermes-delegation-safety/verify_recovery_series.py --source /home/user/.hermes/hermes-agent --upstream-tests
python -m compileall -q integrations/hermes-delegation-safety
```

新しいprobeは旧版でparent-beforeのKanban作成成功、childの拒否、parent-afterの誤拒否を実測してREDにします。修正後は成功、終了code非0、context例外、child-first、親子の並行実行という5条件を実際のLocalEnvironmentで検証します。子の通常/独立プロセス両方のKanban拒否、親の作成成功、通常のshell変数保存も確認します。HOME・Kanban DBは使い捨て領域に固定され、本番盤面を試験に使用しません。genuine childから親probeを起動すると明示的に拒否されます。その拒否を環境解除で回避してはいけません。

結合検証は使い捨てcloneに0001→0002を順に適用します。3つの既存cap/retryシナリオ、新5シナリオ、既存Hermesの関連5ファイルをcanonical runner・2並列で実行し、最終Git treeをmanifestへ照合します。逆順rollbackで基点treeへ完全に戻ることも確認します。2026-09-06の初回検証はartifact suite 14 passed、Hermes既存回帰35 passedです。実行時sourceの新規書込は使い捨てcloneだけです。

## 適用

task・head・changed-files・対象・ordered stepsが一致する新しいdigest-boundなオーナー承認後だけ適用します。

1. 正規`operations/improvement/install.py --check-approval`が`ok=true, mode=checked`を返すことを確認する。古い承認ID、blocked状態のままの承認、HEAD変更後の承認を再使用しない。
2. PDA mainがcleanで他スレッドの変更を含まないことを確認し、承認済みtask headだけをPDA mainへ統合する。pushはしない。
3. live HermesのHEAD、clean状態、3対象ファイルhashが`recovery-manifest.json`の基点と一致することを確認する。不一致なら追加修正やresetをせず停止する。
4. 0001→0002を`git apply --check --index` / `git apply --index`で順に適用する。`git write-tree`がmanifestのexpected_treeと一致し、staged対象が3ファイルだけであることを確認し、当該3ファイルだけをローカルcommitする。remote pushはしない。
5. 承認済みsourceへの新probeを隔離HOMEで実行する。実サービスの再起動直前に現在の会話へ短い中断予告を返す。
6. `hermes-gateway.service`だけを再起動し、bounded health確認後、実会話で親→Luna委任→親の通常端末とKanban読み取りを検証する。終了時はカードへ実測結果を記録する。再起動・E2E不成功時はrollbackへ進み、同じ切替を繰り返さない。

既に汚染されたsnapshotをhot patchや環境印の削除で直す設計ではありません。修正sourceのロードと新しいterminal環境の構築が必要なため、gateway再起動が最終反映に含まれます。保存された会話は同じチャットから継続する方針ですが、実行中runの中断・利用者による次の一言が必要になる可能性は残ります。

## rollback

本番反映前に記録したHermesの基点HEADを正本とします。反映直後のHEAD・clean状態・対象hashが想定どおりの時だけ0002→0001を`git apply --reverse --check --index` / `git apply --reverse --index`で戻し、基点treeとの一致を確認してrollback commitし、gatewayだけを再起動します。driftや予期しない変更があれば自動reset・stash・破棄をせず停止します。PDA側の管理artifactは監査用に保持します。

## 現セッションの暫定経路と限界

正当な親の`terminal(background=true)`は共有snapshotを経由せず、Kanban操作を継続できます。genuine childは同経路でも拒否されることを別途検証済みです。通常foreground端末の恒久修復ではありません。`notify_unsupported`が返るAPI runでは`process`で結果を取得します。Kanban専用tool schemaが会話開始時点で非公開の場合も、正常なCLI経路と区別して報告します。

修復assetはlocal task branchに保存します。本番反映、remote custody、upstream統合はいずれも今回の実装完了とは別です。
