# PDA v0.2

複数の環境、アカウント、エージェントを平等で交換可能な実行器として抽象化し、適切な作業を適切な実行器に割り振って成果を統合する、個人向けの統合推論機構。

- 要件の正本: [docs/requirements.md](docs/requirements.md)
- 基本設計の提案: [docs/design/basic-design-proposal.md](docs/design/basic-design-proposal.md)。Conductor をコアに据える案と、決定事項
- 最初の増分の設計: [docs/design/increment-1.md](docs/design/increment-1.md)。4 実行器をミニ PC で動かすまでの構成、メッセージ、雛形、宣言、作る順序
- 開発の進め方: [docs/process/remake-cycle.md](docs/process/remake-cycle.md)。閉じた指示でのワンショット実装と、捨てて作り直すサイクル
- 実装の指示: [docs/codex-runs/](docs/codex-runs/)。Codex に渡した指示を 1 回 1 ファイルで置く
- 実装の報告と評価: [docs/reports/](docs/reports/)。実装側の報告、証拠、設計側の評価を増分ごとに置く
- 調査記録: [docs/research/README.md](docs/research/README.md)。既存の抽象と実装が要件をどこまで満たすかの調査。未実施分の引き継ぎは [docs/research/core-2026-09-20/HANDOVER.md](docs/research/core-2026-09-20/HANDOVER.md)
- ミニ PC の環境: [docs/environment/mini-pc.md](docs/environment/mini-pc.md)。接続方法、動いているもの、入っているツールと認証
- 旧 PDA（v0.1 系）は tag `v0.1-archive` に保存し、全破棄した。継承の前提にしない。
