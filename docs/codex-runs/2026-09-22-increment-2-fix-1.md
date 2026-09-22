# 増分 2 の修正 1: 試験から指示文書の参照を外す

この指示は完結している。質問はせず、次の 1 点だけを行い、コミットして終える。他のファイルには触れない。

- ブランチ: `main` から分岐した `increment-2-fix-1`
- 対象: `tests/unit/test_registry.py` の `test_registry_contract`
- 変更: `docs/codex-runs/2026-09-22-increment-2.md` を読み、`## 5. 雛形ワークフロー` の節から JSON を取り出して `registry.workflow` と比較している 3 行（`instruction = ...`、`section = ...`、`assert registry.workflow == ...`）を削除する。不要になった `import re` と `import json` があれば削除する。他の assert は残す
- コメント、説明文、置き換えの assert を足さない
- 確認: `ruff check` と `pytest tests/unit` が通る
- コミットメッセージは日本語で 1 文。`Co-Authored-By` 行を付けない
- 報告書は書かない。コミットしたら終える
