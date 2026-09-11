# Claude Desktop履歴: 原文取得と常設操作口

目的はPDA自身による継続した一覧・検索・本文取得であり、本人の手動エクスポートは代替完了条件にしない。

## 2026-09-11に実機で確認した経路

Coworkは `~/Library/Application Support/Claude/local-agent-mode-sessions/*/*/local_*/.claude/projects/*/*.jsonl` に原文がある。metadataのcliSessionIdだけに絞ると同じタスクの過去runが落ちるため、存在する独立したJSONLを全て対象にする。5タスク・7原文・73ユーザー/assistantテキストメッセージについて、実SSH/CLI一覧、全ページ読取り、全7原文の検索→読取り、元原文とmetadataのSHA256/mtime不変を検証した。取得本文は保存・commit・公開PKBへ送っていない。

`history.py --source=desktop-cowork` を既存常設readerへ反映。`code` と `desktop-cache` は別のsourceのまま。通常Chatキャッシュは19会話・112テキストメッセージで、全件/最新クラウド状態とは呼ばない。Coworkもローカル原文範囲なのでcoverage_completeは常にfalse。

## 調査した代替経路と採否

Claude Desktop 1.52386.0の別Chat検索は公式機能として存在する。ただし全件/raw出力の証拠ではない。新規Code/Coworkのdeep linkは確認したが、入力欄への遷移であって自動送信は未実証。bundled Code CLI 2.1.266にはChrome経路があるが、SSH文脈のauth statusはloggedIn=false。Desktopの認証をコピーして代用しない。

定期タスクのregistryはアカウント下のscheduled-tasks.jsonにある。現行コードは起動時に読み込み、稼働中はメモリ上のmapから書き戻す。ファイル追加だけで稼働中の登録が反映されるとみなさない。既存taskのprompt差替えやアプリ再起動による既存sessionの中断は不採用。認証された画面の操作経路を作った後に新規の取得taskを登録する候補は残す。定期実行は実取得のsmoke検証後に必要性を判断する。

SSH側のAppleEvents権限は問い合わせのみで-1744（未承認）だった。既存のKeychainアクセス失敗を迂回せず、本人による一回限りのアプリ操作許可を使う。画面エクスポートを毎回依頼する方式とは異なる。

## 常設GUI操作口の準備

公式CuaDriver 0.26.1をMacへ導入し署名検証を伴うinstaller完了とdoctorを確認。telemetryは無効。daemon起動、OS許可、実GUI読取りは未実施。

`enable_mac_gui.py` と `gui-capabilities.yaml` はMacの `~/Library/Application Support/PDA/claude-history/`、短縮入口は `~/pda-enable-claude-access.sh` に配置・hash照合済み。Mac上で `--inspect` を実行し設定変更/起動なしの表示を確認した。

オーナーがMacで `bash ~/pda-enable-claude-access.sh` を実行し、表示された実manifestを確認してyesと入力すると、Claude限定のbounded LaunchAgentが登録される。次にオーナーがmacOSのCuaDriver Accessibility/Screen Recordingを許可する。秘密情報はPDAへ入力しない。全画面、他アプリ、ブラウザ接続、ファイル転送、アプリ終了を許可しない。睡眠/ロック設定は変更しない。

`--no-permissions-gate`は起動時onboarding UIを抑えるだけで、OS権限を付与/迂回しない。bounded daemonのhealth確認後に、オーナー起動の公式permissions grantで初回設定を案内する。許可前の自動起動や標準/unrestricted daemonへの代替はしない。

## 検証と未完了条件

焦点を絞ったテスト56件成功。別入力コンテキストによるserial・ツールなし・既存Codex経路の静的レビューで指摘なし。ただし独立OS主体の実行検証ではない。コードdigestとレビュー入力digestを別JSONに保存。

Coworkは本番readerからの実検証も成功。通常Chatキャッシュも再検証成功。通常Chat全履歴は未完了。OS許可後、同じSSH経路からClaudeの実snapshot、他アプリ/未許可toolの拒否、従来未収録Chatの実取得、一覧正本との範囲比較をPDAが実施する。操作口が用意されたことを全履歴取得成功と混同しない。

本体の再起動、停止中の自律改善再開、既存Claude sessionの再開/変更、既存定期taskの変更は行っていない。

## 本人設定に失敗した場合

setupは元のstdout/stderrとexit codeを返す。表示を本人に共有してもらい、PDAが専用ログ・LaunchAgent・daemon grantsを再検証する。元の認証保護を下げない。設定入口はMacへ既にあるため再ダウンロード不要。

即時停止は専用daemonに `cua-driver revoke --all`、常駐停止は `launchctl bootout gui/UID/com.pda.claude-desktop-access`。既存の逆SSH、Claudeアプリ、他のLaunchAgentは触らない。readerの前版はprivate workspaceに保存した。通常Chatの本人分の公式取得方法が製品側で不明な場合の窓口はClaudeのGet help → Send us a message（Teamの人的サポートはOwner経由）。問い合わせは送信していない。

公式参照: https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context ; https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork ; https://cua.ai/docs/cua-driver ; https://cua.ai/docs/how-to-guides/driver/write-a-bounded-manifest ; https://cua.ai/docs/how-to-guides/driver/keep-running .
