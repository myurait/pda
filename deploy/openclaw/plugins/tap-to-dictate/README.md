# Tap to Dictate

OpenClaw Control UI plugin: a single tap on the composer microphone button
starts dictation instead of toggling realtime Talk. A second tap stops it and
puts the transcript into the draft. Press-and-hold keeps working.

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

## Build and install

```sh
npm install        # also pulls a peer copy of openclaw (~650 MB); node_modules/ is not needed at runtime,
                   # except a node_modules/openclaw link to the installed package
npm run build
npm run validate
openclaw plugins install . --link --force
```

Requires **Settings > Labs > Custom plugin UI** (`gateway.controlUi.experimental.customPlugins: true`).
After a browser-only rebuild: **Plugins > Advanced > Customize UI > Reload plugin UI**.
After a backend edit: `openclaw plugins reload tap-to-dictate`.

## Undo

`openclaw plugins disable tap-to-dictate` (or uninstall), then reload the browser tab.
