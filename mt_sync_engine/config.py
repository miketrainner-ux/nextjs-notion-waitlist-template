"""
MT Sync Engine — Configuration
Loads from environment variables or mt_sync.yaml (local override).
Zero AI involvement in config resolution.
"""
import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # Notion
    notion_token: str = ""
    notion_root_page_id: str = ""  # optional: scope to subtree

    # Obsidian
    obsidian_vault_path: str = ""
    obsidian_attachments_dir: str = "_attachments"

    # Engine
    index_db_path: str = "mt_sync_index.db"
    log_dir: str = "mt_sync_logs"
    backup_dir: str = "mt_sync_backups"
    batch_size: int = 50          # pages processed per run segment
    max_retries: int = 3
    request_delay_ms: int = 333   # ~3 req/s, within Notion rate limits

    # Sync behaviour
    dry_run: bool = False         # simulate without writing
    full_rebuild: bool = False    # ignore index, re-export everything
    download_assets: bool = True  # copy PDFs, images, attachments

    # Taxonomy — frozen after first init
    taxonomy_locked: bool = True  # prevent auto-creation of new folders


_CONFIG: Config | None = None


def load_config(config_file: str = "mt_sync.yaml") -> Config:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    cfg = Config()

    # 1. Load YAML file if present
    cfg_path = Path(config_file)
    if cfg_path.exists():
        with open(cfg_path) as f:
            data = yaml.safe_load(f) or {}
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)

    # 2. Environment variables override YAML
    env_map = {
        "NOTION_TOKEN": "notion_token",
        "NOTION_ROOT_PAGE_ID": "notion_root_page_id",
        "OBSIDIAN_VAULT_PATH": "obsidian_vault_path",
        "MT_SYNC_INDEX_DB": "index_db_path",
        "MT_SYNC_LOG_DIR": "log_dir",
        "MT_SYNC_BACKUP_DIR": "backup_dir",
        "MT_SYNC_DRY_RUN": "dry_run",
        "MT_SYNC_FULL_REBUILD": "full_rebuild",
        "MT_SYNC_DOWNLOAD_ASSETS": "download_assets",
        "MT_SYNC_BATCH_SIZE": "batch_size",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            field_type = type(getattr(cfg, cfg_key))
            if field_type == bool:
                setattr(cfg, cfg_key, val.lower() in ("1", "true", "yes"))
            elif field_type == int:
                setattr(cfg, cfg_key, int(val))
            else:
                setattr(cfg, cfg_key, val)

    _CONFIG = cfg
    return cfg
