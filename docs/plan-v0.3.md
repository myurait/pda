# PDA v0.3 計画 — OSS の選定

- 更新: 2026-09-27 JST
- 種別: v0.3 の計画。オーナーの指示による目的、v0.2 からの方針の変更、評価の進め方、候補と棄却の台帳。
- 位置付け: v0.2 の要件正本 [docs/requirements.md](requirements.md) は残す。本文書は、それを v0.3 の目的で読み替える差分と、v0.3 の作業計画を持つ。要件正本の本文の改訂は本計画の承認後に行う (要件正本 6 節の手順)。
- 前提: v0.2 の設計 (判定器をフロントドアにし、Conductor をコアに置く形) は凍結する。捨てない。tag `v0.3` の時点の成果として保存する。
- 調査記録: [docs/research/front-door-oss-2026-09-27/](research/front-door-oss-2026-09-27/README.md)

## 1. v0.3 の目的 (オーナーの文のまま)

```
どのOSSならpdaのv02, 03要件を満たせるか、調査したプロダクトのうち最も適した1本を特定する。
OSSで実現可能な範囲と、カスタム開発必要な範囲を切り分ける。
棄却したOSSには、すべて棄却した明確な理由があり、それがセットアップ不備や作業のスキップ・怠慢ではないとオーナーに説明可能である必要がある。
最も適した1本を決める上で、有力候補を3本まで絞り、オーナーに提案し、実際にプレビューをさせて承認を得なければならない。
```

v0.3 の作業は、候補の OSS をミニ PC の上にセットアップし、機能を評価し、オーナーの感触を得ることである。v0.2 で整理し、2026-09-27 の議論で方針を修正した「やりたいこと」を OSS で実現するための製品選定を行う。

## 2. v0.2 からの方針の変更 (2026-09-27 の決定)

### 2.1 発端

オーナーの問題提起は次の 4 点である。

- v0.2 の計画は、Claude の Workflow や subagent、Codex 自身のエージェントループが既に持つ仕組みを作り直している。
- 複数モデルを切り替え、セルとして扱い、最後に集約する形は、コンテキストの効率が悪くトークンも増えそうに見える。
- 欲しいのは、Claude と Codex に hook を後付けする仕組みと、それぞれの実行器を繋ぐ MCP である。
- 結局やりたいのは、ミニ PC に常駐してどの端末からも使える口と、hook と skill の組み合わせの可視化である。ワークフローの仕組みを作り直す必要はない。

議論の結果は次のとおり。

- セルに分けて集約する形そのものはトークンを増やさない。増やすのは、固定プロンプトの大きな Claude Code セッションを最上位に置いて長く回す形のほうで、差の出所は「1 回の呼び出しごとに再送する固定プロンプトの大きさ × 呼び出し回数」である (実測は調査記録の findings.md 4 節)。トークンは選定の決め手ではない。
- フローはどちらの形でも組めるので、決め手は可視化層の厚さと、ベンダーの変更への追従の速さになる。
- v0.2 の要件正本 2 節の発言 (多層的な統合推論機構、workflow 的な構造の保存) は、ベンダーの仕組みを使う形と両立する。本当に矛盾するのは 3.3 節の「特定のツールの画面やセッション管理をコアとして流用しない」と、それに連なる A4 だけである。

### 2.2 決定

1. フローを持つ主体は、ベンダーのエージェント自身のループ (Claude Code の subagent と Workflow、Codex の subagent) である。PDA のコアはワークフローの機構を持たない。
2. 要件正本のうち次を取り下げる。
   - 3.3 節「特定のツールの画面やセッション管理をコアとして流用しない」。
   - A4「コアを動かすのに、どの特定の LLM も必須ではない」。
   - 判定器の繰り返し、分岐と合流、オブザーバー、報告のセルを PDA の機構として作ること。A12〜A18 と A31〜A33 は対象を失う。
   - A19〜A26 の介入は、ベンダーと選定した OSS が出している操作 (中断、追加指示、承認、再試行、再開) の範囲に縮める。セルの挿入と、初期指示の書き換えを次の回から効かせる操作は失う。
3. 判定器をフロントドアにし Conductor をコアに置く形 (3 節の A) は凍結する。
4. 要件正本 2 節のオーナーの発言、3.2 節の周辺要件、A1〜A3、A5〜A11、A27〜A30 は残す。満たし方は、PDA の自作ではなく OSS とベンダーの機能、および skill と hook の配布で行う。

## 3. フロントドアの 3 つの形 (オーナーの整理)

フローの構築の仕方は、フロントドア (オーナーが仕事を頼む相手) をどこに置くかで 3 つに分かれる。

- A. フロントドアを jev などの判定器にして、すべての応答と実行エージェントをワークフローの枠組みに落とし込む。v0.2 の形。Conductor などのワークフロー管理がコアになる。ワークフロー管理とエージェンティックな対話は責任分野が違うので、Conductor がワークフローを管理できることは、それが可視化層として使えることを意味しない。凍結。
- B. フロントドアをエージェントチャットにし、可視化層はベンダーの app。エージェントにワークフローを管理・構築させるためのプロンプトがワークフローのコアになる。フロントドアのエージェントが上位に立ち、他のエージェント環境をサブエージェントか MCP として使う。エージェントアプリとしての機能は揃っているが、ワークフロー制御の可視化は木か一覧であり、Claude と Codex をまたいだ全体像は 1 か所に無い。
- C. フロントドアをエージェントチャットにし、可視化層はサードパーティの app。フロントドアのエージェントは Claude と Codex で切り替え可能で、どの環境がフロントドアに立ってもよいようにワークフロー機能 (skill、hook、プロンプト) を抽象化して配布する。他のエージェント環境をサブエージェントか MCP として使う。当初の要件に最も近い。

v0.3 は C を評価する。B はベンダーが既に出しているものとして、比較の基準に置く。

## 4. v0.3 の要件 (評価の物差し)

出所は要件正本の受け入れ条件 (A 番号) と 2026-09-27 の決定である。判定は観測できる事象で行う。

| 番号 | 要件 | 判定方法 | 出所 |
|---|---|---|---|
| R1 | フロントドアがチャットで、推論のハーネスを Claude Code と Codex で切り替えられる。個人契約の定額ログインをそのまま使う | 同じ画面から Claude Code と Codex のそれぞれに仕事を頼め、API キーではなく既存のログインで動く | 2.2 の決定 1、A1 |
| R2 | 他のエージェント環境をサブエージェントか MCP として使える | Claude Code がフロントドアのとき Codex に仕事を渡せ、その逆もできる。渡した先の進行が見える | 2 節の発言、A2 |
| R3 | 実行単位 (セッション、サブエージェント) ごとに skill・hook・MCP・プロンプトを絞る・足すことができ、正本 1 か所から配れる | あるセッションにだけ hook と skill を付け、別のセッションには付かないことを確かめる。正本の変更が全実行器に届く | A7、オーナーの条件 |
| R4 | ミニ PC (Ubuntu Server、ヘッドレス) に常駐し、開発 PC とスマホから同じものに届く | ミニ PC で常駐させ、Tailscale 経由で PC とスマホのブラウザから開ける。Web の導線の作り込みは後回しだが、到達はできる | A6 の縮小 |
| R5 | 可視化。全体像と今何をしているか。実行器 (セッション) ごとの生死、現在のプロンプト、直近の出力、使ったツール、経過時間。タスクごとの状態、進行の流れ、報告、成果物。出来事の全列挙を主面にしない | 3 つ以上のセッションを同時に動かし、30 秒で「誰が何をしているか」を読めるか。要件正本 3.2 の 6 の項目を 1 つずつ照合する | 3.2 の 6、A27 |
| R6 | 止まるときに報告があり、成果物は報告と独立に一覧できる | タスクの終わりに報告が読め、成果物 (差分、ファイル) が報告とは別の場所から開ける。OSS に無ければ skill で足せるか | 3.2 の 11、A21、A22、A29 |
| R7 | 介入。中断、追加指示、承認、再試行 | 動いているセッションを止め、追加の指示を送り、権限要求に答え、同じ仕事をやり直せる。それがスマホからもできる | A19、A20、A26 の縮小 |
| R8 | 会社契約と個人契約が同じ一覧に並ぶ | v0.3 は個人契約だけで評価し、複数アカウントを扱う機構の有無を記録する | A3 |
| R9 | 出来事の流れが外に出る | hooks、OpenTelemetry、ログのいずれかで、セッションの出来事をログストア (OpenObserve か Datadog) に流せる | 3.2 の 9、A5 |
| R10 | 保守。生きていて、追従できる | 直近 3 か月のコミットとリリース、運営主体、ライセンス、ACP・MCP・OpenTelemetry の採用、ベンダー追従の仕組み | オーナーの条件 |
| R11 | トークン。1 回の呼び出しに載る固定プロンプトの大きさを制御できる | セッションの起動時に読み込む MCP とツールの一覧を絞れる | 2.1 |
| R12 | 実行器の起動と停止が画面からできる | 画面からセッションを起こし、止められる | A23 |

R1、R2、R4 は硬い条件で、満たさないものは 3 本に入れない。

## 5. 進め方

### 5.1 段階

1. 本計画の承認。オーナーが 4 節の要件と 6 節の候補の分け方を承認する。
2. 要件正本の改訂 (2.2 の決定を本文に反映する)。
3. 選別。6.1 と 6.2 の候補それぞれをミニ PC にセットアップし、シナリオ S1 だけを通す。1 製品につき Codex のワンショット 1 回と追加指示 1 回まで。
4. 本評価。選別を通った製品に S1〜S8 を通し、4 節の要件を 1 つずつ判定する。評価記録は `docs/reports/v0.3-<製品>-evaluation.md`、証拠は `docs/reports/evidence/v0.3-<製品>/`。
5. オーナーのプレビュー。本評価を通った製品を Tailscale Serve で公開し、オーナーが開発 PC とスマホから触る。所見は評価記録の「オーナーの所見」に書く。
6. 3 本への絞り込みと承認。硬い条件 (R1、R2、R4) を満たし、R5 と R7 の充足が上位のものを 3 本まで挙げ、オーナーがプレビューの上で承認する。
7. 3 本の深掘り。同じ仕事 (実際の PDA の作業 1 件) を 3 本で回し、R3、R6、R9、R10 を比較する。
8. 1 本の決定。オーナーが決める。決めた 1 本について、要件ごとに「OSS が満たす / skill・hook・設定で満たす / カスタム開発が要る」を切り分けた表を作る。
9. 要件正本の改訂と v0.4 (統合) の範囲の決定。

### 5.2 標準シナリオ

すべての候補に同じシナリオを通す。合否は観測できる事象で書く。

| 番号 | シナリオ | 合格の事象 |
|---|---|---|
| S1 | スマホのブラウザから Claude Code に小さなコーディング作業を頼み、進行を見て、終わりに差分を見る | 頼める。進行中の出力が見える。差分が開ける |
| S2 | S1 を Codex で行う | 同上 |
| S3 | Claude Code をフロントドアにして Codex へ作業を渡す (skill か MCP)。逆も行う | 渡した先の進行が同じ画面で見える。結果が戻る |
| S4 | あるセッションにだけ hook (例: Stop フックの answer-gate) と skill (例: 報告の skill) を付ける | そのセッションでは効き、別のセッションでは効かない |
| S5 | 3 つのセッションを同時に動かし、30 秒だけ画面を見る | 誰が何をしているか、止まっているのは誰かが読める |
| S6 | 動いているセッションを止め、追加の指示を送り、権限要求に答え、やり直す | 4 つの操作がスマホからできる |
| S7 | 出来事を OpenObserve (5080 番) に流す | ツール呼び出しと出力の出来事が検索できる |
| S8 | 常駐と復帰。ミニ PC の再起動後に画面が戻り、セッションの記録が残る | 再起動後に一覧と記録が見える |

### 5.3 棄却の規律

棄却は「机上の棄却」と「評価による棄却」に分ける。

- 机上の棄却は、次の硬い条件のどれかに一次資料で反することが分かった場合に限る。H1: Claude Code と Codex の両方を定額ログインで動かせない。H2: ミニ PC のヘッドレス Linux で常駐できず、Web か API で届かない。H3: 直近 3 か月にコミットもリリースも無い、または保守終了の告知がある。H4: ライセンスが個人の自前運用を許さない。
- それ以外の理由 (画面が薄い、委譲が無い、若い、H1 や H2 が一次資料から分からない) は机上で棄却せず、選別に回す。
- 評価による棄却は、S1〜S8 の記録と 4 節の判定表を根拠にする。
- セットアップが失敗した場合は、指示ファイル、走行記録、エラーを証拠として残し、Codex の追加指示 1 回まで試す。それでも動かなければ「セットアップ不備による棄却」として台帳に載せ、どの手順で何が起きたかを書く。試みの記録が無い棄却は認めない。
- 台帳の書式は、製品、段階 (机上 / 選別 / 本評価 / 深掘り)、反した要件の番号、根拠 (URL か証拠ファイル)、再考の条件の 5 欄。

### 5.4 セットアップの規律

- 実装側 (Codex) が、1 製品につき 1 本の指示ファイル `docs/codex-runs/<日付>-v0.3-<製品>-setup.md` でセットアップする。起動と回収は設計側が行う (`docs/process/remake-cycle.md` の役割)。
- 認証は `~/pda/secrets/` に複製済みの個人契約の認証を使う。ホストの `~/.claude` と `~/.codex` は直接使わない。
- 公開は Tailscale Serve で行い、製品ごとにポートを分ける。設定は人の手順で、指示ファイルに手順書として書かせる。
- 報告書は `docs/reports/v0.3-<製品>-codex.md`、証拠は `docs/reports/evidence/v0.3-<製品>/`。報告書には、動いたか、S1 の結果、詰まった箇所、使ったポートとパスを書かせる。
- 製品のコードには手を入れない。設定ファイルと skill、hook の追加だけを許す。
- ミニ PC の sudo にはパスワードが要り、root の権限が要る作業はオーナーが行う (`docs/environment/mini-pc.md`)。root が要る手順は実装側が人の手順書として書き、設計側がオーナーに依頼する。root が要ることを「セットアップ不備」に数えない。

### 5.5 ミニ PC の資源

- メモリは 12 GiB。v0.2 の常駐 (Conductor、Elasticsearch、Redis、OpenObserve、実行器のコンテナ) を止めるか、OpenObserve だけ残すかはオーナーの判断で、項目ごとに許可を得る。
- 同時に立てる製品は 2 つまで。評価が終わった製品は止めるが、消さない。

### 5.6 役割

- 設計側 (Fable): 指示ファイルの作成、評価、台帳の維持、オーナーへの提案。
- 実装側 (Codex): ミニ PC でのセットアップと S1 の実行、報告書。
- オーナー: 計画の承認、プレビュー、3 本の承認、1 本の決定、ミニ PC の常駐の停止の許可。

## 6. 候補と机上の判定 (2026-09-27 時点)

母集団は GitHub の topic (ai-orchestrator、agent-orchestration、claude-code、codex-cli、parallel-agents、agent-client-protocol) の検索と [awesome-agent-orchestrators](https://github.com/andyrewlee/awesome-agent-orchestrators) の 7 分類で、146 件のメタデータを GitHub の API で取った。34 件は README と公式文書を 7 項目で読み、残りは README と公式文書で硬い条件 H1 と H2 を確かめた。数値と引用は調査記録 (README.md の母集団表、findings.md の 5 節) にある。分類の語は、一次 (選別へ)、二次 (一次の後に選別へ)、棄却 H# (机上の棄却と反した条件)、部品 (app ではなく部品として v0.4 で再考) の 4 つで、3 つの文書で同じ語を使う。

### 6.1 一次候補 (7 項目で読み、硬い条件を満たす引用があるもの)

| 製品 | 星 / ライセンス | 一次資料で確認した要点 |
|---|---|---|
| [omnigent](https://github.com/omnigent-ai/omnigent) | 10.3k / Apache | ログイン済みの公式 CLI を包み ACP も併用。同じセッションに Claude Code と Codex を混ぜて委譲。エージェントは YAML (MCP、サブエージェント)。docker compose でサーバ常駐、iOS / Android、モバイル向け Web。Databricks の AI チームと Neon が構築と表記 |
| [happier](https://github.com/happier-dev/happier) | 1.7k / MIT | ベンダーの CLI をそのまま動かし定額ログインを流用。中継サーバを自前運用。iOS / Android / Web。別のエージェントでレビュー・計画・委譲を起動。MCP を 1 回設定して全エージェントへ。権限要求と問いの受信箱、実行中の舵取り |
| [OpenHands](https://github.com/OpenHands/OpenHands) | 89k / MIT | Agent Canvas が外部の ACP エージェント (Claude Code、Codex) を子プロセスで起こしローカルのログインを拾う。サーバ常駐、スマホはブラウザ。会話の分岐、割り込み。シード 5M ドル |
| [multica](https://github.com/multica-ai/multica) | 51k / Apache に商用ホスティング制限を足した独自条項 | 導入済みの CLI をそのまま使う。デーモン、Docker Compose / Helm。Web / デスクトップ / iPhone / iPad。Squads (人とエージェントの混成)、SKILL.md、ボード、実行中の舵取り |
| [paseo](https://github.com/getpaseo/paseo) | 18.7k / Apache | ヘッドレスのデーモン。Web、iOS、Android、CLI、Docker。Claude Code、Codex、他は ACP。skill で引き継ぎと委員会。MCP と SDK で自動化。個人 1 名 |
| [kandev](https://github.com/kdlbs/kandev) | 849 / AGPL | 全エージェントを ACP で。ワークフローを可搬な YAML で、段ごとに別エージェント、人のゲート。タスク間 MCP。ボードとレビューの対話。自前運用、スマホは Tailscale 経由 |

### 6.2 二次候補 (硬い条件に反する証拠が無く、一次候補の選別の後に選別へ)

7 項目で読んだもの。

| 製品 | 星 / ライセンス | 要点と、一次候補にしなかった理由 |
|---|---|---|
| [agent-orchestrator (Untrivial)](https://github.com/Untrivial-ai/agent-orchestrator) | 12.4k / Apache | 25 以上のハーネス。デスクトップ app (mac / Windows / Linux) がローカルのデーモンを持ち、スマホ app は LAN か Tailscale で対にする。作業を分けてワーカーを起こし、CI の失敗とマージ衝突を直す。live Kanban。ヘッドレスでデーモンだけを動かせるかと Web UI の有無が未確認 |
| [5dive](https://github.com/5dive-ai/5dive) | 61 / MIT | 公式 CLI を systemd で常駐、Pro / Max をそのまま。5dive.yaml、組織図・待ち行列・ゲート。Web は plugin、スマホの記述なし。星が少ない |
| [OpenMausBot](https://github.com/milind-soni/OpenMausBot) | 3.6k / Apache | ボットの実体が Claude か Codex。Markdown でチーム導入。Docker、Android / iOS。承認カード。画面がチャット中心 |
| [amux](https://github.com/mixpeek/amux) | 505 / MIT + Commons Clause | systemd、Web、iOS と PWA。素の CLI を tmux で。ワーカー間の @ メンション、kanban。リリースが 1 回 |
| [bb](https://github.com/get-bb/bb) | 3.9k / MIT | Web / CLI / HTTP API、Linux。ACP。エージェントが別のエージェントを起こす。スマホの記述なし |
| [podium](https://github.com/madeinorbit/podium) | 23 / Apache | ハーネス横断のサブエージェント。Linux のヘッドレスサーバ。ボードとチーム表示。星が少なく 2 名 |
| [claw-orchestrator](https://github.com/Enderfga/claw-orchestrator) | 583 / MIT | 宣言的なワークフローのノード (fanout、council、human_gate、subflow)。`clawo serve`。ACP と MCP。画面が 3 タブで薄い、スマホの記述なし |
| [Archon](https://github.com/coleam00/Archon) | 23.6k / MIT | YAML のワークフロー、ワークフローの図、`archon serve` と Web、Docker。Codex は SDK 経由で定額ログインの可否が未確認 |
| [Orca](https://github.com/stablyai/orca) | 79k / MIT | `orca serve` で Linux 常駐、iOS / Android。任意の CLI を定額で。委譲とワークフローの定義が無く、Claude Code の subagent に任せる前提になる |
| [t3code](https://github.com/pingdotgg/t3code) | 23.7k / MIT | サービス常駐、Web、iOS / Android。委譲とワークフローの定義が無い |
| [jean](https://github.com/coollabsio/jean) | 1.3k / Apache | ヘッドレスサーバ (Linux、Docker)。各 CLI と直接。委譲の仕組みが未確認、スマホの記述なし |
| [vicoa](https://github.com/vicoa-ai/vicoa) | 362 / AGPL | デーモン、Docker、Web / iOS / Android、ACP、skills の管理。2026-08-28 作成で若い |
| [omg.dev](https://github.com/BennyKok/omg.dev) | 541 / MIT | Debian / Ubuntu のローカルサーバと Web、iPhone。ボード。委譲が無い。README とサイトで動作形態の説明が食い違う |
| [intentic](https://github.com/intentic/intentic) | 46 / MIT | エージェントごとの Docker サンドボックス、ターンごとの認証情報の注入、ACP、MCP。星が少ない |
| [opensession](https://github.com/tellahq/opensession) | 386 / MIT | Linux のサービス、PWA と iOS。複数の Codex と Claude の契約。Pi エンジン経由と書かれ、CLI そのものを動かすかが未確認 |
| [herdr](https://github.com/herdrdev/herdr) と [collie](https://github.com/AltanS/collie) | 40.9k / Apache、1.1k / MIT | 端末を常駐させる層。エージェント同士がペインを起こし合う。skill は Markdown。画面はグリッドと状態表示だけ。他の候補の下に敷く部品としても評価する |
| [agent-of-empires](https://github.com/agent-of-empires/agent-of-empires) | 3.3k / MIT | `aoe serve` と PWA。ACP。委譲が無い |
| [mjolnir](https://github.com/BrokkAi/mjolnir) | 64 / GPL | ACP で Claude Code と Codex を並行。Web は Tailscale 経由。委譲とワークフローの定義が無い |
| [agentconnect](https://github.com/agentconnect-md/agentconnect) | 1.4k / Apache | Slack 等で @ メンション。Docker Compose のコンソール。ACP、MCP、OpenTelemetry。フロントドアが Slack |
| [Fusion](https://github.com/Runfusion/Fusion) | 1.2k / MIT | エージェント間のメールボックス、kanban と図、OTLP、Docker。Claude Code と Codex を CLI で動かすかが未確認 |
| [qm](https://github.com/yc-software/qm) | 15.3k / MIT | Y Combinator の組織。Pi / OpenCode / Codex / Claude Code が同じ core を駆動。Slack と Web。全ツール呼び出しで人の承認が要り、多人数向け |
| [OpenClaw](https://github.com/openclaw/openclaw) | 390k / MIT (LICENSE 本文。GitHub の表示は NOASSERTION) | ハーネスを差し替え可能なプラグイン、ACP、全端末のネイティブ app。第一の位置付けは個人アシスタント。要件正本 1 節にある v0.1 の体験劣化と同じ系統 |
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | 249k / MIT | Claude Code と Codex に CLI で委譲、Kanban。公式スマホ app なし。v0.1 で体験劣化を記録した製品だが、その後 Kanban と委譲が加わった |
| [Paperclip](https://github.com/paperclipai/paperclip) | 88k / MIT | ハートビートで起こすアダプタ、組織図と Kanban、Web、自前運用。チャットのフロントドアではない |
| [Goose](https://github.com/aaif-goose/goose) | 54.7k / Apache | 自前のエージェントで、ACP の provider として Claude と Codex を呼ぶ。デスクトップ・CLI・API。Web とスマホの記述なし |

硬い条件だけを確かめたもの (根拠は findings.md の 5.3)。H1 と H2 の両方に「はい」の引用があるものを先に選別する。

- 両方はい: [cezar](https://github.com/open-mercato/cezar) (定額ログイン、ubuntu-vps に systemd、スマホから cockpit、YAML で段ごとに runner)、[ai-maestro](https://github.com/23blocks-OS/ai-maestro) (ヘッドレスのワーカー、Docker、複数マシン、AMP でメッセージ、Kanban)、[garcon](https://github.com/cfal/garcon) (Web、Linux バイナリ、子チャットへの委譲。GPL)、[squid](https://github.com/agent-squid/squid)、[tlbx](https://github.com/tlbx-ai/tlbx)、[mulmoterminal](https://github.com/receptron/mulmoterminal)、[taskuary](https://github.com/ldbumble/taskuary)、[codexia](https://github.com/milisp/codexia) (ヘッドレスの backend、ACP)、[waku](https://github.com/egoist/waku) (waku-daemon と Web、GPL)、[codey](https://github.com/its-ahoh/codey) (Node の gateway、Markdown のボット定義とフローグラフ。デスクトップは macOS)、[clideck](https://github.com/rustykuntz/clideck)、[ateam](https://github.com/clawnify/ateam) (GPL と商用)、[tutti](https://github.com/nutthouse/tutti) (tutti.toml のワークフロー、`tt serve`。3 か月のコミットが 1 件で活動は細い)。
- H2 はい、H1 は不明: [ruflo](https://github.com/ruvnet/ruflo)、[vibe-tree](https://github.com/sahithvibudhi/vibe-tree)、[contrabass](https://github.com/junhoyeo/contrabass) (WORKFLOW.md、headless、JSON / SSE API)、[gastown](https://github.com/gastownhall/gastown)、[Octop](https://github.com/TencentCloud/Octop)、[mission-control](https://github.com/builderz-labs/mission-control)、[OtoDock](https://github.com/OtoDock/oto-dock) (FSL-1.1)、[Ivy-Tendril](https://github.com/Ivy-Interactive/Ivy-Tendril) (FSL-1.1)、[agor](https://github.com/preset-io/agor) (BUSL-1.1)、[cccc](https://github.com/ChesterRa/cccc)、[imcodes](https://github.com/im4codes/imcodes)、[openrig](https://github.com/mvschwarz/openrig)、[trinity](https://github.com/Abilityai/trinity)、[Pane](https://github.com/greenfield-inc/Pane)、[dev-3.0](https://github.com/h0x91b/dev-3.0)、[claude-command-center](https://github.com/amirfish1/claude-command-center) (非商用)、[sortie](https://github.com/sortie-ai/sortie)、[xum](https://github.com/coder/xum)。
- H1 はい、H2 は不明: [agetor](https://github.com/alamops/agetor)、[ai4kanban](https://github.com/ai4kanban/ai4kanban)、[pragma](https://github.com/pragma-sh/pragma)、[zaivern-code](https://github.com/tacyan/zaivern-code)、[dray](https://github.com/monorepo-labs/dray)、[termany](https://github.com/thinkany-ai/termany)、[zuse](https://github.com/swarajbachu/zuse)、[Ghostex](https://github.com/maddada/Ghostex)、[alethe-agents](https://github.com/Kc1t/alethe-agents)、[synara](https://github.com/Emanuele-web04/synara)、[superset](https://github.com/superset-sh/superset) (Elastic License 2.0)。
- 両方不明: [kungfu](https://github.com/kungfu-systems/kungfu)、[evoflux](https://github.com/evoelsewhere/evoflux)、[nimbalyst](https://github.com/nimbalyst/nimbalyst)、[ai-devkit](https://github.com/codeaholicguy/ai-devkit)、[proliferate](https://github.com/proliferate-ai/proliferate)、[cyclops](https://github.com/cyclops-team/cyclops)、[luvus](https://github.com/RizRiyz/luvus)、[cyrus](https://github.com/cyrusagents/cyrus)、[companyhelm](https://github.com/CompanyHelm/companyhelm)、[opentag](https://github.com/amplifthq/opentag) (主 UI が Slack)、[Dorothy](https://github.com/Charlie85270/Dorothy)。

### 6.3 机上の棄却 (反した条件と根拠は findings.md の 5.3 と 5.4)

- H1 (Claude Code と Codex の両方を定額ログインで動かせない): cloudflare-os、rakazo、taOS、hivekeep、stagewise、devspace (フロントドアがベンダーの app で B の部品)、AgentsMesh (BYOK、BSL)、openchamber (OpenCode 専用)、forge-orchestrator (API キー)、octomux (Codex なし)、lionclaw (Claude Code なし)、mosoo-agent-driver (OpenAI の API キーのみ)、berd (Goose のみ)、CodeNomad (OpenCode)、Yao (CLI を起こさない)、takt (API キー。YAML の手順定義は部品として再考)、openswarm (Codex なし、macOS 専用)、Aperant (Claude Code のみ、デスクトップ、3 か月のコミット 0)、muxel (Codex なし、デスクトップ)、Friday (BYOK)、n8n、LangGraph Studio、Open WebUI、Mastra Studio。
- H2 (ヘッドレス Linux で常駐できず Web か API で届かない): happy (Linux のデーモン運用の記述なし。同系の happier を一次候補にした)、emdash、traycer、Meldwork、zeron、munder-difflin、Orkas、agent-teams-ai、ouijit、agent-session-manager-desktop、tempest、monocode、runner、parallel-code、alas、clave、diri、fletch、GraphCode、supacode、superagent-desktop、tortie、hcom (常駐サービスなし。部品として再考)、openyak (Electron、Linux は作業中)、background-agents (Cloudflare Workers と Durable Objects の基盤)、collab-public と constellagent と vibecraft (デスクトップで、かつ 3 か月のコミットが無いか 1 件)、Crystal (2026-02 に終了)、Conductor.build (非公開ソース、Mac のみ)、Zed (デスクトップのみ)。
- H3 (3 か月にコミットもリリースも無い、または保守終了の告知): ClawTeam、automaker、agx (ライセンスも無い)、takopi、shire、sandbox-agent、acp-ui、harnss、golutra、humanlayer (deprecated の告知)、Vibe Kanban (会社の解散)、Terragon (終了)。
- 部品 (app ではなく、v0.4 で部品として再考): open-multi-agent、claudexor (複数アカウントの枠管理は R8 の部品)、crewplane、zenith。

### 6.4 決まっていないこと

- omnigent と happier で Codex が app-server 経由か CLI の包みか。文書に無く、選別で確かめる。
- ミニ PC のヘッドレス環境で、個人契約のログイン (複製した認証ファイル) がそれぞれの製品でそのまま通るか。選別で確かめる。
- v0.2 の常駐を止めるか。オーナーの判断 (5.5)。

## 7. 成果物

- 棄却台帳: 本文書 6 節を更新し続ける。
- 評価記録: `docs/reports/v0.3-<製品>-evaluation.md` と証拠。
- 3 本の提案: `docs/reports/v0.3-shortlist.md`。プレビューの URL、要件の判定表、オーナーの所見。
- 1 本の決定と切り分け: `docs/reports/v0.3-decision.md`。要件ごとの「OSS が満たす / skill・hook・設定で満たす / カスタム開発が要る」。
