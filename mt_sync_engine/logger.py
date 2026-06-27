"""
MT Sync Engine — Structured Logger
JSON lines to file + human-readable to stdout. Zero AI.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SyncLogger:
    def __init__(self, log_dir: str, session_id: str):
        self._dir = Path(log_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._session = session_id
        self._file = self._dir / f"sync_{session_id}.jsonl"
        self._stats: dict[str, int] = {
            "scanned": 0,
            "unchanged": 0,
            "exported": 0,
            "assets_downloaded": 0,
            "errors": 0,
            "conflicts": 0,
        }

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _emit(self, level: str, event: str, **kwargs: Any) -> None:
        record = {
            "ts": self._ts(),
            "session": self._session,
            "level": level,
            "event": event,
            **kwargs,
        }
        with open(self._file, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        color = {"INFO": "\033[0m", "SKIP": "\033[90m", "OK": "\033[32m",
                 "WARN": "\033[33m", "ERROR": "\033[31m"}.get(level, "\033[0m")
        print(f"{color}[{level}] {event}\033[0m", file=sys.stderr)

    def info(self, event: str, **kw: Any) -> None:
        self._emit("INFO", event, **kw)

    def skip(self, notion_id: str, title: str) -> None:
        self._stats["unchanged"] += 1
        self._emit("SKIP", f"unchanged: {title}", notion_id=notion_id)

    def exported(self, notion_id: str, path: str) -> None:
        self._stats["exported"] += 1
        self._emit("OK", f"exported → {path}", notion_id=notion_id)

    def asset(self, url: str, dest: str) -> None:
        self._stats["assets_downloaded"] += 1
        self._emit("OK", f"asset → {dest}", url=url)

    def error(self, event: str, **kw: Any) -> None:
        self._stats["errors"] += 1
        self._emit("ERROR", event, **kw)

    def conflict(self, event: str, **kw: Any) -> None:
        self._stats["conflicts"] += 1
        self._emit("WARN", f"conflict: {event}", **kw)

    def summary(self) -> dict[str, Any]:
        s = {"session": self._session, "ts": self._ts(), **self._stats}
        self._emit("INFO", "SUMMARY", **self._stats)
        return s
