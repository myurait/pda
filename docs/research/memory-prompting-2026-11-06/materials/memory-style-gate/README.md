# memory-style-gate

メモリ・skill・`~/.claude/CLAUDE.md` の書き換えを検査し、書き方の規則 (`~/.claude/memory/feedback_memory_writing_rules.md`) から外れた行を、行番号と直し方を添えて書き手に返すフック。

## 動き

- PostToolUse (Write・Edit・MultiEdit) で、書き換えたファイルが対象なら検査する
- Stop で、ターンの開始 (`mark-turn-start.py` が `~/.claude/hook-state/<session_id>.start` に書く時刻) 以降に変わった対象のファイルを検査する。Bash での書き換えはここで拾う
- 外れた行のあるファイルは `decision: block` と直す行の一覧で返す。同じファイルを同じセッションで 2 回返したあとは通す
- 検査の失敗はすべて通す側に倒す

## 対象

- パスに `/memory/` を含む `.md`、`/skills/` を含む `.md`、`~/.claude/CLAUDE.md`、`~/.claude/MEMORY.md`
- パスに `/skills/synced/`・`/plugins/`・`/tmp/`・`/backup/`・`/results/` を含むファイルは対象から外す

## 検査

1. 構造 (スクリプト内): 強調の `**`、`Why:` と `How to apply` の見出し、「発火」の表、frontmatter の `name` と `description`、索引への登録、`[[name]]` の参照先
2. 文の書き方 (Jev): 本文を 1 文ずつに切り、文ごとに Jev に 5 つのラベル (prescriptive・conditional・prohibitive・rationale・not_a_rule) から 1 つを選ばせる。prescriptive と not_a_rule と、confidence 0.3 未満の uncertain を通す。問いは `memory-style-gate-questions.json` にある
   - 書き換えの対応 (`→` を含む行)・例示 (`例:`)・関連の列挙 (`関連:`) の行は、Jev に問わずに not_a_rule とする
   - ラベルは文の内容と questions ファイルのハッシュごとに `~/.claude/hook-state/memory-style-gate-cache.json` に残し、同じ文は 2 回目から問わない
   - Jev が失敗した文は、語の形で拾う検査で代える

問いの分類は arXiv:2611.04367 の 4 分類 (Prescriptive・Explanatory・Conditional・Prohibitive) に、規則でない行の分類を足したもの。

## 入れ方

```bash
ln -sfn ~/docs/jev/hooks/memory-style-gate/memory-style-gate.py ~/.claude/hooks/memory-style-gate.py
ln -sfn ~/docs/jev/hooks/memory-style-gate/memory-style-gate-questions.json ~/.claude/hooks/memory-style-gate-questions.json
```

`~/.claude/settings.json` に次の 2 つを足す。

```json
{
  "PostToolUse": [
    {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/memory-style-gate.py --post-tool-use", "timeout": 60}]}
  ],
  "Stop": [
    {"hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/memory-style-gate.py --stop", "timeout": 120}]}
  ]
}
```

スクリプトはリンクを辿った先のディレクトリから questions ファイルを読む。

## テスト

```bash
python3 test_memory_style_gate.py
```

テストは Jev を呼ばず、語の形での検査 (`MEMORY_STYLE_GATE_NO_JEV=1`) で動く。

## 記録

- 検査ごとの記録: `~/.claude/debug/memory-style-gate.log` (1 行 1 JSON。event・agent_id・path・findings・blocks)
- 返した回数: `~/.claude/hook-state/memory-style-gate.<session_id>.json`
