# PDA作業worktreeのライフサイクル方針

- Status: active（goal M0(e) の成果。2026-08-22）
- 目的: 改善サイクルと各セッションが作るGit worktreeの生成・保持・削除条件を定め、Kanban正本と物理状態の乖離（worktree残骸・野良worktree）を無くす。
- 関連: `docs/roadmap/autonomous-improvement-goal.md` / `docs/operations/pda-improvement-cycle.md`

## 分類

- **cycle worktree**: 改善サイクルがカード実装用に作るもの。場所は `~/projects/pda-autonomous-tasks/<task_id>`、branchは `pda-auto/<task_id>` に固定する。
- **session worktree**: セッションが場当たりに作るもの（例: `~/projects/pda-<topic>`）。**新規作成は原則禁止**とする。改善・修正作業はカードを起票し、cycle worktreeの規約（task_id束縛のパスとbranch）で行う。カード外の一時検証はコミットを残さない読み取り用途に限る。

## cycle worktreeのライフサイクル

1. **生成**: ready カードへの割当時に、ルーター／オーケストレーターだけが生成する。既存パスとの不一致は fail-closed（現行実装どおり）。
2. **保持**: カードが非terminal（ready / running / review / blocked）である間は、内容の如何にかかわらず保持する。差戻し後の再実装は同じworktreeを再利用する。
3. **削除**: 次のいずれかを満たしたときに削除する（branchも併せて削除）。
   - カードがdoneで、branch headがmainのancestor（統合済み）かつworktreeがclean。
   - カードがarchive/削除され、branch成果の破棄がカード上で明示されている。
4. **削除しない（審査リスト行き）**: カードがterminalなのにbranchが未統合、またはworktreeがdirtyの場合。自動削除せず、オーナー審査リストとしてカードへコメントする。
5. **監査**: 削除・審査リスト送りは、対象カードへ実行者・日時・判定根拠をコメントとして残す。
6. **実装**: M2のオーケストレーターにGCとして組み込む。それまでは本方針に基づく手動棚卸し（下記手順）で運用する。

## 手動棚卸し手順

```bash
cd ~/projects/pda
for d in ~/projects/pda-*/ ~/projects/pda-autonomous-tasks/*/; do
  h=$(git -C "$d" rev-parse HEAD 2>/dev/null) || continue
  git merge-base --is-ancestor "$h" main && st=merged || st=UNMERGED
  dirty=$(git -C "$d" status --porcelain | wc -l)
  echo "$st dirty=$dirty $d"
done
```

merged かつ dirty=0 のものだけが削除候補。削除は `git worktree remove <path>` と `git branch -d <branch>` で行い、対応カードへ記録する。

## 2026-08-22 棚卸し結果

削除候補（merged・clean。削除はオーナー承認後に実施）:

- `pda-autonomous-improvement`（t_8a5c5089, done）
- `pda-autonomous-tasks/t_b18e8066`（t_b18e8066, done）
- `pda-communication-integrity` / `pda-interim-plans` / `pda-kanban-visibility` / `pda-local-backup` / `pda-routing-backup-integration` / `pda-scope-gate` / `pda-semantic-progress`（セッションworktree、いずれも統合済み）

保持（UNMERGED。対応判断が必要）:

- `pda-autonomous-tasks/t_e430a695` — カードはdoneだがbranch未統合。異常として t_e430a695 へコメント済み。オーナー審査対象。
- `pda-delegation-design` — オーナーによる一時停止中（`docs/status/delegation-fable-pause-2026-08-18.md`）。停止解除まで保持。
- `pda-backup-runtime-fix` / `pda-integration-sim` / `pda-notify-hardening` — 未統合の作業内容の要否をオーナー判断後に処置。
