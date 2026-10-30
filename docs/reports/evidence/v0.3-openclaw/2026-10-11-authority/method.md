# 採取方法 (2026-10-11)

依頼文はすべて同じ。各送信に新しい r3-leader セッションを使う。
A1/A2/A3 は authority-persistent の同じ Ed25519 identity をファイルに保存して再使用する。
保存された device token と許可 scope も2回目以降に再使用する。
各Aは1本の WebSocket を開き、最後の leader final と親子の idle を確認するまで保持する (応答待ち上限300秒)。
B/C は sessions_spawn の tool start を受信した時点で close(1000)。close イベントから120000ms以上待つ。
Bの再接続は同じidentityとtoken、Cは新しいidentity/keypairをメモリだけで作る。
Cの秘密鍵・公開鍵・tokenはファイル保存しない。削除の対象を特定するdevice IDの対応表だけリポジトリ外に置く。

前回のclient.mjsを土台に、client.id=cli / mode=cli / protocol=4 / loopback 接続を維持。
ブラウザそのものの操作ではなく、指定されたidentity保存・接続寿命を再現する。
表示名は全試行で PDA authority check 2026-10-11 とした。既存deviceと同じsilent pairing clusterにならないようにするため。
pruneは clientId, clientMode, displayName でclusterを作る。C再接続では今回の古いidentityがprune候補になり得る。

connectedとsocket-closedにGatewayのconnIdと採取側UTCを残す。
同一接続でsessions.messages.subscribeし、sessions.listで親子の実行状態を確認し、chat.historyで記録を採る。
メッセージのtimestampはGateway記録時刻、jsonlのutcは採取側の受信・操作時刻。
Aはchat finalの受信時刻と履歴時刻を両方残す。B/C切断中の引用時刻は再接続後の履歴で確認する。
各試行の開始から終了までの全journal行と指定logファイルの全時間帯一致行を保存する。
同じエラーがevent、history、journal、logに重複するため、単純な全文出現回数を実行失敗回数にはしない。

秘密情報の本体は読まない。identity/key/tokenの値はrepoおよびevidenceに出さず、deviceは別名で記録する。
今回のidentity/token保存先は /home/user/v03/openclaw/authority-check/ (directory 0700, files 0600)。
既存2deviceはoc devices listの前後一覧で保存・照合する。今回作成したdeviceだけoc devices removeの対象にする。
設定、plugin、エージェント、typesafe、workspace指示のハッシュを前後で照合する。

採取コードの修正:
- A1開始後、接続要約のusedStoredTokenをラベルからの推定ではなく実際のtoken有無から記録するようにした。connectedイベントは当初から正しい。
- A2で子が起動しない場合に、親final後もchildren.size条件で待機した。A2は上限まで接続を維持して記録。後続は子なしでもfinal+idleで終了する。
- journalの秘匿処理がdeviceの別名まで隠したため、device値の64桁hexのみを対象に修正し、A1の同じ時間帯を再抽出した。製品への依頼の再送はしていない。

モデル利用不可への回復:
A2とA3の初回はモデル利用不可でworkerを作れなかった。両方とも原因調査・全セッションidle確認・設定未変更確認の後、Gateway再起動を1回、同一文の新規セッションへの再試行を1回実施した。再試行はworker完了まで進んだ。BとCは事前models.listでも同じavailable=falseを確認したため、各1回の再起動で回復させてから本試行を1回ずつ行った。これらは同じGatewayプロセスのまま続けた実験ではない。restart*.jsonに理由とUTC、PID、HTTP readinessを保存。

検証コードの初回失敗:
verification.jsonへの報告リンクを、そのファイル自身を初めて出力する前に存在検査して失敗した。初回検証をverification-first-attempt.jsonに保持した。この出力ファイルだけ生成予定として扱い、生成後には全リンクの実在を別途確認するよう修正し、検証は1回だけやり直した。製品への依頼の追加・再送はない。

提出時の手順:
最初のgit commitはAuthor identity unknownで失敗した。既存のOpenClaw検証コミット591a449にあるCodex <codex@localhost>を確認し、git -c user.name=Codex -c user.email=codex@localhost commitで1回再試行する。Gitの永続設定は変更しない。追加ファイルのstaged diff検査で指摘されたcollector-source.txt末尾の余分な空行は除き、git diff --cached --checkの成功を確認した。
