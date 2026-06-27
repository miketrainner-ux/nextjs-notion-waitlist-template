#!/usr/bin/env python3
"""
MT Sync Engine — CLI
Usage: python -m mt_sync_engine.main [--config mt_sync.yaml] [--dry-run] [--full-rebuild]
"""
import sys
import argparse
import json
from pathlib import Path
from .config import load_config, Config
from .sync import MTSyncEngine


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MT Sync Engine: Notion → Obsidian incremental sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", default="mt_sync.yaml",
        help="Config file (YAML). Env vars override."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate without writing."
    )
    parser.add_argument(
        "--full-rebuild", action="store_true",
        help="Ignore index, re-export everything."
    )
    parser.add_argument(
        "--no-assets", action="store_true",
        help="Skip asset download (PDF, images)."
    )

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    if args.dry_run:
        config.dry_run = True
    if args.full_rebuild:
        config.full_rebuild = True
    if args.no_assets:
        config.download_assets = False

    # Validate
    if not config.notion_token:
        print("ERROR: NOTION_TOKEN not set. Set env var or in config file.", file=sys.stderr)
        return 1
    if not config.obsidian_vault_path:
        print("ERROR: OBSIDIAN_VAULT_PATH not set.", file=sys.stderr)
        return 1

    # Run
    try:
        engine = MTSyncEngine(config)
        result = engine.run()
        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
