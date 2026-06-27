"""
MT.OS Architecture Engine v7.0
Unified logical architecture across Google Drive, iCloud, Notion, Obsidian.
Index-driven with deterministic rules. IA only for exceptions (<10%).
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime, timezone


class Domain(Enum):
    """Frozen domains (11 only)."""
    SISTEMA = "00_Sistema"
    ENTRADA = "01_Entrada"
    PROJETOS = "02_Projetos"
    PESSOAS = "03_Pessoas"
    CONHECIMENTO = "04_Conhecimento"
    CONTEUDO = "05_Conteúdo"
    MIDIA = "06_Mídia"
    EMPRESA = "07_Empresa"
    PESSOAL = "08_Pessoal"
    ARQUIVO = "09_Arquivo"
    REVISAO = "99_Revisão"

    @staticmethod
    def all() -> list[str]:
        return [d.value for d in Domain]

    @staticmethod
    def is_valid(domain_code: str) -> bool:
        return domain_code in [d.value for d in Domain]


class Confidence(Enum):
    """Classification confidence levels."""
    ALTA = 0.95      # ≥95%: automated, no review
    MEDIA = 0.75     # 75-95%: automated, flagged for review
    BAIXA = 0.50     # 50-75%: human review required
    NENHUMA = 0.0    # <50%: send to 99_REVISAO


@dataclass
class FileMetadata:
    """Complete file metadata for indexing."""
    uuid: str
    name: str
    ext: str
    domain: Domain
    subdomain: str  # e.g., "Clientes/Ativos"
    project: Optional[str] = None
    person: Optional[str] = None
    origin: str = "google_drive"  # or "icloud", "notion", "obsidian"
    destination: str = "google_drive"
    content_hash: str = ""
    date_created: str = ""
    date_modified: str = ""
    version: str = "v01"
    status: str = "active"  # "active", "archived", "review", "duplicate", "error"
    tags: list[str] = None
    size_bytes: int = 0
    mime_type: str = ""
    confidence: Confidence = Confidence.ALTA
    notes: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def full_path(self) -> str:
        """Logical path: Domain/Subdomain/FileName."""
        subdomain_part = f"/{self.subdomain}" if self.subdomain else ""
        return f"{self.domain.value}{subdomain_part}/{self._sanitize_filename()}"

    def filename(self) -> str:
        """Standardized filename: YYYY-MM-DD_Project_Subject_V01.ext"""
        date_part = self.date_created.split("T")[0] if self.date_created else "0000-00-00"
        subject = self.name.replace(" ", "_")
        if self.project:
            return f"{date_part}_{self.project}_{subject}_{self.version}.{self.ext}"
        return f"{date_part}_{subject}_{self.version}.{self.ext}"

    def _sanitize_filename(self) -> str:
        """Remove invalid filename characters."""
        import re
        s = re.sub(r'[<>:"|?*]', '', self.name)
        return s.replace(" ", "_") or "untitled"

    def to_dict(self) -> dict:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "domain": self.domain.value,
            "subdomain": self.subdomain,
            "project": self.project,
            "person": self.person,
            "origin": self.origin,
            "destination": self.destination,
            "hash": self.content_hash,
            "created": self.date_created,
            "modified": self.date_modified,
            "version": self.version,
            "status": self.status,
            "tags": self.tags,
            "size": self.size_bytes,
            "mime": self.mime_type,
            "confidence": self.confidence.name,
            "notes": self.notes,
        }


class NamePattern:
    """Validate and parse filename patterns."""

    @staticmethod
    def pattern() -> str:
        """AAAA-MM-DD_Assunto.ext or AAAA-MM-DD_Projeto_Assunto_V01.ext"""
        return r"^\d{4}-\d{2}-\d{2}_.*\.[a-z0-9]+$"

    @staticmethod
    def is_valid(filename: str) -> bool:
        import re
        return bool(re.match(NamePattern.pattern(), filename.lower()))

    @staticmethod
    def parse(filename: str) -> dict:
        """Extract date, project, subject, version from filename."""
        import re
        match = re.match(
            r"^(\d{4}-\d{2}-\d{2})_([^_]+)(?:_(.+?))?(?:_V(\d+))?\.([a-z0-9]+)$",
            filename.lower()
        )
        if not match:
            return {}
        return {
            "date": match.group(1),
            "project_or_subject": match.group(2),
            "subject": match.group(3) or match.group(2),
            "version": match.group(4) or "01",
            "ext": match.group(5),
        }


class DomainRules:
    """Rule engine for file → domain classification."""

    # Extension → domain mapping
    EXTENSION_RULES = {
        "pdf": Domain.CONHECIMENTO,
        "docx": Domain.CONTEUDO,
        "xlsx": Domain.EMPRESA,
        "pptx": Domain.CONTEUDO,
        "mp4": Domain.MIDIA,
        "mov": Domain.MIDIA,
        "mp3": Domain.MIDIA,
        "wav": Domain.MIDIA,
        "jpg": Domain.MIDIA,
        "png": Domain.MIDIA,
        "zip": Domain.ARQUIVO,
        "tar": Domain.ARQUIVO,
    }

    # Path pattern → domain mapping
    PATH_RULES = {
        "client": Domain.PESSOAS,
        "contract": Domain.EMPRESA,
        "invoice": Domain.EMPRESA,
        "photo": Domain.MIDIA,
        "video": Domain.MIDIA,
        "research": Domain.CONHECIMENTO,
    }

    @staticmethod
    def classify(filename: str, path: str, size: int) -> tuple[Domain, Confidence]:
        """Deterministic classification without IA."""
        ext = filename.split(".")[-1].lower()

        # Rule 1: Extension-based (high confidence)
        if ext in DomainRules.EXTENSION_RULES:
            return DomainRules.EXTENSION_RULES[ext], Confidence.ALTA

        # Rule 2: Path-based keywords
        path_lower = path.lower()
        for keyword, domain in DomainRules.PATH_RULES.items():
            if keyword in path_lower:
                return domain, Confidence.MEDIA

        # Rule 3: Empty files → System
        if size == 0:
            return Domain.SISTEMA, Confidence.BAIXA

        # Rule 4: Very large files → Média or Arquivo
        if size > 100_000_000:  # >100MB
            return Domain.MIDIA, Confidence.MEDIA

        # Rule 5: Unknown → send to review
        return Domain.REVISAO, Confidence.NENHUMA

    @staticmethod
    def recommend_subdomain(domain: Domain, filename: str, path: str) -> str:
        """Suggest subdomain based on domain rules."""
        subdomains = {
            Domain.PROJETOS: ["MT.OS", "Michael Training", "Centro Esportivo"],
            Domain.PESSOAS: ["Documentos", "Fotos", "Vídeos", "Contratos"],
            Domain.CONHECIMENTO: ["Livros", "Papers", "Cursos", "Pesquisas"],
            Domain.CONTEUDO: ["Instagram", "YouTube", "Stories", "Podcast"],
            Domain.MIDIA: ["Fotos", "Vídeos", "Áudios", "Assets"],
            Domain.EMPRESA: ["Financeiro", "RH", "Contratos", "Clientes"],
        }
        if domain in subdomains:
            return subdomains[domain][0]  # Default to first
        return ""
