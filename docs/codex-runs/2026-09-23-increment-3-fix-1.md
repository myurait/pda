# 増分 3 の修正 1: Conductor UI コンテナの健康確認

この指示は完結している。質問はせず、次の 1 点だけを行い、コミットして origin に push して終える。他のファイルには触れない。

- 作業場所: ミニ PC の `~/pda`。`main` から分岐したブランチ `increment-3-fix-1`
- 対象: `deploy/docker-compose.yaml` の `conductor-ui` サービス
- 変更: `healthcheck` を足す。`test` は `["CMD", "curl", "-fsS", "http://localhost:5000/"]`、`interval: 10s`、`timeout: 3s`、`retries: 10`。親イメージの健康確認（8080 番）を上書きするためのもの
- コメント、説明文、他の項目の変更を足さない
- 確認: `tests/unit` が通る。`docker compose -f deploy/docker-compose.yaml up -d --no-build conductor-ui` の後、`docker compose -f deploy/docker-compose.yaml ps conductor-ui` が `healthy` になる。結果を確認したら他のコンテナには触れない
- コミットメッセージは日本語で 1 文。`Co-Authored-By` 行を付けない。`git push origin increment-3-fix-1`
- 報告書は書かない
