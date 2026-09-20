# 第3本: ランタイムのラッパー

- 物差し: `docs/requirements.md`（commit `cdd90e9`）3.1 契約 4 項目、コア 5 要素「ランタイムのラッパー」、受け入れ条件 A1・A2・A5
- 形式: 第 1 本と同じ

## 問い

異種のランタイム（Claude Code CLI、Codex CLI、Gemini API、jev の HTTP API、決定論的な検証ツール）を、同じ契約の形に揃える層について、抽象・不変量・実装の揃った対はどれか。特に次の 2 つ。

1. ラッパーが揃えるべき最小の契約は何で、何を契約に入れなかったことで成功したか（異種ランタイムを 1 つの契約に揃えた成功例の分析）
2. ラッパー自身が契約違反（event stream の欠落、成果の種別違反）を起こしたとき、それを検出できる構造があるか

## 起点

- OCI runtime spec と containerd の shim（異種ランタイムを 1 つの契約に揃えた成功例。契約に入れたもの・入れなかったもの）
- Erlang/OTP の behaviour と supervisor（コールバック契約で異種プロセスを監督下に置く。監督が検出できる異常の範囲）
- ACP（Agent Client Protocol）の adapter 群（claude-agent-acp、codex-acp、Gemini CLI native）。adapter が契約のどこまでを機械的に保証し、どこを規約に委ねているか
- Language Server Protocol（異種の言語ツールを 1 つの契約に揃えた例。capability negotiation の構造）
- POSIX プロセスモデル（stdin/stdout/exit code という最小契約で異種プログラムを揃えた極。第 1 本の Unix パイプラインの続き）
- adapter / facade パターンの形式化（wrapper の正しさを述べた研究があるか）
- 第 1 本の含意: どの実行器も要件の形の event stream を自分からは出さない。ラッパーがイベント語彙を閉じ、未知種別に出会ったときの動作を先に決める必要がある
- 第 1 本の含意: 強制力は「包む」か「生成する」かで変わる。choreographic programming（Choral）はコンパイラが射影の段階でロールに属さない処理を生成物から消すため脱出口が無い。Akka は型で絞るが `unsafeUpcast` の脱出口が残る。JADE は javadoc が主張する検証がコードに存在しない。ベンダーのランタイムは改変できないので Choral 型の「生成による強制」は取れない前提で、ラッパーが「契約の形に揃える」以上のことをできるか、できないなら強制の位置がコア側の受け入れ検査に移ることを確かめる

## 第 1 本から引き継ぐ問い

- 要件の「実行器が自由に発話することは許容しない」は、実行器を改変できない以上、コア側（ラッパーと受け入れ検査）が守らせるものとして読む。ラッパーがどこまでを機械的に保証し、どこを受け入れ検査に残すかの境界を、成功例（OCI、ACP adapter、LSP）ごとに記録する
- 要件のプロトコルはコアと実行器の 2 者間なので、multiparty session types の追加装置（global type、projection、coherence）は要らず、binary session types の双対性検査で足りるかを確かめる

## 出力

要素ごとの表。列は「抽象、不変量、実装（強制箇所）、契約との対応、A1/A2/A5 との対応、足りないもの」。加えて「契約に入れなかったことで成功した項目」を成功例ごとに列挙する。
