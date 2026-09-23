# ミニ PC の環境

- 更新: 2026-09-23 JST
- 種別: 実行環境の現状。v0.2 の Conductor、ログストア、実行器を置くホストの構成、接続方法、入っているもの。
- v0.1 の常駐、データ、コンテナは撤去した。v0.1 のコードは tag `v0.1-archive` にある。

## 1. 機械

- GMKtec M8。CPU は AMD Ryzen 5 PRO 6650H（12 スレッド）。OS から見えるメモリは 12 GiB、スワップは 4 GiB。SSD は 452 GB で、LVM の 1 ボリュームをルートに割り当てている。
- Ubuntu Server 24.04.4 LTS。無線 LAN で接続し、LAN のアドレスは `192.168.0.59`。
- 利用者は `user`（UID 1000）。`docker` グループに入っている。sudo にはパスワードが要るので、root の権限が要る作業はオーナーが行う。
- ufw は無効。ホストの `0.0.0.0` で待ち受けるポートは LAN から届く。
- ユーザー単位の常駐はログアウト後も動く（linger 有効）。

## 2. 接続

### 2.1 開発 PC からの SSH

- 開発 PC は SSH の接続名 `agent-node` を持ち、`user@192.168.0.59` へ鍵認証で入る。パスフレーズは要らない。
- 非ログインシェルの PATH には `~/.local/bin` が入らない。`ssh agent-node '<コマンド>'` で codex、claude、uv、node を使うときは、先に `export PATH="$HOME/.local/bin:$PATH"` を実行する。
- 開発 PC の Claude Code から `ssh agent-node` を実行するときは、サンドボックスの外で実行する。サンドボックスは `~/.ssh` を読めず、接続名を解決できない。

### 2.2 Tailscale

- 端末名は `pda-web`（`pda-web.tailaff53a.ts.net`）。公開範囲は tailnet の中だけ。
- ユーザー単位の常駐 `tailscale-pda.service` が、userspace networking で `tailscaled` を動かす。root の権限も TUN デバイスも使わない。本体は `~/.local/opt/tailscale-1.102.2/`、状態は `~/.local/share/tailscale-pda/`。
- CLI は `~/.local/bin/tailscale-pda`。常駐のソケットを指定して `tailscale` を呼ぶ。
- 公開設定（Serve）には v0.1 のサービスへの転送が残っている。転送先（`127.0.0.1` の 9120、9121、9122、18501〜18504）は撤去済みで、どの URL も応答しない。転送は `tailscale-pda serve` で変更する。

### 2.3 逆向きの SSH トンネル

ミニ PC から開発 PC の SSH へ入る経路。

- 開発 PC の LaunchAgent `com.pda.agent-node-reverse-ssh` が、ミニ PC へ SSH で常時つなぎ、ミニ PC の `127.0.0.1:22037` を開発 PC の 22 番へ転送する。
- ミニ PC から開発 PC へは `ssh -i ~/.ssh/id_ed25519_devpc -p 22037 fox4foofighter@127.0.0.1` で入る。
- 設定は `~/bootstrap-main-reverse-ssh.sh`（ミニ PC に置いてあり、開発 PC で実行するもの）が行う。このスクリプトが設定する内容は次のとおり。
  - 開発 PC の macOS のリモートログインを有効にする。
  - 開発 PC の authorized_keys に、ミニ PC の鍵を `127.0.0.1` からの接続に限り、ポート転送と端末の割り当てを禁じて登録する。
  - トンネル用の鍵を開発 PC に作り、ミニ PC の authorized_keys に、`127.0.0.1:22037` の待ち受けだけを許しコマンド実行を禁じて登録する。

## 3. 動いているもの

- システムのサービスは、Ubuntu Server の標準に Docker Engine と containerd を加えたもの。
- ユーザー単位の常駐は `tailscale-pda.service` だけ。独自の定期実行（cron、ユーザーのタイマー）は無い。
- コンテナは v0.2 のものだけ。`~/pda/deploy/docker-compose.yaml` から立てる。Compose のプロジェクト名は `pda-increment-2`。
- 待ち受けるポートは次のとおり。
  - 22: SSH
  - 5000: Conductor UI（v0.2 の構成を立てているとき）
  - 5080: OpenObserve（同上）
  - 8080: Conductor API（同上）
  - 44105: Tailscale の通信
  - `127.0.0.1:22037`: 逆向きの SSH トンネル

## 4. 入っているツールと認証

- Docker Engine 29.6.2、Docker Compose v5.3.1。
- Codex CLI 0.156.0。`~/.local/bin/codex` は `~/.codex/packages/` への symlink。個人契約でログイン済みで、認証は `~/.codex/auth.json`。
- Claude Code CLI 2.1.205。`~/.local/bin/claude` は `~/.local/share/claude/versions/` への symlink。個人契約でログイン済みで、認証は `~/.claude/.credentials.json`。
- v0.2 の実行器は、この 2 つの認証ファイルの複製を `~/pda/secrets/` に置いて使う。ホストの `~/.codex` と `~/.claude` はマウントしない。手順は `docs/runbook/increment-3.md` の 2〜3 節。
- uv 0.11.29（`~/.local/bin/uv`）と、uv が管理する Python 3.11（`~/.local/bin/python3.11`）。OS の `python3` は 3.12.3。
- Node.js 24.18.0。nvm で入れたもので、`~/.local/bin/node`、`npm`、`npx` はその symlink。
- git 2.43.0。

## 5. v0.2 のリポジトリ

- `~/pda.git`: bare リポジトリ。開発 PC のリポジトリでは remote `minipc`（`ssh://agent-node/home/user/pda.git`）として登録している。
- `~/pda`: 作業クローン。origin は `~/pda.git`。`secrets/` と `deploy/.env` は Git の管理外で、このクローンにだけある。

## 6. 使うときの制約

- メモリは 12 GiB。全試験の並列実行のような重い処理は、直列で `nice` を付けて行う。メモリが尽きると SSH も含めてホスト全体が応答しなくなる。
- v0.2 の構成を立てる前に `free -h` で空きを確かめる（`docs/runbook/increment-3.md` の 1 節）。
