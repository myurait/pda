# todo とスクラップ (todo-scrap)

PDA に付随してミニ PC で動く仕組み。個人の todo と、ネットで拾った記事のスクラップ (AI に後で読ませる URL のリスト) を、ミニ PC の Git のリポジトリに Markdown で置く。画面は SilverBullet、iPhone の共有シートからはショートカットと受け口で足し、AI (ミニ PC の PDA の入口の Claude と、開発 PC の Claude) は MCP で読み書きする。

## 構成

- データ: ミニ PC の Git のリポジトリ。正本は bare の `~/todo-scrap.git`、作業クローンは `~/todo-scrap`。画面・受け口・MCP は、作業クローンのファイルを直接読み書きする。データは個人の情報なので、このリポジトリ (pda) には置かない。
- 画面: SilverBullet のコンテナ `todo-scrap-sb`。作業クローンをそのまま割り当て、`127.0.0.1:18800` で待ち受ける。tailnet へは `https://pda-web.tailaff53a.ts.net:18800/` で公開する。
- サーバー: `todo-scrap-mcp.service`。1 つの常駐・1 つのポートで、次の 2 つの口を持つ。`127.0.0.1:18700` で待ち受け、tailnet へは `https://pda-web.tailaff53a.ts.net:18700/` で公開する。
  - 受け口 (`/` への POST): iPhone のショートカットから届いた URL やテキストを `scrap.md` の先頭に足してコミットする。`/` への GET は動いているかの確認。
  - MCP (`/mcp`): AI が todo とスクラップを道具で読み書きする。
- 自動コミット: `todo-scrap-autocommit.timer` が 5 分ごとに、画面と Claude での編集をコミットし、正本とそろえる。

| ファイル | 置き場所 (ミニ PC) | 役目 |
| --- | --- | --- |
| `todo-scrap-mcp` | `~/.local/bin/` | サーバーの本体 (受け口と MCP)。ファイルの書き方は `todo-scrap-receiver` を同じフォルダから読み込んで使う |
| `todo-scrap-mcp.service` | `~/.config/systemd/user/` | サーバーの常駐。`~/.local/share/todo-scrap-mcp/venv` の Python で動かす |
| `todo-scrap-receiver` | `~/.local/bin/` | 届いた本文から 1 行を作る処理、見出しの付け方、`scrap.md` への書き足し (サーバーが読み込む)。単体で動かすと見出しの読み直しができる |
| `todo-scrap-autocommit` | `~/.local/bin/` | 自動コミットの本体 |
| `todo-scrap-autocommit.service` / `.timer` | `~/.config/systemd/user/` | 上を 5 分ごとに動かす |
| `test_todo_scrap_receiver.py` | (置かない) | 届いた本文から 1 行を作る処理の試験 |
| `test_todo_scrap_mcp.py` | (置かない) | todo.md と scrap.md を読み書きする処理の試験 |

## 決まり

- 直すときは、ここを直してコミットし、ミニ PC へ写す。ミニ PC の写しだけを直さない。
- 画面の見た目やホームの一覧は、データのリポジトリのページ (`index.md`、`設定/見た目.md`、`設定/ボタン.md`) にある。SilverBullet の画面から直せるので、データと一緒にデータのリポジトリで管理する。
- アプリは用途ごとに別のポートで公開する。受け口と MCP は、どちらもこのリポジトリで作るもので書き方も共通なので、1 つのサーバーにまとめている。

## データのページ

- `index.md`: ホーム。未完了の todo と未完了のスクラップを出す。一覧の作り方は `設定/ホーム.md` にあり、`index.md` はそれを `${homeTodos()}` と `${homeScraps()}` で呼ぶだけ。
- `todo.md`: todo。見出しの無い 1 つの一覧で、1 行 1 件で `- [ ] ` から始め、新しいものを先頭に足す (上部のバーの ＋ のボタンと MCP の `add_todo` がそうする)。行の末尾に属性 (下の「属性」) を書け、仕事・個人開発・プライベートの分け方もカテゴリの属性で持つ。チェック欄は完了の印。
- `scrap.md`: 後で読む記事。1 行 1 件で `- [ ] <届いた日時> [<見出し>](<URL>)` の形 (URL でないものはテキストのまま)。新しいものが上になるように、一覧の先頭に足す。行の末尾に属性 (下の「属性」) を書ける。チェック欄は、オーナーが片付いたと判断した印 (読んで価値が無かった、オーナーの知識に吸収した、反映が済んだ)。AI は自分の判断だけでチェック欄を付けない。
- `下書き/`: 文章の下書き。
- `設定/見た目.md`: 画面の文字・色 (Space Style)。
- `設定/ホーム.md`: ホームの一覧の作り方 (Space Lua の `homeTodos`・`homeScraps`) と色 (Space Style)。
  - todo: カテゴリ (仕事・個人開発・プライベートの順、無いものは最後に「カテゴリなし」) でまとめ、カテゴリの中を案件でまとめる。案件の無いものはカテゴリの直下に、案件のまとまりの後ろに並べる。並びは期限の近い順で、期限の無いものはページの順 (案件のまとまりどうしは、中の一番近い期限の順)。属性は出さず、期限まで 2 日以内か過ぎたものだけ、本文の後ろに期限の月/日を赤字で出す。
  - スクラップ: ページの順 (新しいものが上) に出し、文字色を AI チェックで分ける (未チェックは灰色、チェック済みは青、反映待ちは橙色)。話題だけ後ろに薄く出す。
- `設定/ボタン.md`: 上部のバーに足すボタン (Space Lua の `actionButtons`)。todo を足す ＋ のボタン (カテゴリを選ぶ枠を出し、選んだカテゴリの属性を付けた `- [ ] ` の行を todo の一覧の先頭に差し込む)、todo とスクラップのページへ飛ぶボタン、再読み込みのボタン。再読み込みは、ホーム画面に追加して単体のアプリとして開くと、ブラウザーの再読み込みが使えないため。
- `設定/日本語入力.md`: iPhone で日本語の変換を確定する Enter を押すと入力中の文字が消える、SilverBullet 2.12 の不具合への手当て。確定の Enter (`isComposing` が真か `keyCode` が 229) を、SilverBullet の iOS の Enter の処理より先に受け止める。原因の処理 (SilverBullet の `client/codemirror/editing/ios_enter.ts`) は iPhone・iPad でだけ動くので、手当ても iPhone・iPad に限る。SilverBullet が直したら消す。

## 属性

todo とスクラップの行の末尾に `[名前: 値]` を並べて書く。SilverBullet の属性の書き方で、画面のクエリから `t.due` のように項目として引ける。名前は英字・数字・`_` (SilverBullet が属性として読む名前はこの文字だけ)、値は日本語。書かない属性は「値なし」として扱う。MCP は値を確かめてから書き、属性を次の順に並べる。

```
- [ ] 設計書を最新化する [category: 仕事] [project: ビューティーパスポート] [due: 2026-11-15] [status: 進行中] [weight: 2]
- [ ] 2026-11-07 12:29 [AIエージェントの自己改善をどう…](https://speakerdeck.com/…) [topic: AI] [aicheck: 反映待ち]
```

todo:

| 名前 | 値 | 書かないとき |
| --- | --- | --- |
| `category` | カテゴリ。`仕事`・`個人開発`・`プライベート`。MCP と ＋ のボタンは足すときに必ず付ける | カテゴリなし |
| `project` | 案件名 | 案件なし |
| `due` | 期限日 (`2026-11-15` の形。時刻は持たない) | 期限なし |
| `status` | 対応状況。`進行中`・`待ち` (人の返事や他の作業を待っていて、自分では進められない) | 未着手 |
| `weight` | 作業の重さ。`1` (1 時間以内)・`2` (半日以内)・`3` (それ以上) | 未設定 |

スクラップ:

| 名前 | 値 | 書かないとき |
| --- | --- | --- |
| `topic` | 話題。`AI`・`ゲーム` (ゲーム開発を含む)・`開発ツール` | どれにも当たらない |
| `aicheck` | AI チェック。`チェック済み` (AI が読んだ)・`反映待ち` (読んだ結果、セキュリティの警告や AI 開発の知見のように別の開発物に取り込むもの) | 未チェック |

- iPhone から届いたスクラップは属性なし (未チェック) で入る。未チェックのものは、AI が中身を読んで `topic` と `aicheck` を付ける。
- 反映待ちのものは、AI とオーナーの棚卸しで開発物に反映する。反映が済んだら、チェック欄を付けて `aicheck` を `チェック済み` に戻す (MCP の `complete_scrap` がそうする)。反映のための todo は足さない。
- 日付の値は、SilverBullet が YAML として読んで `2026-11-15` の文字列にする。文字列のまま比べて期限の順に並ぶ。

## スクラップの足し方 (受け口と MCP の `add_scrap` で共通)

- URL の追跡用のパラメーター (`utm_*`、`fbclid`、X の `s` と `t` など) を外す。
- まず仮の見出し (X なら `X: <アカウント> の投稿`、ほかはサイト名とパス) で足して返事をし、続けて読んだ見出しに置き換えてコミットする。
  - X の投稿: X の埋め込み用の窓口 (`https://publish.x.com/oembed`、認証なし) で読んだ投稿の文の頭。
  - ほかのページ: ページを直接読んだ `og:title` か `<title>`。直接読めないときだけ jina (`https://r.jina.ai/<URL>`) で読む。
  - 見出しの長さは表示の幅で数え (全角 2、半角 1)、32 を超えたら切って「…」を付ける。
  - 見出しから、SilverBullet が Space Lua の式やリンク・HTML として読みうる文字を取り除く。URL のその文字はパーセントエンコードする。
  - ミニ PC の中・tailnet・LAN のアドレスを指す URL と、そこへの転送は読みに行かない。
- 読めなかった行は仮の見出しのまま残る。まとめて読み直すときは、ミニ PC で次を実行する。

```sh
TODO_SCRAP_REPO=~/todo-scrap python3 ~/.local/bin/todo-scrap-receiver --retitle      # 仮の見出しの行だけ
TODO_SCRAP_REPO=~/todo-scrap python3 ~/.local/bin/todo-scrap-receiver --refresh-x    # X の行をすべて
```

## 自動コミットの動き

- サーバーと同じロック (`.git/todo-scrap-commit.lock`) を取ってから git を動かす。
- 編集をコミットしたあと、正本に先に入ったコミット (手元の PC から正本へ送った変更など) を `git pull --rebase --autostash` で取り込んでから push する。取り込みが衝突したら元に戻し、次の回にもう一度試す。

## MCP

MCP の公式の Python SDK (`mcp` 2.3.0。1.x の FastMCP は 2.x で `MCPServer` に名前が変わった) で、関数を道具として公開する。受け口の口は SDK の `custom_route` で足している。streamable HTTP で、状態を持たない形 (stateless) で動く。tailnet の中だけに公開するので認証は付けない。SDK の Host の確認は、`127.0.0.1:18700`・`localhost:18700`・`pda-web.tailaff53a.ts.net(:18700)` だけを通す。

| 道具 | すること |
| --- | --- |
todo の行は、属性を除いた本文に指定の文を含むもので探す。

| 道具 | すること |
| --- | --- |
| `list_todos` | todo の一覧 (本文・属性・完了か)。既定は未完了だけ。カテゴリ・案件・対応状況で絞れ、ページの順か期限の近い順で返す |
| `add_todo` | todo を一覧の先頭に足す。カテゴリは必ず渡す。ほかの属性も付けられる |
| `complete_todo` | 本文に指定の文を含む todo を 1 件、完了 (か未完了) にする。複数に当たると失敗する |
| `set_todo_attributes` | 本文に指定の文を含む todo を 1 件、属性を書き換える。省いた属性はそのまま、空文字で消す。複数に当たると失敗する |
| `replace_todo` | 本文に指定の文を含む todo を 1 件、本文を書き換える。完了かどうかと属性はそのまま (新しい本文の末尾に属性を書くと、その属性も書き換える)。完了したものも対象。複数に当たると失敗する |
| `delete_todo` | 本文に指定の文を含む todo を 1 件消す。完了したものも対象。複数に当たると失敗する |
| `list_scraps` | スクラップの一覧 (届いた日時・見出し・URL・添えた文・属性・片付いたか) を新しい順に。既定は片付いていないものだけ。AI チェックと話題で絞れる |
| `add_scrap` | スクラップを一覧の先頭に足す。受け口と同じく追跡用のパラメーターを外し、見出しを付ける。話題も付けられる |
| `set_scrap_attributes` | URL のスクラップの属性 (話題・AI チェック) を書き換える。チェック欄は変えない |
| `complete_scrap` | URL のスクラップのチェック欄を付ける (か外す)。オーナーとの棚卸しで片付いたものにだけ使う。反映待ちのものはチェック済みに戻す |

Claude への登録:

```sh
# ミニ PC の PDA の入口 (Remote Control の常駐と同じ設定の場所)
HOME=/home/user/v03/agent-home CLAUDE_CONFIG_DIR=/home/user/pda/secrets/claude claude mcp add --scope user --transport http todo-scrap http://127.0.0.1:18700/mcp
# 開発 PC
claude mcp add --scope user --transport http todo-scrap https://pda-web.tailaff53a.ts.net:18700/mcp
```

## 新しい環境に入れる

ミニ PC で行う。データのリポジトリは、正本の bare から作業クローンを作る。

```sh
git clone ~/todo-scrap.git ~/todo-scrap
git -C ~/todo-scrap config user.name todo-scrap
git -C ~/todo-scrap config user.email todo-scrap@pda-web
```

サーバーと自動コミットは、ミニ PC の `~/pda` で入れる。サーバーは Python の環境を作ってから入れる。

```sh
uv venv --python 3.12 ~/.local/share/todo-scrap-mcp/venv
uv pip install --python ~/.local/share/todo-scrap-mcp/venv/bin/python 'mcp==2.3.0'
install -m 755 deploy/todo-scrap/todo-scrap-mcp deploy/todo-scrap/todo-scrap-receiver deploy/todo-scrap/todo-scrap-autocommit ~/.local/bin/
cp deploy/todo-scrap/todo-scrap-mcp.service deploy/todo-scrap/todo-scrap-autocommit.service deploy/todo-scrap/todo-scrap-autocommit.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now todo-scrap-mcp.service todo-scrap-autocommit.timer
```

画面は Docker で立てる。`SB_FOLDER` を付けると、アカウントの無い 1 スペースの形で動く (tailnet の中だけに公開するので認証は付けない)。

```sh
docker run -d --name todo-scrap-sb --restart unless-stopped \
  -p 127.0.0.1:18800:3000 -e SB_FOLDER=/space \
  -v /home/user/todo-scrap:/space ghcr.io/silverbulletmd/silverbullet:latest
```

tailnet へ公開する。

```sh
tailscale-pda serve --bg --https=18800 http://127.0.0.1:18800
tailscale-pda serve --bg --https=18700 http://127.0.0.1:18700
```

Tailscale の管理画面 (Access controls) の規則で、開発 PC・iPhone・Windows の PC からミニ PC の 18700 と 18800 を通す。

## iPhone の設定

画面をホーム画面に置く:

1. iPhone の Tailscale をつなぐ。
2. Safari で `https://pda-web.tailaff53a.ts.net:18800/` を開く。
3. 共有ボタン →「ホーム画面に追加」。

共有シートのショートカット「スクラップ」:

1. ショートカットのアプリで新しいショートカットを作り、名前を「スクラップ」にする。
2. アクション「URL の内容を取得」を足す。URL は `https://pda-web.tailaff53a.ts.net:18700/`、方法は POST、本文を要求は JSON。フィールドを 1 つ足し、型はテキスト、キーは `url`、値は変数「ショートカットの入力」。
3. アクション「通知を表示」を足し、本文に変数「URL の内容」を入れる (受け口の返事が通知に出る)。
4. 情報ボタン (i) で「共有シートに表示」をオンにし、受け取る入力の型を「URL」と「テキスト」にする。

## 確かめ方

```sh
systemctl --user status todo-scrap-mcp.service todo-scrap-autocommit.timer
journalctl --user -u todo-scrap-mcp.service -n 20
docker logs todo-scrap-sb
curl -s http://127.0.0.1:18700/                                       # 「todo-scrap の受け口は動いています」
python3 -m unittest deploy/todo-scrap/test_todo_scrap_receiver.py deploy/todo-scrap/test_todo_scrap_mcp.py    # 試験 (pda で)
```
