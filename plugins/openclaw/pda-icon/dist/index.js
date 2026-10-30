import { defineFeaturePlugin } from "openclaw/plugin-sdk/feature-plugin";
import { contract } from "./contract.js";
import { ICON_FILES } from "./icons.generated.js";
// 画像を配信する HTTP ルート。画面のコード (control-ui.ts) の ROUTE と同じにする。
const ROUTE = "/pda-icon";
const bodies = new Map(Object.entries(ICON_FILES).map(([name, file]) => [
    name,
    { type: file.type, data: Buffer.from(file.base64, "base64") },
]));
function handle(req, res) {
    const method = req.method ?? "GET";
    if (method !== "GET" && method !== "HEAD") {
        res.statusCode = 405;
        res.setHeader("Allow", "GET, HEAD");
        res.end();
        return true;
    }
    const pathname = new URL(req.url ?? "/", "http://localhost").pathname;
    const name = pathname.startsWith(`${ROUTE}/`) ? pathname.slice(ROUTE.length + 1) : "";
    const body = bodies.get(name);
    if (!body) {
        res.statusCode = 404;
        res.setHeader("Content-Type", "text/plain; charset=utf-8");
        res.end("not found");
        return true;
    }
    res.statusCode = 200;
    res.setHeader("Content-Type", body.type);
    res.setHeader("Content-Length", String(body.data.length));
    // URL の ?v= は画像を変えるたびに変わるので、長めに保存させてよい。
    res.setHeader("Cache-Control", "public, max-age=86400");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.end(method === "HEAD" ? undefined : body.data);
    return true;
}
export default defineFeaturePlugin({
    contract,
    name: "PDA Icon",
    description: "Control UI のホーム画面アイコン (iOS) とタブのアイコンを、PDA の X1 門に差し替える。",
    setup(api) {
        // auth: "plugin" = Gateway の認証を通さず、プラグインが自分で扱う。
        // 画像は公開してよい中身で、iOS が「ホーム画面に追加」で認証の情報なしに取りに来るので、認証なしにしている。
        api.registerHttpRoute({
            path: ROUTE,
            match: "prefix",
            auth: "plugin",
            handler: async (req, res) => handle(req, res),
        });
        return {};
    },
});
