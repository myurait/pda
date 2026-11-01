# OpenClaw のツール定義の遅延 (tool-defer)

OpenClaw は、自分のツールを Claude Code に MCP サーバーとして渡すとき、設定に `alwaysLoad: true` を固定で付ける。このため Claude Code のツール検索 (使うときだけ定義を読む仕組み) が効かず、統率役の約 100 個のツールの定義が、どの会話にも最初から入る。上流の issue は [openclaw/openclaw#139477](https://github.com/openclaw/openclaw/issues/139477)。

この部品は OpenClaw にも Claude Code にも手を入れず、間に 2 つの小さな部品を置いて、よく使うツールだけを最初から載せ、残りをツール検索の後ろに遅延する。上流が直したら、`uninstall.sh` で外して捨てる。

| ファイル | 役目 |
| --- | --- |
| `bin/claude` | OpenClaw の常駐が起動する `claude` の入口。`--mcp-config` の openclaw サーバーの接続先を中継に向けた写しを作り、本物の Claude Code を起動する。中継が応答しないときは書き換えない |
| `relay.py` | Claude Code と OpenClaw の MCP サーバーの間の中継。受け渡しはそのまま通し、`tools/list` の応答だけ、`keep-tools.txt` に無いツールに `_meta["anthropic/alwaysLoad"] = false` を付ける (Claude Code 2.1.285 以上は、この印の付いたツールを遅延する) |
| `keep-tools.txt` | 最初から載せるツールの名前。変えると次の `tools/list` から効く |
| `openclaw-tool-defer-relay.service` | 中継の常駐 (127.0.0.1:37191) |
| `tool-defer.conf` | `v03-openclaw.service` の追加設定。PATH の先頭に `bin/` を足し、OpenClaw の常駐だけが入口を通るようにする |
| `install.sh` / `uninstall.sh` | 入れる・外す。どちらも最後に OpenClaw を起動し直す |
| `test_relay.py` | 偽の上流を使った中継と入口の試験 (`python3 -m unittest test_relay`) |

## 入れる・外す

ミニ PC の `~/pda` で行う。

```sh
deploy/openclaw-tool-defer/install.sh
deploy/openclaw-tool-defer/uninstall.sh
```

外すと、OpenClaw の常駐は元の PATH に戻り、中継は止まって登録も消える。OpenClaw の設定と本体には触れていないので、ほかに戻すものは無い。

## 確かめ方

- 入口の記録 `~/.local/state/openclaw-tool-defer/wrapper.log` に `relayed-file` が出ていれば、Claude Code は中継を通っている。`relay-down` は中継が止まっていて素通りしたことを表す。
- 中継の記録 `~/.local/state/openclaw-tool-defer/relay.log` の `tools/list ... deferred=N kept=M` が、遅延したツールと載せたツールの数。
- Claude Code の会話記録の `deferred_tools_delta` に、遅延された `mcp__openclaw__*` の名前が並ぶ。

## 決まり

- 直すときは、ここを直してコミットし、ミニ PC の `~/pda` に pull してから `install.sh` をもう一度実行する。
- 上流が `alwaysLoad` を直した版に上げたら、`uninstall.sh` を実行し、このディレクトリを消す。
