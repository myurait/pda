// X1 門のアイコン一式を作る。
//   node scripts/build-icons.mjs
// 出力: icons/ (svg と png)、assets/icon.png、src/icons.generated.ts、preview/x1-check.png
// SVG を PNG にするのに @resvg/resvg-js を使う。プラグインの依存には入れず、
// 次の順で探す: 環境変数 RESVG_MODULE、このパッケージから見える @resvg/resvg-js、
// 入っている openclaw の node_modules。
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(import.meta.url);

function loadResvg() {
  const candidates = [process.env.RESVG_MODULE, "@resvg/resvg-js"];
  try {
    const openclawDir = path.dirname(require.resolve("openclaw/package.json"));
    candidates.push(path.join(openclawDir, "node_modules", "@resvg", "resvg-js"));
  } catch {}
  const openclawBin = process.env.OPENCLAW_PACKAGE_DIR;
  if (openclawBin) candidates.push(path.join(openclawBin, "node_modules", "@resvg", "resvg-js"));
  for (const c of candidates.filter(Boolean)) {
    try {
      return require(c);
    } catch {}
  }
  throw new Error(
    "@resvg/resvg-js が見つかりません。RESVG_MODULE か OPENCLAW_PACKAGE_DIR (openclaw のパッケージの場所) を指定してください。",
  );
}
const { Resvg } = loadResvg();

// 唯一の原稿。1024 座標の比率を全サイズでそのまま使う。
// 門: y=190..834 (高さ644)、柱: y=470..804 (長さ334)。
const svg = fs.readFileSync(path.join(root, "assets", "x1-gate.source.svg"), "utf8");

// テーマ用は背景の角だけを丸める。門と柱は原稿の要素をそのまま使う。
// 要素数の制限に合わせ、同じ rect を等価な path にまとめる。
function themeArtSvg(source) {
  const pillars = [];
  const theme = source.replace(
    /<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)" rx="([\d.]+)"\/>/g,
    (_, ...args) => {
      const [x, y, w, h, rx] = args.slice(0, 5).map(Number);
      pillars.push(
        `M${x + rx} ${y}H${x + w - rx}A${rx} ${rx} 0 0 1 ${x + w} ${y + rx}V${y + h - rx}` +
        `A${rx} ${rx} 0 0 1 ${x + w - rx} ${y + h}H${x + rx}A${rx} ${rx} 0 0 1 ${x} ${y + h - rx}` +
        `V${y + rx}A${rx} ${rx} 0 0 1 ${x + rx} ${y}Z`,
      );
      return "";
    },
  );
  return theme
    .replace('<rect width="1024" height="1024"', '<rect width="1024" height="1024" rx="225"')
    .replace('<g fill="#f5eedd">', "")
    .replace("<path d=", '<path fill="#f5eedd" d=')
    .replace("</g>", `<path fill="#f5eedd" d="${pillars.join("")}"/>`)
    .replace(/^[ \t]+$/gm, "");
}

const render = (source, size) =>
  new Resvg(source, { fitTo: { mode: "width", value: size } }).render().asPng();

fs.mkdirSync(path.join(root, "icons"), { recursive: true });
fs.mkdirSync(path.join(root, "assets"), { recursive: true });
fs.mkdirSync(path.join(root, "preview"), { recursive: true });

const out = {
  "favicon.svg": Buffer.from(svg),
  "favicon-32.png": render(svg, 32),
  "apple-touch-icon.png": render(svg, 180),
  "icon-512.png": render(svg, 512),
};
for (const [name, data] of Object.entries(out)) fs.writeFileSync(path.join(root, "icons", name), data);
// プラグイン自身の identity アイコンの置き場所 (docs/plugins/manifest/surfaces.md の assets/icon.png)
fs.writeFileSync(path.join(root, "assets", "icon.png"), out["icon-512.png"]);

fs.mkdirSync(path.join(root, "assets", "theme-art"), { recursive: true });
const themeSvg = themeArtSvg(svg);
fs.writeFileSync(path.join(root, "assets", "theme-art", "x1-gate.svg"), themeSvg);

// 画像を変えたら URL の ?v= も変わるようにする (iOS やブラウザの古い保存を避ける)
const hash = createHash("sha256");
for (const name of Object.keys(out).sort()) hash.update(out[name]);
hash.update(themeSvg);
fs.writeFileSync(
  path.join(root, "src", "icon-version.generated.ts"),
  `// scripts/build-icons.mjs が作る。手で直さない。\nexport const ICON_VERSION = ${JSON.stringify(hash.digest("hex").slice(0, 10))};\n`,
);

// ---- バックエンドに埋め込む -------------------------------------------
// 取り込み方の注意: 配布時に __dirname や import.meta を使えないので、画像は文字列にして持つ。
const ts =
  `// scripts/build-icons.mjs が作る。手で直さない。\n` +
  `export const ICON_FILES = {\n` +
  Object.entries(out)
    .map(([name, data]) => {
      const type = name.endsWith(".svg") ? "image/svg+xml" : "image/png";
      return `  ${JSON.stringify(name)}: { type: ${JSON.stringify(type)}, base64: ${JSON.stringify(data.toString("base64"))} },`;
    })
    .join("\n") +
  `\n} as const;\n`;
fs.writeFileSync(path.join(root, "src", "icons.generated.ts"), ts);

// ---- 確認画像 -----------------------------------------------------------
// 180px と 32px を明るい背景・暗い背景に並べる。32px は実寸と、画素を見るための 4 倍 (最近傍) を置く。
const b64 = (n) => out[n].toString("base64");
const row = (y, bg, label, fg) => {
  return (
    `<rect x="0" y="${y}" width="1200" height="320" fill="${bg}"/>` +
    `<text x="24" y="${y + 36}" font-size="20" fill="${fg}" font-family="sans-serif">${label}</text>` +
    // 180px (iOS の角丸に切り抜いた見え方)
    `<g transform="translate(60 ${y + 80})"><g clip-path="url(#c180)"><image width="180" height="180" href="data:image/png;base64,${b64("apple-touch-icon.png")}"/></g></g>` +
    `<text x="60" y="${y + 290}" font-size="16" fill="${fg}" font-family="sans-serif">180px</text>` +
    // 32px 実寸 (タブのアイコン相当、角丸なし)
    `<g transform="translate(340 ${y + 140})"><image width="32" height="32" href="data:image/png;base64,${b64("favicon-32.png")}"/></g>` +
    `<g transform="translate(400 ${y + 140})"><g clip-path="url(#c32)"><image width="32" height="32" href="data:image/png;base64,${b64("favicon-32.png")}"/></g></g>` +
    `<text x="340" y="${y + 290}" font-size="16" fill="${fg}" font-family="sans-serif">32px 実寸</text>` +
    // 32px を 4 倍 (最近傍) と、180px を 60px に縮めたもの (ホーム画面で小さく見る場合)
    `<g transform="translate(540 ${y + 80})"><image width="128" height="128" image-rendering="optimizeSpeed" href="data:image/png;base64,${b64("favicon-32.png")}"/></g>` +
    `<text x="540" y="${y + 290}" font-size="16" fill="${fg}" font-family="sans-serif">32px の 4 倍</text>` +
    `<g transform="translate(740 ${y + 100})"><g clip-path="url(#c60)"><image width="60" height="60" href="data:image/png;base64,${b64("apple-touch-icon.png")}"/></g></g>` +
    `<g transform="translate(830 ${y + 100})"><g clip-path="url(#c60)"><image width="60" height="60" href="data:image/png;base64,${b64("apple-touch-icon.png")}"/></g></g>` +
    `<text x="740" y="${y + 290}" font-size="16" fill="${fg}" font-family="sans-serif">60px</text>`
  );
};
const sheet =
  `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="640" viewBox="0 0 1200 640">` +
  `<defs>${["c180:180:40", "c60:60:13", "c32:32:7"]
    .map((s) => s.split(":"))
    .map(([id, size, r]) => `<clipPath id="${id}"><rect width="${size}" height="${size}" rx="${r}"/></clipPath>`)
    .join("")}</defs>` +
  row(0, "#eef1f5", "明るい背景", "#333333") +
  row(320, "#0e1015", "暗い背景", "#dddddd") +
  `</svg>`;
fs.writeFileSync(
  path.join(root, "preview", "x1-check.png"),
  new Resvg(sheet, { font: { loadSystemFonts: true, defaultFontFamily: "Noto Sans CJK JP" } }).render().asPng(),
);
console.log("done", Object.keys(out).join(", "));
