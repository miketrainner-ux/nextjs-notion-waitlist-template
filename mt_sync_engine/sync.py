"""
MT Sync Engine — Orchestration
Main sync loop: scan → compare → export → write → backup → log.
"""
import uuid
from typing import Optional
from .config import Config
from .index import SyncIndex
from .logger import SyncLogger
from .notion_client import NotionClient
from .obsidian_writer import ObsidianWriter


class MTSyncEngine:
    def __init__(self, config: Config):
        self.cfg = config
        self.session_id = str(uuid.uuid4())[:8]
        self.logger = SyncLogger(config.log_dir, self.session_id)
        self.index = SyncIndex(config.index_db_path)
        self.notion = NotionClient(config.notion_token, config.request_delay_ms)
        self.obsidian = ObsidianWriter(config.obsidian_vault_path)
        self.logger.info("engine_initialized", session=self.session_id)

    def run(self) -> dict:
        """Full sync cycle."""
        self.logger.info("sync_start")
        try:
            # 1. Snapshot before any changes
            snapshot = self.obsidian.snapshot(self.cfg.backup_dir)
            self.logger.info("snapshot_created", path=str(snapshot))

            # 2. Scan Notion (all pages)
            pages = self._scan_notion()
            self.logger.info("notion_scan_complete", pages_found=len(pages))

            # 3. Compare with index (determine what changed)
            to_export = self._compare_with_index(pages)
            self.logger.info("comparison_complete", changes=len(to_export))

            # 4. Export from Notion → Markdown
            exports = self._export_pages(to_export)
            self.logger.info("export_complete", exported=len(exports))

            # 5. Write to Obsidian
            writes = self._write_to_obsidian(exports)
            self.logger.info("obsidian_write_complete", files=len(writes))

            # 6. Summary
            return self.logger.summary()

        except Exception as e:
            self.logger.error("sync_failed", error=str(e))
            raise
        finally:
            self.index.close()
            self.notion.close()

    def _scan_notion(self) -> list[dict]:
        """List all pages from Notion (root or scoped)."""
        pages = []
        try:
            all_pages = self.notion.list_all_pages(self.cfg.notion_root_page_id)
            for page in all_pages:
                try:
                    full = self.notion.get_page(page["id"])
                    pages.append(full)
                except Exception as e:
                    self.logger.error("page_fetch_failed", page_id=page["id"], error=str(e))
            return pages
        except Exception as e:
            self.logger.error("scan_notion_failed", error=str(e))
            return []

    def _compare_with_index(self, pages: list[dict]) -> list[dict]:
        """Determine which pages need export (hash/timestamp comparison)."""
        to_export = []
        for page in pages:
            notion_id = page["id"]
            title = self._extract_title(page)
            mod_time = page.get("last_edited_time", "")
            content_bytes = self._serialize_page(page)

            if self.cfg.full_rebuild or self.index.needs_update(notion_id, self.index._hash(content_bytes), mod_time):
                to_export.append(page)
            else:
                self.logger.skip(notion_id, title)

        return to_export

    def _export_pages(self, pages: list[dict]) -> list[dict]:
        """Convert Notion pages to markdown + metadata."""
        exports = []
        for page in pages:
            try:
                children = self._fetch_block_children(page["id"])
                content = self._render_markdown(children)
                exports.append({
                    "notion_id": page["id"],
                    "title": self._extract_title(page),
                    "content": content,
                    "mod_time": page.get("last_edited_time", ""),
                    "parent_id": page.get("parent", {}).get("page_id"),
                    "properties": page.get("properties", {}),
                })
            except Exception as e:
                self.logger.error("export_failed", page_id=page["id"], error=str(e))

        return exports

    def _write_to_obsidian(self, exports: list[dict]) -> list[str]:
        """Write exported pages to Obsidian vault."""
        if self.cfg.dry_run:
            self.logger.info("dry_run_enabled")
            return [e["notion_id"] for e in exports]

        writes = []
        for exp in exports:
            try:
                folder = self._determine_folder(exp)
                path = self.obsidian.write_page(
                    title=exp["title"],
                    content=exp["content"],
                    folder=folder,
                    notion_id=exp["notion_id"],
                    metadata={"parent_id": exp["parent_id"]} if exp["parent_id"] else None
                )
                self.index.upsert_page(
                    notion_id=exp["notion_id"],
                    title=exp["title"],
                    vault_path=str(path.relative_to(self.obsidian.vault)),
                    content=exp["content"].encode("utf-8"),
                    notion_mod_time=exp["mod_time"],
                    parent_id=exp["parent_id"]
                )
                self.logger.exported(exp["notion_id"], str(path))
                writes.append(str(path))
            except Exception as e:
                self.logger.error("write_failed", page=exp["title"], error=str(e))

        return writes

    def _fetch_block_children(self, block_id: str) -> list[dict]:
        """Recursively fetch all child blocks."""
        children = []
        cursor = None
        while True:
            data = self.notion.get_block_children(block_id, start_cursor=cursor)
            for child in data.get("results", []):
                children.append(child)
                if child.get("has_children"):
                    children.extend(self._fetch_block_children(child["id"]))
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return children

    def _render_markdown(self, blocks: list[dict]) -> str:
        """Convert Notion blocks to markdown."""
        md_lines = []
        for block in blocks:
            md_lines.append(self._block_to_markdown(block))
        return "\n\n".join(filter(None, md_lines))

    def _block_to_markdown(self, block: dict) -> str:
        """Single block → markdown (deterministic, no IA)."""
        t = block.get("type")
        content = block.get(t, {})

        if t == "heading_1":
            return f"# {self._get_rich_text(content)}"
        elif t == "heading_2":
            return f"## {self._get_rich_text(content)}"
        elif t == "heading_3":
            return f"### {self._get_rich_text(content)}"
        elif t in ("paragraph", "bulleted_list_item", "numbered_list_item", "quote"):
            text = self._get_rich_text(content)
            if t == "bulleted_list_item":
                return f"- {text}"
            elif t == "numbered_list_item":
                return f"1. {text}"
            elif t == "quote":
                return f"> {text}"
            return text
        elif t == "code":
            lang = content.get("language", "")
            code = self._get_rich_text(content)
            return f"```{lang}\n{code}\n```"
        elif t == "image":
            url = content.get("external", {}).get("url") or content.get("file", {}).get("url", "")
            return f"![image]({url})"
        elif t == "file":
            url = content.get("external", {}).get("url") or content.get("file", {}).get("url", "")
            return f"[attachment]({url})"
        elif t == "table":
            return "[table content]"
        elif t == "divider":
            return "---"
        elif t == "table_of_contents":
            return "[TOC]"
        else:
            return ""

    def _get_rich_text(self, content: dict) -> str:
        """Extract plaintext from rich_text array."""
        parts = []
        for rt in content.get("rich_text", []):
            text = rt.get("plain_text", "")
            # Markdown formatting from annotations
            annot = rt.get("annotations", {})
            if annot.get("bold"):
                text = f"**{text}**"
            if annot.get("italic"):
                text = f"*{text}*"
            if annot.get("code"):
                text = f"`{text}`"
            if annot.get("strikethrough"):
                text = f"~~{text}~~"
            parts.append(text)
        return "".join(parts)

    def _extract_title(self, page: dict) -> str:
        """Get page title from properties."""
        props = page.get("properties", {})
        for prop_name, prop_value in props.items():
            if prop_value.get("type") == "title":
                return prop_value.get("title", [{}])[0].get("plain_text", "Untitled")
        return "Untitled"

    def _determine_folder(self, page_export: dict) -> str:
        """Map page to vault folder (taxonomy frozen)."""
        # TODO: implement taxonomy mapping based on properties/parent
        return "Pages"

    def _serialize_page(self, page: dict) -> bytes:
        """Serialize page to bytes for hashing."""
        import json
        return json.dumps(page, sort_keys=True, default=str).encode("utf-8")
