# OpenClaw の役と規約

ミニ PC の OpenClaw に配る、全員に共通の指示と、役ごとの指示と規約。決定の背景は [v0.3-decision.md](../../docs/reports/v0.3-decision.md) の「役と規約」。

## ファイルと配り先

- `common.md`: 全エージェントに共通の指示。plugin `pda-common` が、各エージェントのプロンプトを組む段 (`before_prompt_build`) でこのファイルを読み、文脈に足す。ミニ PC では `~/v03/openclaw/pda/common.md` に置く。
- `agents/leader.md`: 統率役 (`leader`) の作業場所の `AGENTS.md`。仕事の分け方、結果の受け取り、報告の前の確かめ。
- `agents/worker.md`: 作業者 (`worker`) の作業場所の `AGENTS.md`。作業中の振る舞いの規約を含む。
- `agents/auditor.md`: 監査役 (`auditor`) の作業場所の `AGENTS.md`。伝え方の規約を含む。
- `plugins/pda-common/`: `common.md` を配る plugin。止める処理と、依頼者の指定を上書きする処理は入れない ([開発の考え方](../../docs/process/progress-over-stopping.md))。

## 規約の出所

規約は、オーナーの伝え方の規約と作業の進め方の規約を、どのモデルが読んでも分かる文に書き直したもの。特定の道具の名前、会社名、個別の事例は入れていない。伝え方の規約は監査役に、作業中の振る舞いの規約は作業者に割り当てる。
