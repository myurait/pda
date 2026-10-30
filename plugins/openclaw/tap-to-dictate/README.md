# Tap to Dictate

OpenClaw Control UI plugin: a single tap on the composer microphone button
starts dictation instead of toggling realtime Talk. A second tap stops it and
puts the transcript into the draft. Press-and-hold keeps working.

It also keeps the microphone stream open between dictations, so the browser
(iOS Home Screen web app in particular) does not ask for the microphone before
every dictation. See "Microphone permission" below.

## How it works

The built-in composer starts dictation only from a press-and-hold (150 ms arm +
350 ms hold) and treats a short press as a Talk toggle. There is no public API
to start dictation. `src/control-ui.ts` adds capture-phase pointer listeners
that swallow the release of a short press on the microphone button, so the
built-in controller carries on to its own start path. The controller, the
transcription session, and the transcript insertion are all the host's.

It depends on the host's button classes
(`chat-send-btn--voice` + `chat-send-btn--hold-enabled`) and on the controller's
150 ms + 350 ms timing (`START_AFTER_MS`). Re-check both after an OpenClaw update.

## Microphone permission

The host calls `getUserMedia` for every dictation and stops the tracks when it
ends (`talk.session` relay, not the Web Speech API). WebKit keeps a grant only
for the page and forgets it once no capture has run for a while (10 minutes in
current WebKit; about 1 minute was reported earlier). While a capture is running
the grant is kept for 24 hours. A Home Screen web app does not use Safari's saved
per-site "Allow". So on iOS the prompt returns before nearly every dictation.

`src/mic-keeper.ts` wraps `navigator.mediaDevices.getUserMedia` for audio-only
requests. The first request acquires the microphone and keeps that track; each
dictation gets a clone of it. The host stopping its clone does not end the
capture, and the next dictation needs no `getUserMedia` call, hence no prompt.

Side effects:

- The microphone stays open, so the iOS recording indicator (orange dot) stays
  on while the app holds it, and other audio on the phone may be affected by the
  open capture (not checked on a device). Nothing is recorded or sent between dictations: the kept track
  is not connected to anything.
- The kept track is released after 30 minutes without a dictation, on `pagehide`,
  and when the browser ends or mutes it (then the next dictation acquires again,
  and may prompt).
- The idle time is read from `localStorage["tap-to-dictate:mic-hold-minutes"]`
  at every dictation: a number of minutes, `0` turns the keeper off (the host
  behaves as before), unset means 30. Set it in the browser console of the
  Control UI: `localStorage.setItem("tap-to-dictate:mic-hold-minutes", "120")`.

## Build and install

```sh
npm install        # also pulls a peer copy of openclaw (~650 MB); node_modules/ is not needed at runtime,
                   # except a node_modules/openclaw link to the installed package
npm run build
npm test
npm run validate
openclaw plugins install . --link --force
```

On the mini PC the plugin is loaded in place from `/home/user/pda/plugins/openclaw/tap-to-dictate`
(see [deploy/openclaw/README.md](../../../deploy/openclaw/README.md)); `dist/` is committed.

Requires **Settings > Labs > Custom plugin UI** (`gateway.controlUi.experimental.customPlugins: true`).
After a browser-only rebuild: **Plugins > Advanced > Customize UI > Reload plugin UI**.
After a backend edit: `openclaw plugins reload tap-to-dictate`.

## Undo

`openclaw plugins disable tap-to-dictate` (or uninstall), then reload the browser tab.
