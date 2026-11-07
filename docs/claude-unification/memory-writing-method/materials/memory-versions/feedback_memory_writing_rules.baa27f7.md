---
name: memory-writing-rules
description: メモリ・`SKILL.md`・`CLAUDE.md` の各文を肯定の動詞の終止形で終わる 1 文にし、適用する物と操作の後に残る物をパス・「」か `` で囲んだ語・数字で書き、索引の各行にメモリの `description` と同じ文字列を書く
metadata:
  node_type: memory
  type: feedback
---

- `~/.claude/memory/` と `~/.claude/projects/*/memory/` の `.md` ファイル (`MEMORY.md` と `communication-index.md` を除く)、`~/.claude/skills/*/SKILL.md`、`~/.claude/CLAUDE.md` の各文 (frontmatter・コードブロック・`#` で始まる見出しの行・`@` で始まる行の外の文と、メモリの `description` の値) を、次の形で書く
  - 日本語の文の文末を、肯定の動詞の終止形 (例: 「書く」「消す」「置く」「実行する」) にする
  - 英語の文の先頭を、肯定の動詞の原形 (例: 「Write」「Run」) にする
  - 「」と `` の外の部分から、「とき」「場合」「なら」「たら」「れば」「際に」と英単語の「if」「when」「unless」を消す
  - 「」と `` の外の部分から、「しない」「禁止」「てはならない」と英単語の「never」「not」「n't」を消す
  - 「」と `` の外の部分から、「ため」「ので」「理由」「背景」と英単語の「because」「why」を消す
  - 「」と `` の外の部分から、「重要」「本質」「適切」「妥当」「十分」「必要」「できる」「なるべく」「意識」「注意」「心がけ」「感じ」「迷」「気づ」「自問」「水準」「同じ型」「失敗の型」「分類」「避け」「タスクを越え」を消す
  - 文末の「確認する」「検討する」「検証する」「考える」「判断する」「見直す」を、その後に行う操作 (「書く」「消す」「実行する」など) の動詞に置き換える
  - 各文か、その文の親の箇条書きの行に、適用する物と操作の後に残る物を、パス・ファイル名・見出し・「」か `` で囲んだ語・数字・「先頭」「末尾」「文末」「直後」「行」のいずれかで書く
- `~/.claude/memory/` と `~/.claude/projects/*/memory/` の各メモリファイル (`MEMORY.md` と `communication-index.md` を除く) を、次の形で書く
  - frontmatter に `name`・`description`・`metadata.node_type`・`metadata.type` のキーを置く
  - `name` の値を、英小文字・数字・ハイフンだけでつないだ語にする
  - `description` の値の、「」と `` の外にある句点「。」の数を 0 にする
  - `metadata.node_type` の値を `memory` にする
  - `metadata.type` の値を `feedback`・`user`・`project`・`reference` のいずれかにする
  - 本文の各行を、空行、`## ` で始まる見出しの行、行頭の空白の後に `- ` が続く 1 文の行のいずれかにする
  - `metadata.type` の値が `feedback` のファイルの本文から、`YYYY-MM-DD`・`YYYY/MM/DD`・`M月D日` の形の日付を消す
  - 本文に書いた他のメモリのファイル名と `name` の値を、`[[<そのメモリの name の値>]]` の形に置き換える
- 索引ファイル (`~/.claude/MEMORY.md`・`~/.claude/memory/communication-index.md`・`~/.claude/projects/*/memory/MEMORY.md`) を、次の形で書く
  - `~/.claude/memory/` の各メモリファイルのファイル名を、`~/.claude/MEMORY.md` の箇条書きの行と `communication-index.md` の表の行の、どちらか一方に書く
  - `~/.claude/projects/<プロジェクト>/memory/` の各メモリファイルのファイル名を、同じディレクトリの `MEMORY.md` の箇条書きの行に書く
  - `MEMORY.md` の箇条書きの各行の「 — 」の後ろと、`communication-index.md` の表の各行の 3 列目に、その行が指すメモリの `description` の値と同じ文字列を書く
  - `name` の値を書き換えたメモリについて、`~/.claude/memory/`・`~/.claude/projects/*/memory/`・`~/.claude/skills/*/SKILL.md`・`~/.claude/CLAUDE.md` にある `[[<旧値>]]` を `[[<新値>]]` に置き換える
