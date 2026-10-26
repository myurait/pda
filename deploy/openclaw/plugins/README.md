# OpenClaw のプラグイン

PDA のために作った OpenClaw のプラグインの正本を置く。ミニ PC の OpenClaw は、ここから読み込む。

| プラグイン | 役目 | 読み込み方 |
| --- | --- | --- |
| [tap-to-dictate](tap-to-dictate/README.md) | Control UI の入力欄のマイクボタンを 1 回タップすると、Talk ではなく音声入力 (dictation) を始める | `plugins.load.paths` でこのフォルダを指す |
| [pda-common](pda-common/README.md) | 全エージェントに共通の指示 (`/home/user/v03/openclaw/pda/common.md`) を、毎回のプロンプトに足す | 今は `/home/user/v03/openclaw/state/extensions/pda-common` に写したものを読む。ここの中身と同じ |

## 決まり

- プラグインを直すときは、ここを直してコミットする。OpenClaw の state の下や作業者の作業フォルダに写したものを直さない。
- `dist/` は、読み込みに使うビルドの結果なのでコミットする。ビルドには `npm install` で 650MB ほどの依存が要るため、取り出しただけで動くようにしておく。
- `node_modules/` はコミットしない。tap-to-dictate は、読み込みに `node_modules/openclaw` のリンクだけが要る。取り出した後に作る。

```sh
cd deploy/openclaw/plugins/tap-to-dictate
mkdir -p node_modules && ln -sfn /home/user/v03/openclaw/lib/node_modules/openclaw node_modules/openclaw
```

## 新しい環境に入れる

```sh
openclaw plugins install /home/user/pda/deploy/openclaw/plugins/tap-to-dictate --link
openclaw config set gateway.controlUi.experimental.customPlugins true   # 自分で入れたプラグインのブラウザ側のコードを動かすのに要る
```

入れた後は、Control UI のタブを再読み込みする。
