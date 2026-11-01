# Claude Code の Remote Control の常駐

ミニ PC で `claude remote-control` を常駐させ、claude.ai/code、モバイルアプリ、デスクトップアプリから環境 `mini-pc` を選んでセッションを始められるようにする。あわせて、常駐が止まる原因になる claude.ai のログインの期限が近づいたら、スマホへ ntfy で通知する。開発 PC の CLI のログインにも同じ通知を入れる (末尾の節)。

| ファイル | 置き場所 (ミニ PC) | 役目 |
| --- | --- | --- |
| `claude-remote-control.service` | `~/.config/systemd/user/` | Remote Control の常駐。`/home/user` で動き、落ちたら起動し直す |
| `claude-login-expiry-notify` | `~/.local/bin/` | ログインの期限を読み、残りが 3 日以下・切れた・読めないときに ntfy へ 1 通送る |
| `claude-login-notify.service` / `.timer` | `~/.config/systemd/user/` | 上のスクリプトを毎日 10:30 に動かす。ミニ PC が止まっていた日は、次の起動時に動かす |
| `ntfy.env.example` | `~/.config/claude-login-notify/ntfy.env` (権限 600) | 通知先。トピックは開発 PC の `~/.claude/notify-ntfy.env` と同じものを書く |

## 決まり

- 直すときは、ここを直してコミットし、ミニ PC へ写す。ミニ PC の写しだけを直さない。
- `ntfy.env` はトピックがパスワードとして働くので、コミットしない。

## ログインと期限

- Remote Control には、claude.ai の契約でのログインが要る。`claude setup-token` の長期トークンや API キーでは使えない。
- ログインは、常駐と同じ `HOME` と `CLAUDE_CONFIG_DIR` を付けて行う。ログインの承認はブラウザで行うので、オーナーが実行する。

```sh
ssh -t agent-node 'HOME=/home/user/v03/agent-home CLAUDE_CONFIG_DIR=/home/user/pda/secrets/claude /home/user/.local/bin/claude auth login'
```

- ログインの期限は、ログインした時点から約 29 日後で、使っている間も延びない。期限は `$CLAUDE_CONFIG_DIR/.credentials.json` の `refreshTokenExpiresAt` にある。切れると常駐は起動に失敗し続けるので、通知を受けたら上のコマンドで再ログインする。再ログインした時点から、また約 29 日になる。
- 同じ `CLAUDE_CONFIG_DIR` を `v03-openclaw.service` も使う。

## 再起動の間隔

`RestartSec=10`、`RestartSteps=5`、`RestartMaxDelaySec=5min` で、失敗が続くと間隔を 10 秒から 5 分まで延ばす。ログイン切れのような続く失敗でログが積み上がらないようにしつつ、一時的な失敗からはすぐ戻る。止まったセッションは、同じフォルダで約 4 時間以内に起動し直せば戻る（公式資料）。延ばした間隔は、`systemctl --user restart` かミニ PC の再起動で 10 秒に戻る。

## 新しい環境に入れる

ミニ PC の `~/pda` で行う。

```sh
cp deploy/claude-remote-control/claude-remote-control.service deploy/claude-remote-control/claude-login-notify.service deploy/claude-remote-control/claude-login-notify.timer ~/.config/systemd/user/
install -m 755 deploy/claude-remote-control/claude-login-expiry-notify ~/.local/bin/
install -d -m 700 ~/.config/claude-login-notify
install -m 600 deploy/claude-remote-control/ntfy.env.example ~/.config/claude-login-notify/ntfy.env   # NTFY_TOPIC を書き足す
systemctl --user daemon-reload
systemctl --user enable --now claude-remote-control.service claude-login-notify.timer
```

- 初めて起動するときは、`/home/user` で一度 `claude` を対話で起動して作業フォルダを信頼し、`claude remote-control` を対話で起動して `Enable Remote Control? (y/n)` に `y` と答えておく。常駐は端末から答えられないので、この 2 つが済むまで起動に失敗する。
- アプリのセッション一覧に、ここで対話で起動したときのセッションが残る。不要ならアーカイブする。

## 確かめ方

```sh
systemctl --user status claude-remote-control.service                                  # active (running) か
journalctl --user -u claude-remote-control.service -n 20                               # 失敗の理由
CLAUDE_CONFIG_DIR=/home/user/pda/secrets/claude claude-login-expiry-notify --dry-run   # 今送るかどうかと本文
python3 -m unittest deploy/claude-remote-control/test_claude_login_expiry_notify.py    # 判定の試験
```

使い捨てのトピックへ実際に送って確かめるときは、`CLAUDE_LOGIN_NOTIFY_ENV` に別の env ファイルを、`CLAUDE_LOGIN_NOTIFY_DAYS` に大きい日数を指定して実行し、`https://ntfy.sh/<トピック>/json?poll=1` で読み戻す。

## 開発 PC のログインの期限の通知

ミニ PC の OpenClaw は、node `dev-pc` を通して開発 PC の `claude -p` を呼ぶ。開発 PC の CLI のログイン (会社のアカウント) の期限が切れると、この呼び出しは失敗する。同じスクリプトを開発 PC でも毎日 10:30 に動かし、期限が近づいたら同じトピックへ通知する。

| ファイル | 置き場所 (開発 PC) | 役目 |
| --- | --- | --- |
| `claude-login-expiry-notify` | `~/.local/bin/` | ミニ PC と同じもの。macOS で `CLAUDE_CONFIG_DIR` を指定しないときは、キーチェーンの項目 `Claude Code-credentials` から期限を読む |
| `com.pda.claude-login-notify.plist` | `~/Library/LaunchAgents/` | 上のスクリプトを毎日 10:30 に動かす。スリープしていた日は、起きたときに動かす。タイトルの先頭は `[dev-pc]` |

- 通知先は、開発 PC の Claude Code の通知と同じ `~/.claude/notify-ntfy.env` を読む。
- 再ログインは、開発 PC の端末で `claude auth login` を実行する。node から呼ばれる `claude` も同じキーチェーンの項目を使う。
- 動いた結果は `~/Library/Logs/claude-login-notify.log` に残る。

開発 PC に入れるときは、リポジトリのフォルダで次を実行する。

```sh
install -m 755 deploy/claude-remote-control/claude-login-expiry-notify ~/.local/bin/
install -m 644 deploy/claude-remote-control/com.pda.claude-login-notify.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.pda.claude-login-notify.plist
launchctl kickstart gui/501/com.pda.claude-login-notify   # 一度動かしてログに結果を出す
```
