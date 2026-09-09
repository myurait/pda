# M2再開票 — INCOMPLETE / 認証境界待ち

正本: default / pda-improvement / t_ec4c52b9。既存計画と再評価仕様の完了条件は不変。主PDA単独・直列。M2全体の完了、M3候補の確定、独立レビューを主張しない。

現在の判定は M2-RESUME-REPORT.html/.md と assessment.json。根拠32ファイルは evidence-manifest.json のSHA-256で照合できる。旧 M2-REPORT/VERDICT と旧添付27の採用結論は撤回済みで歴史資料のみ。

Hermes 0.21.1最小構成: 実プロセス停止、資源故障、依存障害後の読取りと模擬ファイル修復は成立。DB破損と起動不能更新＋非互換DBは120秒内の無人状態回復が不成立。試験側の標準backup/importと正常版起動なら復元できたが自律復帰ではない。stop受理直後はstopping→interrupted、取消完了後はcancelledを保持。模擬fsync作用の同一ID再送では追加作用なし。永続HOMEが作業上限を超えて書ける。本体read-onlyは試験構成の制約であり製品全体の自己更新不能ではない。

Letta Code 0.31.13＋qwen3.5:4b CPU: 不要skillなしの標準設定で基礎読取り成立。読取り専用の故障6ケースと別の実Bash修復は成立。index破損では120秒後も起動不能、復元は試験側が実施。永続HOME保護は未達。実仕事の停止競合・安全再開は未実証。

観測訂正: 中間stop、PID1 no-op、JSON wrapper、再起動中のExitCode、接続reset、importコマンド差、旧run IDの404を区別。最新の有効なHermes依存試験は memory-v3 と model-v4。Letta model-unavailableのraw介入0は誤記で、試験側Ollama startの記録がある。assessmentのcorrectionsを必ず合わせて読む。無人復帰の0介入根拠には使わない。

管理型/混成: 公開資料と環境/標準設定の認証有無を確認。試験認証は見つからず。ユーザーが別環境にアカウントを持たないという意味ではない。Cloudflare PITRはローカル非対応、fiberローカル試験は実クラウド復元の代わりにならない。ローカルfiberデモも未実施。OpenAI保存API＋自前runnerは参考案で完成本体ではない。

次: Letta Cloud管理sandboxの試験用認証・利用枠・合成データ送信条件を確認して実機比較へ進む。採否を先に決めず、同じ元条件を試す。新規契約や認証操作を勝手に行わない。旧構成への独自復旧serviceの追加やscope v2再開には戻らない。

資源: final-dependency-retest-cleanup.jsonでm2proof/m2r2コンテナの残留なし。private .runtimeの状態、ソース、モデルキャッシュ、認証入りbackupは保全しGit/添付対象外。各試行は状態を変更するので盲目的に再実行しない。

カード: 現行CLIは未完了taskの本文編集を提供しない。本文の旧未着手表記は未反映。card-current-body-proposed.mdは更新案であり、反映済みとは扱わない。報告添付・コメントが最新状況。CLIのblocked変更はcannot blockで拒否されたため、未割当triageを維持する。強制変更・readyへの昇格はしていない。保存結果はpublication.jsonを確認する。

main・他worktree・本番サービスは変更しない。この実証branchへのcommitは記録であり、採用・デプロイ・目的達成ではない。
