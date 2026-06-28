#!/usr/bin/env python3
"""
MT Sync Engine — Dashboard
Real-time sync monitoring. Read-only. No IA.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta


class SyncDashboard:
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)

    def latest_session(self) -> str | None:
        """Get most recent session ID from logs."""
        logs = list(self.log_dir.glob("sync_*.jsonl"))
        if not logs:
            return None
        return logs[-1].stem.replace("sync_", "")

    def read_session(self, session_id: str) -> list[dict]:
        """Read all records from a session."""
        log_file = self.log_dir / f"sync_{session_id}.jsonl"
        if not log_file.exists():
            return []
        records = []
        with open(log_file) as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records

    def session_summary(self, session_id: str) -> dict:
        """Aggregate stats for a session."""
        records = self.read_session(session_id)
        stats = {
            "session_id": session_id,
            "start": None,
            "end": None,
            "duration_seconds": 0,
            "scanned": 0,
            "exported": 0,
            "skipped": 0,
            "assets": 0,
            "errors": 0,
            "conflicts": 0,
            "events": defaultdict(int),
        }

        for rec in records:
            ts = rec.get("ts")
            if stats["start"] is None:
                stats["start"] = ts
            stats["end"] = ts

            level = rec.get("level", "")
            stats["events"][level] += 1

            if rec.get("event", "").startswith("unchanged"):
                stats["skipped"] += 1
            elif rec.get("event", "").startswith("exported"):
                stats["exported"] += 1
            elif rec.get("event", "").startswith("asset"):
                stats["assets"] += 1
            elif level == "ERROR":
                stats["errors"] += 1
            elif level == "WARN":
                stats["conflicts"] += 1

        if stats["start"] and stats["end"]:
            start_dt = datetime.fromisoformat(stats["start"])
            end_dt = datetime.fromisoformat(stats["end"])
            stats["duration_seconds"] = int((end_dt - start_dt).total_seconds())

        return stats

    def all_sessions(self) -> list[dict]:
        """List all sessions with summary."""
        sessions = []
        logs = sorted(self.log_dir.glob("sync_*.jsonl"))
        for log_file in logs[-10:]:  # Last 10
            session_id = log_file.stem.replace("sync_", "")
            summary = self.session_summary(session_id)
            sessions.append(summary)
        return sessions

    def print_summary(self, session_id: str | None = None) -> None:
        """Pretty print session summary."""
        if session_id is None:
            session_id = self.latest_session()
        if session_id is None:
            print("No sessions found.")
            return

        summary = self.session_summary(session_id)
        print(f"\n═══ MT Sync Engine — Session {session_id} ═══\n")
        print(f"Start:      {summary['start']}")
        print(f"End:        {summary['end']}")
        print(f"Duration:   {summary['duration_seconds']}s\n")
        print(f"Scanned:    {summary['scanned']}")
        print(f"Exported:   {summary['exported']}")
        print(f"Skipped:    {summary['skipped']}")
        print(f"Assets:     {summary['assets']}")
        print(f"Errors:     {summary['errors']}")
        print(f"Conflicts:  {summary['conflicts']}\n")
        print(f"Events: {dict(summary['events'])}\n")

    def print_timeline(self, session_id: str | None = None) -> None:
        """Print detailed event timeline."""
        if session_id is None:
            session_id = self.latest_session()
        if session_id is None:
            print("No sessions found.")
            return

        records = self.read_session(session_id)
        print(f"\n═══ Timeline — {session_id} ═══\n")
        for rec in records:
            level = rec.get("level", "?")
            ts = rec.get("ts", "").split("T")[1][:8] if rec.get("ts") else "?"
            event = rec.get("event", "")
            color = {"OK": "\033[32m", "SKIP": "\033[90m", "ERROR": "\033[31m", "WARN": "\033[33m"}.get(level, "\033[0m")
            print(f"{color}[{ts}] {level:5} {event}\033[0m")
        print()

    def print_all_sessions(self) -> None:
        """Print table of all sessions."""
        sessions = self.all_sessions()
        print("\n═══ Recent Sessions ═══\n")
        print(f"{'Session':<10} {'Duration':>8} {'Exported':>8} {'Errors':>6}")
        print("─" * 36)
        for s in sessions:
            print(f"{s['session_id']:<10} {s['duration_seconds']:>7}s {s['exported']:>8} {s['errors']:>6}")
        print()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="MT Sync Engine Dashboard")
    parser.add_argument("--log-dir", default="mt_sync_logs", help="Log directory")
    parser.add_argument("--session", help="Session ID (default: latest)")
    parser.add_argument("--timeline", action="store_true", help="Show event timeline")
    parser.add_argument("--all", action="store_true", help="Show all sessions")

    args = parser.parse_args()
    dashboard = SyncDashboard(args.log_dir)

    if args.all:
        dashboard.print_all_sessions()
    elif args.timeline:
        dashboard.print_timeline(args.session)
    else:
        dashboard.print_summary(args.session)

    return 0


if __name__ == "__main__":
    sys.exit(main())
