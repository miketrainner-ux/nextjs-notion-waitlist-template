"""
MT.OS Intelligence Index
Central authority for all file metadata across all systems.
SQLite as source of truth.
"""
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path


@dataclass
class FileRecord:
    """Complete file record in the intelligence index."""
    uuid: str
    name_current: str
    name_original: str
    ext: str
    project: Optional[str]
    person: Optional[str]
    category: str  # 11 domains
    subcategory: str  # sub-folder
    domain_code: str  # 02, 03, etc
    drive_id: str
    content_hash: str
    date_created: str
    date_modified: str
    file_size_bytes: int
    mime_type: str
    version: str  # v1, v2, v3
    origin: str  # google_drive, icloud, notion, obsidian
    destination: str
    confidence: float  # 0.0-1.0
    status: str  # active, archived, review, duplicate
    keywords: list[str]  # extracted from filename + metadata
    notes: str
    last_indexed: str


class IntelligenceIndex:
    """Central index for all files across all systems."""

    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            uuid TEXT PRIMARY KEY,
            name_current TEXT NOT NULL,
            name_original TEXT NOT NULL,
            ext TEXT,
            project TEXT,
            person TEXT,
            category TEXT NOT NULL,
            subcategory TEXT,
            domain_code TEXT NOT NULL,
            drive_id TEXT UNIQUE,
            content_hash TEXT,
            date_created TEXT,
            date_modified TEXT,
            file_size_bytes INTEGER,
            mime_type TEXT,
            version TEXT,
            origin TEXT,
            destination TEXT,
            confidence REAL,
            status TEXT,
            keywords TEXT,
            notes TEXT,
            last_indexed TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_project ON files(project);
        CREATE INDEX IF NOT EXISTS idx_person ON files(person);
        CREATE INDEX IF NOT EXISTS idx_category ON files(category);
        CREATE INDEX IF NOT EXISTS idx_hash ON files(content_hash);
        CREATE INDEX IF NOT EXISTS idx_status ON files(status);
        CREATE INDEX IF NOT EXISTS idx_confidence ON files(confidence);

        CREATE TABLE IF NOT EXISTS duplicates (
            uuid_primary TEXT,
            uuid_duplicate TEXT,
            hash_match TEXT,
            size_match INTEGER,
            name_similarity REAL,
            detected_at TEXT,
            PRIMARY KEY (uuid_primary, uuid_duplicate)
        );

        CREATE TABLE IF NOT EXISTS classification_rules (
            rule_id TEXT PRIMARY KEY,
            rule_type TEXT,
            pattern TEXT,
            target_category TEXT,
            priority INTEGER,
            confidence REAL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS index_stats (
            date_scanned TEXT,
            total_files INTEGER,
            confidence_alta INTEGER,
            confidence_media INTEGER,
            confidence_baixa INTEGER,
            duplicates_found INTEGER,
            execution_time_seconds REAL
        );
        """)
        self.db.commit()

    def upsert_file(self, record: FileRecord) -> None:
        """Insert or update file record."""
        keywords_str = ",".join(record.keywords) if record.keywords else ""
        self.db.execute(
            """INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.uuid, record.name_current, record.name_original, record.ext,
                record.project, record.person, record.category, record.subcategory,
                record.domain_code, record.drive_id, record.content_hash,
                record.date_created, record.date_modified, record.file_size_bytes,
                record.mime_type, record.version, record.origin, record.destination,
                record.confidence, record.status, keywords_str, record.notes,
            )
        )
        self.db.execute("UPDATE files SET last_indexed = ? WHERE uuid = ?",
                       (datetime.now(timezone.utc).isoformat(), record.uuid))
        self.db.commit()

    def find_duplicates(self, hash_value: str) -> list[str]:
        """Find all files with same hash (real duplicates)."""
        rows = self.db.execute(
            "SELECT uuid FROM files WHERE content_hash = ? AND status = 'active'",
            (hash_value,)
        ).fetchall()
        return [row[0] for row in rows]

    def find_by_project(self, project: str) -> list[dict]:
        """Get all files for a project."""
        rows = self.db.execute(
            "SELECT * FROM files WHERE project = ? ORDER BY category, name_current",
            (project,)
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def find_by_person(self, person: str) -> list[dict]:
        """Get all files for a person."""
        rows = self.db.execute(
            "SELECT * FROM files WHERE person = ? ORDER BY category, name_current",
            (person,)
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def find_low_confidence(self, threshold: float = 0.75) -> list[dict]:
        """Find files below confidence threshold."""
        rows = self.db.execute(
            "SELECT * FROM files WHERE confidence < ? AND status = 'active'",
            (threshold,)
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def search(self, query: str, fields: list[str] = None) -> list[dict]:
        """Search across name, keywords, project, person."""
        if fields is None:
            fields = ["name_current", "keywords", "project", "person"]

        q = query.lower()
        rows = self.db.execute("""
            SELECT * FROM files WHERE
            name_current LIKE ? OR
            keywords LIKE ? OR
            project LIKE ? OR
            person LIKE ?
            ORDER BY confidence DESC
        """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_stats(self) -> dict:
        """Statistics on current index."""
        total = self.db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        active = self.db.execute(
            "SELECT COUNT(*) FROM files WHERE status = 'active'"
        ).fetchone()[0]
        duplicates = self.db.execute(
            "SELECT COUNT(DISTINCT content_hash) FROM files WHERE status = 'active' GROUP BY content_hash HAVING COUNT(*) > 1"
        ).fetchall()

        conf_alta = self.db.execute(
            "SELECT COUNT(*) FROM files WHERE confidence >= 0.95"
        ).fetchone()[0]
        conf_media = self.db.execute(
            "SELECT COUNT(*) FROM files WHERE confidence >= 0.75 AND confidence < 0.95"
        ).fetchone()[0]
        conf_baixa = self.db.execute(
            "SELECT COUNT(*) FROM files WHERE confidence < 0.75"
        ).fetchone()[0]

        return {
            "total_files": total,
            "active_files": active,
            "duplicate_groups": len(duplicates),
            "confidence_alta": conf_alta,
            "confidence_media": conf_media,
            "confidence_baixa": conf_baixa,
            "index_size_mb": Path(self.db).stat().st_size / (1024 * 1024),
        }

    def _row_to_dict(self, row: tuple) -> dict:
        """Convert DB row to dict."""
        fields = [
            "uuid", "name_current", "name_original", "ext", "project", "person",
            "category", "subcategory", "domain_code", "drive_id", "content_hash",
            "date_created", "date_modified", "file_size_bytes", "mime_type",
            "version", "origin", "destination", "confidence", "status", "keywords", "notes"
        ]
        return dict(zip(fields, row))

    def close(self) -> None:
        self.db.close()
