"""
MT.OS Drive Organizer
Scan Drive, detect chaos, apply deterministic rules, suggest moves.
No destructive operations. Auditoria completa.
"""
from typing import Optional
import uuid
from .architecture import Domain, FileMetadata, DomainRules, Confidence, NamePattern
from .index import SyncIndex
from .logger import SyncLogger


class ChaosDetector:
    """Identify chaos patterns: empty folders, duplicates, inconsistencies."""

    @staticmethod
    def detect_empty_folders(folders: list[dict]) -> list[dict]:
        """Find folders with no children."""
        return [f for f in folders if f.get("children_count", 0) == 0]

    @staticmethod
    def detect_duplicate_names(files: list[dict]) -> list[tuple[str, list]]:
        """Find files with same name in different locations."""
        from collections import defaultdict
        by_name = defaultdict(list)
        for f in files:
            by_name[f["name"]].append(f)
        return [(name, files) for name, files in by_name.items() if len(files) > 1]

    @staticmethod
    def detect_inconsistent_names(files: list[dict]) -> list[dict]:
        """Find files not matching YYYY-MM-DD pattern."""
        return [f for f in files if not NamePattern.is_valid(f["name"])]

    @staticmethod
    def detect_wrong_extension(filename: str, domain: Domain) -> bool:
        """Check if extension matches domain."""
        ext = filename.split(".")[-1].lower()
        if domain == Domain.CONHECIMENTO and ext not in ("pdf", "epub", "txt"):
            return True
        if domain == Domain.MIDIA and ext not in ("mp4", "mp3", "jpg", "png", "mov"):
            return True
        return False

    @staticmethod
    def detect_temporary_files(filename: str) -> bool:
        """Identify temp files: .tmp, ~, .bak, etc."""
        temp_suffixes = (".tmp", ".bak", ".swp", "~", ".temp", ".cache")
        return filename.lower().endswith(temp_suffixes)


class DriveOrganizer:
    """Scan Drive, apply rules, generate move plan."""

    def __init__(self, index: SyncIndex, logger: SyncLogger):
        self.index = index
        self.logger = logger
        self.plan = []  # List of moves to execute
        self.conflicts = []  # Unresolvable issues

    def scan_drive(self, files: list[dict]) -> list[FileMetadata]:
        """Scan all files, assign metadata, build move plan."""
        metadatas = []
        detector = ChaosDetector()

        # Chaos detection
        empty_folders = detector.detect_empty_folders([f for f in files if f.get("mimeType") == "application/vnd.google-apps.folder"])
        duplicates = detector.detect_duplicate_names(files)
        inconsistent = detector.detect_inconsistent_names(files)

        self.logger.info("chaos_detection",
                        empty_folders=len(empty_folders),
                        duplicates=len(duplicates),
                        inconsistent_names=len(inconsistent))

        for file in files:
            try:
                meta = self._classify_file(file)
                metadatas.append(meta)
                self.index.upsert_page(
                    notion_id=meta.uuid,
                    title=meta.name,
                    vault_path=meta.full_path(),
                    content=b"",  # dummy for hash
                    notion_mod_time=meta.date_modified,
                    type_=meta.domain.value
                )
            except Exception as e:
                self.logger.error("classify_failed", filename=file.get("name"), error=str(e))

        return metadatas

    def _classify_file(self, file: dict) -> FileMetadata:
        """Single file classification with confidence scoring."""
        filename = file.get("name", "unknown")
        path = file.get("fullFileExtension", "")
        size = file.get("size", 0)
        mime = file.get("mimeType", "")

        # Parse filename
        parsed = NamePattern.parse(filename) if NamePattern.is_valid(filename) else {}

        # Classify
        domain, confidence = DomainRules.classify(filename, path, int(size or 0))
        subdomain = DomainRules.recommend_subdomain(domain, filename, path)

        meta = FileMetadata(
            uuid=str(uuid.uuid4()),
            name=filename,
            ext=filename.split(".")[-1].lower() if "." in filename else "",
            domain=domain,
            subdomain=subdomain,
            project=parsed.get("project_or_subject"),
            date_created=file.get("createdTime", ""),
            date_modified=file.get("modifiedTime", ""),
            content_hash=file.get("md5Checksum", ""),
            size_bytes=int(size or 0),
            mime_type=mime,
            confidence=confidence,
            origin="google_drive",
            destination="google_drive",
        )

        # Flag issues
        if not NamePattern.is_valid(filename):
            meta.status = "review"
            meta.notes = "Filename doesn't match pattern YYYY-MM-DD_Subject.ext"
            self.logger.info("bad_filename", filename=filename)

        if ChaosDetector.detect_temporary_files(filename):
            meta.status = "review"
            meta.notes = "Temporary file detected"

        if confidence == Confidence.NENHUMA:
            meta.status = "review"
            self.logger.conflict(f"Cannot classify: {filename}", domain="unknown")

        return meta

    def generate_move_plan(self, metadatas: list[FileMetadata]) -> list[dict]:
        """Generate moves without executing."""
        plan = []
        for meta in metadatas:
            if meta.status != "active":
                continue  # Skip files needing review

            # Current path (dummy Drive ID)
            current_path = f"/root/{meta.name}"
            target_path = f"/root/{meta.full_path()}/{meta.filename()}"

            if current_path != target_path:
                plan.append({
                    "uuid": meta.uuid,
                    "name": meta.name,
                    "current": current_path,
                    "target": target_path,
                    "domain": meta.domain.value,
                    "confidence": meta.confidence.name,
                    "reason": "Organizational standard",
                })

        self.plan = plan
        return plan

    def group_by_confidence(self) -> dict:
        """Group moves by confidence for batched execution."""
        groups = {
            "ALTA": [],
            "MEDIA": [],
            "BAIXA": [],
            "REVISAO": [],
        }
        for move in self.plan:
            groups[move["confidence"]].append(move)
        return groups

    def rename_to_standard(self, metadatas: list[FileMetadata]) -> list[dict]:
        """Plan filename standardization without executing."""
        renames = []
        for meta in metadatas:
            if NamePattern.is_valid(meta.name):
                continue  # Already valid

            standard_name = meta.filename()
            renames.append({
                "uuid": meta.uuid,
                "current": meta.name,
                "standard": standard_name,
                "reason": "Standardization: YYYY-MM-DD_Project_Subject_V01.ext",
            })
        return renames

    def consolidate_duplicates(self, duplicates: list[tuple[str, list]]) -> list[dict]:
        """Detect and flag duplicate files."""
        consolidations = []
        for filename, files in duplicates:
            if len(files) > 1:
                consolidations.append({
                    "filename": filename,
                    "count": len(files),
                    "files": files,
                    "action": "REVIEW",  # Manual dedup
                    "reason": "Multiple files with same name",
                })
                self.logger.conflict(f"Duplicate: {filename}", count=len(files))
        return consolidations

    def summary(self) -> dict:
        """Summary of org plan."""
        grouped = self.group_by_confidence()
        return {
            "total_moves": len(self.plan),
            "by_confidence": {k: len(v) for k, v in grouped.items()},
            "conflicts": len(self.conflicts),
            "plan": self.plan,
        }
