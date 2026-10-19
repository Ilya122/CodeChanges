import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

KINDS = ("plan", "change")
RISKS = ("low", "medium", "high")

# pending -> approved | denied | revising   (user decides)
# revising -> pending                       (AI revises)
# approved -> applied                       (AI applies and reports the commit)
DECISIONS = {"apply": "approved", "deny": "denied", "revise": "revising"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL DEFAULT 'default',
    kind TEXT NOT NULL DEFAULT 'change',
    file TEXT,
    title TEXT NOT NULL,
    why TEXT NOT NULL DEFAULT '',
    patch TEXT NOT NULL DEFAULT '',
    risk TEXT NOT NULL DEFAULT 'low',
    status TEXT NOT NULL DEFAULT 'pending',
    revision INTEGER NOT NULL DEFAULT 1,
    comment TEXT NOT NULL DEFAULT '',
    commit_hash TEXT,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    block_id INTEGER NOT NULL REFERENCES blocks(id),
    at REAL NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);
"""


class Store:
    def __init__(self, repo):
        folder = Path(repo) / ".codechange"
        folder.mkdir(exist_ok=True)
        # self-ignoring folder, so the DB never shows up in the repo's own git status
        (folder / ".gitignore").write_text("*\n")
        self.path = folder / "db.sqlite"
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _event(conn, block_id, actor, action, data=None):
        conn.execute(
            "INSERT INTO events (block_id, at, actor, action, data) VALUES (?,?,?,?,?)",
            (block_id, time.time(), actor, action, json.dumps(data or {})),
        )

    @staticmethod
    def _get(conn, block_id):
        row = conn.execute("SELECT * FROM blocks WHERE id = ?", (block_id,)).fetchone()
        if row is None:
            raise LookupError(f"block {block_id} not found")
        return row

    def create(self, data):
        kind = data.get("kind", "change")
        risk = data.get("risk", "low")
        title = str(data.get("title", "")).strip()
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if risk not in RISKS:
            raise ValueError(f"risk must be one of {RISKS}")
        if not title:
            raise ValueError("title is required")
        if kind == "change" and not (data.get("file") and data.get("patch")):
            raise ValueError("a change block needs file and patch")
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO blocks (task, kind, file, title, why, patch, risk, created, updated)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(data.get("task") or "default"), kind, data.get("file"), title,
                    str(data.get("why", "")), str(data.get("patch", "")), risk, now, now,
                ),
            )
            self._event(conn, cur.lastrowid, "ai", "proposed")
            return dict(self._get(conn, cur.lastrowid))

    def list(self, statuses=None, task=None):
        sql, args = "SELECT * FROM blocks", []
        where = []
        if statuses:
            where.append(f"status IN ({','.join('?' * len(statuses))})")
            args += statuses
        if task:
            where.append("task = ?")
            args.append(task)
        if where:
            sql += " WHERE " + " AND ".join(where)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql + " ORDER BY id", args)]

    def get(self, block_id):
        with self._conn() as conn:
            block = dict(self._get(conn, block_id))
            events = conn.execute(
                "SELECT at, actor, action, data FROM events WHERE block_id = ? ORDER BY id",
                (block_id,),
            )
            block["events"] = [{**dict(e), "data": json.loads(e["data"])} for e in events]
            return block

    def counts(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT status, COUNT(*) n FROM blocks GROUP BY status")
            return {r["status"]: r["n"] for r in rows}

    def decide(self, block_id, decision, comment=""):
        if decision not in DECISIONS:
            raise ValueError(f"decision must be one of {tuple(DECISIONS)}")
        comment = comment.strip()
        if decision == "revise" and not comment:
            raise ValueError("a revise decision needs a comment")
        with self._conn() as conn:
            block = self._get(conn, block_id)
            if block["status"] != "pending":
                raise ValueError(f"block is {block['status']}, not pending")
            conn.execute(
                "UPDATE blocks SET status = ?, comment = ?, updated = ? WHERE id = ?",
                (DECISIONS[decision], comment, time.time(), block_id),
            )
            self._event(conn, block_id, "user", decision, {"comment": comment})
            return dict(self._get(conn, block_id))

    def revise(self, block_id, data):
        with self._conn() as conn:
            block = self._get(conn, block_id)
            if block["status"] != "revising":
                raise ValueError(f"block is {block['status']}, not revising")
            fields = {k: str(data[k]) for k in ("title", "why", "patch") if k in data}
            if "risk" in data:
                if data["risk"] not in RISKS:
                    raise ValueError(f"risk must be one of {RISKS}")
                fields["risk"] = data["risk"]
            if not fields:
                raise ValueError("nothing to revise: send title, why, patch or risk")
            # keep what the user saw, so the history shows what changed
            before = {k: block[k] for k in fields}
            sets = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(
                f"UPDATE blocks SET {sets}, status = 'pending', revision = revision + 1,"
                " updated = ? WHERE id = ?",
                (*fields.values(), time.time(), block_id),
            )
            self._event(conn, block_id, "ai", "revised", {"before": before})
            return dict(self._get(conn, block_id))

    def mark_applied(self, block_id, commit=""):
        commit = str(commit).strip()
        with self._conn() as conn:
            block = self._get(conn, block_id)
            # plans have no diff to commit, so the commit is optional for them
            if block["kind"] == "change" and not commit:
                raise ValueError("commit is required")
            if block["status"] != "approved":
                raise ValueError(f"block is {block['status']}, not approved")
            conn.execute(
                "UPDATE blocks SET status = 'applied', commit_hash = ?, updated = ? WHERE id = ?",
                (commit or None, time.time(), block_id),
            )
            self._event(conn, block_id, "ai", "applied", {"commit": commit})
            return dict(self._get(conn, block_id))
