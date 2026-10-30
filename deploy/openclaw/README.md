# OpenClaw に置くもの

ミニ PC の OpenClaw に配る、全員に共通の指示、役ごとの指示と規約、プラグインの入れ方。決定の背景は [v0.3-decision.md](../../docs/reports/v0.3-decision.md) の「役と規約」。プラグインのソースは [plugins/](../../plugins/README.md) にある。

## ファイルと配り先

- `common.md`: 全エージェントに共通の指示。プラグイン `pda-common` が、各エージェントのプロンプトを組む段 (`before_prompt_build`) でこのファイルを読み、文脈に足す。配り先は無く、`plugins.entries.pda-common.config.commonFile` が `/home/user/pda/deploy/openclaw/common.md` (反映用の取り出しの中のこのファイル) を直接指す。
- `agents/leader.md`: 統率役 (`leader`) の作業フォルダーの `AGENTS.md`。仕事の分け方、結果の受け取り、報告の前の確かめ。
- `agents/worker.md`: 作業者 (`worker`) の作業フォルダーの `AGENTS.md`。作業中の振る舞いの規約を含む。
- `agents/auditor.md`: 監査役 (`auditor`) の作業フォルダーの `AGENTS.md`。伝え方の規約を含む。

役ごとの指示は、各エージェントの作業フォルダーに写して配る。リポジトリが正本で、写した先は直さない。

```sh
cd /home/user/pda
for r in leader worker auditor; do cp deploy/openclaw/agents/$r.md /home/user/v03/work/openclaw/$r/AGENTS.md; done
```

## プラグイン

4 つとも、`/home/user/pda/plugins/` の中の場所を指したまま入れる (`--link`。コピーしない)。ソースを直したら、`/home/user/pda` で `git pull --ff-only` するだけで反映される (画面のコードの変更は、ビルドしてコミットした `dist/` が正本)。

| プラグイン | 場所 | 設定 |
| --- | --- | --- |
| pda-icon | `plugins/openclaw/pda-icon` | 追加なし |
| tap-to-dictate | `plugins/openclaw/tap-to-dictate` | 追加なし |
| touch-selection-popup | `plugins/openclaw/touch-selection-popup` | 追加なし |
| pda-common | `plugins/pda/pda-common` | `plugins.entries.pda-common.config.commonFile` = `/home/user/pda/deploy/openclaw/common.md`、`plugins.entries.pda-common.hooks.allowConversationAccess` = `true` |

画面のコードを動かす設定として `gateway.controlUi.experimental.customPlugins` を `true` にしておく (pda-icon、tap-to-dictate、touch-selection-popup に要る)。

### 取り出した後に作るもの

読み込みに要る `node_modules/openclaw` のリンクを、画面のコードを持つ 3 つに作る (`node_modules/` はコミットしない)。pda-common には要らない。

```sh
cd /home/user/pda/plugins/openclaw
for p in pda-icon tap-to-dictate touch-selection-popup; do
  mkdir -p $p/node_modules && ln -sfn /home/user/v03/openclaw/lib/node_modules/openclaw $p/node_modules/openclaw
done
```

### 入れる

```sh
openclaw plugins install /home/user/pda/plugins/openclaw/pda-icon --link --force
openclaw plugins install /home/user/pda/plugins/openclaw/tap-to-dictate --link --force
openclaw plugins install /home/user/pda/plugins/openclaw/touch-selection-popup --link --force
openclaw plugins install /home/user/pda/plugins/pda/pda-common --link --force
openclaw config set plugins.entries.pda-common.config.commonFile /home/user/pda/deploy/openclaw/common.md
openclaw config set plugins.entries.pda-common.hooks.allowConversationAccess true --strict-json
```

- 入れ直すときに `uninstall` は使わない (`plugins.entries` の設定が消える)。`--force` で上書きする。
- 入れたあと、結果に `restartRequired` が出たら Gateway の再起動が要る。出なければ要らない。画面のコードの変更は、Control UI のタブを再読み込みする。
- 確かめ方: `openclaw plugins list`、`openclaw plugins inspect <id>` (Source が上の場所)、`openclaw gateway call plugins.controlUi.list`。
- `pda-common` は、共通の指示の変更には再導入も再起動も要らない (毎回ファイルから読む)。ログに hook 名、読込結果、バイト数、SHA-256 を記録し、指示本文と会話は記録しない。

## 規約の出所

規約は、オーナーの伝え方の規約と作業の進め方の規約を、どのモデルが読んでも分かる文に書き直したもの。特定の道具の名前、会社名、個別の事例は入れていない。伝え方の規約は監査役に、作業中の振る舞いの規約は作業者に割り当てる。
