# Touch Selection Popup

OpenClaw Control UI plugin for touch devices (スマートフォン). It hides the
host's **"Add to chat" / "Ask in side chat"** popup (`.chat-selection-popup`) that
appears when text in a message is selected. The system's own selection menu
(copy, paste, ...) is not touched. It applies only while the primary pointer is
coarse (`(pointer: coarse)`); a desktop browser behaves exactly as before.

## Why a plugin and not a setting

The popup has no setting. The host builds it in the transcript's `pointerup`
handler when text inside a message bubble (`.chat-bubble`) is selected. It does
not appear for a selection inside the composer.

## Enter does not send: that is a setting, not this plugin

On a phone, Enter should insert a newline. That is
**Settings > Appearance > Send shortcut = Cmd/Ctrl+Enter**
(`ui.prefs.chatSendShortcut: "modifier-enter"`), which the host supports itself.
The preference is saved in the Gateway config and is shared by every browser, so
Enter is a newline on every device and sending is Cmd/Ctrl+Enter or the send
button.

```sh
openclaw gateway call config.patch --params '{"raw":"{\"ui\":{\"prefs\":{\"chatSendShortcut\":\"modifier-enter\"}}}","baseHash":"<hash from config.get>"}'
```

(`openclaw config set ui.prefs.chatSendShortcut modifier-enter` is the same change when the CLI has write access.)

## How it works

`src/control-ui.ts` adds the style rule from `src/style.ts`:

```css
@media (pointer: coarse) { .chat-selection-popup { display: none !important; } }
```

The host still builds and removes the popup itself. The plugin depends on the
host's class name `.chat-selection-popup`; re-check it after an OpenClaw update.

`src/style.ts` holds the rule apart from the DOM; `npm test` covers it.

## Build and install

```sh
npm install        # also pulls a peer copy of openclaw (~650 MB); node_modules/ is not needed at runtime,
                   # except a node_modules/openclaw link to the installed package
npm run build
npm run validate
npm test
openclaw plugins install . --link --force
```

`build` needs `typescript` and `esbuild` to be resolvable from this folder. If you
skip `npm install`, link them for the build and remove the links before installing
(the install scan rejects a `node_modules` link that points outside the folder,
except `node_modules/openclaw`):

```sh
mkdir -p node_modules && ln -sfn /home/user/v03/openclaw/lib/node_modules/openclaw node_modules/openclaw
# link typescript, @typescript, esbuild and @esbuild from another plugin's node_modules, then:
# ... build / validate / test ...
rm node_modules/typescript node_modules/@typescript node_modules/esbuild node_modules/@esbuild
```

On the mini PC the plugin is loaded in place from `/home/user/pda/plugins/openclaw/touch-selection-popup`
(see [deploy/openclaw/README.md](../../../deploy/openclaw/README.md)); `dist/` is committed.

Requires **Settings > Labs > Custom plugin UI** (`gateway.controlUi.experimental.customPlugins: true`).
After a browser-only rebuild: **Plugins > Advanced > Customize UI > Reload plugin UI**.

## Undo

`openclaw plugins disable touch-selection-popup` (or uninstall), then reload the browser tab.
