"""起動と報告の台帳 (SQLite)。セッション、ターン、送信と判定、出来事を持つ。"""
import json
import pathlib
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, t3_thread_id TEXT, claude_session_id TEXT, claude_started INTEGER DEFAULT 0,
  role TEXT, parent_session_id TEXT, title TEXT, cwd TEXT, model TEXT, created_at TEXT);
CREATE INDEX IF NOT EXISTS sessions_thread ON sessions (t3_thread_id);
CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, requester TEXT, request TEXT,
  started_at TEXT, ended_at TEXT, outcome TEXT, final_text TEXT, notified_at TEXT, reported_to TEXT);
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, turn_id INTEGER, started_at TEXT, ended_at TEXT,
  submitted TEXT, drafts TEXT, verdicts TEXT, decision TEXT);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, session_id TEXT, turn_id INTEGER, kind TEXT, data TEXT);
"""

ADDED_COLUMNS = [
    ("sessions", "workdir_fixed", "INTEGER DEFAULT 0"),
]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _dumps(obj):
    return json.dumps(obj, ensure_ascii=False)


class Ledger:
    def __init__(self, path):
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        for table, column, decl in ADDED_COLUMNS:
            if column not in {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def _one(self, sql, args=()):
        row = self.db.execute(sql, args).fetchone()
        return dict(row) if row else None

    def _all(self, sql, args=()):
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    # セッション
    def session(self, session_id):
        return self._one("SELECT * FROM sessions WHERE id=?", (session_id,))

    def session_by_thread(self, thread_id):
        if not thread_id:
            return None
        return self._one("SELECT * FROM sessions WHERE t3_thread_id=? ORDER BY created_at DESC", (thread_id,))

    def create_session(self, session_id, thread_id, claude_session_id, cwd, role=None, parent=None, title=None,
                       model=None):
        self.db.execute(
            "INSERT INTO sessions (id, t3_thread_id, claude_session_id, role, parent_session_id, title, cwd, model,"
            " created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (session_id, thread_id, claude_session_id, role, parent, title, cwd, model, now()))
        return self.session(session_id)

    def update_session(self, session_id, **fields):
        sets = ", ".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE sessions SET {sets} WHERE id=?", (*fields.values(), session_id))

    def children(self, session_id):
        return self._all("SELECT * FROM sessions WHERE parent_session_id=? ORDER BY created_at", (session_id,))

    def sessions(self):
        return self._all("SELECT * FROM sessions ORDER BY created_at")

    # ターン
    def start_turn(self, session_id, requester, request):
        cur = self.db.execute("INSERT INTO turns (session_id, requester, request, started_at) VALUES (?,?,?,?)",
                              (session_id, requester, request, now()))
        return cur.lastrowid

    def finish_turn(self, turn_id, outcome, final_text):
        self.db.execute("UPDATE turns SET ended_at=?, outcome=?, final_text=? WHERE id=?",
                        (now(), outcome, final_text, turn_id))

    def mark_turn(self, turn_id, **fields):
        sets = ", ".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE turns SET {sets} WHERE id=?", (*fields.values(), turn_id))

    def turn(self, turn_id):
        return self._one("SELECT * FROM turns WHERE id=?", (turn_id,))

    def turns(self, session_id=None, limit=50):
        if session_id:
            return self._all("SELECT * FROM turns WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, limit))
        return self._all("SELECT * FROM turns ORDER BY id DESC LIMIT ?", (limit,))

    def recent_exchanges(self, session_id, before_turn, limit=3):
        rows = self._all(
            "SELECT request, final_text FROM turns WHERE session_id=? AND id<? AND final_text IS NOT NULL"
            " ORDER BY id DESC LIMIT ?", (session_id, before_turn, limit))
        return list(reversed(rows))

    def close_dangling_turns(self):
        self.db.execute("UPDATE turns SET ended_at=?, outcome='failed' WHERE outcome IS NULL", (now(),))

    # 送信と判定
    def start_attempt(self, turn_id, submitted):
        cur = self.db.execute("INSERT INTO attempts (turn_id, started_at, submitted) VALUES (?,?,?)",
                              (turn_id, now(), submitted))
        return cur.lastrowid

    def finish_attempt(self, attempt_id, drafts, verdicts, decision):
        self.db.execute("UPDATE attempts SET ended_at=?, drafts=?, verdicts=?, decision=? WHERE id=?",
                        (now(), _dumps(drafts), _dumps(verdicts), decision, attempt_id))

    def attempts(self, turn_id):
        rows = self._all("SELECT * FROM attempts WHERE turn_id=? ORDER BY id", (turn_id,))
        for row in rows:
            for key in ("drafts", "verdicts"):
                row[key] = json.loads(row[key]) if row[key] else None
        return rows

    # 出来事
    def event(self, kind, data, session_id=None, turn_id=None):
        self.db.execute("INSERT INTO events (ts, session_id, turn_id, kind, data) VALUES (?,?,?,?,?)",
                        (now(), session_id, turn_id, kind, _dumps(data)))

    def events(self, turn_id=None, kind=None, limit=500):
        sql, args = "SELECT * FROM events WHERE 1=1", []
        if turn_id is not None:
            sql += " AND turn_id=?"
            args.append(turn_id)
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        rows = self._all(sql + " ORDER BY id DESC LIMIT ?", (*args, limit))
        for row in rows:
            row["data"] = json.loads(row["data"]) if row["data"] else None
        return list(reversed(rows))
