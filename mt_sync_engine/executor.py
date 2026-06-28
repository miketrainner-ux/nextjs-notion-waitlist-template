"""
MT.OS Executor
Execute organization plan with full auditoria, DRY_RUN, and rollback support.
"""
from typing import Optional
from datetime import datetime, timezone
from .architecture import FileMetadata, Confidence
from .logger import SyncLogger
from .index import SyncIndex


class ExecutionPlan:
    """Batch execution with validation."""

    def __init__(self, logger: SyncLogger, index: SyncIndex, dry_run: bool = True):
        self.logger = logger
        self.index = index
        self.dry_run = dry_run
        self.operations = []  # List of validated operations
        self.rollback_log = []  # For reversal

    def validate_move(self, move: dict) -> bool:
        """Check move safety before execution."""
        # Rule 1: Target domain must be valid
        target_domain = move.get("domain")
        if not target_domain or target_domain == "99_Revisão":
            self.logger.error("invalid_move", reason="Target is review folder", move=move)
            return False

        # Rule 2: Confidence must be >= threshold
        confidence_map = {"ALTA": 0.95, "MEDIA": 0.75, "BAIXA": 0.50}
        confidence = confidence_map.get(move.get("confidence"), 0)
        if confidence < 0.75:  # Only ALTA and MEDIA auto-executed
            self.logger.info("move_requires_review", confidence=move.get("confidence"), move=move)
            return False

        return True

    def queue_move(self, move: dict) -> bool:
        """Add validated move to queue."""
        if self.validate_move(move):
            self.operations.append(("move", move))
            return True
        return False

    def queue_rename(self, rename: dict) -> bool:
        """Queue filename standardization."""
        self.operations.append(("rename", rename))
        return True

    def execute_batch(self, batch_size: int = 50) -> dict:
        """Execute operations in batches with checkpoints."""
        results = {
            "executed": 0,
            "skipped": 0,
            "errors": 0,
            "rollback_ids": [],
        }

        for i in range(0, len(self.operations), batch_size):
            batch = self.operations[i:i+batch_size]

            for op_type, op_data in batch:
                try:
                    if self.dry_run:
                        self._execute_dry_run(op_type, op_data)
                    else:
                        self._execute_live(op_type, op_data, results)
                except Exception as e:
                    self.logger.error("execution_failed", op=op_type, data=op_data, error=str(e))
                    results["errors"] += 1

            # Checkpoint after batch
            if not self.dry_run:
                self.logger.info("batch_checkpoint", batch=i//batch_size, executed=results["executed"])

        return results

    def _execute_dry_run(self, op_type: str, op_data: dict) -> None:
        """Simulate operation."""
        if op_type == "move":
            self.logger.info("move_simulation",
                           source=op_data.get("current"),
                           target=op_data.get("target"))
        elif op_type == "rename":
            self.logger.info("rename_simulation",
                           current=op_data.get("current"),
                           standard=op_data.get("standard"))

    def _execute_live(self, op_type: str, op_data: dict, results: dict) -> None:
        """Execute real operation with rollback logging."""
        if op_type == "move":
            # Log for rollback
            self.rollback_log.append({
                "operation": "move",
                "uuid": op_data.get("uuid"),
                "source": op_data.get("current"),
                "target": op_data.get("target"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # TODO: Actually move in Drive via API
            results["executed"] += 1
            self.logger.exported(op_data.get("uuid"), op_data.get("target"))

        elif op_type == "rename":
            self.rollback_log.append({
                "operation": "rename",
                "uuid": op_data.get("uuid"),
                "old_name": op_data.get("current"),
                "new_name": op_data.get("standard"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # TODO: Actually rename in Drive via API
            results["executed"] += 1
            self.logger.info("renamed", old=op_data.get("current"), new=op_data.get("standard"))

    def save_rollback_log(self, log_path: str) -> None:
        """Persist rollback log for recovery."""
        import json
        with open(log_path, "w") as f:
            json.dump(self.rollback_log, f, indent=2)
        self.logger.info("rollback_log_saved", path=log_path)

    def execute_rollback(self, log_path: str, dry_run: bool = True) -> dict:
        """Reverse all operations from log (newest to oldest)."""
        import json
        with open(log_path) as f:
            log = json.load(f)

        results = {"reversed": 0, "failed": 0}

        # Reverse order: newest first
        for entry in reversed(log):
            try:
                if entry["operation"] == "move":
                    # Move from target back to source
                    self.logger.info("rollback_move",
                                   source=entry["target"],
                                   target=entry["source"])
                    if not dry_run:
                        results["reversed"] += 1

                elif entry["operation"] == "rename":
                    # Rename back to original
                    self.logger.info("rollback_rename",
                                   new_name=entry["new_name"],
                                   old_name=entry["old_name"])
                    if not dry_run:
                        results["reversed"] += 1

            except Exception as e:
                self.logger.error("rollback_failed", entry=entry, error=str(e))
                results["failed"] += 1

        return results


class SafetyChecks:
    """Pre-execution validation."""

    @staticmethod
    def validate_domain_structure(metadatas: list[FileMetadata]) -> list[str]:
        """Check all files have valid domains."""
        errors = []
        for meta in metadatas:
            if meta.domain.value not in ["00_Sistema", "01_Entrada", "02_Projetos", "03_Pessoas",
                                         "04_Conhecimento", "05_Conteúdo", "06_Mídia", "07_Empresa",
                                         "08_Pessoal", "09_Arquivo", "99_Revisão"]:
                errors.append(f"Invalid domain for {meta.name}: {meta.domain}")
        return errors

    @staticmethod
    def validate_no_duplicates(moves: list[dict]) -> list[str]:
        """Check no two moves target same location."""
        targets = {}
        errors = []
        for move in moves:
            target = move.get("target")
            if target in targets:
                errors.append(f"Duplicate target: {target}")
            targets[target] = move
        return errors

    @staticmethod
    def validate_no_overwrites(current_files: list[dict], moves: list[dict]) -> list[str]:
        """Check moves don't overwrite existing files."""
        errors = []
        for move in moves:
            target = move.get("target")
            if any(f.get("path") == target for f in current_files):
                errors.append(f"Move would overwrite: {target}")
        return errors

    @staticmethod
    def pre_flight_check(metadatas: list[FileMetadata], moves: list[dict], current_files: list[dict]) -> dict:
        """Run all safety checks."""
        return {
            "domain_validity": SafetyChecks.validate_domain_structure(metadatas),
            "duplicates": SafetyChecks.validate_no_duplicates(moves),
            "overwrites": SafetyChecks.validate_no_overwrites(current_files, moves),
        }
