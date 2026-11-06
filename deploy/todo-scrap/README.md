# todo とスクラップ (todo-scrap)

PDA に付随してミニ PC で動く仕組み。個人の todo と、ネットで拾った記事のスクラップ (AI に後で読ませる URL のリスト) を、ミニ PC の Git のリポジトリに Markdown で置く。画面は SilverBullet、iPhone の共有シートからはショートカットと受け口で足す。PDA の入口の Claude はこのリポジトリのファイルを直接読み書きする。

## 構成

- データ: ミニ PC の Git のリポジトリ。正本は bare の `~/todo-scrap.git`、作業クローンは `~/todo-scrap`。SilverBullet・受け口・Claude は、作業クローンのファイルを直接読み書きする。データは個人の情報なので、このリポジトリ (pda) には置かない。
- 画面: SilverBullet のコンテナ `todo-scrap-sb`。作業クローンをそのまま割り当て、`127.0.0.1:18800` で待ち受ける。tailnet へは `https://pda-web.tailaff53a.ts.net:18800/` で公開する。
- 受け口: `todo-scrap-receiver.service`。iPhone のショートカットから届いた URL やテキストを `scrap.md` に 1 行足してコミットする。`127.0.0.1:18700` で待ち受け、tailnet へは `https://pda-web.tailaff53a.ts.net:18700/` で公開する。
- 自動コミット: `todo-scrap-autocommit.timer` が 5 分ごとに、画面と Claude での編集をコミットし、正本とそろえる。

| ファイル | 置き場所 (ミニ PC) | 役目 |
| --- | --- | --- |
| `todo-scrap-receiver` | `~/.local/bin/` | 受け口の本体 (Python の標準ライブラリだけで動く) |
| `todo-scrap-receiver.service` | `~/.config/systemd/user/` | 受け口の常駐。落ちたら起動し直す |
| `todo-scrap-autocommit` | `~/.local/bin/` | 自動コミットの本体 |
| `todo-scrap-autocommit.service` / `.timer` | `~/.config/systemd/user/` | 上を 5 分ごとに動かす |
| `test_todo_scrap_receiver.py` | (置かない) | 受け口の、届いた本文から 1 行を作る処理の試験 |

## 決まり

- 直すときは、ここを直してコミットし、ミニ PC へ写す。ミニ PC の写しだけを直さない。
- 画面の見た目やホームの一覧は、データのリポジトリのページ (`index.md`、`設定/見た目.md`、`設定/ボタン.md`) にある。SilverBullet の画面から直せるので、データと一緒にデータのリポジトリで管理する。
- アプリは用途ごとに別のポートで公開する。

## データのページ

- `index.md`: ホーム。未完了の todo と未読のスクラップを、ページの並びのまま一覧で出す (どちらも新しいものが上)。
- `todo.md`: todo。仕事・PDA の開発・自分のことに分ける。1 行 1 件で `- [ ] ` から始め、新しいものは節の先頭に足す (上部のバーの ＋ のボタンがそうする)。todo には日時が無いので、節をまたいだ新しさの順にはならない。
- `scrap.md`: 後で読む記事。1 行 1 件で `- [ ] <届いた日時> [<見出し>](<URL>)` の形 (URL でないものはテキストのまま)。新しいものが上になるように、受け口が一覧の先頭に足す。読んだものは `[x]` にする。
- `下書き/`: 文章の下書き。
- `設定/見た目.md`: 画面の文字・色 (Space Style) と、ホームの一覧の行の形 (Space Lua の `templates.listTask`)。
- `設定/ボタン.md`: 上部のバーに足すボタン (Space Lua の `actionButtons`)。todo を足す ＋ のボタン (todo のページではカーソルのある節、ほかのページからは最初の節の先頭に `- [ ] ` の行を差し込む)、todo とスクラップのページへ飛ぶボタン、再読み込みのボタン。再読み込みは、ホーム画面に追加して単体のアプリとして開くと、ブラウザーの再読み込みが使えないため。
- `設定/日本語入力.md`: iPhone で日本語の変換を確定する Enter を押すと入力中の文字が消える、SilverBullet 2.12 の不具合への手当て。確定の Enter (`isComposing` が真か `keyCode` が 229) を、SilverBullet の iOS の Enter の処理より先に受け止める。原因の処理 (SilverBullet の `client/codemirror/editing/ios_enter.ts`) は iPhone・iPad でだけ動くので、手当ても iPhone・iPad に限る。SilverBullet が直したら消す。

## 受け口の動き

- URL の追跡用のパラメーター (`utm_*`、`fbclid`、X の `s` と `t` など) を外す。
- まず仮の見出し (X なら `X: <アカウント> の投稿`、ほかはサイト名とパス) で足して iPhone へ返し、続けて読んだ見出しに置き換えてコミットする。
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

- 受け口と同じロック (`.git/todo-scrap-commit.lock`) を取ってから git を動かす。
- 編集をコミットしたあと、正本に先に入ったコミット (手元の PC から正本へ送った変更など) を `git pull --rebase --autostash` で取り込んでから push する。取り込みが衝突したら元に戻し、次の回にもう一度試す。

## 新しい環境に入れる

ミニ PC で行う。データのリポジトリは、正本の bare から作業クローンを作る。

```sh
git clone ~/todo-scrap.git ~/todo-scrap
git -C ~/todo-scrap config user.name todo-scrap
git -C ~/todo-scrap config user.email todo-scrap@pda-web
```

受け口と自動コミットは、ミニ PC の `~/pda` で入れる。

```sh
install -m 755 deploy/todo-scrap/todo-scrap-receiver deploy/todo-scrap/todo-scrap-autocommit ~/.local/bin/
cp deploy/todo-scrap/todo-scrap-receiver.service deploy/todo-scrap/todo-scrap-autocommit.service deploy/todo-scrap/todo-scrap-autocommit.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now todo-scrap-receiver.service todo-scrap-autocommit.timer
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
systemctl --user status todo-scrap-receiver.service todo-scrap-autocommit.timer
journalctl --user -u todo-scrap-receiver.service -n 20
docker logs todo-scrap-sb
curl -s http://127.0.0.1:18700/                                       # 「todo-scrap の受け口は動いています」
python3 -m unittest deploy/todo-scrap/test_todo_scrap_receiver.py    # 受け口の試験 (pda で)
```
