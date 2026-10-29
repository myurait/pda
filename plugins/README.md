# プラグイン

PDA のために作った OpenClaw のプラグインのソースの正本を置く。ミニ PC の OpenClaw は、`/home/user/pda` (反映用の取り出し) のここを指して読み込む (`openclaw plugins install <場所> --link --force`)。入れ方と設定は [deploy/openclaw/README.md](../deploy/openclaw/README.md)。

## 分け方

プラグインは、何に頼って目的を果たすかで、2 つのフォルダーに分ける。

| フォルダー | 入れるもの | 判断の基準 |
| --- | --- | --- |
| [openclaw/](openclaw/) | OpenClaw の画面や機能を補う・改変するもの | OpenClaw の画面 (DOM、クラス名、`<link>`)、タイミング、キー処理など、公開された仕組みではない部分に頼る。OpenClaw の更新で動かなくなりうるので、更新のたびに確かめる |
| [pda/](pda/) | PDA の思想を実現するもの | 公開されたプラグインの仕組み (hook、設定、HTTP ルートなど) だけで動く。OpenClaw の画面や内部の作りには頼らない |

迷ったら、「OpenClaw の画面を開いて見た目や操作が変わるか」で決める。変わるなら `openclaw/`、エージェントの動きや指示が変わるなら `pda/`。

## 一覧

| プラグイン | 場所 | 役目 |
| --- | --- | --- |
| [pda-icon](openclaw/pda-icon/README.md) | `openclaw/` | Control UI のアイコン (ホーム画面に追加したときのアイコン、タブのアイコン) を PDA の X1 門にする |
| [tap-to-dictate](openclaw/tap-to-dictate/README.md) | `openclaw/` | Control UI の入力欄のマイクボタンを 1 回タップすると、Talk ではなく音声入力 (dictation) を始める |
| [touch-selection-popup](openclaw/touch-selection-popup/README.md) | `openclaw/` | Control UI で本文を選んだときの「チャットに追加」「サイドチャットで質問」の吹き出しを、タッチ端末では出さない |
| [pda-common](pda/pda-common/README.md) | `pda/` | 全エージェントに共通の指示 ([deploy/openclaw/common.md](../deploy/openclaw/common.md)) を、毎回のプロンプトに足す |

## 決まり

- プラグインを直すときは、ここを直してコミットする。OpenClaw の state の下や作業者の作業フォルダーに写したものを直さない。
- `dist/` は、読み込みに使うビルドの結果なのでコミットする (pda-common は `dist/` の無い作りで、ソースをそのまま読む)。ビルドには `npm install` で 650MB ほどの依存が要るため、取り出しただけで動くようにしておく。ルートの `.gitignore` は `plugins/*/*/dist/` だけ除外から外してある。
- `node_modules/` はコミットしない。読み込みに要るのは `node_modules/openclaw` のリンクだけ。取り出した後に作る (手順は [deploy/openclaw/README.md](../deploy/openclaw/README.md))。
- 新しいプラグインは、上の基準でどちらかに置く。基準で決まらないものは、`openclaw/` に置く (更新のたびに確かめる側に入れておくほうが安全)。
