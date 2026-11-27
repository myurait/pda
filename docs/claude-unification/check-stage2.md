# 確かめた記録: 案Cの段階2

- 日付: 2026-11-27 JST から
- 対象: [段階2の設計](design-stage2.md)のとおりに足したPDAのパイプライン ([deploy/pda-pipeline/](../../deploy/pda-pipeline/README.md))。
- 物差し: [段階2の作業計画](plan-stage2.md)の3節の完了条件。

## 1. 結論

| 項目 | 結果 | 走行 |
|---|---|---|
| 作業するディレクトリの差し替え (C19) | 成り立った | 3.1節 |
| 定額のログインへの備え (C11) | `-p` の既定が `--bare` に替わったあとも定額のログインを使う指定は、公式の資料に無かった。ログインを使えずに終わったターンは、一通と台帳で見分けられる | 3.2節 |

## 2. 走行の構成

- 走行は、本番の常駐と別に起こした確かめ用の常駐で行った。確かめ用の常駐は、別のソケット・設定・台帳と、使い捨てのntfyのトピックを持つ。本番の常駐の設定と通知先は変えていない。
- 依頼は、T3 Codeの代わりにACPの口を起こす確かめ用のクライアント (`tests/acp_client.py`) から送った。T3 Codeの画面を通した走行は、項目の節に書く。
- メインセッションのモデルは、定額の枠の消費を抑えるためHaiku 5.5にした。報告係と判定器 (Jev、Codexの `gpt-6.2-sol`) は既定のままである。
- 台帳のターンの番号は、確かめ用の常駐の台帳のものである。

## 3. 項目ごとの手順と結果

### 3.1 作業するディレクトリの差し替え (C19)

前提として、Claude Code 2.1.293で、あるディレクトリで始めたセッションを、別のディレクトリから `claude -p --resume` で起こした。前の会話が続き、コマンドは起こしたディレクトリで実行された。

走行に使ったディレクトリは次のとおり。

- ミニPCにある公開のリポジトリのクローン (`AGENTS.md` を持つ)
- 確かめ用のクローン `~/pda-dev` (AI向けの指示のファイルを持たないリポジトリ)
- 走行の中で作らせたディレクトリ

結果は次のとおり。

1. セッションの途中で「これからは (公開のリポジトリのクローンのパス) で作業します。」と伝えた。セッションは `set_workdir` を呼び、次のターンで `cd` をせずに実行させた `pwd` の出力は、替えた先のディレクトリだった (台帳のターン2、3)。
2. 「(パス) の下に made-1 というディレクトリを作り、以後はその中で作業します。」と伝えた。セッションはディレクトリを作って `set_workdir` を呼び、次のターンの `pwd` の出力は、作ったディレクトリだった (ターン4、5)。
3. `AGENTS.md` を持つリポジトリに替えたターンで、セッションは、ファイルを開かずに `AGENTS.md` の最初の見出しを答えた (ターン2)。次のターンにセッションへ渡した役の指示のファイルには、役の指示のあとに `AGENTS.md` の本文と、扱いを添える文が入っていた (ターン3、9)。指示のファイルを持たないリポジトリに替えると、次のターンに渡した役の指示のファイルに `AGENTS.md` の本文は入っていなかった (ターン10、11)。
4. 台帳のセッションの作業ディレクトリは、替えるたびに絶対パスで替わった。

- 作業ディレクトリを替えたあとも、Claude Codeの会話の記録には、前に `set_workdir` の戻り値で届いた指示が残る。ターン5で、セッションは「そのディレクトリを離れたので、いまの作業には当てはめていません。」と答えた。
- 作業ディレクトリを替えたターンのうちは、`claude -p` は前の作業ディレクトリで動いている。セッションは、替えた先を絶対パスや `git -C` で指して実行した (ターン6)。

### 3.2 定額のログインへの備え (C11)

公式の資料で確かめたこと (2026-11-27に取得)。

- [Run Claude Code programmatically](https://code.claude.com/docs/en/headless) は、`--bare` について "`--bare` is the recommended mode for scripted and SDK calls, and will become the default for `-p` in a future release." と書く。時期とバージョンは書かれていない。
- 同じページは "In bare mode, Claude Code never reads OAuth credentials or the system keychain." と書く。[Authentication](https://code.claude.com/docs/en/authentication) は、`claude setup-token` の長く使えるトークンについて "does not read `CLAUDE_CODE_OAUTH_TOKEN`. If your script passes `--bare`, authenticate with `ANTHROPIC_API_KEY` or an `apiKeyHelper` instead." と書く。
- `--bare` を外す指定 (引数、環境変数、設定のキー) は、次のページに無かった。
  - Run Claude Code programmatically (全文)
  - Authentication (全文)
  - [Settings](https://code.claude.com/docs/en/settings) (全文)
  - [CLI reference](https://code.claude.com/docs/en/cli-reference) (引数の表の途中まで原文、残りは要約で確かめた)
  - [Environment variables](https://code.claude.com/docs/en/env-vars) (表の途中まで。末尾の一部は取得していない)
- ミニPCの `claude --help` (2.1.293) にも、`--bare` を外す引数は無い。

走行の結果は次のとおり。

1. 確かめ用の常駐を、ログインの無いClaudeの設定のディレクトリに向けて、依頼を1つ送った。1秒後に「Claudeのログインを使えなかったので、このターンの作業は始まっていません。ミニPCのClaudeのログインの状態を確かめてください。」の一通が出た (台帳のターン12)。台帳の結果は `failed`、出来事 `claude_error` に `authentication_failed` が残り、通知は題名に「[点検なし]」の付いた1通だった。
2. ログインを戻して同じセッションに続きの依頼を送ると、Claude Codeの側にセッションの記録が無く、返事が作られなかった (ターン13)。台帳を直して起こし直す処理を足したあとは、同じセッションで一通が返り (ターン14)、次のターンで前のターンの内容を使った答えが返った (ターン15)。
