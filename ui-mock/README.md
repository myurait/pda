# PDA v0.2 画面モック

## 1. 開き方

ビルド済みの静的ファイルは `site/` にあります。リポジトリのルートで次を実行し、`http://localhost:8000/#/overview` を開きます。Node.js のインストールは不要です。

```sh
python3 -m http.server --directory ui-mock/site
```

開発用には Node.js と npm を使います。確認環境は Node.js 24.18.0、npm 11.16.0、Linux、Chromium です。

```sh
cd ui-mock
nice -n 10 npm ci --cache .cache/npm
nice -n 10 npm run dev
```

開発サーバは `http://127.0.0.1:5173/#/overview`。ビルドは `nice -n 10 npm run build`、型だけの検査は `nice -n 10 npm run typecheck` です。ビルド先は `site/`、パスは相対パスです。公開サーバや配信の設定は含みません。

操作した状態はブラウザのローカル保存に残ります。実サービスへの接続はありません。外部出力のリンクも、モック内の所在と資料のプレビューを開きます。

設計は [ux-design.md](docs/ux-design.md)、次の API 設計が要る情報は [data-needs.md](docs/data-needs.md) を参照してください。

## 2. 画面の一覧

| 画面 | URL と役割 |
|---|---|
| 概観 | `#/overview`：自分の番、動いている全セル、実行器を順に見渡す |
| タスク | `#/tasks`：件数付き状態フィルター、文字検索、並べ替え、10 件ごとのページ送り |
| タスク詳細 | `#/tasks/api`：分岐と合流のフロー、実行切り替え、介入、報告、成果物 |
| セル詳細 | `#/tasks/api?run=run-1&tab=flow&cell=api-implement`：PC は右、スマートフォンは下に開く |
| 報告 | `#/tasks/result?run=run-1&tab=report&report=result-r1-report`：整形文書、目次、コード複写、報告ごとの問い |
| 成果物 | `#/tasks/result?tab=artifacts`：文書・画像、git の所在、外部出力を開く／持ち出す |
| 入力待ち | `#/inbox`、`#/inbox/questions`：タスク横断の報告、返答、初期指示・分岐図・判断・成果物 |
| 実行器 | `#/executors`、`#/executors/codex-personal`：生死と全担当セル、受け渡し、起動・停止 |
| 新しいタスク | `#/new`：長い指示と Markdown プレビュー、任意の作業場所、前回の報告担当 |

## 3. 見本の操作の枠の使い方

各画面の下端にある「見本の操作」を開きます。

- 「見本の場面」で通常、タスクなし、読み込み中、上流に届かない、60 件、入力待ちなし、実行器が不明を切り替えます。
- 「初期に戻す」で通常の 12 タスクと 6 実行器に戻します。作成したタスクと介入を消し、前回の報告担当の選択は保持します。
- 「1 歩進める」は、開いている進行中タスクを優先し、それ以外では先頭の進行中タスクを進めます。判定、作業の終了／失敗、判定器 A、再試行の複製、オブザーバー B、やり直し、合流、報告を段階的に変えます。通知に今回の変化が出ます。完了と中止は自動で記録しません。

| タスク ID | 見られる場面 |
|---|---|
| `api`、`sessions` | codex-personal が 2 タスクの 3 セルを同時に担当。API は 2 分岐、取り込みは長時間 |
| `questions` | 失敗 → A → B → 返答待ち → 合流 → 報告。承認・選択・自由文の 3 問 |
| `result` | 自動作業なしの報告。3,554 字の Markdown、見出し・表・コード・18 項目のリスト、4 成果物 |
| `retry` | 判定器が再試行を選び、複製が動いている。オーナーも実行器を替えて再試行できる |
| `environment` | 環境問題から B が分解を指示し、作業セルがやり直している |
| `interrupted` | オーナーが中断し、A がオブザーバーを選択。1 歩進めると B が判断を要すると判定 |
| `core` | コア規則による停止と HTML の報告 |
| `restart` | 同じタスクに 2 実行。実行 1 は中断で、以前の報告も読める |
| `large` | 8 回 30 セル。終了回の折り畳み／展開、現在位置への移動 |
| `complete`、`cancelled` | オーナーが完了／中止として記録したタスク |

初期指示、重ねた指示、書き換え、返答はフロー上のオーナーセルです。作業セルや判定器はオーナーへ直接問いません。observe/report は今回指定された見本用 type であり、宣言ファイルは変更していません。

## 4. 受け入れ条件（10 節）の合否と確かめ方

2026-09-25、ビルド済み `site/` を localhost で配って確認しました。Playwright は 1 worker で直列実行し、1440px と 390px で UC12 件と追加検査 3 件ずつ、計 30 件が成功しました。

再実行するコマンドは次のとおりです。ブラウザの取得、ビルド、検証を順番に実行します。Python プロジェクトの依存は使いません。

```sh
cd ui-mock
PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright nice -n 10 npx playwright install chromium
nice -n 10 npm run build
nice -n 10 npm run verify:data
PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright nice -n 10 npm test
```

手順は [walkthrough.spec.ts](tests/walkthrough.spec.ts)。[browser-verification.json](docs/browser-verification.json) に各検査の合否・通信・JavaScript エラー、[model-verification.json](docs/model-verification.json) に見本の規模・報告文字数・段階進行を記録しています。Playwright の一時トレースは失敗時だけ `test-results/` に保存し、コミットしません。

| # | 受け入れ条件 | 合否 | 確かめ方 |
|---|---|---|---|
| 1 | 設計書の 9 見出しと UC1〜UC12 の手順・成功状態 | 合格 | `verify:data` で見出しと全 UC を検査し、設計書 3 節の手順と成功状態を照合 |
| 2 | 全 UC を 1440px と 390px で辿れる | 合格 | Playwright の UC1〜UC12 を両幅で実行。成功状態を確認し 24 枚を保存 |
| 3 | 8 介入と返答でフローか一覧が変わる | 合格 | UC4〜UC11 と追加検査。セル増加・状態・実行数・回答後の一覧除外、完了・中止を確認 |
| 4 | 種類ごとの形と印、分岐と合流、8 回 30 セルの操作 | 合格 | UC3・UC9、凡例の 6 種、折り畳み 7 回／展開 30 セル、全体表示と現在位置の変換を確認。画像も確認 |
| 5 | 報告の見出し・表・コードが整形される | 合格 | UC11 で見出し目次、table、pre、18 リスト項目とコード複写を確認。HTML も追加検査 |
| 6 | 問いと報告と文脈が同じ画面にある | 合格 | UC10 で報告、質問、初期指示、分岐図、B の判断、関連成果物を確認 |
| 7 | 失敗／中断の A・複製・B・やり直し・返答待ちが分岐内にある | 合格 | UC4・UC9 と見本の型を確認。retry、environment、questions、interrupted の接続を画像と図で照合 |
| 8 | オーナーへの問いは報告セルからだけ届く | 合格 | `verify:data` で全報告と report セル、問いのある報告と B・待ち終端・合流の関係を検査 |
| 9 | 同時 3 セルの実行器で全 3 セルが見える | 合格 | UC12 で codex-personal の担当 3 件を確認。`verify:data` で 2 タスクに所属することを確認 |
| 10 | 両幅で本文が横にはみ出さない | 合格 | 全画面・全場面と各 UC の終了時に文書の scrollWidth が画面幅以下であることを確認。図の中だけパン可能 |
| 11 | 明るい配色だけ | 合格 | 明色を固定。全画面で color-scheme が light であることと、スクリーンショットの白・明灰色の面を確認 |
| 12 | 本文・操作・表が 14px 以上 | 合格 | 全画面の表示される p・button・input・textarea・th・td・li・label・a の計算後の文字サイズを検査。図の縮小表示はズームに従う |
| 13 | 実行時の外部要求がゼロ | 合格 | 全 30 検査で request を記録し、localhost 以外の HTTP 要求がゼロ。フォントと図の素材は同梱 |
| 14 | ソースと見本データに Unicode 絵文字がない | 合格 | `verify:data` が `src/` 全ファイルを Unicode Extended_Pictographic で走査。印は SVG と部品のアイコン |
| 15 | 全 UC 中の JavaScript エラーがゼロ | 合格 | 全 30 検査で pageerror と console.error を記録し、ゼロを確認 |
| 16 | ビルドと型検査が通る | 合格 | `npm run build` が `tsc --noEmit` と Vite のビルドを完了し、`site/` を生成 |

各 UC の最後の状態の画像です。詳細枠を開く UC は画面内の表示、他はページ全体を記録しています。24 枚です。

| UC | 1440px | 390px |
|---|---|---|
| UC1 概観 | [画像](docs/screenshots/UC01-1440.png) | [画像](docs/screenshots/UC01-390.png) |
| UC2 新しいタスク | [画像](docs/screenshots/UC02-1440.png) | [画像](docs/screenshots/UC02-390.png) |
| UC3 セルの詳細 | [画像](docs/screenshots/UC03-1440.png) | [画像](docs/screenshots/UC03-390.png) |
| UC4 中断 | [画像](docs/screenshots/UC04-1440.png) | [画像](docs/screenshots/UC04-390.png) |
| UC5 指示を重ねる | [画像](docs/screenshots/UC05-1440.png) | [画像](docs/screenshots/UC05-390.png) |
| UC6 書き換えとやり直し | [画像](docs/screenshots/UC06-1440.png) | [画像](docs/screenshots/UC06-390.png) |
| UC7 セルの挿入 | [画像](docs/screenshots/UC07-1440.png) | [画像](docs/screenshots/UC07-390.png) |
| UC8 追加入力 | [画像](docs/screenshots/UC08-1440.png) | [画像](docs/screenshots/UC08-390.png) |
| UC9 再試行 | [画像](docs/screenshots/UC09-1440.png) | [画像](docs/screenshots/UC09-390.png) |
| UC10 返答 | [画像](docs/screenshots/UC10-1440.png) | [画像](docs/screenshots/UC10-390.png) |
| UC11 結果の受け取り | [画像](docs/screenshots/UC11-1440.png) | [画像](docs/screenshots/UC11-390.png) |
| UC12 実行器の起動と停止 | [画像](docs/screenshots/UC12-1440.png) | [画像](docs/screenshots/UC12-390.png) |

## 5. 使った依存と版

直接依存は固定版です。間接依存も `package-lock.json` に記録しています。

| 用途 | パッケージ | 版 |
|---|---|---|
| 画面 | react / react-dom | 19.3.0 / 19.3.0 |
| 部品・外枠 | @cloudscape-design/components | 3.0.1385 |
| 基本スタイル | @cloudscape-design/global-styles | 1.0.70 |
| フロー図 | @xyflow/react | 12.12.0 |
| 層状の自動配置 | elkjs | 0.12.0 |
| Markdown | react-markdown / remark-gfm | 10.1.0 / 4.0.1 |
| HTML 解析・無害化 | rehype-raw / rehype-sanitize | 7.0.0 / 6.0.0 |
| ハッシュルーティング | react-router | 8.4.0 |
| 開発・ビルド | vite / @vitejs/plugin-react | 8.3.1 / 6.1.1 |
| 型検査 | typescript | 7.0.2 |
| 型定義 | @types/react / @types/react-dom / @types/node | 19.3.0 / 19.3.0 / 26.6.2 |
| ブラウザ検証 | @playwright/test | 1.63.0 |
| 見本の整合性検証 | tsx | 4.23.15 |

## 6. 指示どおりにできなかったこと

受け入れ条件の未達はありません。

実行器・Conductor への接続、実ファイルの変更、外部への公開は行いません。成果物の git・公開先は見本です。宣言にない observe/report の実 API 契約、生死の取得、オーナー入力の保存など、次の実装で新しく必要な情報は `data-needs.md` に明記しています。

Vite は同梱 JavaScript の大きさについて警告を出します。ELK と画面の依存をまとめた JavaScript は約 3.2 MB、CSS は約 1.2 MB（いずれも圧縮前）です。ビルドは成功し、実行時の外部取得はありません。
