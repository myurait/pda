# pda-icon

OpenClaw の Control UI のアイコンを、PDA の「X1 門」(太いアーチの門の中に、対等な 3 本の柱) に差し替える OpenClaw のプラグインです。

目的は、iPhone の Safari で「ホーム画面に追加」したときのアイコンを、赤いロブスターから X1 にすることです。OpenClaw の本体のファイルは書き換えません。アイコンの設定は Control UI の画面にないので、プラグインのコードで差し替えます。

## 何をするか

1. プラグイン自身の HTTP ルート `/pda-icon/<ファイル名>` で、X1 の画像 (`apple-touch-icon.png`、`favicon.svg`、`favicon-32.png`、`icon-512.png`) を配信します。画像はバックエンドのコードに埋め込んであります。
2. 画面のコード (`src/control-ui.ts`) が、ページの `<link rel="apple-touch-icon">` と `<link rel="icon">` の参照先を、その画像に書き換えます。
   - 本体は、画面の起動時に、これらの `<link>` の参照先を自分の画像に設定します。プラグインの画面のコードは、Gateway に接続して有効になってから動くので、その後で書き換えます。
   - 本体があとから書き換えても、`MutationObserver` で見つけてもう一度差し替えます。
   - 本体が、タブのアイコンに稼働中の印を重ねるときに覚える「元の参照先」(`data-openclaw-original-favicon`) も X1 に直します。印の土台と、印が消えたあとの戻り先が X1 になります。
   - プラグインの画面のコードを止めると (外すと)、元の参照先に戻します。
3. (任意) テーマ `pda-icon/pda-x1` を登録します。選ぶと、画面の中のロゴが X1 になり、ロブスターが出なくなります。選ぶかどうかは使う人の設定で、プラグインを入れただけでは変わりません。

## ファイル

| パス | 中身 |
| --- | --- |
| `openclaw.plugin.json` | プラグインの宣言。`controlUi` は `openclaw plugins build` が書く |
| `package.json` | 依存とビルドの手順。`openclaw.controlUi` が画面のコードの元 |
| `src/index.ts` | バックエンド。画像を配信する HTTP ルート (`auth: "plugin"`) |
| `src/control-ui.ts` | 画面のコード。`<link>` の書き換え |
| `src/contract.ts` | 空の feature 契約 (理由はコメント) |
| `src/icons.generated.ts`、`src/icon-version.generated.ts` | 画像の埋め込みと版。`scripts/build-icons.mjs` が作る |
| `scripts/build-icons.mjs` | X1 の SVG を描き、PNG を書き出し、埋め込みと確認画像を作る |
| `icons/` | `favicon.svg`、`favicon-32.png`、`apple-touch-icon.png` (180px)、`icon-512.png` |
| `assets/icon.png` | プラグイン自身のアイコン (カタログ用。`icon-512.png` と同じ) |
| `assets/theme-art/x1-gate.svg`、`themes/pda-x1.json` | テーマ |
| `preview/x1-check.png` | 確認画像。180px と 32px を明るい背景・暗い背景に並べたもの |

## 入れ方

前提: Gateway の設定 `gateway.controlUi.experimental.customPlugins` が `true` であること (画面のコードを動かす設定。この Gateway では有効)。

```bash
cd openclaw-plugins/pda-icon
npm install            # 型の確認とビルドに typescript、esbuild、openclaw を使う (openclaw は約 700MB)
npm run build          # tsc と openclaw plugins build。dist/ と、openclaw.plugin.json の controlUi が更新される
npm run validate       # openclaw plugins validate --json
openclaw plugins install -l --force "$PWD"   # 場所を指したまま入れる (コピーしない)
```

- `npm install` が openclaw 本体を取りに行くのを避けたいときは、`node_modules/openclaw` を入れ済みの本体 (`.../lib/node_modules/openclaw`) へのシンボリックリンクにし、`typescript`、`esbuild`、`@types/node` だけ別に入れます。
- テーマを使うので、`openclaw plugins pack` の tgz では入れません。tgz には `themes/` と `assets/` が入らないためです (バックエンドと画面のコードだけが入ります)。上の、ディレクトリを指す入れ方にします。
- 入れたあと、Control UI のブラウザのタブを再読み込みします。画面のコードだけを直したときは、Plugins → Advanced → Customize UI → Reload plugin UI (管理者) でもかまいません。
- `openclaw plugins install -l` は、`--force` なしでは「Install cancelled; rerun with --force after reviewing the source.」で止まります。中身を確かめたうえで `--force` を付けて実行します。Gateway の再起動は要りません。

### iPhone での反映

iOS は、ホーム画面に追加した時点のアイコンを保存します。入れたあと、Safari で Control UI を開き直し、画面が表示されて数秒たってから、次の手順にします。

1. ホーム画面の古いアイコンを削除する。
2. Safari で Control UI を開き、共有 →「ホーム画面に追加」で追加し直す。

画面の読み込み直後 (プラグインの画面のコードが動く前) に追加すると、ロブスターのままになることがあります。

### テーマを使う場合

Settings → Appearance で `PDA X1` を選びます。

- 画面の中のロゴが X1 になり、ロブスターが出なくなります。色は X1 の青緑とアイボリーです。
- 副作用: 本体の仕様 (`brandIcon` が `claw` 以外のとき) で、タブのアイコンが X1 ではなく、テーマの色の汎用の印になります。タブのアイコンも X1 にしたいときは、テーマを選ばずにおきます (ホーム画面のアイコンには関係しません)。

## 外し方

```bash
openclaw plugins uninstall pda-icon
```

- 外したあとは、ブラウザのタブを再読み込みします。ホーム画面のアイコンは、iOS が保存しているので、削除して追加し直すまで X1 のままです。
- プラグインの画面のコードだけを止めたいときは、Settings → Labs → Custom plugin UI を切ります。画像の配信は続きますが、`<link>` の書き換えは行われません。

## 効く範囲

- **iOS のホーム画面のアイコンにだけ効きます。** iOS はページの `<link rel="apple-touch-icon">` を読むためです。
- Android とデスクトップの PWA (インストール) は、`manifest.webmanifest` のアイコンを使います。本体のロブスターのままです。このプラグインは manifest を変えません。
- ブラウザのタブのアイコンも X1 になります (上のテーマを選んだ場合を除く)。

## 認証について

- 画像は、`auth: "plugin"` のルートで、**Gateway の認証を通さずに** 配信します。この Gateway は認証が `none` なので、この前提で作りました。iOS が「ホーム画面に追加」でアイコンを取りに行くとき、ログインの情報 (Cookie など) を付けるかどうかは確かめていません。付かない場合でも取れるように、認証なしにしてあります。
- 画像に秘密の情報は入っていません。Gateway に届く人なら誰でも取れます。
- 使い捨ての Gateway で確かめたところ、認証を `token` にしても `/pda-icon/...` は認証なしで 200 でした (ルートが Gateway の認証に依存しないため)。ただし次の場合は壊れえます。
  - 認証を有効にすると、画面のコード (プラグインの画面のコード) は、ログイン後でないと読み込まれません。ログイン前のページに `<link>` を書き換えるコードは動きません。
  - 認証付きの前段 (リバースプロキシ、Cloudflare Access など) の背後に置くと、iOS の取得が前段で止まり、画像を取れなくなります。
  - ネイティブの画面のコードは、HTTPS かループバックの URL でないと読み込まれません (Control UI の資料)。
- テーマのロゴ (`/__openclaw__/plugin-theme-art/...`) は、本体の配信で、認証が有効だと認証が要ります (画面にログインしていれば表示されます)。

## 画像を作り直す

`scripts/build-icons.mjs` の寸法と色を直し、次を実行します。

```bash
RESVG_MODULE=<@resvg/resvg-js の場所> npm run icons   # 省略時は、openclaw の node_modules の @resvg/resvg-js を探す
npm run build
```

原稿は `assets/x1-gate.source.svg` の 1 つだけです。32px、180px、512px はこれを縮小して書き出し、テーマ用のロゴは同じ形のまま背景の角だけ丸めます。サイズごとに形を変えないでください。

## 検証したこと

- `npm run build` (tsc、`openclaw plugins build`) と `npm run validate` が通る。
- バックエンドのルートを、模擬の `api` と応答で呼び、GET と HEAD の 200、未知のファイルの 404、POST の 405 を確かめた。
- 使い捨ての Gateway (状態と設定と HOME を `/tmp` に分け、ポート 18999、ループバック) に `plugins.load.paths` で読み込み、`curl` で、画像が認証なしで取れること、テーマが `themes.list` に出ること、テーマのロゴが配信されることを確かめた。
- 本体の `index.html` を jsdom で読み、本体の起動処理と同じ `<link>` の設定のあとに、ビルドした画面のコードを動かし、書き換え、稼働中の印の重ね、本体の書き戻し、外したときの復元を確かめた。

まだ確かめていないこと: 実機の iOS で新しいアイコンになるか、本物の Control UI のブラウザ上での動作 (実ブラウザが使えなかった)、実機の Gateway へのインストール。
