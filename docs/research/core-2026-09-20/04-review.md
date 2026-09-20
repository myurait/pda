# 第4本の確認結果 — ログストア

確認日: 2026-09-20 JST。対象は `04-log-store.md` と `04-log-store.evidence.md`。物差しは `docs/requirements.md` の commit `cdd90e945d938769aefa17a2b8de3236647f6bdc`。

## 1. 結論

9対について、本文が限定した不変量と実装箇所の対応を確認した。schema登録の互換性、各payloadの適合検査、追記中の読取り、保存内容の改変検知、記録対象の完全性を別の性質として扱う判定を維持する。契約4項目やA5・A6・A8・A9全体の達成を確認したものではない。

第1本の「event streamの完全性に抽象が無い」という報告は、そのまま全体評価へ引き継げない。PeerReviewやSLiCには前提付きの完全性の抽象があり、CTにも提出の証拠と期限に基づく収録義務がある。ただし、どれも観測できない任意の内部行為の存在まで明らかにする保証ではない。

## 2. 確認範囲と方法

1. 根拠集のコード・仕様・RFC・公式HTMLの63箇所を、本体が公開URLから独立に再取得した。全件HTTP 200で、逐語引用が指定行に存在することと、その前後の条件分岐を確認した。Git資料は根拠集の固定コミットを使用した。
2. 論文6資料を原URLから再取得した。全件HTTP 200で取得物のSHA-256が一致し、指定PDFページの引用を確認した。LamportとMatternの数式は文字抽出だけで判定せず、該当ページの画像でも確認した。
3. 上記69箇所は本体確認である。担当の報告を再取得せずに引用確認済みとした箇所はない。取得失敗URLの応答履歴は担当の報告であり、本体が全件を再試行したという意味ではない。

確認したのは引用とコード経路である。各broker、workflow engine、SDK、storeを起動した検証、任意入力の拒否試験、故障注入、PDAの受け入れ試験は行っていない。保存の全入口を網羅した証明でもない。

## 3. 不変量と判定の確認

| 対象 | 確認した根拠ID | 本体で確認した内容 | 維持する限界 |
|---|---|---|---|
| Pulsar / Confluent | P0〜P7、S0〜S3 | schema登録・互換性検査、標準publish経路、ledger追加とReader、client側のpayload検査。Confluentのbroker製品仕様はID検査を説明 | 登録済みIDがあることはpayloadの適合ではない。JSON serializerの検査は既定falseで、非公開brokerのコードを検査したとはしない |
| Iceberg | I1〜I4 | Sparkのwrite schemaを検査し、設定に応じてnullability等の不適合を拒否する | snapshot/fileのsequenceは個々の実行器eventの発生順序ではなく、逐次購読とも異なる |
| Temporal | T1〜T7 | serverによる種別とattributesの構築、履歴IDの増分、終了後の追加拒否、long-poll。Activity開始をtransientとして完了時に補う経路 | workflow履歴はActivity内の全行為ではなく、すべての開始・再試行を即時出力する保証でもない |
| Restate | R1〜R6 | 再生commandのdecode、header/index照合、journal保存、payload比較を省略できる設定、旧仕様のarchive状態 | debug assertionはrelease時の拒否を証明しない。旧版の全遷移の文言を現行版の無条件保証へ移さない |
| OpenTelemetry / GenAI / Dapper | O1〜O7、G1〜G5、L4 | Logsのemit時export、Spanのend時export、samplingとqueue drop、event_nameの自由度、現行GenAI規約のDevelopmentとopt_in | 共通の形から名前別payload検証、全件性、永続性は導けない。記録の不在だけで行為の不在を判定しない |
| CT / Trillian | C0〜C7 | treeの追記とroot/proof検証、RFC 6962のSCTとMMD、RFC 9162が述べる異なるviewの問題 | 証明対象は提出・公表済み記録。TrillianのRFC 6962由来実装をRFC 9162準拠の証明とはしない |
| Agents SDK / A2A / protobuf | A1〜A5、B1・B2 | SDKの標準event構築とqueue読取り、省略されるitem、dataclass/Literalの型注釈、proto3 open enumとoneof | 型宣言だけを任意入力の実行時拒否としない。queueは永続ログではなく、oneofは値の必須性を保証しない |
| Git / Automerge / n8n | V1〜V4、M1〜M3 | commitとrevertの履歴、actor別連番・重複の検査、n8nの公式利用文書 | 定義の取消しは実行済み外部作用の取消しではない。自己改変の判断根拠の必須記録は未確認。n8n本体は未読 |
| 完全性・順序の抽象 | L1〜L3、L5・L6 | OLEPの同じ更新列、Lamportの片方向条件、Matternのvector time、SLiCの許容損失範囲、PeerReviewの正しいnodeとの通信と観測可能な逸脱 | 異なる順序概念を統一しない。PeerReviewとSLiCの固定実装箇所は未確認として片側に残す |

## 4. 照合中の修正と要件解釈

1. Icebergの不変量をwrite schema検査APIのnullability条件と対応させた。format仕様のsequence numberを型検査の直接の根拠にする対応のずれを解消した。
2. Restateの対は現行protocolのjournal mismatchと現行SDKの再生照合に限定した。旧prose仕様は系譜の説明へ分離した。
3. 要件は共通形式のevent streamを要求するが、その検査を必ずstore自身に置くとは定めていない。本文はブリーフの責務配置の推論と要件本文を区別している。
4. A6はスマホでの一続きの可視化を含むため、ログ機構だけをもって達成とはしない。A9も変更履歴と取消しだけでは、改変日時・根拠・変更前後の全条件を満たしたことにはならない。

## 5. 第5本への扱い

第5本では、記録対象と前提を明示した部分的保証として用いる。「完全性の抽象が無い」「schemaを持つため全payloadを検査する」「ログに無ければ行為も無かった」という一般化は継承しない。詳細なURL、固定SHA、逐語引用、ページ位置は [根拠集](04-log-store.evidence.md) を参照する。
