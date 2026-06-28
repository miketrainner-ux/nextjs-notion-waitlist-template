#!/usr/bin/env python3
"""
MT.OS Architecture Engine v7.0 — CLI
Organize Google Drive, iCloud, Notion, Obsidian with unified structure.
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from .config import load_config, Config
from .index import SyncIndex
from .logger import SyncLogger
from .drive_organizer import DriveOrganizer, ChaosDetector
from .executor import ExecutionPlan, SafetyChecks
from .architecture import Domain


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MT.OS Architecture Engine v7.0: Unified organization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default="mt_sync.yaml", help="Config file")
    parser.add_argument("--scan", action="store_true", help="Scan and detect chaos")
    parser.add_argument("--plan", action="store_true", help="Generate org plan (no exec)")
    parser.add_argument("--execute", action="store_true", help="Execute moves + renames")
    parser.add_argument("--rollback", action="store_true", help="Reverse last execution")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for execution")
    parser.add_argument("--log-dir", default="mt_sync_logs", help="Log directory")
    parser.add_argument("--index-db", default="mt_sync_index.db", help="Index database")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = SyncLogger(args.log_dir, session_id)
    index = SyncIndex(args.index_db)

    try:
        if args.scan:
            return _cmd_scan(config, logger, index)
        elif args.plan:
            return _cmd_plan(config, logger, index)
        elif args.execute:
            return _cmd_execute(config, logger, index, args.dry_run, args.batch_size)
        elif args.rollback:
            return _cmd_rollback(config, logger, args.log_dir, args.dry_run)
        else:
            parser.print_help()
            return 1

    except Exception as e:
        logger.error("fatal", error=str(e))
        return 1
    finally:
        index.close()


def _cmd_scan(config: Config, logger: SyncLogger, index: SyncIndex) -> int:
    """Scan Drive/iCloud and detect chaos."""
    logger.info("scan_start")

    # TODO: Scan Drive via API
    files = []  # Placeholder

    organizer = DriveOrganizer(index, logger)
    metadatas = organizer.scan_drive(files)

    summary = {
        "scanned": len(metadatas),
        "by_domain": {},
        "chaos": {
            "empty_folders": 0,
            "duplicates": 0,
            "inconsistent_names": 0,
            "temporary_files": 0,
        }
    }

    # Count by domain
    for meta in metadatas:
        domain = meta.domain.value
        summary["by_domain"][domain] = summary["by_domain"].get(domain, 0) + 1

        # Chaos detection
        if ChaosDetector.detect_inconsistent_names([{"name": meta.name}]):
            summary["chaos"]["inconsistent_names"] += 1
        if ChaosDetector.detect_temporary_files(meta.name):
            summary["chaos"]["temporary_files"] += 1

    print(json.dumps(summary, indent=2))
    return 0


def _cmd_plan(config: Config, logger: SyncLogger, index: SyncIndex) -> int:
    """Generate organization plan without executing."""
    logger.info("plan_start")

    # TODO: Get files from Drive
    files = []

    organizer = DriveOrganizer(index, logger)
    metadatas = organizer.scan_drive(files)
    plan = organizer.generate_move_plan(metadatas)

    # Safety checks
    checks = SafetyChecks.pre_flight_check(metadatas, plan, files)
    if any(checks.values()):
        logger.error("safety_checks_failed", issues=checks)
        return 1

    summary = organizer.summary()
    summary["safety_checks"] = checks
    summary["timestamp"] = datetime.now().isoformat()

    print(json.dumps(summary, indent=2))
    return 0


def _cmd_execute(config: Config, logger: SyncLogger, index: SyncIndex,
                 dry_run: bool, batch_size: int) -> int:
    """Execute organization plan."""
    logger.info("execute_start", dry_run=dry_run, batch_size=batch_size)

    # TODO: Load plan from previous _cmd_plan output
    plan = []

    executor = ExecutionPlan(logger, index, dry_run=dry_run)
    for move in plan:
        executor.queue_move(move)

    results = executor.execute_batch(batch_size=batch_size)

    if not dry_run:
        rollback_path = Path("mt_sync_logs") / f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        executor.save_rollback_log(str(rollback_path))
        logger.info("execution_complete", results=results, rollback_log=str(rollback_path))

    print(json.dumps(results, indent=2))
    return 0


def _cmd_rollback(config: Config, logger: SyncLogger, log_dir: str, dry_run: bool) -> int:
    """Reverse organization operations."""
    logger.info("rollback_start", dry_run=dry_run)

    # Find latest rollback log
    logs = sorted(Path(log_dir).glob("rollback_*.json"))
    if not logs:
        logger.error("no_rollback_logs_found")
        return 1

    rollback_log = str(logs[-1])
    executor = ExecutionPlan(logger, None, dry_run=dry_run)
    results = executor.execute_rollback(rollback_log, dry_run=dry_run)

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
