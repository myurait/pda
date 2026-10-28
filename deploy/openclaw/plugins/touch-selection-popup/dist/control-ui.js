import { defineControlUiPlugin } from "openclaw/plugin-sdk/control-ui";
import { contract } from "./contract.js";
import { SELECTION_POPUP_STYLE } from "./style.js";
/**
 * Hides the host's "Add to chat" / "Ask in side chat" popup
 * (.chat-selection-popup) on touch devices (the primary pointer is coarse, e.g. a
 * phone), so only the system's own selection menu (copy, paste, ...) shows when
 * text in a message is selected. A desktop browser keeps the host's behaviour
 * untouched.
 */
function installStyle() {
    if ("adoptedStyleSheets" in document && typeof CSSStyleSheet !== "undefined") {
        try {
            const sheet = new CSSStyleSheet();
            sheet.replaceSync(SELECTION_POPUP_STYLE);
            document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
            return () => {
                document.adoptedStyleSheets = document.adoptedStyleSheets.filter((s) => s !== sheet);
            };
        }
        catch {
            // fall through to a <style> element
        }
    }
    const element = document.createElement("style");
    element.dataset.plugin = contract.pluginId;
    element.textContent = SELECTION_POPUP_STYLE;
    document.head.append(element);
    return () => element.remove();
}
export default defineControlUiPlugin({
    id: contract.pluginId,
    activate() {
        return installStyle();
    },
});
