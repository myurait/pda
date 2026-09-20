# 第 1 本の確認結果

第 1 本（共通の input/output ストアとランタイム間のプロトコル）は独立に 2 版ある。それぞれの引用を一次資料と突き合わせた結果を記す。確認日は 2026-09-20。

## v1 `01-store-and-protocol.v1.md`

物差しは要件のコミット `0bacb27`（A12 が「種別」に限定される前）。

確認した範囲: 主要なコード引用を、本文に書かれたコミット SHA で GitHub から再取得して突き合わせた。

見つかった誤り:

- Temporal の `EventType` の値の数を 72 と書いているが、本文が固定したコミットでは 61
- Scribble の `EndSockGen.java` の位置を `endpointapi/` 配下と書いているが、実際は `scribble-codegen/.../statechanapi/EndSockGen.java`

結論への影響: 無し。上の 2 件はいずれも周辺の数字と位置の誤りで、対の成立・不成立の判定は変わらない。

## v2 `01-store-and-protocol.v2.md`

物差しは要件のコミット `cdd90e9`（現行）。根拠集 `01-store-and-protocol.v2.evidence.md` が併置され、本文が自ら取得した箇所と分担先の報告を区別している。

確認した範囲: 「本体確認」と書かれたコード引用 17 箇所と論文引用 14 箇所を、本文のコミット SHA と URL で再取得して突き合わせた。

一致した主な箇所: Ptolemy の `hasToken()` が無条件に true を返す箇所、Akka の型付き `ActorRef` と `unsafeUpcast` の脱出口、Scribble の線形ソケットの再利用例外、JADE の `setPerformative` に範囲検査が無い箇所、Kafka の値が `ByteBuffer` のままである箇所、Temporal の `EventType` 61 値、Choral の射影がロール外の式を消す箇所、HasChor の `Empty`、LangGraph が未知ノードへの `Send` を警告だけで無視する箇所、OpenAI Agents SDK の実行中イベント 11 値、A2A の proto 812 行に費用を表す語が 0 件で `Message` と `Artifact` が別型である箇所、MCP の最新スキーマ版が `2026-07-28` である箇所。論文は Gelernter 1985 の「実行時型検査を不可能にする」、Nii 1986 の「概念であって計算仕様ではない」、van der Aalst 1998 の soundness 定理、Honda-Yoshida-Carbone JACM の「2 者間なら双対性検査で足りる」と「参加者情報は静的」がすべて逐語で一致。

見つかったずれ（結論に影響しない）:

- Kafka `DefaultRecord.java` の path が `record/` 直下と書かれているが、実際は `record/internal/` 配下。根拠集の方は正しい
- JADE `ACLMessage` の int 引数コンストラクタが 331-333 行と書かれているが、実際は 332-334 行
- OpenAI Agents SDK の handoff ツール名は `transfer_to_{agent.name}` をそのまま返すのではなく、関数名形式へ変換してから返す

確認できなかった箇所: Kahn 1974 の逐語引用 2 件。配布 PDF がスキャン画像で文字層が無く、機械的に照合できない。

## 2 版の関係

空白の判定は一致している。費用・到達資源・state を機械可読に宣言する語彙はどの抽象にも実装にも無く、event stream の形式にも抽象が無い。

「要件に最も近い対」の判定は異なる。v1 は状態機械複製と Temporal を挙げる。v2 は choreographic programming（Choral）を挙げ、Temporal は軸が違う補足に置く。v2 の根拠は、Choral が許されていない通信を生成物から消すため脱出口が原理的に無い点だが、v2 自身が、改変できないベンダーのランタイムを包む PDA にはこの形の強制は取れないと書いている。

v2 が要件へ向けた疑義とその扱い:

- A12 の「決定論的に分類可能」を成果の中身の分類と読んだ疑義は、要件側で既に決着している。A12 は種別の分類に限定されており（`cdd90e9`）、v2 自身が挙げた A2A の `Part` の oneof や Temporal の閉じた enum が種別の分類に当たる。要件は変えない
- 「実行器が自由に発話することは許容しない」をコアの受け入れ検査が守らせる意味に読んでよいかという問いは、そのとおりでよい。実行器は改変できず、平等の定義が実行器側の協力を前提にしないため、守らせる主体はラッパーと受け入れ検査しかない。どこに置くかは設計の話で、ラッパーのブリーフに移した
- MCP は「ランタイム間のプロトコル」の位置には入らない（向きが逆）という判定は、自己宣言のブリーフに評価軸として移した
