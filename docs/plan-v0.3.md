# PDA v0.3 計画 — OSS の選定

- 更新: 2026-09-28 JST (オーナーの判断を反映。記録は 8 節)
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
   - A19〜A26 の介入は、ベンダーと選定した OSS が出している操作 (中断、追加指示、承認、再試行、再開) の範囲に縮める。フローの途中へのセルの挿入と、初期指示を書き換えて次の回から効かせる操作は要件から外す (2026-09-28 オーナー承認)。
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
| R4 | ミニ PC (Ubuntu Server、ヘッドレス) に常駐し、開発 PC とスマホから同じものに届く | ミニ PC で常駐させ、Tailscale 経由で PC とスマホから開ける。ブラウザか app かは問わない。Web の導線の作り込みは後回しだが、到達はできる | A6 の縮小 |
| R5 | 可視化。全体像と今何をしているか。実行器 (セッション) ごとの生死、現在のプロンプト、直近の出力、使ったツール、経過時間。タスクごとの状態、進行の流れ、報告、成果物。出来事の全列挙を主面にしない | 3 つ以上のセッションを同時に動かし、30 秒で「誰が何をしているか」を読めるか。要件正本 3.2 の 6 の項目を 1 つずつ照合する | 3.2 の 6、A27 |
| R6 | 止まるときに報告があり、成果物は報告と独立に一覧できる | タスクの終わりに報告が読め、成果物 (差分、ファイル) が報告とは別の場所から開ける。OSS に無ければ skill で足せるか | 3.2 の 11、A21、A22、A29 |
| R7 | 途中で止める | 動いているセッションを、画面から途中で止められる。スマホからもできる | A19、2026-09-28 オーナー |
| R13 | 途中の出力が見える。1 つの入力に 1 つの応答だけが返る形に縛られず、実行中のモデルの状態を見渡せる | 実行中に、モデルの途中の出力 (流れてくる文、ツール呼び出し、端末の出力) が画面に出る。依頼を投げて最終結果だけが返る形は不合格 | 2026-09-28 オーナー |
| R14 | 途中の介入。追加の指示、権限要求への返答、やり直し | 動いているセッションに追加の指示を送り、権限要求に答え、同じ仕事をやり直せる。スマホからもできる | A20、A26 の縮小 |
| R8 | 会社契約と個人契約が同じ一覧に並ぶ | v0.3 は個人契約だけで評価し、複数アカウントを扱う機構の有無を記録する | A3 |
| R9 | 出来事の流れが外に出る | hooks、OpenTelemetry、ログのいずれかで、セッションの出来事をログストア (OpenObserve か Datadog) に流せる | 3.2 の 9、A5 |
| R10 | 保守。生きていて、追従できる | 直近 3 か月のコミットとリリース、運営主体、ライセンス、ACP・MCP・OpenTelemetry の採用、ベンダー追従の仕組み | オーナーの条件 |
| R11 | トークン。1 回の呼び出しに載る固定プロンプトの大きさを制御できる | セッションの起動時に読み込む MCP とツールの一覧を絞れる | 2.1 |
| R12 | 実行器の起動と停止が画面からできる | 画面からセッションを起こし、止められる | A23 |

R1、R2、R4、R7、R13 は必須で、満たさないものは 3 本に入れない (2026-09-28 オーナー承認。R7 と R13 は同日に必須へ加えた)。それ以外は 3 本の中で比べる材料にする。

## 5. 進め方

### 5.1 段階

1. 本計画の承認。必須の条件、要件からの取り下げ、ミニ PC の v0.2 の停止、main への取り込みと送信は 2026-09-28 に済んだ (8 節)。
2. 要件正本の改訂 (2.2 の決定を本文に反映する)。
3. 静的なふるい分け。候補すべてについて、必須の条件を資料 (README、公式文書) で確かめる。反すると明記した記述を引用できたものは、その場で落とす。資料から分からないものは選別へ回す (2026-09-28 オーナー指示「静的に落とせる候補は落とせ」)。
4. 選別。ふるい分けを通った候補それぞれをミニ PC にセットアップし、シナリオ S1 だけを通す。1 製品につき Codex のワンショット 1 回と追加指示 1 回まで。
5. 本評価。選別を通った製品に S1〜S8 を通し、4 節の要件を 1 つずつ判定する。評価記録は `docs/reports/v0.3-<製品>-evaluation.md`、証拠は `docs/reports/evidence/v0.3-<製品>/`。
6. オーナーのプレビュー。本評価を通った製品を Tailscale Serve で公開し、オーナーが開発 PC とスマホから触る。所見は評価記録の「オーナーの所見」に書く。
7. 3 本への絞り込みと承認。必須の条件 (R1、R2、R4、R7、R13) を満たし、R5 と R14 の充足が上位のものを 3 本まで挙げ、オーナーがプレビューの上で承認する。
8. 3 本の深掘り。同じ仕事 (実際の PDA の作業 1 件) を 3 本で回し、R3、R6、R9、R10 を比較する。
9. 1 本の決定。オーナーが決める。決めた 1 本について、要件ごとに「OSS が満たす / skill・hook・設定で満たす / カスタム開発が要る」を切り分けた表を作る。
10. 要件正本の改訂と v0.4 (統合) の範囲の決定。

### 5.2 標準シナリオ

すべての候補に同じシナリオを通す。合否は観測できる事象で書く。

| 番号 | シナリオ | 合格の事象 |
|---|---|---|
| S1 | スマホから Claude Code に小さなコーディング作業を頼み、進行を見て、途中で一度止め、再開して、終わりに差分を見る | 頼める。進行中の途中の出力が見える。止められる。差分が開ける |
| S2 | S1 を Codex で行う | 同上 |
| S3 | Claude Code をフロントドアにして Codex へ作業を渡す (skill か MCP)。逆も行う | 渡した先の進行が同じ画面で見える。結果が戻る |
| S4 | あるセッションにだけ hook (例: Stop フックの answer-gate) と skill (例: 報告の skill) を付ける | そのセッションでは効き、別のセッションでは効かない |
| S5 | 3 つのセッションを同時に動かし、30 秒だけ画面を見る | 誰が何をしているか、止まっているのは誰かが読める |
| S6 | 動いているセッションを止め、追加の指示を送り、権限要求に答え、やり直す | 4 つの操作がスマホからできる |
| S7 | 出来事を OpenObserve (5080 番) に流す | ツール呼び出しと出力の出来事が検索できる |
| S8 | 常駐と復帰。ミニ PC の再起動後に画面が戻り、セッションの記録が残る | 再起動後に一覧と記録が見える |

### 5.3 棄却の規律

棄却は「机上の棄却」と「評価による棄却」に分ける。

- 机上の棄却は、次のどれかに一次資料で反することが分かった場合に限る。H1: Claude Code と Codex の両方を定額ログインで動かせない (API キーが必須)。H2: GUI の無い Linux に常駐できず、別の端末から操作できない。H3: 直近 3 か月にコミットもリリースも無い、または保守終了の告知がある。H4: ライセンスが個人の自前運用を許さない。H5: 動いている実行を画面から途中で止められない (R7)。H6: 実行中の途中の出力が見えず、依頼 1 つに最終結果だけが返る (R13)。
- 「反する」は、制約を明記した記述を引用できる場合だけとする。記述が見つからないことは反する根拠にしない。
- それ以外の理由 (画面が薄い、委譲が無い、若い、H1〜H6 が一次資料から分からない) は机上で棄却せず、選別に回す。
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

- メモリは 12 GiB。2026-09-28 に、オーナーの許可で v0.2 のコンテナ (Conductor の本体と画面、Elasticsearch、Redis、ミラー、実行器 4 つ、v0.2 の画面) を止めた。消していないので `docs/runbook/increment-4.md` の手順で戻せる。停止後の空きは 10 GiB。
- 残したのは OpenObserve とその受け口 (otel-collector) で、候補がセッションの出来事を外へ流せるか (R9、S7) を試す先に使う。何を残すかはオーナーから任された (2026-09-28)。
- 同時に立てる製品は 2 つまで。評価が終わった製品は止めるが、消さない。

### 5.6 役割

- 設計側 (Fable): 指示ファイルの作成、評価、台帳の維持、オーナーへの提案。
- 実装側 (Codex): ミニ PC でのセットアップと S1 の実行、報告書。
- オーナー: 計画の承認、プレビュー、3 本の承認、1 本の決定、ミニ PC の常駐の停止の許可。

## 6. 候補と判定 (2026-09-28 時点)

母集団 (147 件) の集め方と 2026-09-27 の判定は調査記録にある。2026-09-28 に、それまで棄却していない 84 件について、必須の 4 条件 H1 (定額ログイン)、H2 (常駐と遠隔操作)、H5 (途中で止める)、H6 (途中の出力) を README と公式文書で確かめた (findings.md の 5.4)。R2 (Claude Code と Codex の間で仕事を渡し、渡した先が見える) は、skill や MCP で足せるので資料では判定せず、選別で確かめる。分類の語は次の 4 つで、3 つの文書で同じ語を使う。

- 選別 (4 条件の記述あり): 4 条件すべてに、満たすと読める記述がある。最初に選別する。
- 選別 (記述なし: H#): 反する記述は無いが、括弧の条件を満たす記述が資料に無い。選別で確かめる。
- 棄却 H#: 括弧の条件に反すると明記した記述を引用できる。
- 部品: app ではなく、v0.4 で部品として再考する。

件数は、選別 (4 条件の記述あり) 20 本、選別 (記述なし) 55 本、棄却 76 本、部品 4 本。herdr と collie は組で 1 本と数える。

### 6.1 選別 (4 条件の記述あり、20 本)

| 製品 | 星 / ライセンス | 要点 |
|---|---|---|
| [happier](https://github.com/happier-dev/happier) | 1.7k / MIT | ベンダーの CLI をそのまま動かし、全端末へ映す。iOS / Android / Web。別のエージェントでレビュー・計画・委譲を起動 |
| [multica](https://github.com/multica-ai/multica) | 51k / Apache に商用ホスティング制限を足した独自条項 | デーモン、Docker Compose。Web / デスクトップ / iPhone。Squads、SKILL.md、ボード。実行記録から停止 |
| [paseo](https://github.com/getpaseo/paseo) | 18.7k / Apache | ヘッドレスのデーモン。Web、iOS、Android、CLI。skill で引き継ぎ。個人 1 名 |
| [5dive](https://github.com/5dive-ai/5dive) | 61 / MIT | 公式 CLI を systemd で常駐。組織図・待ち行列・ゲート、5dive.yaml。`task cancel` で停止 |
| [Orca](https://github.com/stablyai/orca) | 79k / MIT | `orca serve` でヘッドレス、iOS / Android。埋め込み端末。委譲とワークフロー定義は無い。YC |
| [t3code](https://github.com/pingdotgg/t3code) | 23.7k / MIT | systemd の常駐、Web、iOS / Android。流れるチャット、Esc で停止。委譲は無い |
| [vicoa](https://github.com/vicoa-ai/vicoa) | 362 / AGPL | デーモン、Docker、Web / iOS / Android。Stop ボタン、チャットの隣に生の端末。2026-08 作成 |
| [intentic](https://github.com/intentic/intentic) | 46 / MIT | ノート PC から離してサーバへ移せる workspace、エージェントごとの Docker。"stoppable mid-thought" |
| [mjolnir](https://github.com/BrokkAi/mjolnir) | 64 / GPL | Claude Code と Codex を並行。Tailscale 経由の Web。Esc で中断 |
| [OpenClaw](https://github.com/openclaw/openclaw) | 390k / MIT | Claude Code を CLI のバックエンドで、Codex は定額で。Control UI。第一の位置付けは個人アシスタント |
| [cezar](https://github.com/open-mercato/cezar) | 253 / MIT | "No API key needed"。VPS に常駐。途中の文・ツール呼び出し・費用を生で。YAML で段ごとに runner |
| [garcon](https://github.com/cfal/garcon) | 88 / GPL | 自前の Web とスマホ。中断と停止。子チャットへ委譲 |
| [squid](https://github.com/agent-squid/squid) | 18 / MIT | 常駐、Tailscale。/stop。途中の出力とツールの動き |
| [mulmoterminal](https://github.com/receptron/mulmoterminal) | 225 / MIT | ブラウザの端末グリッド、実 PTY、スマホ |
| [waku](https://github.com/egoist/waku) | 1.5k / GPL | waku-daemon と Web。Escape で停止。stream-json |
| [tutti](https://github.com/nutthouse/tutti) | 128 / MIT | tutti.toml のワークフロー、Web ダッシュボード、個別の停止。3 か月のコミットが 1 件 |
| [cccc](https://github.com/ChesterRa/cccc) | 1.3k / Apache | デーモンと Web、端末のタイル、Stop Group、@all / @peers の宛先指定 |
| [claude-command-center](https://github.com/amirfish1/claude-command-center) | 173 / 現行は非商用 | Linux のヘッドレスとブラウザ。Pause で中断 |
| [synara](https://github.com/Emanuele-web04/synara) | 1.9k / MIT | ヘッドレスの Web 版。中断。子の活動を画面に出す。early-stage |
| [luvus](https://github.com/RizRiyz/luvus) | 922 / Apache | TUI が主。Luvus Web と遠隔の機械。端末 |

### 6.2 選別 (記述なし、55 本)

括弧の条件は、資料に満たすと読める記述が無かったもの。セットアップして S1 で確かめる。

- 記述なし H1 (13 本): [trinity](https://github.com/Abilityai/trinity)、[agent-of-empires](https://github.com/agent-of-empires/agent-of-empires)、[agentconnect](https://github.com/agentconnect-md/agentconnect)、[Archon](https://github.com/coleam00/Archon)、[gastown](https://github.com/gastownhall/gastown)、[herdr](https://github.com/herdrdev/herdr) と [collie](https://github.com/AltanS/collie)、[contrabass](https://github.com/junhoyeo/contrabass)、[kandev](https://github.com/kdlbs/kandev)、[taskuary](https://github.com/ldbumble/taskuary)、[podium](https://github.com/madeinorbit/podium)、[hermes-agent](https://github.com/NousResearch/hermes-agent)、[paperclip](https://github.com/paperclipai/paperclip)、[ruflo](https://github.com/ruvnet/ruflo)。
- 記述なし H5 (11 本): [ateam](https://github.com/clawnify/ateam)、[ai-devkit](https://github.com/codeaholicguy/ai-devkit)、[jean](https://github.com/coollabsio/jean)、[cyrus](https://github.com/cyrusagents/cyrus)、[bb](https://github.com/get-bb/bb)、[codey](https://github.com/its-ahoh/codey)、[OpenMausBot](https://github.com/milind-soni/OpenMausBot)、[codexia](https://github.com/milisp/codexia)、[omnigent](https://github.com/omnigent-ai/omnigent)、[oto-dock](https://github.com/OtoDock/oto-dock)、[vibe-tree](https://github.com/sahithvibudhi/vibe-tree)。
- 記述なし H1、H5 (8 本): [omg.dev](https://github.com/BennyKok/omg.dev)、[dev-3.0](https://github.com/h0x91b/dev-3.0)、[imcodes](https://github.com/im4codes/imcodes)、[Ghostex](https://github.com/maddada/Ghostex)、[amux](https://github.com/mixpeek/amux)、[pragma](https://github.com/pragma-sh/pragma)、[Fusion](https://github.com/Runfusion/Fusion)、[tlbx](https://github.com/tlbx-ai/tlbx)。
- 記述なし H5、H6 (6 本): [opentag](https://github.com/amplifthq/opentag)、[Pane](https://github.com/greenfield-inc/Pane)、[OpenHands](https://github.com/OpenHands/OpenHands)、[agor](https://github.com/preset-io/agor)、[proliferate](https://github.com/proliferate-ai/proliferate)、[opensession](https://github.com/tellahq/opensession)。
- 記述なし H1、H5、H6 (6 本): [ai-maestro](https://github.com/23blocks-OS/ai-maestro)、[mission-control](https://github.com/builderz-labs/mission-control)、[xum](https://github.com/coder/xum)、[Ivy-Tendril](https://github.com/Ivy-Interactive/Ivy-Tendril)、[sortie](https://github.com/sortie-ai/sortie)、[Octop](https://github.com/TencentCloud/Octop)。
- 記述なし H1、H2 (4 本): [agetor](https://github.com/alamops/agetor)、[claw-orchestrator](https://github.com/Enderfga/claw-orchestrator)、[openrig](https://github.com/mvschwarz/openrig)、[qm](https://github.com/yc-software/qm)。
- 記述なし H2 (3 本): [ai4kanban](https://github.com/ai4kanban/ai4kanban)、[cyclops](https://github.com/cyclops-team/cyclops)、[superset](https://github.com/superset-sh/superset)。
- 記述なし H6 (1 本): [goose](https://github.com/aaif-goose/goose)。
- 記述なし H2、H5 (1 本): [termany](https://github.com/thinkany-ai/termany)。
- 記述なし H2、H5、H6 (1 本): [kungfu](https://github.com/kungfu-systems/kungfu)。
- 記述なし H1、H2、H5、H6 (1 本): [companyhelm](https://github.com/CompanyHelm/companyhelm)。

### 6.3 棄却 (反した条件と根拠は findings.md の 5.3、5.4、5.5)

- H1 (Claude Code と Codex の両方を定額ログインで動かせない): cloudflare-os、rakazo、taOS、hivekeep、stagewise、devspace (フロントドアがベンダーの app で B の部品)、AgentsMesh (BYOK、BSL)、openchamber (OpenCode 専用)、forge-orchestrator (API キー)、octomux (Codex なし)、lionclaw (Claude Code なし)、mosoo-agent-driver (OpenAI の API キーのみ)、berd (Goose のみ)、CodeNomad (OpenCode)、Yao (CLI を起こさない)、takt (API キー。YAML の手順定義は部品として再考)、openswarm (Codex なし、macOS 専用)、Aperant (Claude Code のみ、デスクトップ、3 か月のコミット 0)、muxel (Codex なし、デスクトップ)、Friday (BYOK)、n8n、LangGraph Studio、Open WebUI、Mastra Studio。
- H2 (GUI の無い Linux に常駐できず、別の端末から操作できない) 2026-09-27: happy (Linux のデーモン運用の記述なし。同系の happier を選別へ回した)、emdash、traycer、Meldwork、zeron、munder-difflin、Orkas、agent-teams-ai、ouijit、agent-session-manager-desktop、tempest、monocode、runner、parallel-code、alas、clave、diri、fletch、GraphCode、supacode、superagent-desktop、tortie、hcom (常駐サービスなし。部品として再考)、openyak (Electron、Linux は作業中)、background-agents (Cloudflare Workers と Durable Objects の基盤)、collab-public と constellagent と vibecraft (デスクトップで、かつ 3 か月のコミットが無いか 1 件)、Crystal (2026-02 に終了)、Conductor.build (非公開ソース、Mac のみ)、Zed (デスクトップのみ)。
- H2 2026-09-28 (4 条件の判定で、反すると明記した記述を引用できたもの): agent-orchestrator (Untrivial。デーモンはデスクトップ app が動かし、"AO does not turn the local desktop product into a hosted multi-user service")、clideck ("CliDeck works on macOS and Windows.")、zaivern-code ("`--headless` is unimplemented in MVP")、dray、zuse、alethe-agents (いずれもデスクトップ app で、サーバの形の記述なし)、evoflux ("shipped as a desktop product")、nimbalyst ("couples the agent runtime and the GUI in one desktop process")、Dorothy ("Agent management and terminal features require the Electron app")。
- H3 (3 か月にコミットもリリースも無い、または保守終了の告知): ClawTeam、automaker、agx (ライセンスも無い)、takopi、shire、sandbox-agent、acp-ui、harnss、golutra、humanlayer (deprecated の告知)、Vibe Kanban (会社の解散)、Terragon (終了)。

### 6.4 部品

- 部品 (app ではなく、v0.4 で部品として再考): open-multi-agent、claudexor (複数アカウントの枠管理は R8 の部品)、crewplane、zenith。

### 6.5 決まっていないこと

- Claude を動かす形。Anthropic の規約は、手を加えていない Claude Code の実行ファイルに本人がログインする形を認め、第三者の製品が Claude Agent SDK や ACP の adapter を通して定額ログインで Claude を動かす形を認めていない (findings.md の 6 節)。選別で、各製品がどちらの形で Claude を動かすかを確かめ、評価記録に書く。後者の形の製品を候補から外すかはオーナーの判断。
- ミニ PC のヘッドレス環境で、個人契約のログイン (複製した認証ファイル) がそれぞれの製品でそのまま通るか。選別で確かめる。

## 7. 成果物

- 棄却台帳: 本文書 6 節を更新し続ける。
- 評価記録: `docs/reports/v0.3-<製品>-evaluation.md` と証拠。
- 3 本の提案: `docs/reports/v0.3-shortlist.md`。プレビューの URL、要件の判定表、オーナーの所見。
- 1 本の決定と切り分け: `docs/reports/v0.3-decision.md`。要件ごとの「OSS が満たす / skill・hook・設定で満たす / カスタム開発が要る」。

## 8. オーナーの判断の記録

### 2026-09-28

- 3 本に残す必須の条件は、Claude Code と Codex の両方に同じ画面から定額ログインで仕事を頼めること (R1)、両者の間で仕事を渡せて渡した先の進行が見えること (R2)、ミニ PC に常駐して開発 PC とスマホから開けること (R4) に、次の 2 つを加える。
  - 途中で止められること (R7)。「途中で止められない、はあり得ないので、それはmust」。
  - 途中の出力が見えること (R13)。「1入力1応答の形で束縛されており、途中出力がなくモデルの状態を俯瞰できないものはng」。
- 候補のうち、資料だけで落とせるものは落とす。「静的に落とせる候補は落とせ」。
- フローの途中へのセルの挿入と、初期指示を書き換えて次の回から効かせる操作は、要件から外してよい。
- ミニ PC で動いている v0.2 のコンテナは止めてよい。何を残すかは任せる。
- 計画を main に入れ、ミニ PC と GitHub に送ってよい。
