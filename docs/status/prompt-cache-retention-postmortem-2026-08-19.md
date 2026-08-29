# `prompt_cache_retention` HTTP 400 ポストモーテム — 2026-08-19

- Status: analysis complete（文書化のみ。対策コード・設定・実環境は本カードでは変更していない）
- Incident surface: Open WebUI → Hermes Runs API → OpenAI Codex Responses
- User-visible failures: 同一のOpen WebUI会話で2回
- Additional reproduction: 調査用の別会話で1回

## 1. 判定ラベル

本書では証拠の強さを次の3段階で明示する。

- **[確定]** 保存されたrun状態、ログ、request dump、または現在のソースで直接確認した事実。
- **[高確度推定]** 同一の経路・モデル・エラー署名から強く支持されるが、当該requestそのもののwire dumpが残っていない判断。
- **[未確認]** 現在の証拠では確定できず、恒久対策の検証対象として残す事項。

## 2. 要約

**[確定]** 2026-08-19、Open WebUIで選択されたモデル別名 `hermes-agent` は、Hermes API Serverの `/v1/runs` を通り、実効provider/model `openai-codex:gpt-5.6-sol`、`https://chatgpt.com/backend-api/codex/responses` へ到達していた。同一会話の2つのrunが、次のHTTP 400で終了した。

```text
prompt_cache_retention is not supported on this model
param=prompt_cache_retention
code=invalid_parameter
```

**[確定]** 2回ともログ上は `attempt 1/3` の直後に `Non-retryable client error` と判定され、残りの試行へ進まずrunが終了した。1回目の後、オーナーは「エラーのポストモーテムは後に実施するとして、作業を続けろ」と継続を指示したが、継続runも同じ形で終了した。

**[確定]** 続く調査用会話でも同じ400を1回再現した。そのrequest dumpでは、Hermesが送ったJSON本文に `prompt_cache_key` はある一方、`prompt_cache_retention` は存在しない。それにもかかわらずresponseは同項目を `invalid_parameter` として拒否している。

**結論:**

1. **[確定: 調査用再現]** `prompt_cache_retention` はPDA/Open WebUI/Hermes transportが送った値ではなく、Codex backend側の上流処理で付加された。
2. **[高確度推定: 元の2run]** 同一provider、model、endpoint、エラー署名であるため、元の2runも同じ上流付加経路で失敗した。
3. **[確定]** 応答を停止させた直接の増幅要因は、当時のHermesがこの最適化ヒント由来の400を決定的なrequest format errorとして非再試行扱いしたことである。

したがって、根本原因は「上流が対象modelで未対応の最適化ヒントを付加したこと」と「意味結果に不要なヒントの拒否をHermesが回復可能と扱わなかったこと」の組合せである。`prompt_caching.cache_ttl` の単純な設定ミスや、`gpt-5.6-sol` 自体が常時利用不能だった事象ではない。

## 3. タイムライン

時刻は保存ログのJST表記による。

| 時刻 | 確度 | 事象 |
| --- | --- | --- |
| 11:16:01 | [確定] | Open WebUI Progress Pipeが最初のrunを作成し、event streamを購読した。 |
| 11:32:47 | [確定] | run内で最後の記録済みfile writeが完了した。失敗はtool実行前ではなく、作業進行後に起きた。 |
| 11:32:49 | [確定] | `gpt-5.6-sol` へのAPI callが同400で失敗。`attempt 1/3` から非再試行終了し、runがfailedになった。 |
| 11:33:49 | [確定] | オーナーの継続指示を受けて同一Open WebUI会話に新しいrunを作成した。 |
| 11:36:41 | [確定] | 継続runも同じ400を非再試行扱いしてfailedになった。 |
| 11:38以降 | [確定] | 別のOpen WebUI会話から障害調査を開始した。 |
| 11:44:02 | [確定] | 調査runでも同じ400を再現。保存されたrequest本文に `prompt_cache_retention` が無いことを確認できる証拠が残った。 |

保持中のテキストログで確認できた同一署名は、この3つの実事象（元会話2回、調査会話1回）である。`agent.log.1` と `errors.log` の二重記録を別事象としては数えていない。

## 4. 影響範囲

### 4.1 確認済みの発生経路

**[確定]** 発生した経路は次のとおり。

```text
Open WebUI
  → openwebui-hermes-progress Pipe
  → POST Hermes /v1/runs  (model alias: hermes-agent)
  → Hermes common conversation loop / codex_responses transport
  → openai-codex:gpt-5.6-sol
  → https://chatgpt.com/backend-api/codex/responses
  → HTTP 400 invalid_parameter
  → run.failed
  → Open WebUIに「Hermesエラー: …」を表示
```

- **Surface:** Open WebUIのユーザー可視run。
- **Hermes platform:** `api_server`。
- **Open WebUI model指定:** `hermes-agent`（PDA側の別名）。
- **実効provider/model:** `openai-codex:gpt-5.6-sol`。
- **API mode:** Responses API。
- **失敗状態:** `/v1/runs/{run_id}` が `status=failed`、`last_event=run.failed`、同じerror文字列を保持した。

### 4.2 ユーザーへの影響

- **[確定]** 元の会話では、作業が進んだ後の最終応答が2回停止した。
- **[確定]** 1回目は多数のAPI/tool処理後であり、失敗直前にもfile write完了が記録されている。run失敗は、それ以前のtool side effectを巻き戻すトランザクションではない。
- **[確定]** そのため、ユーザーは回答を受け取れないだけでなく、途中成果がどこまで成立したかを別途再照合しなければ信頼できない状態になった。
- **[未確認]** 当該runが触れた全artifactの最終状態と、失敗による業務上の追加損失は本カードの対象外であり再監査していない。

### 4.3 確認できていない範囲

- **[未確認]** CLI、他のgateway platform、cron、delegate等で同じ400が実際に発生した証拠はない。
- **[高確度推定]** 失敗判定は共通conversation loop内にあったため、同じCodex backend responseを受ければOpen WebUI以外のsurfaceでもturnを停止し得た。
- **[未確認]** `gpt-5.6-sol` 以外のmodel、OpenAI API key直結、OpenRouter、xAI、GitHub/Copilot等での再現性は確認していない。
- **[確定]** `gpt-5.6-sol` は各失敗前に多数のrequestへ正常応答しており、調査用会話の冒頭でも通常応答していた。よって「このmodel指定は常に無効」は反証されている。

## 5. 直接原因

### 5.1 Trigger: 上流での未対応cache hint付加

**[確定: 調査用再現]** 保存request dumpの事実は次のとおり。

- request URLは `https://chatgpt.com/backend-api/codex/responses`。
- request modelは `gpt-5.6-sol`。
- JSON本文には `prompt_cache_key` がある。
- JSON本文には `prompt_cache_retention` がない。
- responseは `param=prompt_cache_retention`、`code=invalid_parameter` で400を返した。

現在のHermes transportも、`prompt_cache_retention=24h` を付けるのは、hostnameが厳密にAmazon Bedrock Mantle形で、かつ対象model familyに一致するときだけである。`chatgpt.com/backend-api/codex` ではこの関数は `None` を返し、fieldを送らない。

以上から、調査用再現で拒否されたfieldは、Hermes request作成後のCodex backend上流処理で追加されたと確定できる。

### 5.2 Failure amplifier: 回復可能な400を非再試行扱い

**[確定]** 当時のログは、各失敗について次の順序を記録している。

1. `API call failed (attempt 1/3)`
2. `Non-retryable client error`
3. `run.failed`

cache routing/retention hintは生成内容の意味には不要な最適化情報である。にもかかわらず、一般の「未対応parameter」と同じ決定的format errorとして扱われたため、provider側の別instanceへ再試行すれば解消し得る一時的な不整合でturn全体が終了した。

### 5.3 非原因として切り分けたもの

- **[確定]** Open WebUIが `prompt_cache_retention` を送った形跡はない。Pipeが `/v1/runs` へ渡す主な値はinput、history、session ID、model aliasである。
- **[確定]** HermesのCodex request本文にも当該fieldはなかった。
- **[確定]** local requestには `prompt_cache_key` があったが、これは `prompt_cache_retention` とは別のrouting hintである。
- **[確定]** errorはnative compaction用の `context_management` / `compact_threshold` の拒否ではない。
- **[高確度推定]** 長いcontextが上流routing/retry層の選択に影響した可能性はあるが、因果を示す比較証拠はない。context長を原因とは判定しない。

## 6. 検知

### 6.1 当時すでに存在した検知面

- **[確定]** `agent.log` / `errors.log` はprovider、model、endpoint、attempt、HTTP要約、errorのparam/codeを残していた。
- **[確定]** Runs APIはfailed状態、`last_event=run.failed`、error本文を保持していた。
- **[確定]** Open WebUI Progress Pipeはevent streamの `run.failed` をterminal eventとして扱い、ユーザー回答へ `Hermesエラー: <error>` を追記し、進捗状態を「失敗」にした。

### 6.2 検知上の欠陥

- **[確定]** 検知はterminal failure後の受動表示であり、同じcache hint拒否の再発を分類・集約する専用signalはなかった。
- **[確定]** ログに `attempt 1/3` と出ても、classifierが非再試行と判断したため、見かけ上のretry budgetと実挙動が一致しなかった。
- **[高確度推定]** Open WebUI上の汎用エラー表示だけでは、「入力修正が必要な決定的400」と「同じrequestを再routeすべき一時的400」をオーナーが区別できない。

### 6.3 再発時の検知条件

次を同一incident signatureとして扱う。

```text
HTTP status = 400
AND (
  error.param IN {prompt_cache_key, prompt_cache_retention}
  OR error.message contains "<same field> is not supported"
)
```

推奨する観測は二段階とする。

1. **回復した場合:** `cache_hint_rejection_retried` をwarningとして1回記録し、provider、model、field、attempt、run ID、最終outcomeを構造化する。ユーザー通知は不要。
2. **retry後もterminal failureの場合:** `run.failed` を即時にユーザー可視化し、同じ構造化情報でalert対象にする。同一sessionで2回を待たず、1回目から検知する。

秘密値、request本文、認証headerはsignalへ含めない。

## 7. 恒久対策

### 7.1 現在のインストール済みHermesに存在する対策

以下は本カードで実装したものではなく、調査時点のインストール済みソースを静的に確認したもの。

1. **送信側のfield gate**
   - `prompt_cache_retention` は厳密なBedrock Mantle hostnameと対応model familyの組合せにだけ付加する。
   - Codex backendを含む他endpointでは省略する。

2. **受信側の回復分類**
   - `prompt_cache_key` / `prompt_cache_retention` を名指す400を、一般のrequest format error判定より先に検出する。
   - `FailoverReason.server_error`、`retryable=True` として、同じturnを停止せずbounded retryへ渡す。

3. **回帰条件**
   - 元incidentと同じstructured errorがretryableになること。
   - message文字列しかないcache-key拒否もretryableになること。
   - 無関係な未対応parameter（例: `max_tokens`）は引き続きnon-retryable format errorであること。
   - Codex endpointではtransportが `prompt_cache_retention` を送らないこと。

この組合せは、上流付加そのものをPDA側から除去できなくても、同じ一時的な付加失敗でユーザー応答を停止しない設計である。

### 7.2 別カードで実装すべき追加対策案

本カードのwrite scopeは文書1本に限定されているため、以下は提案であり未実装。

1. **conversation-loop統合回帰テスト（最優先）**
   - fake providerが1回目に当該400、2回目にsuccessを返す。
   - 同じrunが `run.completed` になり、ユーザー回答が返ることを固定する。
   - retryによって既完了tool side effectが重複実行されないことも固定する。

2. **構造化telemetryとalert**
   - 6.3のsignatureを専用eventとして記録する。
   - recovered / exhaustedを区別し、terminal failureだけを即時通知する。
   - provider/model/field別の発生数を集約し、上流側の再発・拡大を検出可能にする。

3. **bounded recoveryの維持**
   - cache hint拒否だけをretry対象にし、無関係なunsupported parameterはfail-fastのままにする。
   - retry上限を外さず、恒常的な上流不整合による無限loopを防ぐ。

4. **run failure時の整合案内**
   - tool実行後にterminal failureした場合、Open WebUI表示へ「途中の変更は自動rollbackされない」旨と、再開時に状態確認が必要なことを短く示す。

### 7.3 採らない対策

- `prompt_caching.cache_ttl` を一律offにする: local requestが当該fieldを送っていなかったため、原因を除去せずcache効率だけを落とす。
- `gpt-5.6-sol` を恒久的に外す: model自体は同じsessionで多数回成功しており、常時非対応という証拠がない。
- 全HTTP 400をretryする: 決定的なformat errorまで反復し、費用・遅延・loop riskを増やす。
- Open WebUI側だけでerrorを握り潰す: runはfailedのままであり、回答継続にも整合性回復にもならない。

## 8. 検証状態と残存リスク

### 確認済み

- 元Open WebUI会話の2つのfailed runと、そのprovider/model/error署名。
- 調査会話での第3再現。
- 第3再現request本文に `prompt_cache_retention` が無いこと。
- Runs API、ログ、Open WebUI表示までのerror伝播。
- 現在のtransport gate、retry classifier、関連unit testの存在と相互整合。

### 本カードでは未確認

- 現在稼働中のgateway processが当該ソース版を実際にloadしていること。
- fake/live providerを使った「最初の400から同じrunが成功まで継続する」end-to-end結果。
- retry時にtool side effectが重複しないことの専用回帰テスト。
- 上流proxyがfieldを付加する正確な内部条件。

保持中のテキストログでは、同一署名は2026-08-19の3事象以後に見つからなかった。ただしログ保持範囲内の否定的観測であり、恒久解消の証明にはしない。

## 9. 推奨判断

- 本incidentに対してPDA設定やmodelを変更する必要はない。
- 現在の「cache hint拒否だけをretryableにする」対策方針を維持する。
- 次の実装は、統合回帰テストと構造化検知を1つの限定カードで行う。
- そのカードがgreenになるまでは、「現行ソースに防止ロジックはあるが、実runの回復経路は未検証」を残存リスクとして扱う。

## 10. 証拠索引

- 元incidentのAPI/runログ:
  - `~/.hermes/logs/agent.log.1:21938-21959`
  - `~/.hermes/logs/agent.log.1:22053-22060`
  - `~/.hermes/logs/errors.log:2827-2832`
- 調査用再現とwire-level request dump:
  - `~/.hermes/logs/agent.log.1:22213-22218`
  - `~/.hermes/sessions/request_dump_owui_b23e1ec736761e26f08c67105650f818_20260819_114402_795092.json:1-13,2234-2257`
- Open WebUI → Runs APIおよびerror表示:
  - `integrations/openwebui-hermes-progress/functions/hermes_progress_pipe.py:1616-1641,1681-1775,1842-1965`
- 現在のHermes transport gate:
  - `~/.hermes/hermes-agent/agent/transports/codex.py:108-134,515-551`
  - `~/.hermes/hermes-agent/tests/agent/transports/test_codex_transport.py:170-208`
- 現在のretry classifier:
  - `~/.hermes/hermes-agent/agent/error_classifier.py:462-476,1492-1512`
  - `~/.hermes/hermes-agent/tests/agent/test_error_classifier.py:1297-1344`
