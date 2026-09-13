# Gemini交換アダプタ — 隔離試行のみ・全goal未完了

## 今回の結果と適用条件

`report_editor/adapters/gemini.py` は、既存workerからGeminiを単発で呼ぶ薄いアダプタです。
共通pipeline・主モデル・汎用delegationを変更せず、編集専用のfactoryで交換します。
今回の限定commitは、このファイル、上記adapter、`tests/test_gemini_adapter.py` の3新規ファイルだけです。
既存READMEや未完了の対話終端WIPは混ぜません。本番反映用の完成パッケージではありません。

適用先は既存 `integrations/hermes-report-editor/` です。依存はPython 3.11、httpx、openai、
python-dotenv、Hermesの `hermes_constants.get_hermes_home`、既存contractsの `EDITOR_SYSTEM`。
共通復帰の試験は現在の隔離WIP（pipeline/material/contracts/workerとdialogue_fixtures）にも依存します。
3ファイルだけを旧baselineへ移しても、訂正後のsend/returnや構造化資料の正式統合は完成しません。

実試行の初回4件は互換APIで全503、同じ4件のnative試行も全503でした。
短い公開診断は200/STOPで `OK`。これは報告編集の成功ではありません。
時間を空けた最後のC入力1回はnative/highで実本文を取得しました（8.016569秒、STOP）。
指定された全4例の編集出力は揃っていません。Aの謝罪/意味保持、情報不足のreturn、
差戻し往復、正式template境界、実UI、安定性、元goal全A〜Lは未達・未検証を残します。
Cは推奨・採否理由・未検証・検証開始のみの判断を維持しましたが、末尾は冗長です。
モデルの自己申告retainedは意味品質の証明ではありません。

## 編集専用設定

以下は許可された隔離試験環境の設定例です。本番configへは書いていません。
既存plugin設定のadapter部分だけを交換し、`author_adapter` は元主担当のままにします。

```yaml
plugins:
  entries:
    pda-report-editor:
      settings:
        enabled: false  # 本番では有効化しない
        adapter:
          factory: report_editor.adapters.gemini:GeminiAdapter
          model: gemini-3.8-flash
          transport: native
          reasoning_effort: high
          credential_file: /ABSOLUTE/EXISTING/HERMES-HOME/.env
```

- 認証は既存.envの `PDA_REPORT_EDITOR_GEMINI_API_KEY` だけを参照します。省略時のファイルは現在のHermes home/.envです。
- `dotenv_values(..., interpolate=False)` で読み、環境や秘密ファイルを書き換えません。キーを引数・画面・証拠へ表示しません。
- `transport` は `native` / `openai`。省略時は互換APIなので、今回の再現には明示的にnativeを指定します。
- nativeは `https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent`。
  highは `thinkingLevel: HIGH`、`includeThoughts: false` です。
- 互換APIは `https://generativelanguage.googleapis.com/v1beta/openai/`。
  `reasoning_effort: high`、`max_retries=0`、streamなし、候補1、toolsなしです。
- nativeのHTTPX transportに接続retryを追加しません。両経路ともredirectなし、自動fallbackや別モデル切替なし。
- `edit(request, deadline)` は既存 `EDITOR_SYSTEM` を使います。直接比較試行だけはresearchのbridgeが保存済みsystem指示を完全同一で渡しました。

## 期限・故障・計測

共通workerが単調時計の総deadline、cancel、process group回収を持ち、adapterは残時間から0.25秒を予約します。
HTTP timeoutは各I/Oの上限であり、それ単独を総時間保証とは呼びません。
今回の公開直接probeは事前記録した総75秒（起動・待ち・通信・回収込み）です。
この値を通常報告/return経路へ反映してはいません。報告の有限往復は共通pipelineの責任です。

認証なし、期限切れ、503、空文、非text、不完全終了、timeout、切断等は不採用です。
審査前の通信失敗では共通処理が原稿へ復帰します。却下済み原稿は共通処理の拒否状態で復活させず、
cancel時は本文を返しません。adapter自体は返信配信や新しい技術作業を行いません。
通常の呼出結果は取得したtextを無改稿で返し、診断projectionから内部思考・署名・tool引数を外します。
APIエラーは安全なstatus/code/messageの限定projectionで、任意の例外本文は共通workerに出しません。

usageのinput/outputはproviderが返したprompt/candidate tokensです。nativeのthoughts/totalは
`provider_response.usage` に数値として別保存します。思考本文は保存しません。
取得できないusage、課金回数、費用はnull/不明です。send hook数とサーバー側の課金回数を同一視しません。

## 限定試験

```sh
python integrations/hermes-report-editor/run_tests.py \
  --hermes-source /ABSOLUTE/ISOLATED/hermes-worktree \
  -- tests/test_gemini_adapter.py -q
```

ローカルHTTP serverと合成キーによる試験です。実Gemini品質や実UIの代用ではありません。
元の正負境界に加え、実worker経由の故障復帰・総期限・cancel・回収・却下後原稿非復活を確認します。
不正native候補でAttributeErrorになる欠陥はREDを記録し、型検査で固定理由へ変換しました。
実C再確認はこの型検査修正の前です。修正後の実モデル再呼出しはownerの回数上限に従い行いません。

## 無効化・切戻し

今回、本番は未導入です。本番の無効化・再起動操作は不要なため実行しません。
将来の許可された試験導入時には、変更前の編集専用設定と対象3ファイルの有無/内容を保存します。
無効化は試験pluginの `settings.enabled=false`。Open WebUI側も使用していれば
既存 `ENABLE_REPORT_EDITOR` をfalseへ戻します。変更を読込むのは所有する試験runtimeだけです。
切戻しは保存したadapter設定を復元するか、無効化のまま今回追加3ファイルだけを導入前状態へ戻します。
共通WIP、主model、汎用delegation、既存認証・停止設定へreset/stash/上書きをしません。
実UIに導入した場合の正常性は、その時点の所有する実経路で別途検証が必要です。

## 証拠・再開

今回の証拠正本:
`/home/user/.hermes/research/dialogue-endpoint-correction-20260912/`

- `gemini-trial/initial-compat-gemini-trial-result.json`: 初回4失敗
- `gemini-trial/native-01/result.json`: nativeの4失敗
- `gemini-trial/route-diagnostic.json` と `native-diagnostic-request.json`: 2モデルGET＋公開診断1生成
- `gemini-trial/native-C-final/result.json`: 最後のC実入出力・時刻・usage・source hash
- `gemini-trial-report.html` / `gemini-recovery-all-results.json`: 全試行の統合閲覧用

追加生成は今回実施しません。ownerが次の単発再確認を許可したときだけ、同じnative goalがactiveかつ
有限予算内であることを確認し、researchの `run_gemini_final_c.py --batch <新しい一意名>` を1回実行できます。
既存batch名なら拒否します。自己resume/reset/別goal作成はしません。
成功確認は200だけでなく、実本文・finish・完全同一のsystem/user・回数・回収と意味の読み合わせです。
A/不足例の再試験には別途具体的な回数と入力範囲が必要です。

Google公式資料:
- 互換API: https://ai.google.dev/gemini-api/docs/openai
- 障害対応: https://ai.google.dev/gemini-api/docs/troubleshooting
- 稼働状況: https://aistudio.google.com/status
- 公式開発者forum: https://discuss.ai.google.dev/c/gemini-api/4

503は当時の供給側UNAVAILABLEとして保存しています。Cで復帰しましたが、全般的な復旧/安定性は未証明です。
継続する場合の問い合わせは、時刻・model・native/互換経路・HTTP status・安全なエラー文と
非機密の最小再現を提示し、同じ設定で継続的503になる原因/再開条件を確認します。キー・全会話は送らず、
外部への問い合わせ送信はownerの許可後です。課金層変更や別モデルは自動的に行いません。
