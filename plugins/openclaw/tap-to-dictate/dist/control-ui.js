import { defineControlUiPlugin } from "openclaw/plugin-sdk/control-ui";
import { contract } from "./contract.js";
/**
 * The built-in composer starts dictation only from a press-and-hold gesture:
 * the microphone button controller arms 150 ms after pointerdown, starts
 * recording 350 ms later, and treats a release before that as a tap, which
 * toggles realtime Talk. There is no public API to start dictation, and the
 * controller is private to the Control UI bundle.
 *
 * This plugin keeps the controller's own start path and changes only what it
 * sees: a release (and the follow-up lostpointercapture / pointermove events)
 * that happens before recording would start is swallowed, so the controller
 * carries on as if the button were still held. After the controller has started
 * recording, a later tap stops dictation through the built-in click handler.
 */
// Matches the microphone button only while the built-in hold gesture is wired.
// While recording the button swaps to --dictating, so stop taps are untouched.
const MIC_BUTTON = "button.chat-send-btn--voice.chat-send-btn--hold-enabled";
// pressing (150 ms) + holding (350 ms) in the built-in controller.
const START_AFTER_MS = 500;
// Clean-up margin after the controller has started.
const SETTLE_AFTER_MS = 700;
// composedPath() keeps the match working if the composer ever renders inside an
// open shadow root, where event.target is retargeted to the shadow host.
function isMicButton(event) {
    return event.composedPath().some((node) => node instanceof Element && node.matches(MIC_BUTTON));
}
export default defineControlUiPlugin({
    id: contract.pluginId,
    activate(host) {
        let press = null;
        let settleTimer = null;
        const clearSettleTimer = () => {
            if (settleTimer !== null) {
                clearTimeout(settleTimer);
                settleTimer = null;
            }
        };
        const beforeStart = (event) => press !== null &&
            event.isTrusted &&
            event.pointerId === press.pointerId &&
            performance.now() - press.startedAt < START_AFTER_MS;
        const onPointerDown = (event) => {
            clearSettleTimer();
            press = null;
            if (!event.isTrusted || event.button !== 0 || !isMicButton(event))
                return;
            press = {
                pointerId: event.pointerId,
                startedAt: performance.now(),
                released: false,
            };
        };
        const onPointerUp = (event) => {
            if (!press || press.released || !beforeStart(event))
                return;
            press.released = true;
            event.stopImmediatePropagation();
            // The controller suppresses the click that follows its pointerdown until it
            // sees the matching release. The swallowed release is replayed after the
            // controller has started so that suppression is cleared even if no click
            // arrives. It is a no-op when the click already cleared it.
            const { pointerId } = press;
            clearSettleTimer();
            settleTimer = setTimeout(() => {
                settleTimer = null;
                press = null;
                document.dispatchEvent(new PointerEvent("pointerup", { pointerId, bubbles: true }));
            }, SETTLE_AFTER_MS);
        };
        // Releasing a captured pointer fires lostpointercapture, which the controller
        // treats as a cancel; moving the cursor off the button also cancels.
        const swallowWhileArming = (event) => {
            if (press?.released && beforeStart(event))
                event.stopImmediatePropagation();
        };
        const options = { capture: true };
        window.addEventListener("pointerdown", onPointerDown, options);
        window.addEventListener("pointerup", onPointerUp, options);
        window.addEventListener("lostpointercapture", swallowWhileArming, options);
        window.addEventListener("pointermove", swallowWhileArming, options);
        return () => {
            clearSettleTimer();
            press = null;
            window.removeEventListener("pointerdown", onPointerDown, options);
            window.removeEventListener("pointerup", onPointerUp, options);
            window.removeEventListener("lostpointercapture", swallowWhileArming, options);
            window.removeEventListener("pointermove", swallowWhileArming, options);
        };
    },
});
