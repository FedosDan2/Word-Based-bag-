import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Storage:
    def __init__(self, path: Path, ttl_days: int) -> None:
        self.path = path
        self.ttl_days = ttl_days
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def _initialize(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            created_at TEXT NOT NULL,
            last_active TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('active', 'completed')),
            stage TEXT NOT NULL DEFAULT 'collecting',
            question_rounds INTEGER NOT NULL DEFAULT 0,
            extracted_data TEXT NOT NULL DEFAULT '{}',
            pending_field TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS sessions_user_status ON sessions(user_id, status);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bug_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
            extracted_data TEXT NOT NULL,
            md_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS request_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS request_events_user_time ON request_events(user_id, timestamp);
        """)
        self.db.commit()

    def _touch_user(self, user_id: int) -> None:
        now = utc_now().isoformat()
        self.db.execute(
            "INSERT INTO users(tg_id,created_at,last_active) VALUES(?,?,?) "
            "ON CONFLICT(tg_id) DO UPDATE SET last_active=excluded.last_active",
            (user_id, now, now),
        )

    def create_session(self, user_id: int) -> str:
        self._touch_user(user_id)
        self.db.execute("UPDATE sessions SET status='completed' WHERE user_id=? AND status='active'", (user_id,))
        now = utc_now()
        session_id = uuid4().hex
        self.db.execute(
            "INSERT INTO sessions(id,user_id,status,created_at,expires_at) VALUES(?,?,'active',?,?)",
            (session_id, user_id, now.isoformat(), (now + timedelta(days=self.ttl_days)).isoformat()),
        )
        self.db.commit()
        return session_id

    def get_active_session(self, user_id: int) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM sessions WHERE user_id=? AND status='active' ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()

    def get_session(self, session_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()

    def update_session(self, session_id: str, **values: Any) -> None:
        allowed = {"stage", "question_rounds", "extracted_data", "pending_field", "status"}
        updates = {k: v for k, v in values.items() if k in allowed}
        if "extracted_data" in updates:
            updates["extracted_data"] = json.dumps(updates["extracted_data"], ensure_ascii=False)
        if not updates:
            return
        setters = ", ".join(f"{key}=?" for key in updates)
        self.db.execute(f"UPDATE sessions SET {setters} WHERE id=?", (*updates.values(), session_id))
        self.db.commit()

    def save_message(self, session_id: str, role: str, text: str) -> None:
        self.db.execute(
            "INSERT INTO messages(session_id,role,text,timestamp) VALUES(?,?,?,?)",
            (session_id, role, text, utc_now().isoformat()),
        )
        self.db.commit()

    def get_messages(self, session_id: str, limit: int = 30) -> list[dict[str, str]]:
        rows = self.db.execute(
            "SELECT role,text FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["text"]} for r in reversed(rows)]

    def save_report(self, session_id: str, fields: dict[str, Any], markdown: str) -> None:
        self.db.execute(
            "INSERT INTO bug_reports(session_id,extracted_data,md_text,created_at) VALUES(?,?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET extracted_data=excluded.extracted_data,"
            "md_text=excluded.md_text,created_at=excluded.created_at",
            (session_id, json.dumps(fields, ensure_ascii=False), markdown, utc_now().isoformat()),
        )
        self.db.commit()

    def record_request(self, user_id: int, hourly_limit: int) -> bool:
        self._touch_user(user_id)
        cutoff = (utc_now() - timedelta(hours=1)).isoformat()
        count = self.db.execute(
            "SELECT COUNT(*) FROM request_events WHERE user_id=? AND timestamp>=?", (user_id, cutoff)
        ).fetchone()[0]
        if count >= hourly_limit:
            self.db.commit()
            return False
        self.db.execute("INSERT INTO request_events(user_id,timestamp) VALUES(?,?)", (user_id, utc_now().isoformat()))
        self.db.commit()
        return True

    def user_summary(self, user_id: int) -> tuple[int, int]:
        rows = self.db.execute(
            "SELECT status,COUNT(*) AS n FROM sessions WHERE user_id=? GROUP BY status", (user_id,)
        ).fetchall()
        counts = {r["status"]: r["n"] for r in rows}
        return counts.get("active", 0), counts.get("completed", 0)

    def delete_user_data(self, user_id: int) -> None:
        self.db.execute("DELETE FROM users WHERE tg_id=?", (user_id,))
        self.db.commit()

    def cleanup_expired(self) -> int:
        now = utc_now().isoformat()
        cur = self.db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        self.db.execute("DELETE FROM request_events WHERE timestamp < ?", ((utc_now() - timedelta(days=2)).isoformat(),))
        self.db.execute("DELETE FROM users WHERE tg_id NOT IN (SELECT user_id FROM sessions)")
        self.db.commit()
        return cur.rowcount

    def close(self) -> None:
        self.db.close()
