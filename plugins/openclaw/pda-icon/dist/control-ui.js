import { defineControlUiPlugin } from "openclaw/plugin-sdk/control-ui";
import { ICON_VERSION } from "./icon-version.generated.js";
// 画像を配信する HTTP ルート (index.ts の ROUTE と同じ)。
const ROUTE = "/pda-icon";
const iconUrl = (file) => `${window.location.origin}${ROUTE}/${file}?v=${ICON_VERSION}`;
// 本体が index.html の <link> に付ける印と、その参照先の差し替え先。
// 本体は起動時に、各 <link> の href を自分の画像に設定する (control-ui-core の起動処理)。
// このコードはその後 (Gateway に接続して、プラグインの画面のコードが有効になった時点) に動く。
const APPLE_TOUCH = 'link[rel="apple-touch-icon"]';
const ICON = 'link[rel="icon"]';
// 本体がタブのアイコンに稼働中の印などを重ねるとき、元の href をここに入れておき、戻すときに使う。
// 内部の印なので、無くても (名前が変わっても) 動くようにしてある。
const HOST_ORIGINAL = "openclawOriginalFavicon";
const originals = new WeakMap();
function fileForIcon(link) {
    let type = link.getAttribute("type");
    const saved = link.dataset[HOST_ORIGINAL];
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            if (Array.isArray(parsed) && typeof parsed[1] === "string")
                type = parsed[1];
        }
        catch { }
    }
    if (type === "image/svg+xml")
        return "favicon.svg";
    if (type === "image/png")
        return "favicon-32.png";
    return null;
}
function point(link, file, isTabIcon) {
    const url = iconUrl(file);
    if (isTabIcon) {
        // 本体が元の参照先を覚えているなら、そちらも差し替える。
        // 稼働中の印を重ねた画像の土台と、印が消えたときの戻り先が、X1 になる。
        const saved = link.dataset[HOST_ORIGINAL];
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                if (Array.isArray(parsed) && parsed[0] !== url) {
                    link.dataset[HOST_ORIGINAL] = JSON.stringify([url, ...parsed.slice(1)]);
                }
            }
            catch { }
        }
        // 本体が重ねた画像 (data: URL) が出ている間は触らない。
        if (link.href.startsWith("data:"))
            return;
    }
    if (link.href === url)
        return;
    if (!originals.has(link))
        originals.set(link, link.getAttribute("href") ?? "");
    link.setAttribute("href", url);
}
function apply() {
    for (const link of document.head.querySelectorAll(APPLE_TOUCH)) {
        point(link, "apple-touch-icon.png", false);
    }
    for (const link of document.head.querySelectorAll(ICON)) {
        const file = fileForIcon(link);
        if (file)
            point(link, file, true);
    }
}
export default defineControlUiPlugin({
    id: "pda-icon",
    activate() {
        apply();
        // 本体が後からまた <link> を書き換えたら、もう一度差し替える。
        // 差し替え済みなら何もしないので、自分の書き込みで無限に回ることはない。
        const observer = new MutationObserver(apply);
        observer.observe(document.head, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["href"],
        });
        return () => {
            observer.disconnect();
            // 外すとき (プラグインの画面のコードを止めたとき) は、元の参照先に戻す。
            for (const link of document.head.querySelectorAll(`${APPLE_TOUCH}, ${ICON}`)) {
                const original = originals.get(link);
                if (original !== undefined && link.href.includes(ROUTE))
                    link.setAttribute("href", original);
                const saved = link.dataset[HOST_ORIGINAL];
                if (original !== undefined && saved) {
                    try {
                        const parsed = JSON.parse(saved);
                        if (Array.isArray(parsed))
                            link.dataset[HOST_ORIGINAL] = JSON.stringify([original, ...parsed.slice(1)]);
                    }
                    catch { }
                }
            }
        };
    },
});
