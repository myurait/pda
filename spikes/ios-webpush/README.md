# iPhone Home Screen Web Push spike

Question: with the existing Open WebUI Home Screen installation, can a server-originated notification received while the iPhone is locked open the exact conversation inside that app without creating a Safari tab?

This is a temporary experiment, not replacement of the completion-notification integration. Owner authorized the physical-device experiment on 2026-09-11 in owui_a7d12bd6b2fe070c5f674c8a2a0c9712. Existing ntfy, Progress Pipe, Open WebUI root and Hermes routes are unchanged.

## Architecture

- Existing origin: https://pda-web.tailaff53a.ts.net
- Added route: /pda-push-test -> http://127.0.0.1:9122/pda-push-test
- Fixed target: the owner-authenticated current conversation, configured at server launch; no client-selected redirect destination.
- Entry: Open WebUI's standard banner, ID `pda-webpush-spike`, containing an ordinary same-context relative anchor with `data-sveltekit-reload`. Do not start the test from an ntfy click or an external-tab chat hyperlink. Do not install a separate test PWA; that would test a different app.
- Feature detection: `window.pushManager` for Apple's declarative Web Push (no SW). Fallback registers only `/pda-push-test/sw.js`, scoped to `/pda-push-test/`, with no fetch/cache handlers, root registration, or client claiming.
- The original manifest is retained. Its start URL is `/`, display mode is `standalone`; its default manifest scope covers the test and chat paths.
- Push registration is invoked immediately inside the permission button's tap event. All API calls require the existing Open WebUI owner session. Cross-origin writes are denied.
- One fixed-content notification is scheduled 20 seconds after the explicit send button. The server, not an iOS page timer, owns the delay. Only `https://web.push.apple.com` endpoints are accepted. VAPID + aes128gcm encryption; no redirects; bounded transport timeout; TTL 120 seconds.
- Notification navigate opens the same-origin test landing page. It records the actual standalone flag and then returns in the same context to the fixed chat. That flag is diagnostic, not independent proof of physical receipt or no Safari-tab increase.
- No prompts, response text, chat title or chat ID enter the push payload. Subscription and private key are mode 0600 inside a mode 0700 directory outside Git. Access logs are disabled; event logs omit endpoint, keys and auth tokens.
- Delivery is one explicit experiment at a time; it is not an automatic completion hook. No retry after process interruption. In-flight transport cancellation is recorded as uncertain, not unsent.

## Runtime and rollback

Runtime: `/home/user/.local/state/pda/webpush-spike/runtime/` (exact tested asset copy).
State and isolated venv: `/home/user/.local/state/pda/webpush-spike/`.
Transient user unit: `pda-webpush-spike.service`, loopback-only port 9122, RuntimeMaxSec=86400. It is not installed/enabled for reboots. Test service startup does not restart Open WebUI, Hermes, Tailscale, or the gateway.

The baseline JSON in the state directory holds the prior Serve configuration, banners, Function digest and deployed asset digests; it contains no bearer token, VAPID private key or push endpoint.

Rollback after the physical test:
1. In the test page, use the test-unsubscribe button to cancel an unsent reservation, remove the server's test subscription, and unsubscribe the matching browser key only. Never remove unrelated subscriptions or root service workers.
2. Through the existing authenticated Open WebUI banners API, remove only `id=pda-webpush-spike` from a fresh list and read back; preserve all other banners, including changes since this experiment began.
3. Remove only this Serve route with:
   `/home/user/.local/opt/tailscale-1.102.2/tailscale --socket=/home/user/.local/share/tailscale-pda/tailscaled.sock serve --bg --yes --https=443 --set-path /pda-push-test http://127.0.0.1:9122/pda-push-test off`
4. Verify all unrelated Serve settings are unchanged. Never use `serve reset` or broad `serve --https=443 off`.
5. Stop only `pda-webpush-spike.service`. Preserve sanitized experiment evidence. Remove private test key/subscription material only within this experiment's scope after recording the verdict.

The route-removal command was actually exercised before adding the banner; complete Serve JSON equality with the baseline was verified, then the route was restored. After the 24-hour transient service expires, the test route/banner must still be removed (expiry does not remove them automatically); normal Open WebUI routes remain unaffected.

## Verification on 2026-09-11

- Python focused tests: 12 passed. Authentication, origin rejection, one scheduled push, subscription privacy, strict endpoint validation, tap telemetry, unsubscribe, and in-flight uncertainty behavior exercised.
- Node behavior tests: 4 passed. Ordinary tabs cannot register, permission request remains in the user gesture, landing records mode/returns to the fixed chat, and legacy SW renders/navigates only to same-origin test paths.
- Actual pywebpush 2.5.0 crypto/VAPID code executed with the final HTTP send intercepted in a hermetic test. Payload was encrypted; redirect following disabled. Its fixture HTTP 201 is NOT live Apple delivery evidence.
- Live server: HTML 200; missing-owner API 401; real existing owner authentication 200; cross-origin write 403; no subscription or sends at setup verification.
- Server-side Tailscale userspace dial -> valid TLS 1.3 -> test HTML 200.
- Added route is the only Serve JSON change; Funnel remains disabled. Port 9122 is 127.0.0.1 only.
- Test banner written/read back; pre-existing banner list retained and notification Function digest unchanged; live Open WebUI health true.

## Physical-device acceptance (pending)

Open the existing Home Screen app, use its new banner, permit notifications, request the 20-second test and lock the phone. Tap specifically `PDA ホーム画面テスト` (not the existing ntfy completion alert). Confirm physical lock-screen receipt, the exact original chat opens in the Home Screen app, and Safari tab count does not increase. Correlate the user's report with server push status and landing telemetry. Repeat if the initial result is ambiguous; do not promote desktop mocks or server HTTP success into iPhone proof.

## Verdict: PARTIAL — device test pending

The isolated, authenticated test path is operational. Feasibility on the owner's iPhone is not established yet. Do not switch normal completion notifications or mark the original Kanban outcome complete until the physical acceptance conditions are met.

Primary references: https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers ; https://webkit.org/blog/16535/meet-declarative-web-push/ ; https://tailscale.com/docs/reference/tailscale-cli/serve .
