"""
MT Sync Engine — Notion API Client
Wrapper around Notion API. No IA. Just API calls.
"""
import requests
import time
from typing import Any
from urllib.parse import urljoin


class NotionClient:
    BASE_URL = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"

    def __init__(self, token: str, delay_ms: int = 333):
        self.token = token
        self.delay_ms = delay_ms / 1000.0
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Notion-Version": self.API_VERSION,
            "Content-Type": "application/json",
        })

    def _rate_limit(self) -> None:
        time.sleep(self.delay_ms)

    def _req(self, method: str, path: str, **kwargs: Any) -> dict:
        url = urljoin(self.BASE_URL, path)
        self._rate_limit()
        resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_page(self, page_id: str) -> dict:
        return self._req("GET", f"/pages/{page_id}")

    def get_block_children(self, block_id: str, start_cursor: str | None = None) -> dict:
        params = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return self._req("GET", f"/blocks/{block_id}/children", params=params)

    def query_database(
        self, db_id: str, filter_: dict | None = None, sorts: list | None = None,
        start_cursor: str | None = None
    ) -> dict:
        payload = {}
        if filter_:
            payload["filter"] = filter_
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor
        return self._req("POST", f"/databases/{db_id}/query", json=payload)

    def search(self, query: str, sort_: dict | None = None) -> dict:
        payload = {"query": query}
        if sort_:
            payload["sort"] = sort_
        return self._req("POST", "/search", json=payload)

    def get_file_url(self, file_id: str) -> str:
        """Generate download URL for a Notion file (expiring 1h)."""
        return f"https://www.notion.so/api/v3/getFileTemporaryAccessUrl?fileId={file_id}"

    def list_all_pages(self, root_id: str | None = None) -> list[dict]:
        """Recursively list all pages under root_id (or entire workspace if None)."""
        if root_id:
            pages = self._list_children(root_id)
        else:
            results = self.search("")["results"]
            pages = [p for p in results if p["object"] == "page"]
        return pages

    def _list_children(self, parent_id: str) -> list[dict]:
        pages = []
        cursor = None
        while True:
            data = self.get_block_children(parent_id, start_cursor=cursor)
            for child in data.get("results", []):
                if child["type"] in ("child_page", "page"):
                    pages.append(child)
                    if child.get("has_children"):
                        pages.extend(self._list_children(child["id"]))
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return pages

    def get_block_content(self, block_id: str) -> str:
        """Extract plaintext from a block (supports rich_text, heading, paragraph, etc)."""
        block = self._req("GET", f"/blocks/{block_id}")
        return self._extract_text(block)

    def _extract_text(self, block: dict) -> str:
        """Deterministic text extraction from Notion block."""
        t = block.get("type")
        content = block.get(t, {})
        if "rich_text" in content:
            return "".join(rt["plain_text"] for rt in content["rich_text"])
        if "text" in content:
            return content["text"]
        if t == "image" and "external" in content:
            return content["external"]["url"]
        if t == "file" and "external" in content:
            return content["external"]["url"]
        return ""

    def close(self) -> None:
        self.session.close()
