"""SQLite persistence for voice_items and settings."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _user_data_dir() -> Path:
    """Per-user app data directory.

    Override via VOICE_NOTES_DATA_DIR env var for portable installs.
      - Windows: %APPDATA%/voice-notes/
      - macOS:   ~/Library/Application Support/voice-notes/
      - Linux:   $XDG_DATA_HOME/voice-notes/ or ~/.local/share/voice-notes/
    """
    override = os.environ.get("VOICE_NOTES_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "voice-notes"


_DATA_DIR = _user_data_dir()
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_SQLITE_PATH = _DATA_DIR / "voice_notes.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    c = _conn()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS voice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL CHECK (item_type IN ('note','task')),
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','done')),
                priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high')),
                due_at TEXT,
                tags TEXT NOT NULL DEFAULT '[]',
                source TEXT NOT NULL DEFAULT 'typed' CHECK (source IN ('typed','voice-transcript','voice-command')),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_vi_type_status
            ON voice_items (item_type, status, created_at DESC)
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS quick_todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'typed' CHECK (source IN ('typed','voice')),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_qt_done_created
            ON quick_todos (done, created_at DESC)
        """)
        c.commit()
    finally:
        c.close()


def db_get_setting(key: str, default: str = "") -> str:
    c = _conn()
    try:
        row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        c.close()


def db_set_setting(key: str, value: str) -> None:
    c = _conn()
    try:
        c.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value),
        )
        c.commit()
    finally:
        c.close()


def db_create(item_type, title, body, priority, tags, source) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    c = _conn()
    try:
        cur = c.execute(
            """INSERT INTO voice_items (item_type,title,body,priority,tags,source,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?) RETURNING *""",
            (item_type, title, body, priority, json.dumps(tags), source, now, now),
        )
        row = cur.fetchone()
        c.commit()
        return dict(row)
    finally:
        c.close()


def db_list(item_type=None, status="all", q="", limit=200) -> list[dict]:
    where = ["1=1"]
    args: list = []
    if item_type:
        where.append("item_type = ?")
        args.append(item_type)
    if status != "all":
        where.append("status = ?")
        args.append(status)
    if q.strip():
        where.append("(title LIKE ? OR body LIKE ?)")
        like = f"%{q.strip()}%"
        args.extend([like, like])
    sql = (
        f"SELECT * FROM voice_items WHERE {' AND '.join(where)}"
        " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END,"
        " updated_at DESC LIMIT ?"
    )
    args.append(limit)
    c = _conn()
    try:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


_ALLOWED_UPDATE_COLS = frozenset({
    "item_type", "title", "body", "status", "priority", "due_at", "tags", "source",
})


def db_update(item_id: int, fields: dict) -> dict | None:
    if not fields:
        return None
    sets = []
    args: list = []
    for col, val in fields.items():
        # Defense in depth: column names are not parameterizable via ?, so
        # we whitelist them. SQLi-via-key would require a buggy caller, but
        # this makes the function itself safe even when misused.
        if col not in _ALLOWED_UPDATE_COLS:
            raise ValueError(f"db_update: refusing to update unknown column {col!r}")
        if col == "tags":
            val = json.dumps(val)
        sets.append(f"{col} = ?")
        args.append(val)
    sets.append("updated_at = ?")
    args.append(datetime.now(timezone.utc).isoformat())
    args.append(item_id)
    c = _conn()
    try:
        cur = c.execute(
            f"UPDATE voice_items SET {', '.join(sets)} WHERE id = ? RETURNING *", args
        )
        row = cur.fetchone()
        c.commit()
        return dict(row) if row else None
    finally:
        c.close()


def db_delete(item_id: int) -> bool:
    c = _conn()
    try:
        cur = c.execute("DELETE FROM voice_items WHERE id = ? RETURNING id", (item_id,))
        row = cur.fetchone()
        c.commit()
        return row is not None
    finally:
        c.close()


# ── quick_todos: right-pane running todo list ──────────────────────────────

def qt_create(text: str, source: str = "typed") -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("quick todo text cannot be empty")
    now = datetime.now(timezone.utc).isoformat()
    c = _conn()
    try:
        cur = c.execute(
            "INSERT INTO quick_todos (text, source, created_at) VALUES (?, ?, ?) RETURNING *",
            (text, source, now),
        )
        row = cur.fetchone()
        c.commit()
        return dict(row)
    finally:
        c.close()


def qt_list(include_done: bool = True, done_limit: int = 20) -> list[dict]:
    """Open todos first (newest first), then optionally the last N completed."""
    c = _conn()
    try:
        opens = [dict(r) for r in c.execute(
            "SELECT * FROM quick_todos WHERE done = 0 ORDER BY created_at DESC"
        ).fetchall()]
        if not include_done:
            return opens
        dones = [dict(r) for r in c.execute(
            "SELECT * FROM quick_todos WHERE done = 1 ORDER BY completed_at DESC LIMIT ?",
            (done_limit,),
        ).fetchall()]
        return opens + dones
    finally:
        c.close()


def qt_toggle(todo_id: int) -> dict | None:
    """Flip done state. Sets completed_at when marking done, clears when un-doing."""
    c = _conn()
    try:
        row = c.execute("SELECT done FROM quick_todos WHERE id = ?", (todo_id,)).fetchone()
        if row is None:
            return None
        new_done = 0 if row["done"] else 1
        completed_at = datetime.now(timezone.utc).isoformat() if new_done else None
        cur = c.execute(
            "UPDATE quick_todos SET done = ?, completed_at = ? WHERE id = ? RETURNING *",
            (new_done, completed_at, todo_id),
        )
        out = cur.fetchone()
        c.commit()
        return dict(out) if out else None
    finally:
        c.close()


def qt_delete(todo_id: int) -> bool:
    c = _conn()
    try:
        cur = c.execute("DELETE FROM quick_todos WHERE id = ? RETURNING id", (todo_id,))
        row = cur.fetchone()
        c.commit()
        return row is not None
    finally:
        c.close()


def qt_clear_done() -> int:
    c = _conn()
    try:
        cur = c.execute("DELETE FROM quick_todos WHERE done = 1")
        deleted = cur.rowcount
        c.commit()
        return deleted
    finally:
        c.close()


def qt_count_open() -> int:
    c = _conn()
    try:
        row = c.execute("SELECT COUNT(*) AS n FROM quick_todos WHERE done = 0").fetchone()
        return int(row["n"]) if row else 0
    finally:
        c.close()
