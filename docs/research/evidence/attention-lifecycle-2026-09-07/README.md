# 注意・記憶寿命の出典台帳

観測日: 2026-09-07 JST。

- `source-map.json`: 追加取得した公式資料7件。URL、観測日、UTF-8本文のSHA-256、逐語根拠、public PKB内のraw locator。
- `citation-ledger.json`: 上記資料の引用番号。元の2026-09-06広域調査とは別namespaceであり、番号を混ぜない。
- 対応文書: [注意の切替と記憶・skillの部分的忘却](../../../design/v2-attention-memory-lifecycle-2026-09-07.md)。

本文は `/home/user/pkb/raw/articles/attention-lifecycle-2026-09-07-source-01.md` から `07.md` のimmutable captureへ保存した。PKB helperが末尾改行を付与した正規化本文についてhashを照合した。Hindsight Mental Modelsのtool返却はhead/tailで省略されたため、extractorが保存した完全なcaptureを使用した。

このディレクトリには短い根拠とlocatorを残す。完全な取得本文そのものはPDAリポジトリに同梱していないため、このリポジトリ単独で全文の再照合を行う場合は公開URLから再取得するか、別管理のpublic PKBを参照する。公開ページが変化した場合は観測済み本文hashと一致しない可能性がある。

検証は引用番号・逐語根拠・raw本文hash・文書間local link・要求IDの連続性を対象とする。topic切替、長期の抽象化品質、休眠skill再発見、provider実働、製品benchmarkは実施していない。
