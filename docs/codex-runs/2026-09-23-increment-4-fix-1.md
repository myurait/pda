# 増分 4 の修正 1: 画面の CSS の整形

この指示は完結している。質問はせず、次の 1 点だけを行い、コミットして origin に push して終える。他のファイルには触れない。

- 作業場所: ミニ PC の `~/pda`。`main` から分岐したブランチ `increment-4-fix-1`
- 対象: `src/pda_view/static/app.css`
- 変更: 1 行に詰め込まれている CSS を、規則ごとに改行し、宣言ごとに 1 行ずつ 2 スペースで字下げした形に整形する。セレクタ、宣言、値、順序、メディアクエリの内容は一切変えない。コメントを足さない
- 確認: 整形前後で、空白と改行を取り除いた文字列が一致すること（`tr -d ' \n'` で比べる）。`tests/unit` が通る。`docker compose -f deploy/docker-compose.yaml up -d --no-build --force-recreate pda-view` の後、`curl -fsS http://127.0.0.1:5081/static/app.css` が 200 で返る
- コミットメッセージは日本語で 1 文。`Co-Authored-By` 行を付けない。`git push origin increment-4-fix-1`
- 報告書は書かない
