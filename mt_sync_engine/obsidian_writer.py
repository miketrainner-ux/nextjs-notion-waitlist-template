"""
MT Sync Engine — Obsidian Vault Writer
Writes .md files, manages folder structure, creates backlinks. Pure code.
"""
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


class ObsidianWriter:
    def __init__(self, vault_path: str):
        self.vault = Path(vault_path)
        self.vault.mkdir(parents=True, exist_ok=True)

    def create_structure(self, folders: list[str]) -> None:
        """Create predefined folder structure (taxonomy frozen)."""
        for folder in folders:
            (self.vault / folder).mkdir(parents=True, exist_ok=True)

    def write_page(
        self, title: str, content: str, folder: str, notion_id: str,
        tags: list[str] | None = None, links: list[str] | None = None,
        metadata: dict | None = None
    ) -> Path:
        """Write a .md file with metadata frontmatter."""
        folder_path = self.vault / folder
        folder_path.mkdir(parents=True, exist_ok=True)

        filename = self._sanitize_filename(title)
        file_path = folder_path / f"{filename}.md"

        frontmatter = {
            "notion_id": notion_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tags": tags or [],
            "links": links or [],
        }
        if metadata:
            frontmatter.update(metadata)

        fm_str = self._render_frontmatter(frontmatter)
        body = self._clean_content(content)
        backlinks = self._render_backlinks(links) if links else ""

        full_content = f"{fm_str}\n\n{body}\n\n{backlinks}".strip() + "\n"

        file_path.write_text(full_content, encoding="utf-8")
        return file_path

    def _sanitize_filename(self, title: str) -> str:
        """Remove invalid filename characters."""
        s = re.sub(r'[<>:"|?*]', '', title)
        s = re.sub(r'\s+', ' ', s).strip()
        return s or "untitled"

    def _clean_content(self, content: str) -> str:
        """Basic markdown cleanup."""
        lines = content.split("\n")
        cleaned = []
        for line in lines:
            line = line.rstrip()
            if line or cleaned:
                cleaned.append(line)
        return "\n".join(cleaned).strip()

    def _render_frontmatter(self, data: dict) -> str:
        """YAML frontmatter."""
        lines = ["---"]
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            elif isinstance(v, str):
                lines.append(f'{k}: "{v}"')
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        return "\n".join(lines)

    def _render_backlinks(self, links: list[str]) -> str:
        """Generate backlinks section."""
        if not links:
            return ""
        return "## Related\n\n" + "\n".join(f"- [[{link}]]" for link in links)

    def download_asset(
        self, url: str, filename: str, content: bytes,
        subfolder: str = "_attachments"
    ) -> Path:
        """Download and store asset (PDF, image, etc)."""
        asset_dir = self.vault / subfolder
        asset_dir.mkdir(parents=True, exist_ok=True)

        file_path = asset_dir / filename
        file_path.write_bytes(content)
        return file_path

    def create_moc(self, title: str, folder: str, entries: list[tuple[str, str]]) -> Path:
        """Create Map of Contents from entries (title, link)."""
        content = f"# {title}\n\n"
        for entry_title, link in entries:
            content += f"- [[{link}|{entry_title}]]\n"
        return self.write_page(title, content, folder, notion_id="moc")

    def create_graph_json(self, relations: list[dict]) -> Path:
        """Write obsidian graph data (nodes/edges for visualization)."""
        graph = {
            "nodes": [],
            "links": []
        }
        seen = set()
        for rel in relations:
            if rel["from"] not in seen:
                graph["nodes"].append({"id": rel["from"], "label": rel.get("from_title", rel["from"])})
                seen.add(rel["from"])
            if rel["to"] not in seen:
                graph["nodes"].append({"id": rel["to"], "label": rel.get("to_title", rel["to"])})
                seen.add(rel["to"])
            graph["links"].append({"source": rel["from"], "target": rel["to"], "type": rel.get("type", "links")})

        import json
        graph_path = self.vault / ".obsidian" / "graph.json"
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        return graph_path

    def snapshot(self, backup_dir: str) -> Path:
        """Create backup snapshot of entire vault."""
        from datetime import datetime
        import shutil
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(backup_dir) / f"vault_backup_{ts}"
        shutil.copytree(self.vault, backup_path, dirs_exist_ok=True)
        return backup_path
