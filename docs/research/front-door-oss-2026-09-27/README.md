# フロントドアの OSS 調査 (2026-09-27)

- 種別: 調査記録。[docs/plan-v0.3.md](../../plan-v0.3.md) の候補と棄却の根拠。
- 範囲: v0.3 の 3 つの形 (A 判定器 / B ベンダー app / C サードパーティ app) のうち、A の可視化層、B のベンダー app が持つ可視化、C の製品の母集団と絞り込み。
- 更新: 2026-09-28 (必須条件の判定を反映)。
- 数値は 2026-09-27 に GitHub の API (GraphQL) で取った値。コミットとリリースは 2026-06-27 からの 3 か月。リリースは 25 件までしか数えていないので、25 は 25 以上を意味する。
- 製品ごとの所見は [findings.md](findings.md) に置く。

## 1. 方法

1. 母集団。GitHub の topic 検索 (ai-orchestrator、agent-orchestration、claude-code、codex-cli、parallel-agents、agent-client-protocol、および自由語 "claude code codex parallel agents") と、[awesome-agent-orchestrators](https://github.com/andyrewlee/awesome-agent-orchestrators) の 7 分類 (端末、デスクトップと Web、スウォーム、ループランナー、タスクランナー、基盤、個人アシスタント、休止) を合わせ、説明文で C の条件に当たりそうな 147 件を選んだ。
2. メタデータ。147 件の星、ライセンス、作成日、最終 push、3 か月のリリース数、3 か月のコミット数、アーカイブの有無を API で取った (2 節)。
3. 一次資料。34 件について README と公式文書を読み、7 項目 (対応エージェントと繋ぎ方、会話する相手、常駐と端末、協調とワークフローの定義、画面と介入、プロトコル、運営) を引用付きで埋めた (findings.md の 5.1、5.2)。99 件については README と公式文書で棄却の条件 H1 と H2 だけを確かめた (findings.md の 5.3)。残りは 2026-09-18 の調査で読んだもの (OpenClaw、Hermes、Paperclip) と、メタデータの時点で H3 に当たるものである。
4. 分類 (2026-09-27)。棄却の条件 H1〜H4 に反する証拠があるものを棄却し、残りを選別の候補にした。
5. 必須条件の判定 (2026-09-28)。オーナーが必須の条件に「途中で止められる」「途中の出力が見える」を加えたので、それまで棄却していない 84 件について、H1 (定額ログイン)、H2 (常駐と遠隔操作)、H5 (途中で止める)、H6 (途中の出力) を README と公式文書で確かめた (findings.md の 5.4)。反すると明記した記述を引用できたものを棄却し、残りを選別へ回した。
6. 分類の語は、選別 (4 条件の記述あり)、選別 (記述なし: 括弧の条件を満たす記述が資料に無い)、棄却 H# (反した条件)、部品 (app ではなく v0.4 で部品として再考) の 4 つで、計画と findings.md と同じ語を使う。

## 2. 母集団のメタデータと分類

列は、製品、星、ライセンス、作成、最終 push、3 か月のリリース、3 か月のコミット、分類。

| 製品 | 星 | ライセンス | 作成 | push | リリース | コミット | 分類 |
|---|---|---|---|---|---|---|---|
| openclaw/openclaw | 390621 | MIT (本文。表示は NOASSERTION) | 2025-11-24 | 2026-09-27 | 25 | 38603 | 選別 (4 条件の記述あり) |
| NousResearch/hermes-agent | 249326 | MIT | 2025-07-22 | 2026-09-27 | 18 | 31785 | 選別 (記述なし: H1) |
| OpenHands/OpenHands | 89260 | MIT | 2024-03-13 | 2026-09-26 | 25 | 685 | 選別 (記述なし: H5、H6) |
| paperclipai/paperclip | 88225 | MIT | 2026-03-02 | 2026-09-27 | 11 | 1738 | 選別 (記述なし: H1) |
| stablyai/orca | 79166 | MIT | 2026-03-17 | 2026-09-27 | 25 | 6448 | 選別 (4 条件の記述あり) |
| ruvnet/ruflo | 73353 | MIT | 2025-06-02 | 2026-09-27 | 25 | 650 | 選別 (記述なし: H1) |
| multica-ai/multica | 51419 | 独自条項 | 2026-01-13 | 2026-09-27 | 25 | 1716 | 選別 (4 条件の記述あり) |
| herdrdev/herdr | 40940 | Apache-2.0 | 2026-03-27 | 2026-09-27 | 25 | 811 | 選別 (記述なし: H1) |
| slopus/happy | 23921 | MIT | 2025-07-18 | 2026-09-22 | 9 | 310 | 棄却 H2 (Linux のデーモン運用の記述なし。happier を優先) |
| pingdotgg/t3code | 23660 | MIT | 2026-02-08 | 2026-09-27 | 25 | 2607 | 選別 (4 条件の記述あり) |
| coleam00/Archon | 23564 | MIT | 2025-02-07 | 2026-09-26 | 9 | 1758 | 選別 (記述なし: H1) |
| getpaseo/paseo | 18668 | Apache-2.0 | 2025-10-13 | 2026-09-26 | 25 | 1390 | 選別 (4 条件の記述あり) |
| gastownhall/gastown | 18199 | MIT | 2025-12-16 | 2026-09-18 | 0 | 161 | 選別 (記述なし: H1) |
| yc-software/qm | 15260 | MIT | 2026-07-29 | 2026-09-27 | 13 | 696 | 選別 (記述なし: H1、H2) |
| superset-sh/superset | 14669 | Elastic License 2.0 | 2025-10-21 | 2026-09-27 | 25 | 1542 | 選別 (記述なし: H2) |
| Untrivial-ai/agent-orchestrator | 12410 | Apache-2.0 | 2026-02-13 | 2026-09-27 | 25 | 1398 | 棄却 H2 (2026-09-28) |
| openchamber/openchamber | 10714 | MIT | 2025-09-11 | 2026-09-27 | 25 | 2107 | 棄却 H1 (OpenCode 専用) |
| omnigent-ai/omnigent | 10275 | Apache-2.0 | 2026-06-11 | 2026-09-27 | 16 | 3298 | 選別 (記述なし: H5) |
| cloudflare/cloudflare-os | 10150 | Apache-2.0 | 2026-04-15 | 2026-09-26 | 0 | 407 | 棄却 H1 |
| YaoApp/yao | 8030 | 修正版 Apache | 2021-09-06 | 2026-09-27 | 24 | 152 | 棄却 H1 |
| chaitanyagiri/munder-difflin | 8025 | MIT | 2026-05-31 | 2026-09-27 | 21 | 754 | 棄却 H2 |
| open-multi-agent/open-multi-agent | 6957 | MIT | 2026-03-31 | 2026-09-25 | 15 | 259 | 部品 |
| stagewise-io/stagewise | 6822 | AGPL-3.0 | 2025-04-26 | 2026-09-23 | 25 | 311 | 棄却 H1 |
| builderz-labs/mission-control | 6273 | MIT | 2026-02-13 | 2026-09-26 | 3 | 170 | 選別 (記述なし: H1、H5、H6) |
| generalaction/emdash | 5849 | Apache-2.0 | 2025-08-28 | 2026-09-27 | 25 | 2415 | 棄却 H2 |
| HKUDS/ClawTeam | 5544 | MIT | 2026-03-17 | 2026-05-09 | 0 | 0 | 棄却 H3 |
| TencentCloud/Octop | 5182 | MIT | 2026-07-08 | 2026-09-27 | 6 | 634 | 選別 (記述なし: H1、H5、H6) |
| Waishnav/devspace | 5143 | MIT | 2026-06-14 | 2026-09-25 | 10 | 645 | 棄却 H1 (フロントドアがベンダーの app) |
| kungfu-systems/kungfu | 4524 | Apache-2.0 | 2017-11-15 | 2026-09-19 | 12 | 4105 | 選別 (記述なし: H2、H5、H6) |
| get-bb/bb | 3949 | MIT | 2026-02-24 | 2026-09-26 | 25 | 2191 | 選別 (記述なし: H5) |
| golutra/golutra | 3846 | NOASSERTION | 2026-02-15 | 2026-09-24 | 0 | 0 | 棄却 H3 |
| milind-soni/OpenMausBot | 3593 | Apache-2.0 | 2026-08-11 | 2026-09-27 | 25 | 2853 | 選別 (記述なし: H5) |
| agent-of-empires/agent-of-empires | 3290 | MIT | 2026-01-09 | 2026-09-27 | 16 | 989 | 選別 (記述なし: H1) |
| ColeMurray/background-agents | 3291 | MIT | 2026-01-25 | 2026-09-27 | 0 | 969 | 棄却 H2 (Cloudflare Workers の基盤) |
| AutoMaker-Org/automaker | 3221 | NOASSERTION | 2025-12-07 | 2026-05-22 | 0 | 0 | 棄却 H3 |
| elie222/rakazo | 2986 | Apache-2.0 | 2026-08-13 | 2026-09-27 | 8 | 944 | 棄却 H1 |
| AgentsMesh/AgentsMesh | 2354 | BSL-1.1 | 2026-02-28 | 2026-09-23 | 5 | 17 | 棄却 H1 (BYOK) |
| zeronsh/zeron | 2245 | MIT | 2026-07-20 | 2026-09-27 | 25 | 1644 | 棄却 H2 |
| 777genius/agent-teams-ai | 2173 | AGPL-3.0 | 2026-02-21 | 2026-09-27 | 13 | 2772 | 棄却 H2 |
| Orkas-AI/Orkas | 2127 | MIT | 2026-04-29 | 2026-09-27 | 10 | 277 | 棄却 H2 |
| coder/xum | 2038 | AGPL-3.0 | 2025-09-17 | 2026-09-27 | 10 | 863 | 選別 (記述なし: H1、H5、H6) |
| nimbalyst/nimbalyst | 1784 | MIT | 2025-10-30 | 2026-09-24 | 25 | 1274 | 棄却 H2 (2026-09-28) |
| happier-dev/happier | 1737 | MIT | 2025-12-16 | 2026-09-27 | 25 | 2911 | 選別 (4 条件の記述あり) |
| codeaholicguy/ai-devkit | 1636 | Apache-2.0 | 2025-10-14 | 2026-09-27 | 25 | 220 | 選別 (記述なし: H5) |
| rivet-dev/sandbox-agent | 1575 | Apache-2.0 | 2026-01-25 | 2026-06-19 | 0 | 0 | 棄却 H3 |
| traycerai/traycer | 1528 | MIT | 2024-05-11 | 2026-09-27 | 25 | 1399 | 棄却 H2 |
| agentconnect-md/agentconnect | 1436 | Apache-2.0 | 2026-07-24 | 2026-09-27 | 25 | 2267 | 選別 (記述なし: H1) |
| preset-io/agor | 1413 | BUSL-1.1 | 2025-10-04 | 2026-09-27 | 0 | 693 | 選別 (記述なし: H5、H6) |
| nrslib/takt | 1390 | MIT | 2026-01-25 | 2026-09-26 | 0 | 585 | 棄却 H1 (部品として再考) |
| coollabsio/jean | 1296 | Apache-2.0 | 2026-01-23 | 2026-09-27 | 21 | 626 | 選別 (記述なし: H5) |
| ChesterRa/cccc | 1254 | Apache-2.0 | 2025-08-15 | 2026-09-26 | 17 | 342 | 選別 (4 条件の記述あり) |
| Runfusion/Fusion | 1247 | MIT | 2026-04-13 | 2026-09-27 | 25 | 4221 | 選別 (記述なし: H1、H5) |
| AltanS/collie | 1111 | MIT | 2026-06-28 | 2026-09-27 | 25 | 1761 | 選別 (記述なし: H1) |
| banteg/takopi | 1051 | MIT | 2025-12-29 | 2026-05-25 | 0 | 0 | 棄却 H3 |
| im4codes/imcodes | 971 | MIT | 2026-03-18 | 2026-09-27 | 25 | 790 | 選別 (記述なし: H1、H5) |
| RizRiyz/luvus | 922 | Apache-2.0 | 2026-06-22 | 2026-09-27 | 25 | 492 | 選別 (4 条件の記述あり) |
| milisp/codexia | 920 | MIT | 2025-08-13 | 2026-09-25 | 23 | 288 | 選別 (記述なし: H5) |
| kdlbs/kandev | 849 | AGPL-3.0 | 2026-01-09 | 2026-09-27 | 25 | 2035 | 選別 (記述なし: H1) |
| thesongzhu/Friday | 838 | MIT | 2026-03-12 | 2026-07-20 | 0 | 313 | 棄却 H1 (BYOK) |
| cyrusagents/cyrus | 830 | Apache-2.0 | 2025-04-19 | 2026-09-24 | 6 | 68 | 選別 (記述なし: H5) |
| openswarm-ai/openswarm | 820 | AGPL-3.0 | 2026-03-13 | 2026-09-23 | 25 | 1122 | 棄却 H1、H2 |
| 23blocks-OS/ai-maestro | 799 | MIT | 2025-10-10 | 2026-09-25 | 25 | 158 | 選別 (記述なし: H1、H5、H6) |
| openyak/openyak | 703 | Apache-2.0 | 2026-03-20 | 2026-09-05 | 3 | 69 | 棄却 H2 |
| mvschwarz/openrig | 599 | Apache-2.0 | 2026-04-01 | 2026-09-27 | 25 | 1613 | 選別 (記述なし: H1、H2) |
| Abilityai/trinity | 589 | Apache-2.0 | 2025-12-10 | 2026-09-27 | 8 | 244 | 選別 (記述なし: H1) |
| Enderfga/claw-orchestrator | 583 | MIT | 2026-01-30 | 2026-09-26 | 25 | 191 | 選別 (記述なし: H1、H2) |
| jaylfc/taOS | 552 | AGPL-3.0 | 2026-04-05 | 2026-09-27 | 25 | 2222 | 棄却 H1 |
| BennyKok/omg.dev | 541 | MIT | 2026-06-17 | 2026-09-27 | 25 | 2973 | 選別 (記述なし: H1、H5) |
| aannoo/hcom | 521 | MIT | 2025-07-21 | 2026-09-26 | 4 | 116 | 棄却 H2 (部品として再考) |
| proliferate-ai/proliferate | 507 | AGPL-3.0 | 2026-04-30 | 2026-09-27 | 25 | 1743 | 選別 (記述なし: H5、H6) |
| mixpeek/amux | 505 | MIT + Commons Clause | 2026-02-18 | 2026-09-27 | 1 | 5264 | 選別 (記述なし: H1、H5) |
| greenfield-inc/Pane | 492 | AGPL-3.0 | 2026-02-27 | 2026-09-27 | 25 | 587 | 選別 (記述なし: H5、H6) |
| razzant/claudexor | 488 | MIT | 2026-06-05 | 2026-09-26 | 25 | 1794 | 部品 |
| formulahendry/acp-ui | 486 | MIT | 2026-01-31 | 2026-05-25 | 0 | 0 | 棄却 H3 |
| thinkany-ai/termany | 440 | AGPL-3.0 | 2026-06-29 | 2026-09-24 | 25 | 180 | 選別 (記述なし: H2、H5) |
| tellahq/opensession | 386 | MIT | 2026-06-08 | 2026-09-26 | 25 | 6217 | 選別 (記述なし: H5、H6) |
| OpenSource03/harnss | 378 | MIT | 2026-02-19 | 2026-08-10 | 0 | 0 | 棄却 H3 |
| vicoa-ai/vicoa | 362 | AGPL-3.0 | 2026-08-28 | 2026-09-27 | 15 | 159 | 選別 (4 条件の記述あり) |
| Charlie85270/Dorothy | 348 | MIT | 2026-01-24 | 2026-07-07 | 1 | 5 | 棄却 H2 (2026-09-28) |
| Intelligent-Internet/zenith | 314 | Apache-2.0 | 2026-05-08 | 2026-09-06 | 0 | 13 | 部品 |
| h0x91b/dev-3.0 | 299 | Apache-2.0 | 2026-02-18 | 2026-09-27 | 25 | 1076 | 選別 (記述なし: H1、H5) |
| sahithvibudhi/vibe-tree | 267 | MIT | 2025-07-29 | 2026-07-25 | 1 | 72 | 選別 (記述なし: H5) |
| open-mercato/cezar | 253 | MIT | 2026-05-19 | 2026-09-27 | 9 | 1071 | 選別 (4 条件の記述あり) |
| Ryder-Sun/Meldwork | 231 | 表記に矛盾 | 2026-07-29 | 2026-09-17 | 6 | 212 | 棄却 H2 |
| receptron/mulmoterminal | 225 | MIT | 2026-06-14 | 2026-09-27 | 25 | 5387 | 選別 (4 条件の記述あり) |
| junhoyeo/contrabass | 222 | Apache-2.0 | 2026-03-05 | 2026-07-17 | 1 | 51 | 選別 (記述なし: H1) |
| swarajbachu/zuse | 209 | AGPL-3.0 | 2026-05-02 | 2026-09-26 | 25 | 432 | 棄却 H2 (2026-09-28) |
| Ivy-Interactive/Ivy-Tendril | 198 | FSL-1.1-ALv2 | 2026-04-15 | 2026-09-15 | 25 | 2334 | 選別 (記述なし: H1、H5、H6) |
| sortie-ai/sortie | 192 | Apache-2.0 | 2026-03-17 | 2026-09-26 | 14 | 1389 | 選別 (記述なし: H1、H5、H6) |
| OtoDock/oto-dock | 187 | FSL-1.1-Apache-2.0 | 2026-07-09 | 2026-09-15 | 13 | 27 | 選別 (記述なし: H5) |
| amirfish1/claude-command-center | 173 | 非商用 | 2026-04-13 | 2026-09-27 | 25 | 3386 | 選別 (4 条件の記述あり) |
| nxtg-ai/forge-orchestrator | 161 | FSL-1.1-ALv2 | 2026-02-09 | 2026-09-26 | 3 | 41 | 棄却 H1 |
| rustykuntz/clideck | 159 | MIT | 2026-03-03 | 2026-09-22 | 14 | 51 | 棄却 H2 (2026-09-28) |
| nutthouse/tutti | 128 | MIT | 2026-03-12 | 2026-07-28 | 0 | 1 | 選別 (4 条件の記述あり) |
| ldbumble/taskuary | 124 | MIT | 2026-08-17 | 2026-09-26 | 25 | 1652 | 選別 (記述なし: H1) |
| tlbx-ai/tlbx | 112 | AGPL-3.0 | 2025-12-29 | 2026-09-27 | 25 | 510 | 選別 (記述なし: H1、H5) |
| monorepo-labs/dray | 101 | Apache-2.0 | 2026-07-25 | 2026-09-26 | 25 | 598 | 棄却 H2 (2026-09-28) |
| cfal/garcon | 88 | GPL-3.0 | 2026-02-23 | 2026-09-27 | 2 | 615 | 選別 (4 条件の記述あり) |
| alamops/agetor | 79 | MIT | 2026-05-16 | 2026-09-24 | 13 | 182 | 選別 (記述なし: H1、H2) |
| CompanyHelm/companyhelm | 76 | MIT | 2026-03-12 | 2026-08-28 | 0 | 2 | 選別 (記述なし: H1、H2、H5、H6) |
| langgenius/mosoo-agent-driver | 74 | Apache-2.0 | 2026-06-05 | 2026-09-23 | 0 | 58 | 棄却 H1 |
| BrokkAi/mjolnir | 64 | GPL-3.0 | 2026-05-18 | 2026-09-27 | 25 | 3314 | 選別 (4 条件の記述あり) |
| MarlBurroW/hivekeep | 63 | MIT | 2026-06-07 | 2026-09-26 | 1 | 122 | 棄却 H1 |
| 5dive-ai/5dive | 61 | MIT | 2026-05-15 | 2026-09-27 | 25 | 1869 | 選別 (4 条件の記述あり) |
| tacyan/zaivern-code | 52 | Apache-2.0 | 2026-07-20 | 2026-09-25 | 25 | 844 | 棄却 H2 (2026-09-28) |
| intentic/intentic | 46 | MIT | 2026-08-04 | 2026-09-27 | 25 | 3697 | 選別 (4 条件の記述あり) |
| crewplaneai/crewplane | 40 | Apache-2.0 | 2026-06-24 | 2026-09-25 | 18 | 94 | 部品 |
| victor36max/shire | 40 | MIT | 2026-03-17 | 2026-05-03 | 0 | 0 | 棄却 H3 |
| ai4kanban/ai4kanban | 38 | Apache-2.0 (web/ は再配布不可) | 2026-07-10 | 2026-09-27 | 16 | 771 | 選別 (記述なし: H2) |
| ramarlina/agx | 29 | なし | 2026-02-02 | 2026-05-06 | 0 | 0 | 棄却 H3、H4 |
| madeinorbit/podium | 23 | Apache-2.0 | 2026-06-02 | 2026-09-26 | 3 | 9402 | 選別 (記述なし: H1) |
| ShreyPaharia/octomux | 22 | MIT | 2026-03-09 | 2026-09-18 | 6 | 493 | 棄却 H1 (Codex なし) |
| moshthepitt/lionclaw | 19 | MIT | 2026-03-12 | 2026-09-01 | 0 | 79 | 棄却 H1 (Claude Code なし) |
| agent-squid/squid | 18 | MIT | 2026-05-21 | 2026-09-26 | 6 | 665 | 選別 (4 条件の記述あり) |
| its-ahoh/codey | 15 | MIT | 2026-02-20 | 2026-09-27 | 25 | 266 | 選別 (記述なし: H5) |
| clawnify/ateam | 13 | GPL-3.0 と商用 | 2026-06-03 | 2026-09-26 | 25 | 214 | 選別 (記述なし: H5) |
| cyclops-team/cyclops | 12 | MIT | 2026-08-01 | 2026-09-08 | 2 | 952 | 選別 (記述なし: H2) |
| evoelsewhere/evoflux | 10 | Apache-2.0 | 2026-08-03 | 2026-09-26 | 16 | 1349 | 棄却 H2 (2026-09-28) |
| pragma-sh/pragma | 10 | AGPL-3.0 | 2026-06-11 | 2026-09-27 | 25 | 967 | 選別 (記述なし: H1、H5) |
| AndyMik90/Aperant | 14572 | AGPL-3.0 | 2025-12-04 | 2026-06-14 | 0 | 0 | 棄却 H1、H2、H3 |
| humanlayer/humanlayer | 11615 | NOASSERTION | 2024-08-05 | 2026-06-19 | 0 | 0 | 棄却 H3 (deprecated の告知) |
| collabs-inc/collab-public | 2947 | FSL-1.1-ALv2 | 2026-03-15 | 2026-08-08 | 0 | 0 | 棄却 H2、H3 |
| NeuralNomadsAI/CodeNomad | 2600 | MIT | 2025-11-01 | 2026-09-27 | 25 | 194 | 棄却 H1 (OpenCode) |
| supabitapp/supacode | 2389 | FSL-1.1-ALv2 | 2026-01-21 | 2026-09-05 | 5 | 158 | 棄却 H2 (macOS 26.0+) |
| Emanuele-web04/synara | 1896 | MIT | 2026-03-27 | 2026-09-26 | 25 | 1875 | 選別 (4 条件の記述あり) |
| hardbeat920/monocode | 1563 | MIT | 2026-08-20 | 2026-09-27 | 25 | 657 | 棄却 H2 |
| egoist/waku | 1538 | GPL-3.0 | 2026-07-31 | 2026-09-23 | 14 | 481 | 選別 (4 条件の記述あり) |
| johannesjo/parallel-code | 1023 | MIT | 2026-02-18 | 2026-09-26 | 11 | 435 | 棄却 H2 |
| block/berd | 946 | Apache-2.0 | 2026-08-11 | 2026-09-26 | 9 | 215 | 棄却 H1 (Goose のみ) |
| maddada/Ghostex | 843 | MIT | 2026-04-27 | 2026-09-27 | 25 | 3332 | 選別 (記述なし: H1、H5) |
| Kc1t/alethe-agents | 743 | AGPL-3.0 | 2026-06-15 | 2026-09-26 | 8 | 363 | 棄却 H2 (2026-09-28) |
| cristicretu/diri | 335 | Apache-2.0 | 2026-08-04 | 2026-09-25 | 25 | 428 | 棄却 H2 |
| owengretzinger/constellagent | 215 | 不明 (LICENSE が 404) | 2026-02-10 | 2026-05-05 | 0 | 0 | 棄却 H2、H3 |
| tempestai-dev/tempest | 180 | Apache-2.0 | 2026-06-24 | 2026-09-27 | 23 | 421 | 棄却 H2 |
| ouijit/ouijit | 172 | AGPL-3.0 | 2026-02-03 | 2026-09-08 | 8 | 68 | 棄却 H2 |
| yicheng47/runner | 172 | MIT | 2026-04-21 | 2026-09-27 | 25 | 1330 | 棄却 H2 (Linux 非対応) |
| scgopi/GraphCode | 128 | FSL-1.1-MIT | 2026-07-26 | 2026-09-27 | 25 | 1458 | 棄却 H2 (macOS 15+) |
| gregce/tortie | 87 | Apache-2.0 | 2026-08-12 | 2026-09-24 | 25 | 1771 | 棄却 H2 (macOS) |
| antasphere/clave | 51 | MIT | 2026-02-12 | 2026-09-27 | 25 | 308 | 棄却 H2 |
| rayzhudev/vibecraft | 35 | Apache-2.0 | 2026-03-02 | 2026-07-19 | 0 | 1 | 棄却 H2、H3 |
| pungme/superagent-desktop | 26 | MIT | 2026-07-28 | 2026-09-26 | 25 | 911 | 棄却 H2 (Mac app) |
| fwdai/fletch | 25 | AGPL-3.0 | 2026-05-25 | 2026-09-25 | 25 | 1806 | 棄却 H2 (macOS 13+) |
| ProjectHax/muxel | 22 | GPL-3.0 と商用 | 2026-06-24 | 2026-09-26 | 19 | 311 | 棄却 H1、H2 |
| izll/agent-session-manager-desktop | 21 | MIT | 2026-06-22 | 2026-09-26 | 25 | 545 | 棄却 H2 (ヘッドレス不可と明記) |
| mrmans0n/alas | 18 | MIT | 2026-04-29 | 2026-09-27 | 25 | 987 | 棄却 H2 (macOS 15+) |
| amplifthq/opentag | 1378 | MIT | 2026-06-24 | 2026-09-14 | 8 | 482 | 選別 (記述なし: H5、H6) |
| aaif-goose/goose | 54696 | Apache-2.0 | - | 2026-09-23 | 14 | - | 選別 (記述なし: H6) |

母集団に無く、前段で読んだもの: Vibe Kanban (棄却 H3、会社の解散)、Crystal (棄却 H3、2026-02 に終了)、Terragon (棄却 H3)、Conductor.build (棄却 H2、非公開ソースで Mac のみ)、Zed (棄却 H2、デスクトップのみ)、n8n と LangGraph Studio と Open WebUI と Mastra Studio (棄却 H1)。

## 3. A の可視化層と B のベンダー app

A と B の調査結果は findings.md の 1 節と 2 節に置く。要点は次のとおり。

- Conductor OSS 3.32.4 の画面は、実行の検索、図 (DO_WHILE、DYN. FORK、JOIN を描く)、時間軸、入出力、Queue Monitor、Agent Executions を持つ。チャットで仕事を頼む画面と、実行器 (ワーカー) の一覧は無い。Agents 機能は Conductor 自身の LLM エージェント (モデル名と API キー) の実行系で、Claude Code や Codex のセッションを包む機構ではない。
- Claude Code は CLI で subagent を入れ子の木に、/workflows でフェーズの木に表示する。デスクトップ app は Tasks ペイン、Web は一覧と差分、スマホは cloud セッションと Remote Control。Codex は Subagents パネル (Active / Done) と cloud のタスク一覧、ChatGPT app で監視と承認。どちらも図は無く、Claude と Codex をまたいだ全体像は無い。
- 後付けの観測製品は Datadog Lapdog (Claude Code と Codex)、Langfuse (両方、hooks)、o11y-dev/opentelemetry-hooks (8 種)、SigNoz と claude-code-otel と claude_telemetry (Claude Code のみ)。
- ACP の仕様は v1.9.1 (2026-09-18)、claude-agent-acp と codex-acp は 8 月以降それぞれ 20 回以上のリリースで、ACP の組織が保守する。subagent、hooks、skills が ACP 越しにどう見えるかを書いた公式文書は無い。
- トークンの実測と推定は findings.md の 4 節。
