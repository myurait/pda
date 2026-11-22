import json, os

D = os.path.dirname(os.path.abspath(__file__))
HEAD = "あなたはユーザーに向けて日本語の文章を書くアシスタントです。次の素材を読み、"
T = []


def add(tid, focus, purpose, material):
    T.append({"id": tid, "focus": focus, "prompt": HEAD + purpose + "\n\n" + material.strip() + "\n"})


add("m01", ["列", "表"], "この変更をレビューする人に向けて、PR の説明文を書いてください。何が変わり、既存のデータにどう影響するかを含めてください。", r'''
```php
// database/migrations/2026_11_20_000000_add_delivery_state.php
return new class extends Migration {
    public function up(): void
    {
        Schema::create('delivery_instructions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('post_group_id')->constrained('post_groups');
            $table->string('platform', 32);
            $table->timestamp('scheduled_at');
            $table->timestamp('dispatched_at')->nullable();
            $table->unique(['post_group_id', 'platform']);
        });
        Schema::table('post_google_location_relationships', function (Blueprint $table) {
            $table->string('delivery_state', 16)->default('pending')->after('sent_at');
            $table->string('external_key')->nullable()->after('delivery_state');
            $table->index(['delivery_state', 'updated_at']);
        });
        DB::statement("UPDATE post_google_location_relationships SET delivery_state = 'sent' WHERE sent_at IS NOT NULL");
    }
};
```
''')

add("m02", ["列", "表"], "このスキーマの差分が本番の集計にどう影響するかを、調査結果としてユーザーに報告してください。", r'''
```diff
--- a/doc/dbml/app/schema.dbml
+++ b/doc/dbml/app/schema.dbml
@@ Table post_search {
-  tstamp timestamp [not null]
+  tstamp datetime [not null]
   post_group_id bigint [not null]
-  location_ids json
+  location_ids json [note: 'deprecated, use post_search_locations']
 }
+Table post_search_locations {
+  post_group_id bigint [not null]
+  location_id bigint [not null]
+  indexes { (post_group_id, location_id) [unique] }
+}
```
```
mysql> SELECT COUNT(*) FROM post_search WHERE JSON_LENGTH(location_ids) > 0;
| 412883 |
mysql> SELECT COUNT(*) FROM post_search_locations;
| 0 |
```
The nightly report query still reads `post_search.location_ids` and joins nothing else.
''')

add("m03", ["書き戻し"], "このコードで起きる不具合を、Backlog の課題の本文としてユーザー向けに書いてください。起きる条件と影響を含めてください。", r'''
```php
// app/Services/SyncGbpPostsService.php
public function handle(Collection $locationIds): void
{
    $rows = PostGoogleLocationRelationship::whereIn('location_id', $locationIds)->get(); // (1)
    foreach ($rows as $row) {
        $remote = $this->gbp->fetchPost($row->external_key);             // takes 1-3 seconds per call
        $row->state = $remote->state;
        $row->published_at = $remote->updateTime;
    }
    $this->bulkUpdateModels($rows); // (2)
}

private function bulkUpdateModels(Collection $rows): void
{
    PostGoogleLocationRelationship::upsert(
        $rows->map->getAttributes()->all(),
        ['id']
        // no update columns specified => every column is overwritten
    );
}
```
Meanwhile `PostUpdateService::saveOnCompleted()` soft-deletes the old row (`deleted_at = now()`) when an edited post is delivered successfully.
''')

add("m04", ["書き戻し"], "この処理の流れと問題点を、ユーザーに説明してください。", r'''
```go
// worker/internal/settings/sync.go
func (s *Syncer) Run(ctx context.Context, storeID int64) error {
    local, err := s.repo.LoadSettings(ctx, storeID)   // read from MySQL
    if err != nil { return err }
    remote, err := s.api.GetSettings(ctx, storeID)    // read from external API
    if err != nil { return err }
    merged := merge(local, remote)                     // remote wins on hours, local wins on name
    if err := s.api.PutSettings(ctx, storeID, merged); err != nil { return err }
    return s.repo.SaveSettings(ctx, storeID, merged)   // UPDATE settings SET ... (all fields)
}
```
Operators also edit `settings.name` from the admin screen at any time. The job runs every 10 minutes for 80,000 stores.
''')

add("m05", ["段"], "作業する人に向けて、このリリースの進め方を日本語で説明してください。", r'''
Release runbook (draft, English)
1. Apply schema migration `2026_11_20_000000_add_delivery_state` to production.
2. Deploy api v3.14.0 and go-api v2.8.0. Verify the health check.
3. Disable the legacy batch schedule `sync-google-posts` in Step Functions.
4. Wait until the legacy SQS queue `post-delivery` is drained (ApproximateNumberOfMessages = 0).
5. Deploy worker v5.2.0 which reads from the new queue `post-dispatch`.
6. Enable the dispatcher schedule (rate(1 minute)).
Rollback: revert step 6, then step 5, then re-enable step 3. Steps 1 and 2 are not rolled back.
''')

add("m06", ["段"], "この CI の構成を、新しく参加したメンバーに日本語で説明してください。どこで失敗すると何が止まるかを含めてください。", r'''
```yaml
# .github/workflows/deploy.yml
on: { push: { branches: [main] } }
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: composer install
      - run: php artisan test --parallel
  build:
    needs: test
    steps:
      - run: docker build -t api:${{ github.sha }} .
      - run: docker push $ECR/api:${{ github.sha }}
  deploy-staging:
    needs: build
    steps:
      - run: aws ecs update-service --cluster stg --service api --force-new-deployment
  deploy-production:
    needs: deploy-staging
    environment: production   # requires manual approval
    steps:
      - run: aws ecs update-service --cluster prd --service api --force-new-deployment
```
''')

add("m07", ["窓"], "この取り込み処理がどの投稿を取り込み、どの投稿を取り込まないかを、ユーザーに説明してください。", r'''
```php
// app/Services/ImportGbpPostsService.php
private const SKIP_RECENT_HOURS = 3;
private const PURGE_AFTER_DAYS = 30;

public function shouldImport(GbpPost $p, Carbon $now): bool
{
    // posts created in the last 3 hours may still be in flight from our own dispatcher
    if ($p->createTime->gt($now->copy()->subHours(self::SKIP_RECENT_HOURS))) {
        return false;
    }
    return true;
}

public function purge(Carbon $now): int
{
    return ImportedPost::where('imported_at', '<', $now->copy()->subDays(self::PURGE_AFTER_DAYS))->delete();
}
```
Cron: `0 1 * * *` (runs at 01:00 JST, takes about 9 hours to finish all stores).
''')

add("m08", ["窓"], "このレビューコメントの指摘を、日本語でユーザーに説明し、対応案を書いてください。", r'''
Review comment (English):
> There is a race here. Between `SELECT ... FOR UPDATE` being released at the end of `reserve()` and the `INSERT` in `confirm()`, another request can reserve the same slot. In load tests the gap was 40-120 ms, and we saw 3 double bookings per 10,000 requests. The rate limiter uses a 60-second sliding window, so retries inside that period are rejected, but retries after it can hit the same gap again.
''')

add("m09", ["一覧"], "このコードで、投稿グループが重複して作られる理由をユーザーに説明してください。", r'''
```php
// app/Services/SyncGbpPostsService.php
public function importNewPosts(int $locationId, array $gbpPosts): void
{
    $knownKeys = PostGoogleLocationRelationship::where('location_id', $locationId)
        ->whereNotIn('id', $this->excludedRowIds)   // rows excluded from this run
        ->pluck('external_key')
        ->all();

    foreach ($gbpPosts as $post) {
        if (in_array($post->name, $knownKeys, true)) {
            continue; // already linked to a post group
        }
        $this->createPostGroupFrom($post);
    }
}
```
A recent change added the edited-source rows to `$this->excludedRowIds` so that they are not overwritten later in the same run.
''')

add("m10", ["一覧"], "この関数が何を計算して返し、呼び出し側でどう使われるかを、ユーザーに説明してください。", r'''
```go
// go-api/internal/report/summary.go
type StoreSummary struct {
    StoreID   int64
    Failed    int
    PostIDs   []int64
}

func Summarize(rows []DeliveryRow) []StoreSummary {
    byStore := map[int64]*StoreSummary{}
    for _, r := range rows {
        s, ok := byStore[r.StoreID]
        if !ok {
            s = &StoreSummary{StoreID: r.StoreID}
            byStore[r.StoreID] = s
        }
        if r.State == "failed" {
            s.Failed++
            s.PostIDs = append(s.PostIDs, r.PostID)
        }
    }
    out := make([]StoreSummary, 0, len(byStore))
    for _, s := range byStore {
        if s.Failed > 0 { out = append(out, *s) }
    }
    return out
}

// caller
summaries := report.Summarize(rows)
for _, s := range summaries { notifier.Alert(s.StoreID, s.PostIDs) }
```
''')

json.dump(T, open(f"{D}/tasks.json", "w"), ensure_ascii=False, indent=1)
import re
bad = re.compile(r"列|書き戻|一覧|表|段|窓|カラム|テーブル|配列|リスト|手順|ステップ|期間|時間帯|上書き")
for t in T:
    print(t["id"], bad.findall(t["prompt"]))
