# iPhoneホーム画面版の通知テスト・再設定

## 用途と現在の結論

既存のホーム画面版Open WebUIがWeb Pushを受け取り、通知タップでSafariの新規タブではなく同アプリ内を開けるかを確認する、本人専用の診断機能です。特定のチャット、セッション、会話タイトルを必要としません。戻り先はOpen WebUIのトップ `/` です。

初回の実機試験は成功しました。2026-09-12のowner成功報告と、Apple HTTP 201・`arrival_standalone=true` のサーバー記録を照合しています。初回は固定チャットへ戻す旧版での成功です。今回の汎用化後はトップへの遷移を自動テストとlive APIで別に検証済みです。新たな通知の実機再送試験は今回の変更確認には含めません。

これは診断機能であり、通常の完了通知をWeb Pushへ切り替える実装ではありません。既存ntfy、Hermes Progress Pipe、Open WebUI本体、`/hermes`、Funnel設定は変更しません。

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
5. 「PDA ホーム画面テスト」をタップし、ホーム画面アプリ内のOpen WebUIトップが開くこと、Safariのタブが増えないことを確認します。通常のntfy完了通知とは別です。
6. 再設定が必要なら「テスト購読を解除」→このページを開き直す→①→②。再表示・非表示だけなら購読解除は不要です。
7. 終了後はPDA側で `hide` → `status`。再利用用の鍵・購読は保持します。

通知拒否の場合はiPhoneの「設定 → 通知 → ホーム画面アプリ名」で許可して開き直します。別VAPID鍵の購読が見つかった場合は、他機能を壊さないよう上書きせず停止します。無関係な購読・Service Workerを削除しません。

通知が来ない場合は `status`、試験ページの「状態を再確認」、本人認証、iPhoneの通知設定、Tailscale接続を順に確認します。HTTP 201はApple受付までの証拠であり、端末受信の証明ではありません。`arrival_standalone` とownerの目視結果を区別して記録してください。

## 配置・起動・復旧

ソース・テスト・起動定義はこのディレクトリでGit管理します。

- origin: `https://pda-web.tailaff53a.ts.net`
- 専用経路: `/pda-push-test` → `http://127.0.0.1:9122/pda-push-test`
- 配備コピー: `~/.local/state/pda/webpush-spike/runtime/`
- Python環境: `~/.local/state/pda/webpush-spike/venv/`
- 秘密・試験記録: `~/.local/state/pda/webpush-spike/`
- unit: `~/.config/systemd/user/pda-webpush-spike.service`
- 非秘密の本人ID設定: `~/.local/state/pda/webpush-spike/service.env` の `PDA_PUSH_OWNER_ID`
- バナー操作の既存認証: `~/openwebui/.admin-api-key`（mode 0600、値を記録・表示しない）

旧24時間限定のtransient unitは、同名の通常のsystemd user serviceへ置き換えました。`enable` により次回のuser manager起動後も起動でき、時限消滅による診断不能を防ぎます。サーバーは127.0.0.1だけで待機し、明示的なテスト予約がない限り通知を送りません。Open WebUI/Hermes/Tailscaleの再起動は不要です。異常時はこのunitだけを通常の `restart` で戻します。

再配置はこのディレクトリをcwdとして行います。既存端末を再設定せず復旧するには、既存stateとVAPID鍵を保持してください。

```bash
STATE="$HOME/.local/state/pda/webpush-spike"
install -d -m 700 "$STATE" "$STATE/runtime"
python3 -m venv "$STATE/venv"  # 環境がない場合のみ
"$STATE/venv/bin/python" -m pip install -r requirements.txt
install -m 600 server.py app.js index.html sw.js control.py "$STATE/runtime/"
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

通知内容は固定文のみ、チャットの本文・タイトル・IDを送りません。Apple endpoint限定、暗号化、redirect禁止、10秒timeout、TTL120秒、20秒後の明示テスト1件だけです。

## 検証

```bash
~/.local/state/pda/webpush-spike/venv/bin/python -m pytest test_server.py test_control.py -q
node --test test_frontend.cjs
systemd-analyze --user verify pda-webpush-spike.service
```

今回の限定検証: Python20件・Node4件が成功。チャット非依存のconfig/landing、認証・origin制限、購読・暗号化・送信・中断挙動、バナーのhide/show反復と他バナー保持、フラグ検証、書き戻し確認の失敗、private credentialと送信先固定、CLI起動を対象にしました。暗号化のHTTP応答はfixtureであり実機証拠ではありません。

配備後の状態・非表示/再表示・再起動・既存設定不変の結果は `verification-2026-09-12.json` に記録済みです。hide→show→show→hideで0件→1件→1件→0件、診断サービス再起動後も非表示と購読・鍵・過去試験ログの保持を確認しました。本人認証200・未認証401・別origin書き込み403、配備ソース一致、既存Function/Valves/Serve設定/他バナー不変、Open WebUI health正常を確認しています。通常unitのenableとLinger=yesは確認済みですが、ホスト全体の再起動試験はしていません。テスト送信はボタンを押したときだけで、今回の配備確認から新しいPushを送りません。

## 完全撤去する場合だけ

通常の非表示は `hide` だけです。完全撤去はownerが撤去を指示した場合に限ります。

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
