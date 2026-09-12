# iPhoneホーム画面版の通常通知・テスト・再設定

## 用途と現在の結論

既存のホーム画面版Open WebUIがWeb Pushを受け取り、通知タップでSafariの新規タブではなく同アプリ内を開けるかを確認する、本人専用の診断機能です。特定のチャット、セッション、会話タイトルを必要としません。戻り先はOpen WebUIのトップ `/` です。

初回の実機試験は成功しました。2026-09-12のowner成功報告と、Apple HTTP 201・`arrival_standalone=true` のサーバー記録を照合しています。初回は固定チャットへ戻す旧版での成功です。その後の診断汎用化ではトップへの遷移を自動テストとlive APIで別に検証し、新たな実機Pushは送信しませんでした。以下の通常通知統合は、その次の別変更です。

2026-09-12の追加owner指示により、同じ購読を通常のOpen WebUI完了通知にも接続しました。診断はチャット非依存でトップへ戻り、通常通知は毎回その通知を発生させたチャットへ戻ります。通常経路も、実機確認依頼へのowner回答「done」により、通知受信・ホーム画面版で対象チャット表示・Safariタブ非増加を確認済みです。初回診断の成功とは別のowner実機報告として記録しています。

## 通常通知の切替と復旧

通常の完了通知は、既存Hermes Progress Pipe → 本PDAのntfy互換relay → 暗号化Web Push → 既存ホーム画面版Open WebUIへ送ります。Pipeの変更は後述の特定ローカルrelay宛先の許可だけです。本人の保存済みassistant `done=true`、title/回答冒頭、非ブロッキング、message単位の送信試行抑止を維持します。通常通知のntfy.sh送信は行わず、失敗時にも自動で二重送信・旧経路へのfallbackはしません。

```bash
PY="$HOME/.local/state/pda/webpush-spike/venv/bin/python"
CTL="$HOME/.local/state/pda/webpush-spike/runtime/notifications.py"
"$PY" "$CTL" status   # 秘密値を表示せずlive/persisted一致を確認
"$PY" "$CTL" webpush  # 本人購読・サービス応答を確認してホーム画面版へ
"$PY" "$CTL" ntfy     # 退避した旧ntfy経路へ戻す
"$PY" "$CTL" off      # 通常完了通知だけを停止
```

操作はPDAが行います。`webpush`の正常結果は `mode=webpush`, `persisted_matches=true`, `enabled=true`。`NTFY_SERVER_URL` と `NTFY_TOPIC` という既存Valve名を互換利用していますが、送信先はntfy.shではなく `http://host.docker.internal:9122/pda-push-test/notify/<秘密token>` です。relayは256-bit専用tokenで認証し、本人の既存購読だけへ送信します。tokenをログ、URL例、Gitに出してはいけません。

このホストのTailscaleはuserspace動作で、通常ホスト/コンテナDNSから公開アプリ名は解決できません。送信元コンテナは既存`host.docker.internal:host-gateway`経由で、ホスト内Docker bridgeだけを通ります。Pipeとinstallerはこの完全一致のrelay URLだけを特例として許可し、一般の外部HTTPや別port/pathは引き続き拒否します。relay tokenと本文はホスト内のHTTP区間では平文なので、ローカルDocker管理者を信頼境界に含みます。ホスト外のApple向けはHTTPS + Web Push暗号化です。

切替時は他のValves（計画強制の停止状態を含む）を保持し、更新後に全体を再取得確認します。失敗時は通知の2項目だけを復元し、再取得で検証します。元の2項目は `~/.local/state/pda/webpush-spike/ntfy-rollback.json` にmode0600で退避。切替値は `~/openwebui/.completion-push.json` にmode0600で保持し、更新したinstallerもこれを優先します。再インストール後に旧通知へ戻ってしまうことを防ぎます。Open WebUI/Hermesの再起動は不要です。

共有 `~/openwebui/.env` は変更しません。チャット完了とは独立した日次状態報告のntfy配送は今回の切替対象外で、従来どおり維持します。

relayのHTTP202は受付だけ、Apple HTTP201はApple受付だけです。既存方式同様にadvisory配送でありdurable queueではありません。通知サービス再起動時は自動再送せず、queuedを未再送、publishingを配送不明として記録します。最大8件の同時送信、正常時10秒の送信timeout、TTL120秒。通常通知のローカル記録 `notifications.json` は直近200件（送信中は別途保持）のID・遷移先・本文/titleのSHA256・結果・起動modeだけで、本文/titleの平文は保存しません。iPhone上の通知履歴には表示内容が残ります。

通常のtapは同一originの既存landingへ入り、本人認証で通知IDから対象を引き、検証済み `/c/<chat_id>` に同一画面遷移します。入力URLで任意redirectは指定できません。古い記録が保持件数を超えて消えた場合は自動遷移できず、トップへ戻るリンクを表示します。ログイン期限切れはホーム画面版で再ログインしてから再試行してください。

購読期限切れや未受信時は `status` と本人用 `/api/status` の `notifications` を確認し、必要なら診断入口をshowして再設定します。`ntfy`は端末再設定までの手動復帰策です。診断バナーのhideは通常通知を停止しませんが、「通知購読を解除」は通常通知も停止します。

## 普段は入口を非表示

表示フラグの保存先:
`~/.local/state/pda/webpush-spike/settings.json`

```json
{"show_banner": false}
```

`false` はOpen WebUI上部の試験バナーだけを取り除きます。診断ページ、Push購読、VAPID鍵、通知許可は消しません。非表示はアクセス制御ではありません。APIには従来どおりOpen WebUI本人認証と同一origin条件が必要です。

操作はPDA側で行います。通常はownerが「通知テストを再表示して」「通知テストを隠して」とPDAに指示すれば足ります。

```bash
# 再表示
~/.local/state/pda/webpush-spike/venv/bin/python ~/.local/state/pda/webpush-spike/runtime/control.py show

# 非表示
~/.local/state/pda/webpush-spike/venv/bin/python ~/.local/state/pda/webpush-spike/runtime/control.py hide

# フラグと実際のバナーが一致しているか確認（更新しない）
~/.local/state/pda/webpush-spike/venv/bin/python ~/.local/state/pda/webpush-spike/runtime/control.py status

# JSONを直接編集した場合、そのフラグを反映
~/.local/state/pda/webpush-spike/venv/bin/python ~/.local/state/pda/webpush-spike/runtime/control.py apply
```

JSON編集だけではUIは変わりません。`show` / `hide` はAPI更新→再取得一致確認→フラグ保存まで行うので、通常はこちらを使います。既存一覧から `id=pda-webpush-spike` だけを追加・除去し、他のバナーをそのまま保持します。同時の管理画面編集にはAPI側のCASがないため、編集を重ねないでください。再取得不一致は失敗として報告し、成功フラグを保存しません。

非表示の正常結果は `show_banner=false`, `live_count=0`, `matches=true`。再表示時は `true`, `1`, `true` です。再表示は診断サービスの応答を確認できた場合だけ許可します。Open WebUIの再起動は不要です。既に開いているiPhone画面に反映されなければ、ホーム画面版を終了して同じアイコンから開き直してください。

## iPhoneでの再テスト・再設定

1. PDA側で `show`。必要なら先に `systemctl --user restart pda-webpush-spike.service`。再度 `status` で `service_ready=true` を確認します。
2. Safariのタブやチャット中の外部リンクではなく、既存のホーム画面アイコンからOpen WebUIを開きます。ログイン済みであることを確認し、上部「通知テストを開く」を押します。別のホーム画面アイコンは作りません。
3. 「① このアプリの通知を許可」を押します。既に許可済みなら新たなOSダイアログは不要です。OSの通知許可は端末の所有者が操作します。
4. 「② 20秒後にテスト通知を送る」を押し、iPhoneをロックします。サーバー側のタイマーなので、ページが停止しても送信予約は進みます。
5. 「PDA ホーム画面テスト」をタップし、ホーム画面アプリ内のOpen WebUIトップが開くこと、Safariのタブが増えないことを確認します。通常通知と同じ購読ですが、診断の戻り先はトップです。
6. 再設定が必要なら「通知購読を解除（通常通知も停止）」→このページを開き直す→①→②。再表示・非表示だけなら購読解除は不要です。
7. 終了後はPDA側で `hide` → `status`。再利用用の鍵・購読は保持します。

通知拒否の場合はiPhoneの「設定 → 通知 → ホーム画面アプリ名」で許可して開き直します。別VAPID鍵の購読が見つかった場合は、他機能を壊さないよう上書きせず停止します。無関係な購読・Service Workerを削除しません。

通知が来ない場合は `status`、試験ページの「状態を再確認」、本人認証、iPhoneの通知設定、Tailscale接続を順に確認します。HTTP 201はApple受付までの証拠であり、端末受信の証明ではありません。`arrival_standalone` とownerの目視結果を区別して記録してください。

## 配置・起動・復旧

ソース・テスト・起動定義はこのディレクトリでGit管理します。今回の変更はローカルmainへ統合済みです。originは公開リポジトリであるため、運用記録の外部公開を伴うpushは今回行っていません。

- origin: `https://pda-web.tailaff53a.ts.net`
- 専用経路: `/pda-push-test` → `http://127.0.0.1:9122/pda-push-test`
- 配備コピー: `~/.local/state/pda/webpush-spike/runtime/`
- Python環境: `~/.local/state/pda/webpush-spike/venv/`
- 秘密・試験記録: `~/.local/state/pda/webpush-spike/`
- unit: `~/.config/systemd/user/pda-webpush-spike.service`
- 非秘密の本人ID設定: `~/.local/state/pda/webpush-spike/service.env` の `PDA_PUSH_OWNER_ID`
- バナー操作の既存認証: `~/openwebui/.admin-api-key`（mode 0600、値を記録・表示しない）

旧24時間限定のtransient unitは、同名の通常のsystemd user serviceへ置き換えました。`enable` により次回のuser manager起動後も起動でき、時限消滅による診断不能を防ぎます。ブラウザ用APIは127.0.0.1と既存Serve経路を維持し、コンテナ送信用に既存Docker host-gateway `172.17.0.1:9122` にも待機します。Docker側の接続は `/notify/` だけを許可し、LANアドレスや0.0.0.0では待機しません。明示的な診断予約または認証済み通常完了通知の受信時だけ送信します。Open WebUI/Hermes/Tailscaleの再起動は不要です。異常時はこのunitだけを通常の `restart` で戻します。

再配置はこのディレクトリをcwdとして行います。既存端末を再設定せず復旧するには、既存stateとVAPID鍵を保持してください。

```bash
STATE="$HOME/.local/state/pda/webpush-spike"
install -d -m 700 "$STATE" "$STATE/runtime"
python3 -m venv "$STATE/venv"  # 環境がない場合のみ
"$STATE/venv/bin/python" -m pip install -r requirements.txt
install -m 600 server.py app.js index.html sw.js control.py notifications.py live_completion_probe.py "$STATE/runtime/"
install -D -m 600 pda-webpush-spike.service "$HOME/.config/systemd/user/pda-webpush-spike.service"
```

初回再構築時だけ、Open WebUIの既存本人認証で `/api/v1/auths/` の `id` を確認し、`service.env` に `PDA_PUSH_OWNER_ID=<確認したid>` をmode 0600で保存します。特定チャットIDやセッションIDは設定しません。初回のtransient unitがまだ動いている場合は、先にそれだけをstopしてから通常unitを起動します。

```bash
systemctl --user stop pda-webpush-spike.service
systemctl --user daemon-reload
systemctl --user enable --now pda-webpush-spike.service
"$STATE/venv/bin/python" "$STATE/runtime/control.py" hide
"$STATE/venv/bin/python" "$STATE/runtime/control.py" status
```

秘密鍵・購読情報はGitに置きません。stateディレクトリは0700、ファイルは0600。`events.jsonl` はmode・時刻・結果だけを記録し、token、push endpoint、鍵を含みません。予約中の再起動は自動再送せず、中断状態を残します。送信中の中断は未送信と断定せず不明として扱います。

Serve経路は既存設定を維持します。再構築で経路がない場合だけ、`serve status --json` で他経路を確認してから専用pathを登録します。

```bash
~/.local/opt/tailscale-1.102.2/tailscale --socket="$HOME/.local/share/tailscale-pda/tailscaled.sock" serve --bg --yes --https=443 --set-path /pda-push-test http://127.0.0.1:9122/pda-push-test
```

`serve reset` やHTTPS全体の停止は使いません。

## 動作契約と変更点

初版は試験用の固定チャットを `--target` で指定していました。再利用版ではこの引数を削除し、configとarrivalの戻り先を `/` に統一しました。「この会話」「元の会話」というUI・通知文を「Open WebUIのトップ」へ変更しました。任意redirectの入力口はありません。

バナーは削除して終わりではなく、`control.py` と `show_banner` で再生成可能にしました。既存バナーIDを維持し、何度showしても1件、hideしても他のバナーは残ります。表示制御はOpen WebUIのサポートされたbanners APIを使い、DB直接更新・Function差し替えを行いません。

Push処理自体は初回実機成功版を維持します。`window.pushManager` があればDeclarative Web Pushを使い、非対応時だけ試験path内のService Workerへfallbackします。root worker・fetch/cache handler・client claimingは追加しません。既存manifestを保持します。リンクは同じアプリ内の通常相対リンクと `data-sveltekit-reload` を使います。

診断の通知内容は固定文のみ、チャット本文・タイトル・IDを送りません。通常通知は既存Pipeが承認済みの保存済みタイトル（100文字）と回答冒頭（240文字）を暗号化し、Appleへ送ります。Apple endpoint限定、redirect禁止、10秒timeout、TTL120秒は共通です。

## 検証

```bash
~/.local/state/pda/webpush-spike/venv/bin/python -m pytest test_server.py test_control.py -q
node --test test_frontend.cjs
systemd-analyze --user verify pda-webpush-spike.service
```

診断再利用化時の限定検証: Python20件・Node4件が成功。チャット非依存のconfig/landing、認証・origin制限、購読・暗号化・送信・中断挙動、バナーのhide/show反復と他バナー保持、フラグ検証、書き戻し確認の失敗、private credentialと送信先固定、CLI起動を対象にしました。暗号化のHTTP応答はfixtureであり実機証拠ではありません。

診断再利用化時の配備状態・非表示/再表示・再起動・既存設定不変の結果は `verification-2026-09-12.json` に記録済みです。hide→show→show→hideで0件→1件→1件→0件、診断サービス再起動後も非表示と購読・鍵・過去試験ログの保持を確認しました。本人認証200・未認証401・別origin書き込み403、配備ソース一致、既存Function/Valves/Serve設定/他バナー不変、Open WebUI health正常を確認しています。通常unitのenableとLinger=yesは確認済みですが、ホスト全体の再起動試験はしていません。テスト送信はボタンを押したときだけで、この旧診断配備確認では新しいPushを送りませんでした。

## 通常通知への反映と確認（2026-09-12）

通常の完了通知をWeb Pushへ反映済みです。Open WebUI/Hermes/Serveは再起動せず、通知専用user serviceだけを更新・再起動しました。Functionはv2.1.0-local.19をAPIからsource更新し、既存Valvesを全保持した後、通知の2項目だけを切り替えています。現行の計画強制停止を維持しています。全体installerは実行していません。

最終sourceでPython 139件、Node 5件が通過。source/runtime/APIの照合は10資産で一致し、元の購読・VAPID鍵・共有env・非表示設定・過去の診断結果・他バナーも不変です。`webpush → ntfy → webpush` の切替・復元・永続値の一致を実環境で確認しました。初回配備の健康確認でcontrollerの必要とするcapability flag不足を検出し、RED→GREENの回帰テストと差分の独立reviewを経て修正してから通常送信へ切り替えました。

実frontend形式の新規チャット「通常通知の切替テスト」で、保存済みdone=true・画面用完了status・通常Web Push 1件・Apple HTTP201・保存タイトル/本文一致・旧ntfy重複0件を確認しました。直接非同期APIも実行完了し、通常Web Push増加0件、旧ntfy増加0件を確認しています。Tailscale userspace netstack経由の既存診断URLもTLS1.3/HTTP200でした。

詳細は `verification-normal-2026-09-12.json`。初回保存時は通常経路の実機確認待ちでしたが、その後の確認依頼（届いた通常通知をタップし、ホーム画面版の対象チャットが開きSafariのタブが増えないこと）に対し、2026-09-12にownerが「done」と回答しました。通常経路の端末条件は、このowner実機報告により確認済みです。追記時の保持された試験通知レコードには `arrival_standalone` がなく、サーバーが起動modeを観測したとは主張しません。初回診断のtelemetryやApple受付を今回の端末証拠の代わりにはしていません。

同日の読み取り確認でも通常通知は `mode=webpush`, `persisted_matches=true`, `enabled=true`、診断入口は `show_banner=false`, `live_count=0`, `matches=true`, `service_ready=true` でした。この確認追記では再送信・設定変更・サービス再起動を行っていません。ホスト全体の再起動試験も行っていません。

通常通知の実機確認待ちは解消しました。Kanban `t_5eccc2cc` に既存記録のある補助ツールの保守安全性（初回ntfy復元先の固定、全Valves更新と同時編集の競合、古いin-flightを含む記録件数の上限）は別の残項目として維持します。今回の成功報告で将来の設定切替の競合安全性まで確認済みにはせず、次回設定切替前の評価事項として残します。

## 通常通知の検証手順

リポジトリrootで実行する対象テスト:

```bash
uv run --no-project --with pytest --with pytest-asyncio --with aiohttp --with fastapi --with pywebpush --with cryptography --with requests python -m pytest spikes/ios-webpush/ integrations/openwebui-hermes-progress/tests/test_hermes_progress_pipe.py integrations/openwebui-hermes-progress/tests/test_install_hermes_progress_pipe.py -q
node --test spikes/ios-webpush/test_frontend.cjs
```

実送信（ownerが試験を指示したときだけ）:

```bash
~/.local/state/pda/webpush-spike/venv/bin/python ~/.local/state/pda/webpush-spike/runtime/live_completion_probe.py
```

このprobeは配備済み `~/openwebui/tests/live_openwebui_notification_probe.py` の既存API/helperを利用します。再構築ではintegrationの同ファイルも配置してください。特定の既存チャットを必要とせず、実frontend形式で新規chatを1件作成し、保存された最終回答から通常通知を1件送ります。確認対象は `saved_done`, `completion_push_count=1`, `push_status=201`, title/bodyの保存値一致、`legacy_ntfy_matching_count=0`。成功/失敗を問わず試験chatはタップ確認と調査用に残し、無断削除しません。

ownerは送信前にiPhoneをロックし、届いた通常通知をタップして、ホーム画面版内のその試験chatを開けること、Safariタブが増えないことを確認します。本人用status内の `arrival_standalone=true` は補助証拠であり、ownerの実機報告と合わせるまで端末条件を完了扱いにしません。

## 完全撤去する場合だけ

通常の非表示は `hide` だけです。完全撤去はownerが撤去を指示した場合に限ります。撤去前に必ず `notifications.py ntfy` で通常完了通知を旧経路へ戻し、`status`で一致を確認してください。

1. `show` して試験ページの購読解除ボタンを押し、端末側とサーバー側の試験購読だけを解除します。送信開始済みなら確定まで待ちます。
2. `hide` と `status` で試験バナーが0件、他バナーが保持されたことを確認します。
3. 専用Serve経路だけを削除します。
   `~/.local/opt/tailscale-1.102.2/tailscale --socket="$HOME/.local/share/tailscale-pda/tailscaled.sock" serve --bg --yes --https=443 --set-path /pda-push-test http://127.0.0.1:9122/pda-push-test off`
4. `systemctl --user disable --now pda-webpush-spike.service`。unit・配備コピーの削除はこの診断の範囲だけに限定します。他のServe経路・Open WebUI・Hermes・ntfyを変更しません。
5. 検証記録を保持したうえで、必要なら試験専用の秘密鍵・購読情報を削除します。再利用する場合は消しません。

## 参考

- https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers
- https://webkit.org/blog/16535/meet-declarative-web-push/
- https://tailscale.com/docs/reference/tailscale-cli/serve
