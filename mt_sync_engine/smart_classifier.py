"""
MT.OS Smart Classifier
Deterministic classification with priority:
1. Keywords in filename
2. Current path context
3. File metadata (extension, size, mime)
4. Fallback to review
"""
import re
from typing import Tuple
from .architecture import Domain, Confidence


class SmartClassifier:
    """Multi-level deterministic classifier."""

    # Priority 1: Keywords that override extension
    KEYWORD_RULES = {
        # Contracts
        r"(contrato|contract|agreement|nda|term)": {
            "domain": Domain.EMPRESA,
            "subdomain": "Contratos",
            "confidence": 0.98,
        },
        # Invoices
        r"(nota.?fiscal|invoice|receipt|fatura)": {
            "domain": Domain.EMPRESA,
            "subdomain": "Financeiro",
            "confidence": 0.99,
        },
        # Research papers
        r"(paper|research|estudo|artigo|thesis)": {
            "domain": Domain.CONHECIMENTO,
            "subdomain": "Pesquisas",
            "confidence": 0.92,
        },
        # Books
        r"(livro|book|ebook|pdf.*book|manual|apostila)": {
            "domain": Domain.CONHECIMENTO,
            "subdomain": "Livros",
            "confidence": 0.90,
        },
        # Certifications
        r"(certificad|certific|diploma|badge)": {
            "domain": Domain.PESSOAL,
            "subdomain": "Certificados",
            "confidence": 0.95,
        },
        # Videos
        r"(video|vídeo|filmagem|recording|footage)": {
            "domain": Domain.MIDIA,
            "subdomain": "Vídeos",
            "confidence": 0.95,
        },
        # Photos
        r"(foto|photo|image|imagem|screenshot|screenshot|captura)": {
            "domain": Domain.MIDIA,
            "subdomain": "Fotos",
            "confidence": 0.93,
        },
        # Audio
        r"(áudio|audio|podcast|voice|recording|mp3|wav)": {
            "domain": Domain.MIDIA,
            "subdomain": "Áudios",
            "confidence": 0.94,
        },
        # Presentations
        r"(apresentação|presentation|slide|ppt|deck)": {
            "domain": Domain.CONTEUDO,
            "subdomain": "Apresentações",
            "confidence": 0.92,
        },
        # Content creation
        r"(artigo|article|post|reels|stories|instagram|youtube|tiktok)": {
            "domain": Domain.CONTEUDO,
            "subdomain": "Redes Sociais",
            "confidence": 0.85,
        },
    }

    # Priority 2: Path context
    PATH_RULES = {
        r"(cliente|client|person)": {
            "domain": Domain.PESSOAS,
            "confidence": 0.85,
        },
        r"(projeto|project)": {
            "domain": Domain.PROJETOS,
            "confidence": 0.80,
        },
        r"(conhecimento|knowledge|study)": {
            "domain": Domain.CONHECIMENTO,
            "confidence": 0.80,
        },
        r"(financeiro|finance|accounting)": {
            "domain": Domain.EMPRESA,
            "confidence": 0.88,
        },
    }

    # Priority 3: Extension fallback (weak)
    EXTENSION_RULES = {
        "pdf": (Domain.CONHECIMENTO, "Pesquisas", 0.70),
        "docx": (Domain.CONTEUDO, "Documentos", 0.65),
        "doc": (Domain.CONTEUDO, "Documentos", 0.65),
        "xlsx": (Domain.EMPRESA, "Financeiro", 0.75),
        "xls": (Domain.EMPRESA, "Financeiro", 0.75),
        "pptx": (Domain.CONTEUDO, "Apresentações", 0.75),
        "mp4": (Domain.MIDIA, "Vídeos", 0.88),
        "mov": (Domain.MIDIA, "Vídeos", 0.88),
        "mkv": (Domain.MIDIA, "Vídeos", 0.88),
        "mp3": (Domain.MIDIA, "Áudios", 0.88),
        "wav": (Domain.MIDIA, "Áudios", 0.88),
        "jpg": (Domain.MIDIA, "Fotos", 0.88),
        "jpeg": (Domain.MIDIA, "Fotos", 0.88),
        "png": (Domain.MIDIA, "Fotos", 0.88),
        "gif": (Domain.MIDIA, "Fotos", 0.88),
        "zip": (Domain.ARQUIVO, "Backups", 0.70),
        "rar": (Domain.ARQUIVO, "Backups", 0.70),
        "7z": (Domain.ARQUIVO, "Backups", 0.70),
    }

    @staticmethod
    def classify(filename: str, current_path: str = "", file_size: int = 0,
                 mime_type: str = "") -> Tuple[Domain, str, float, list[str]]:
        """
        Classify file with priority order + confidence + keywords extracted.
        Returns: (domain, subdomain, confidence, keywords)
        """
        filename_lower = filename.lower()
        path_lower = current_path.lower()
        keywords = SmartClassifier._extract_keywords(filename_lower)

        # PRIORITY 1: Keywords in filename (strongest signal)
        for pattern, rule in SmartClassifier.KEYWORD_RULES.items():
            if re.search(pattern, filename_lower):
                return (
                    rule["domain"],
                    rule.get("subdomain", ""),
                    rule["confidence"],
                    keywords
                )

        # PRIORITY 2: Path context (context-aware)
        for pattern, rule in SmartClassifier.PATH_RULES.items():
            if re.search(pattern, path_lower):
                # Combine with extension if available
                ext = filename_lower.split(".")[-1] if "." in filename_lower else ""
                if ext in SmartClassifier.EXTENSION_RULES:
                    ext_domain, ext_sub, ext_conf = SmartClassifier.EXTENSION_RULES[ext]
                    if ext_domain == rule["domain"]:
                        return (rule["domain"], ext_sub, max(rule["confidence"], ext_conf), keywords)
                return (rule["domain"], "", rule["confidence"], keywords)

        # PRIORITY 3: Extension (weakest, but fast)
        ext = filename_lower.split(".")[-1] if "." in filename_lower else ""
        if ext in SmartClassifier.EXTENSION_RULES:
            domain, subdomain, confidence = SmartClassifier.EXTENSION_RULES[ext]
            return (domain, subdomain, confidence, keywords)

        # Fallback: Temp files / System files
        if SmartClassifier._is_temp(filename_lower):
            return (Domain.REVISAO, "Temporal", 0.99, keywords)

        # Last resort: Review
        return (Domain.REVISAO, "Sem_Categoria", 0.30, keywords)

    @staticmethod
    def _extract_keywords(filename: str) -> list[str]:
        """Extract meaningful keywords from filename."""
        # Remove extension
        name = filename.rsplit(".", 1)[0]
        # Split on common separators
        parts = re.split(r"[_\-\s\.]+", name)
        # Keep words > 3 chars
        keywords = [p for p in parts if len(p) > 3 and not p.isdigit()]
        return list(set(keywords))[:5]  # Max 5 unique

    @staticmethod
    def _is_temp(filename: str) -> bool:
        """Detect temporary files."""
        temp_patterns = [r"\.tmp$", r"~$", r"\.bak$", r"\.swp$", r"\.cache$"]
        return any(re.search(p, filename) for p in temp_patterns)

    @staticmethod
    def calculate_confidence_score(rules_matched: int, keyword_match: bool,
                                   path_context: bool, extension_match: bool) -> float:
        """Calculate composite confidence score."""
        score = 0.5  # Base score

        if keyword_match:
            score += 0.35  # Keywords are strongest signal
        if path_context:
            score += 0.20
        if extension_match:
            score += 0.15

        return min(score, 0.99)  # Cap at 0.99


class PilotValidator:
    """Validate classifier accuracy on small batch before mass execution."""

    def __init__(self, test_files: list[dict]):
        """
        test_files: [
            {"filename": "...", "path": "...", "expected_domain": Domain.CONHECIMENTO, "expected_subdomain": "Livros"},
            ...
        ]
        """
        self.test_files = test_files
        self.results = []

    def run(self) -> dict:
        """Classify all test files and measure accuracy."""
        for test in self.test_files:
            domain, subdomain, confidence, keywords = SmartClassifier.classify(
                test["filename"],
                test.get("path", ""),
                test.get("size", 0),
                test.get("mime", "")
            )

            match = (
                domain == test.get("expected_domain") and
                subdomain == test.get("expected_subdomain", "")
            )

            self.results.append({
                "filename": test["filename"],
                "expected": f"{test.get('expected_domain').value}/{test.get('expected_subdomain', '')}",
                "classified": f"{domain.value}/{subdomain}",
                "confidence": confidence,
                "correct": match,
                "keywords": keywords,
            })

        return self.summarize()

    def summarize(self) -> dict:
        """Accuracy report."""
        total = len(self.results)
        correct = sum(1 for r in self.results if r["correct"])
        accuracy = (correct / total * 100) if total > 0 else 0

        by_confidence = {
            "alta": len([r for r in self.results if r["confidence"] >= 0.95 and r["correct"]]),
            "media": len([r for r in self.results if 0.75 <= r["confidence"] < 0.95 and r["correct"]]),
            "baixa": len([r for r in self.results if r["confidence"] < 0.75]),
        }

        return {
            "total_tested": total,
            "correct": correct,
            "accuracy_pct": accuracy,
            "by_confidence": by_confidence,
            "results": self.results,
            "ready_for_production": accuracy >= 90.0,
        }
