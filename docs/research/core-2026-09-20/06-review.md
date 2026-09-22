# 第6本の確認結果 — コアの機能と、コアと実行器の関係

確認日: 2026-09-21 JST。対象は `06-core-and-relationship.md` と `06-core-and-relationship.evidence.md`。物差しは `docs/requirements.md` の commit `aa2c92c42cf7941406534eb5b99846a4dcdee86c`。

## 1. 結論

14件について、本文が限定した仕様上の性質と、検査・構築・状態遷移を行う実装箇所の対応を確認した。前段出力からの動的展開、回数・時間による監督、中央の状態保持、責任付き契約違反、promptの展開とprovenanceには部分的な対応がある。

A16の全入力の限定、A17の全変更の前段指示への限定、A18の全判定の規則特定と必須記録を、未改変runtimeと交換可能な判定器の共通契約へ一体で対応付けた対は未発見という本文の判定を維持する。「実装が存在しない」「必ず自作する」という結論にはしない。

## 2. 照合範囲と方法

1. 15リポジトリの固定SHAにあるコード・同梱仕様の54引用を、初回のtarball取得とは別に、公開raw URLの40ファイルから再取得して確認した。全件HTTP 200で、ファイルのSHA-256と一致した。すべての逐語引用が指定したpath:lineの範囲に存在した。
2. 論文・標準PDFの8資料を原URLから再取得した。全件HTTP 200で取得物のSHA-256が一致し、10引用の指定物理ページを照合した。Chandra–Touegの物理8ページのcompleteness/accuracy定義と、Findler–Felleisenの物理4ページの責任帰属の説明は画像でも確認した。
3. 公式HTML/API資料18件を再取得した。全件HTTP 200で取得物のSHA-256が一致し、20引用と周辺説明を確認した。HTMLの抽出行番号は補助位置とし、URL・取得物ハッシュ・引用を合わせて固定した。
4. 合計66取得元・84引用の照合である。本文執筆後に追加したArgoの状態反映、DSPyの既定指示呼出し、auditのstage定義は、すでに独立再取得済みのファイル本文と照合した。DSPyの最終誘導先とKubernetes API validation仕様の引用は追加で再取得した。未実施の取得を再取得済みと数えていない。
5. 取得表には探索で取得したが逐語引用に採用しなかった資料も含む。32件のPDF/HTML取得物すべてを引用対象として数えたわけではない。第1〜5本の本文とreviewから引き継いだ事実は「報告」であり、過去の全一次資料を第6本で再取得したという意味ではない。

以上は本書の作成者が別取得で行った引用・コード経路の照合であり、別の研究者による独立審査ではない。各engine、compiler、controller、SDKの実行、障害注入、PDAの受け入れ試験、現行コードに対する論文定理の再証明はしていない。

## 3. 主要な対応と留保

| 対象 | 確認した根拠 | 照合した内容 | 維持する限界 |
|---|---|---|---|
| Conductor Dynamic Fork | CON0〜5 | 前段のtask列参照例、入力解決、task生成、map/参照名/JOIN検査 | 一般の入力源を直前出力だけに制限しない。INLINEの例を未改変ベンダーruntimeの証明にしない |
| Airflow Dynamic Task Mapping | AF0〜2 | XComとliteralの別経路、mapping長、空列SKIPPED、instance生成と除去 | 既定taskのinstance数の展開と、任意のセルtype/実行器を含むフロー定義変更を分ける |
| Argo withParam | AR0〜2 | JSON配列のdecode、template維持、whenに応じたエラー、NodeError/NodeSkipped | 配列を渡せることは前段出力の専用経路ではない。不正値でもwhenが偽なら同じ拒否にならない |
| Temporal | TE0〜7、HTR・HTR2 | Worker command、子開始と完了event IDの対応、回数・期限・取消し、retry task、server timer、MutableState/Describe | Workerの指示元は直前セルと同義ではない。Activity開始のhistory掲載は遅延し、全試行のlive streamではない |
| OTP | ER0〜3 | restart種別、MaxR/MaxT、monotonic時刻、上限超過reason、未知info | process再起動は別実行器への仕事再投入ではない。未知事象を判定器へ自動委譲しない |
| Kubernetes Job | HKJ、KJ1〜3 | 規則順、未一致の既定処理、FailJobのrule index、backoff/deadline、suspend/resume | Ignore/Count/FailIndexも同じrule index付きmessageを記録するとはしない。全コア行為の履歴ではない |
| Pekkoと故障検出理論 | HPH、PH1〜2、PCT | phiの式・近似、threshold、heartbeat未観測時の0、completenessとaccuracy | 数値的な疑いを実際の停止の証明としない。Pekkoがperfect detectorであるという対応は作らない |
| Resilience4j | HCB、CB1〜3 | 最低件数・失敗率/遅延率、CLOSED→OPEN、event listener省略と例外 | 遮断とfallback先選択・再投入を分ける。状態通知可能性を全件記録へ繰り上げない |
| OPA | OP0〜4 | 成立規則labelsの採取、同一mapの統合、decision logへの格納、undefined応答、drop/mask | labels無しや統合がある。一意な全規則の識別子ではなく、decision IDだけで根拠を証明するものでもない |
| Kubernetes API | HKV・HKA・HKA2、KA1〜3 | decodeの拒否とWarn継続、auditのResponseComplete、None/未設定/overflow | 拒否の分岐と記録の前提を別々に記載。全不正fieldを無条件拒否し必ず記録するとはしない |
| Racket contracts | PFF、RA1〜3 | blameの反転、引数個数違反、blame object付き例外 | 全高階契約の現行実装証明ではない。責任付き例外と不受理event永続化を分ける |
| Langfuse / MLflow | HLF・HML、LF1〜3、ML1〜3 | 事前promptの取得・展開・trace関連付け、未指定変数とfallback/partialの例外 | promptを参照したことと最終入力が一致することは別。全write経路のimmutable性を検証したとはしない |
| noWorkflow / PROV | PNW・PNW2、NW1〜2、HPR・HPA | AST計測、評価ID間の依存、network/DB直接採取の留保、記述の整合性と信頼の分離 | 元sourceを手編集しないことを、任意ベンダーruntimeへの非介入計測と同一視しない。noWorkflowのPROV全適合も未照合 |
| 計画・関係・その他の起点 | HT1・PHT、HBD、PHY、PBP・HCD、PGR、PAI・PAI2、HRE、HRB、HSQ・HKF、HDS・DS1〜2、HVA | 計画と実行、BDI、policy/mechanism、中央/分散、グラフ・scope更新、発火通知、再試行量、再配信、signature、Valk書誌 | 抽象/API/所在確認と固定実装の対を分ける。対応未確認のものを14件へ混入しない |

## 4. 照合中の修正と要件解釈

1. ブリーフの「コアの義務6項」は参照先の要件表と一致しないため、正本の7項で評価した。要件文書は変更していない。
2. 第4本の「検査位置が未決定」という旧要件に基づく留保は終了した。今回の正本では、ランタイム本体はストアへ直接触れず、ラッパーが仲介し、コアが受理時に形を検査する。
3. OPAは取得SHAにrule_labelsが実装されていたため、判定IDしか記録できないという読みを採用しなかった。一方、labelsの任意性・統合・drop/maskを記載し、全規則の一意な記録とは判定しなかった。
4. ArgoのJSON parse失敗にはwhenによる条件があり、常に同じ拒否になるという一般化を避けた。KubernetesのWarn、Pekkoの未監視扱い、Langfuseのfallback属性省略、Temporalの開始event掲載時点も明記した。
5. 論文内の単語が改行・段組で分断された箇所は引用を短く取り直し、PDFページ内の逐語一致を確認した。論文の内容の要約と、そのままの引用を混同していない。
6. DSPyは旧URLから二段階の誘導HTMLを取得した後、実際の本文を取得した。HTTP 200だけで本文取得済みとは扱わなかった。Valkは書誌のみであり、論文本体を読んだとする記述はない。
7. A14に排他的な状態所有や遅延ゼロの故障判定を追加せず、A15にIDを含むbyte列の同一性を追加せず、A9に外部作用の原子的な取消しを追加していない。A17では内部の管理用nodeとPDAのセルを根拠なく同一視しない。
8. 前5本からの集約では、費用・資源・stateの語彙や前提付き完全性の存在を維持した。部分的な新しい対応を、A1〜A4やA13〜A18の全体達成へ拡張していない。

## 5. 成果物の整合性

本文、根拠集、reviewのローカル参照と根拠IDを照合した。研究READMEの第6本を完了へ更新し、HANDOVERの残作業表示も更新した。第6本末尾には第5本の集約表を6本分へ更新した表を置いた。要件文書と第1〜5本の本文・根拠・reviewは変更していない。

詳細な固定SHA、URL、取得ハッシュ、逐語引用は [根拠集](06-core-and-relationship.evidence.md) を参照する。
