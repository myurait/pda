# フロントドアの OSS 調査 (2026-09-27)

- 種別: 調査記録。[docs/plan-v0.3.md](../../plan-v0.3.md) の候補と棄却の根拠。
- 範囲: v0.3 の 3 つの形 (A 判定器 / B ベンダー app / C サードパーティ app) のうち、A の可視化層、B のベンダー app が持つ可視化、C の製品の母集団と絞り込み。
- 数値は 2026-09-27 に GitHub の API (GraphQL) で取った値。コミットとリリースは 2026-06-27 からの 3 か月。リリースは 25 件までしか数えていないので、25 は 25 以上を意味する。
- 製品ごとの所見は [findings.md](findings.md) に置く。

## 1. 方法

1. 母集団。GitHub の topic 検索 (ai-orchestrator、agent-orchestration、claude-code、codex-cli、parallel-agents、agent-client-protocol、および自由語 "claude code codex parallel agents") と、[awesome-agent-orchestrators](https://github.com/andyrewlee/awesome-agent-orchestrators) の 7 分類 (端末、デスクトップと Web、スウォーム、ループランナー、タスクランナー、基盤、個人アシスタント、休止) を合わせ、説明文で C の条件に当たりそうな 120 件を選んだ。
2. メタデータ。120 件の星、ライセンス、作成日、最終 push、3 か月のリリース数、3 か月のコミット数、アーカイブの有無を API で取った (2 節)。
3. 一次資料。34 件について README と公式文書を読み、7 項目 (対応エージェントと繋ぎ方、会話する相手、常駐と端末、協調とワークフローの定義、画面と介入、プロトコル、運営) を引用付きで埋めた (findings.md)。
4. 分類。硬い条件 (H1〜H4、計画 5.3) に反する証拠があるものを机上で棄却し、残りを一次候補と二次候補に分けた。

## 2. 母集団のメタデータ

列は、製品、星、ライセンス、作成、最終 push、3 か月のリリース、3 か月のコミット、分類。分類の語は、一次 (一次候補)、二次 (二次候補)、棄却 H1〜H4 (机上の棄却と反した条件)、部品 (app ではなく部品として再考)、対象外 (説明文の段階で C の条件に当たらない。理由を併記)。

| 製品 | 星 | ライセンス | 作成 | push | リリース | コミット | 分類 |
|---|---|---|---|---|---|---|---|
| openclaw/openclaw | 390621 | 独自表記 | 2025-11-24 | 2026-09-27 | 25 | 38603 | 二次 (個人アシスタント) |
| NousResearch/hermes-agent | 249326 | MIT | 2025-07-22 | 2026-09-27 | 18 | 31785 | 二次 (個人アシスタント) |
| OpenHands/OpenHands | 89260 | MIT | 2024-03-13 | 2026-09-26 | 25 | 685 | 一次 |
| paperclipai/paperclip | 88225 | MIT | 2026-03-02 | 2026-09-27 | 11 | 1738 | 二次 |
| stablyai/orca | 79166 | MIT | 2026-03-17 | 2026-09-27 | 25 | 6448 | 二次 |
| ruvnet/ruflo | 73353 | MIT | 2025-06-02 | 2026-09-27 | 25 | 650 | 対象外 (Claude 向けスウォームの枠組み、CLI を包む app ではない) |
| multica-ai/multica | 51419 | 独自条項 | 2026-01-13 | 2026-09-27 | 25 | 1716 | 一次 |
| herdrdev/herdr | 40940 | Apache-2.0 | 2026-03-27 | 2026-09-27 | 25 | 811 | 二次 (端末の層) |
| slopus/happy | 23921 | MIT | 2025-07-18 | 2026-09-22 | 9 | 310 | 対象外 (happier の前身、クライアントのみ) |
| pingdotgg/t3code | 23660 | MIT | 2026-02-08 | 2026-09-27 | 25 | 2607 | 二次 |
| coleam00/Archon | 23564 | MIT | 2025-02-07 | 2026-09-26 | 9 | 1758 | 二次 |
| getpaseo/paseo | 18668 | Apache-2.0 | 2025-10-13 | 2026-09-26 | 25 | 1390 | 一次 |
| gastownhall/gastown | 18199 | MIT | 2025-12-16 | 2026-09-18 | 0 | 161 | 対象外 (端末とワークツリーの管理、最終リリース 2026-06) |
| yc-software/qm | 15260 | MIT | 2026-07-29 | 2026-09-27 | 13 | 696 | 対象外 (Slack と Web の多人数向け。全ツール呼び出しで承認が要る) |
| superset-sh/superset | 14669 | NOASSERTION | 2025-10-21 | 2026-09-27 | 25 | 1542 | 棄却 H2 |
| Untrivial-ai/agent-orchestrator | 12410 | Apache-2.0 | 2026-02-13 | 2026-09-27 | 25 | 1398 | 二次 (デスクトップ app がデーモンを持つ。ヘッドレスの可否が未確認) |
| openchamber/openchamber | 10714 | MIT | 2025-09-11 | 2026-09-27 | 25 | 2107 | 対象外 (OpenCode 専用) |
| omnigent-ai/omnigent | 10275 | Apache-2.0 | 2026-06-11 | 2026-09-27 | 16 | 3298 | 一次 |
| cloudflare/cloudflare-os | 10150 | Apache-2.0 | 2026-04-15 | 2026-09-26 | 0 | 407 | 対象外 (Cloudflare Workers 上の会社 OS、CLI を起こさない) |
| YaoApp/yao | 8030 | 独自条項 | 2021-09-06 | 2026-09-27 | 24 | 152 | 棄却 H1 |
| chaitanyagiri/munder-difflin | 8025 | MIT | 2026-05-31 | 2026-09-27 | 21 | 754 | 棄却 H2 |
| open-multi-agent/open-multi-agent | 6957 | MIT | 2026-03-31 | 2026-09-25 | 15 | 259 | 部品 |
| stagewise-io/stagewise | 6822 | AGPL-3.0 | 2025-04-26 | 2026-09-23 | 25 | 311 | 対象外 (IDE 拡張、CLI を包む app ではない) |
| builderz-labs/mission-control | 6273 | MIT | 2026-02-13 | 2026-09-26 | 3 | 170 | 対象外 (3 か月のコミット 170、リリース 3 で活動が細い。OpenClaw 向け) |
| generalaction/emdash | 5849 | Apache-2.0 | 2025-08-28 | 2026-09-27 | 25 | 2415 | 棄却 H2 |
| HKUDS/ClawTeam | 5544 | MIT | 2026-03-17 | 2026-05-09 | 0 | 0 | 棄却 H3 |
| TencentCloud/Octop | 5182 | MIT | 2026-07-08 | 2026-09-27 | 6 | 634 | 対象外 (個人アシスタント、CLI を起こす記述なし) |
| Waishnav/devspace | 5143 | MIT | 2026-06-14 | 2026-09-25 | 10 | 645 | 対象外 (MCP でサンドボックスを出す部品。フロントドアはベンダーのチャット app、つまり B) |
| kungfu-systems/kungfu | 4524 | Apache-2.0 | 2017-11-15 | 2026-09-19 | 12 | 4105 | 対象外 (作業の引き継ぎの枠組み、画面の記述なし) |
| get-bb/bb | 3949 | MIT | 2026-02-24 | 2026-09-26 | 25 | 2191 | 二次 |
| golutra/golutra | 3846 | NOASSERTION | 2026-02-15 | 2026-09-24 | 0 | 0 | 棄却 H3 (3 か月のコミット 0) |
| milind-soni/OpenMausBot | 3593 | Apache-2.0 | 2026-08-11 | 2026-09-27 | 25 | 2853 | 二次 |
| agent-of-empires/agent-of-empires | 3290 | MIT | 2026-01-09 | 2026-09-27 | 16 | 989 | 二次 |
| ColeMurray/background-agents | 3291 | MIT | 2026-01-25 | 2026-09-27 | 0 | 969 | 対象外 (クラウドのサンドボックスで PR を作る自動化) |
| AutoMaker-Org/automaker | 3221 | NOASSERTION | 2025-12-07 | 2026-05-22 | 0 | 0 | 棄却 H3 |
| elie222/rakazo | 2986 | Apache-2.0 | 2026-08-13 | 2026-09-27 | 8 | 944 | 対象外 (個人アシスタント。CLI を起こす記述なし) |
| AgentsMesh/AgentsMesh | 2354 | NOASSERTION | 2026-02-28 | 2026-09-23 | 5 | 17 | 対象外 (3 か月のコミット 17) |
| zeronsh/zeron | 2245 | MIT | 2026-07-20 | 2026-09-27 | 25 | 1644 | 棄却 H2 |
| 777genius/agent-teams-ai | 2173 | AGPL-3.0 | 2026-02-21 | 2026-09-27 | 13 | 2772 | 棄却 H2 |
| Orkas-AI/Orkas | 2127 | MIT | 2026-04-29 | 2026-09-27 | 10 | 277 | 棄却 H2 |
| coder/xum | 2038 | AGPL-3.0 | 2025-09-17 | 2026-09-27 | 10 | 863 | 対象外 (デスクトップ app) |
| nimbalyst/nimbalyst | 1784 | MIT | 2025-10-30 | 2026-09-24 | 25 | 1274 | 対象外 (デスクトップ app。スマホは監視のみ) |
| happier-dev/happier | 1737 | MIT | 2025-12-16 | 2026-09-27 | 25 | 2911 | 一次 |
| codeaholicguy/ai-devkit | 1636 | Apache-2.0 | 2025-10-14 | 2026-09-27 | 25 | 220 | 対象外 (tmux の CLI 制御、画面は TUI) |
| rivet-dev/sandbox-agent | 1575 | Apache-2.0 | 2026-01-25 | 2026-06-19 | 0 | 0 | 棄却 H3 |
| traycerai/traycer | 1528 | MIT | 2024-05-11 | 2026-09-27 | 25 | 1399 | 対象外 (説明文からは自前運用の記述が取れず、未読) |
| agentconnect-md/agentconnect | 1436 | Apache-2.0 | 2026-07-24 | 2026-09-27 | 25 | 2267 | 二次 |
| preset-io/agor | 1413 | NOASSERTION | 2025-10-04 | 2026-09-27 | 0 | 693 | 対象外 (最終リリース 2026-03、未読) |
| nrslib/takt | 1390 | MIT | 2026-01-25 | 2026-09-26 | 0 | 585 | 棄却 H1 (部品として再考) |
| coollabsio/jean | 1296 | Apache-2.0 | 2026-01-23 | 2026-09-27 | 21 | 626 | 二次 |
| ChesterRa/cccc | 1254 | Apache-2.0 | 2025-08-15 | 2026-09-26 | 17 | 342 | 対象外 (グループチャット型の協調、未読) |
| Runfusion/Fusion | 1247 | MIT | 2026-04-13 | 2026-09-27 | 25 | 4221 | 二次 |
| AltanS/collie | 1111 | MIT | 2026-06-28 | 2026-09-27 | 25 | 1761 | 二次 (herdr と組) |
| banteg/takopi | 1051 | MIT | 2025-12-29 | 2026-05-25 | 0 | 0 | 棄却 H3 |
| im4codes/imcodes | 971 | MIT | 2026-03-18 | 2026-09-27 | 25 | 790 | 対象外 (説明文がエージェント間の IM。未読) |
| RizRiyz/luvus | 922 | Apache-2.0 | 2026-06-22 | 2026-09-27 | 25 | 492 | 対象外 (未読) |
| milisp/codexia | 920 | MIT | 2025-08-13 | 2026-09-25 | 23 | 288 | 対象外 (Codex と Claude Code のワークステーション。デスクトップ) |
| kdlbs/kandev | 849 | AGPL-3.0 | 2026-01-09 | 2026-09-27 | 25 | 2035 | 一次 |
| thesongzhu/Friday | 838 | MIT | 2026-03-12 | 2026-07-20 | 0 | 313 | 棄却 H3 (最終リリース 2026-05、push 2026-07) |
| cyrusagents/cyrus | 830 | Apache-2.0 | 2025-04-19 | 2026-09-24 | 6 | 68 | 対象外 (課題追跡から起動する背景エージェント) |
| openswarm-ai/openswarm | 820 | AGPL-3.0 | 2026-03-13 | 2026-09-23 | 25 | 1122 | 棄却 H1、H2 |
| 23blocks-OS/ai-maestro | 799 | MIT | 2025-10-10 | 2026-09-25 | 25 | 158 | 対象外 (Codex の記述なし、未読) |
| openyak/openyak | 703 | Apache-2.0 | 2026-03-20 | 2026-09-05 | 3 | 69 | 対象外 (活動が細い) |
| mvschwarz/openrig | 599 | Apache-2.0 | 2026-04-01 | 2026-09-27 | 25 | 1613 | 対象外 (未読。Claude Code と Codex を 1 系にする harness) |
| Abilityai/trinity | 589 | Apache-2.0 | 2025-12-10 | 2026-09-27 | 8 | 244 | 対象外 (未読) |
| Enderfga/claw-orchestrator | 583 | MIT | 2026-01-30 | 2026-09-26 | 25 | 191 | 二次 |
| jaylfc/taOS | 552 | AGPL-3.0 | 2026-04-05 | 2026-09-27 | 25 | 2222 | 対象外 (個人アシスタント OS) |
| BennyKok/omg.dev | 541 | MIT | 2026-06-17 | 2026-09-27 | 25 | 2973 | 二次 |
| aannoo/hcom | 521 | MIT | 2025-07-21 | 2026-09-26 | 4 | 116 | 対象外 (端末間のメッセージ、画面なし) |
| proliferate-ai/proliferate | 507 | AGPL-3.0 | 2026-04-30 | 2026-09-27 | 25 | 1743 | 対象外 (未読) |
| mixpeek/amux | 505 | MIT + Commons Clause | 2026-02-18 | 2026-09-27 | 1 | 5264 | 二次 |
| greenfield-inc/Pane | 492 | NOASSERTION | 2026-02-27 | 2026-09-27 | 25 | 587 | 対象外 (端末専用、未読) |
| razzant/claudexor | 488 | MIT | 2026-06-05 | 2026-09-26 | 25 | 1794 | 部品 |
| formulahendry/acp-ui | 486 | MIT | 2026-01-31 | 2026-05-25 | 0 | 0 | 棄却 H3 |
| thinkany-ai/termany | 440 | NOASSERTION | 2026-06-29 | 2026-09-24 | 25 | 180 | 対象外 (端末) |
| tellahq/opensession | 386 | MIT | 2026-06-08 | 2026-09-26 | 25 | 6217 | 二次 |
| OpenSource03/harnss | 378 | MIT | 2026-02-19 | 2026-08-10 | 0 | 0 | 棄却 H3 |
| vicoa-ai/vicoa | 362 | AGPL-3.0 | 2026-08-28 | 2026-09-27 | 15 | 159 | 二次 |
| Charlie85270/Dorothy | 348 | MIT | 2026-01-24 | 2026-07-07 | 1 | 5 | 棄却 H3 |
| Intelligent-Internet/zenith | 314 | Apache-2.0 | 2026-05-08 | 2026-09-06 | 0 | 13 | 対象外 (活動が細い) |
| h0x91b/dev-3.0 | 299 | Apache-2.0 | 2026-02-18 | 2026-09-27 | 25 | 1076 | 対象外 (kanban と tmux、未読) |
| sahithvibudhi/vibe-tree | 267 | MIT | 2025-07-29 | 2026-07-25 | 1 | 72 | 棄却 H3 |
| open-mercato/cezar | 253 | MIT | 2026-05-19 | 2026-09-27 | 9 | 1071 | 対象外 (未読) |
| Ryder-Sun/Meldwork | 231 | Apache-2.0 | 2026-07-29 | 2026-09-17 | 6 | 212 | 対象外 (未読) |
| receptron/mulmoterminal | 225 | MIT | 2026-06-14 | 2026-09-27 | 25 | 5387 | 対象外 (端末グリッド) |
| junhoyeo/contrabass | 222 | Apache-2.0 | 2026-03-05 | 2026-07-17 | 1 | 51 | 棄却 H3 |
| swarajbachu/zuse | 209 | AGPL-3.0 | 2026-05-02 | 2026-09-26 | 25 | 432 | 対象外 (クラウドのエージェント) |
| Ivy-Interactive/Ivy-Tendril | 198 | NOASSERTION | 2026-04-15 | 2026-09-15 | 25 | 2334 | 対象外 (未読) |
| sortie-ai/sortie | 192 | Apache-2.0 | 2026-03-17 | 2026-09-26 | 14 | 1389 | 対象外 (課題追跡から起動) |
| OtoDock/oto-dock | 187 | NOASSERTION | 2026-07-09 | 2026-09-15 | 13 | 27 | 対象外 (FSL-1.1、活動が細い) |
| amirfish1/claude-command-center | 173 | NOASSERTION | 2026-04-13 | 2026-09-27 | 25 | 3386 | 対象外 (未読) |
| nxtg-ai/forge-orchestrator | 161 | NOASSERTION | 2026-02-09 | 2026-09-26 | 3 | 41 | 対象外 (活動が細い) |
| rustykuntz/clideck | 159 | MIT | 2026-03-03 | 2026-09-22 | 14 | 51 | 対象外 (活動が細い) |
| nutthouse/tutti | 128 | MIT | 2026-03-12 | 2026-07-28 | 0 | 1 | 棄却 H3 |
| ldbumble/taskuary | 124 | MIT | 2026-08-17 | 2026-09-26 | 25 | 1652 | 対象外 (受信箱の自動化) |
| tlbx-ai/tlbx | 112 | AGPL-3.0 | 2025-12-29 | 2026-09-27 | 25 | 510 | 対象外 (端末の多重化) |
| monorepo-labs/dray | 101 | Apache-2.0 | 2026-07-25 | 2026-09-26 | 25 | 598 | 対象外 (デスクトップ) |
| cfal/garcon | 88 | NOASSERTION | 2026-02-23 | 2026-09-27 | 2 | 615 | 対象外 (ライセンス未確認、未読) |
| alamops/agetor | 79 | MIT | 2026-05-16 | 2026-09-24 | 13 | 182 | 対象外 (未読) |
| CompanyHelm/companyhelm | 76 | MIT | 2026-03-12 | 2026-08-28 | 0 | 2 | 棄却 H3 |
| langgenius/mosoo-agent-driver | 74 | Apache-2.0 | 2026-06-05 | 2026-09-23 | 0 | 58 | 部品 (Dify の作者による実行の橋渡し) |
| BrokkAi/mjolnir | 64 | GPL-3.0 | 2026-05-18 | 2026-09-27 | 25 | 3314 | 二次 |
| MarlBurroW/hivekeep | 63 | MIT | 2026-06-07 | 2026-09-26 | 1 | 122 | 対象外 (個人アシスタント) |
| 5dive-ai/5dive | 61 | MIT | 2026-05-15 | 2026-09-27 | 25 | 1869 | 二次 |
| tacyan/zaivern-code | 52 | Apache-2.0 | 2026-07-20 | 2026-09-25 | 25 | 844 | 対象外 (デスクトップ) |
| intentic/intentic | 46 | MIT | 2026-08-04 | 2026-09-27 | 25 | 3697 | 二次 |
| crewplaneai/crewplane | 40 | Apache-2.0 | 2026-06-24 | 2026-09-25 | 18 | 94 | 部品 (CLI のワークフロー) |
| victor36max/shire | 40 | MIT | 2026-03-17 | 2026-05-03 | 0 | 0 | 棄却 H3 |
| ai4kanban/ai4kanban | 38 | Apache-2.0 | 2026-07-10 | 2026-09-27 | 16 | 771 | 対象外 (未読) |
| ramarlina/agx | 29 | なし | 2026-02-02 | 2026-05-06 | 0 | 0 | 棄却 H3、H4 |
| madeinorbit/podium | 23 | Apache-2.0 | 2026-06-02 | 2026-09-26 | 3 | 9402 | 二次 |
| ShreyPaharia/octomux | 22 | MIT | 2026-03-09 | 2026-09-18 | 6 | 493 | 対象外 (Claude Code と Cursor のみ) |
| moshthepitt/lionclaw | 19 | MIT | 2026-03-12 | 2026-09-01 | 0 | 79 | 対象外 (活動が細い) |
| agent-squid/squid | 18 | MIT | 2026-05-21 | 2026-09-26 | 6 | 665 | 対象外 (未読) |
| its-ahoh/codey | 15 | MIT | 2026-02-20 | 2026-09-27 | 25 | 266 | 対象外 (macOS app) |
| clawnify/ateam | 13 | NOASSERTION | 2026-06-03 | 2026-09-26 | 25 | 214 | 対象外 (macOS と iPhone) |
| cyclops-team/cyclops | 12 | MIT | 2026-08-01 | 2026-09-08 | 2 | 952 | 対象外 (端末) |
| evoelsewhere/evoflux | 10 | Apache-2.0 | 2026-08-03 | 2026-09-26 | 16 | 1349 | 対象外 (デスクトップ) |
| pragma-sh/pragma | 10 | AGPL-3.0 | 2026-06-11 | 2026-09-27 | 25 | 967 | 対象外 (デスクトップ、未読) |

「未読」と書いた製品は、説明文の分類だけで一次資料を読んでいない。二次候補の選別が終わった後、未読のうち説明文が C の条件に当たるものは一次資料を読んで再分類する。

## 3. A の可視化層と B のベンダー app

A と B の調査結果は findings.md の 1 節と 2 節に置く。要点は次のとおり。

- Conductor OSS 3.32.4 の画面は、実行の検索、図 (DO_WHILE、DYN. FORK、JOIN を描く)、時間軸、入出力、Queue Monitor、Agent Executions を持つ。チャットで仕事を頼む画面と、実行器 (ワーカー) の一覧は無い。Agents 機能は Conductor 自身の LLM エージェント (モデル名と API キー) の実行系で、Claude Code や Codex のセッションを包む機構ではない。
- Claude Code は CLI で subagent を入れ子の木に、/workflows でフェーズの木に表示する。デスクトップ app は Tasks ペイン、Web は一覧と差分、スマホは cloud セッションと Remote Control。Codex は Subagents パネル (Active / Done) と cloud のタスク一覧、ChatGPT app で監視と承認。どちらも図は無く、Claude と Codex をまたいだ全体像は無い。
- 後付けの観測製品は Datadog Lapdog (Claude Code と Codex)、Langfuse (両方、hooks)、o11y-dev/opentelemetry-hooks (8 種)、SigNoz と claude-code-otel と claude_telemetry (Claude Code のみ)。
- ACP の仕様は v1.9.1 (2026-09-18)、claude-agent-acp と codex-acp は 8 月以降それぞれ 20 回以上のリリースで、ACP の組織が保守する。subagent、hooks、skills が ACP 越しにどう見えるかを書いた公式文書は無い。
