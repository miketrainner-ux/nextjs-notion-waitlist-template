"""
MT Sync Engine — Index Database
SQLite: persists notion_id, hash, mod_time, vault_path. Idempotent comparisons.
"""
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path


class SyncIndex:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            notion_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            vault_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            notion_modified_at TEXT NOT NULL,
            synced_at TEXT NOT NULL,
            parent_id TEXT,
            type TEXT DEFAULT 'page'
        );
        CREATE INDEX IF NOT EXISTS idx_vault_path ON pages(vault_path);
        CREATE INDEX IF NOT EXISTS idx_parent ON pages(parent_id);

        CREATE TABLE IF NOT EXISTS assets (
            url TEXT PRIMARY KEY,
            vault_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            downloaded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS relations (
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            relation_type TEXT,
            PRIMARY KEY (from_id, to_id)
        );
        """)
        self.db.commit()

    def _hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def page_exists(self, notion_id: str) -> bool:
        r = self.db.execute(
            "SELECT 1 FROM pages WHERE notion_id = ?", (notion_id,)
        ).fetchone()
        return r is not None

    def needs_update(self, notion_id: str, content_hash: str, mod_time: str) -> bool:
        r = self.db.execute(
            "SELECT content_hash FROM pages WHERE notion_id = ?", (notion_id,)
        ).fetchone()
        if r is None:
            return True
        return r[0] != content_hash

    def upsert_page(
        self, notion_id: str, title: str, vault_path: str, content: bytes,
        notion_mod_time: str, parent_id: str | None = None, type_: str = "page"
    ) -> None:
        h = self._hash(content)
        self.db.execute(
            """INSERT OR REPLACE INTO pages
            (notion_id, title, vault_path, content_hash, notion_modified_at, synced_at, parent_id, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (notion_id, title, vault_path, h, notion_mod_time, self._now(), parent_id, type_)
        )
        self.db.commit()

    def upsert_asset(self, url: str, vault_path: str, content: bytes) -> None:
        h = self._hash(content)
        self.db.execute(
            "INSERT OR REPLACE INTO assets (url, vault_path, content_hash, downloaded_at) VALUES (?, ?, ?, ?)",
            (url, vault_path, h, self._now())
        )
        self.db.commit()

    def record_relation(self, from_id: str, to_id: str, rel_type: str = "links") -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO relations (from_id, to_id, relation_type) VALUES (?, ?, ?)",
            (from_id, to_id, rel_type)
        )
        self.db.commit()

    def get_relations(self, notion_id: str) -> list[tuple[str, str]]:
        rows = self.db.execute(
            "SELECT to_id, relation_type FROM relations WHERE from_id = ?",
            (notion_id,)
        ).fetchall()
        return rows

    def get_vault_path(self, notion_id: str) -> str | None:
        r = self.db.execute(
            "SELECT vault_path FROM pages WHERE notion_id = ?", (notion_id,)
        ).fetchone()
        return r[0] if r else None

    def all_pages(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT notion_id, title, vault_path, content_hash, notion_modified_at FROM pages"
        ).fetchall()
        return [
            {
                "notion_id": row[0], "title": row[1], "vault_path": row[2],
                "content_hash": row[3], "notion_modified_at": row[4]
            }
            for row in rows
        ]

    def close(self) -> None:
        self.db.close()
