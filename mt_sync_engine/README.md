# MT Sync Engine

**Zero-token, deterministic Notion → Obsidian incremental sync.**

## Philosophy

- **Code first.** Algorithms resolve 95%+ of tasks without AI.
- **Incremental.** Compare by hash/timestamp; sync only changed pages.
- **Immutable.** Taxonomy frozen. No auto-creation. No IA-driven classification.
- **Preserving.** Nothing is discarded. Full cloning: pages, databases, assets, metadata.
- **Audited.** Every operation logged (JSON lines). Rollback snapshots taken before each sync.

## Architecture

```
Notion (API)
    ↓
[Client → Scan all pages]
    ↓
[Index (SQLite) → Compare hash/timestamp]
    ↓
[Sync Engine → Export to Markdown]
    ↓
[Obsidian Writer → Write .md + structure]
    ↓
[Backup snapshot]
    ↓
[Logs (JSONL)]
```

## Install

```bash
pip install -r mt_sync_engine/requirements.txt
```

## Configure

1. Copy `mt_sync_engine/mt_sync.yaml.example` → `mt_sync.yaml`
2. Set your values:
   ```yaml
   notion_token: "secret_..."
   obsidian_vault_path: "/path/to/vault"
   ```
3. Or use environment variables:
   ```bash
   export NOTION_TOKEN=secret_...
   export OBSIDIAN_VAULT_PATH=/path/to/vault
   ```

## Usage

### Dry run (no writes)
```bash
python -m mt_sync_engine.main --dry-run
```

### Full rebuild (ignore index)
```bash
python -m mt_sync_engine.main --full-rebuild
```

### Normal incremental sync
```bash
python -m mt_sync_engine.main
```

### Output
```json
{
  "session": "abc12345",
  "scanned": 145,
  "unchanged": 128,
  "exported": 17,
  "assets_downloaded": 5,
  "errors": 0,
  "conflicts": 0
}
```

## Modules

- **`config.py`** — Load YAML + env vars, typed config
- **`index.py`** — SQLite: track notion_id, hash, timestamp, vault_path
- **`logger.py`** — JSON lines to file + colored stderr
- **`notion_client.py`** — Notion API wrapper (no IA)
- **`obsidian_writer.py`** — Write .md, manage structure, create backlinks
- **`sync.py`** — Orchestration: scan → compare → export → write → backup
- **`main.py`** — CLI entry point

## What it does

1. **Scan Notion** — List all pages under root (or full workspace)
2. **Compare** — Hash+timestamp against index; identify changed pages
3. **Export** — Convert Notion blocks → Markdown (deterministic)
4. **Write** — Save .md files to Obsidian vault
5. **Index** — Update SQLite with new state
6. **Backup** — Snapshot vault before any changes
7. **Log** — Record all operations (JSON lines for analysis)

## What it doesn't do

- ❌ Classify pages with IA
- ❌ Guess folder structure
- ❌ Auto-create taxonomy
- ❌ Summarize content
- ❌ Generate insights
- ❌ Parse proprietary formats (only Markdown)

## What stays frozen

- Folder structure (defined once)
- Notion IDs (canonical)
- Property mapping (user-defined)
- Relation semantics (stored in DB)

## Performance

- **~30 pages/min** (Notion API rate limit: 3 req/s)
- **SQLite index** for instant hash lookup
- **Incremental only** — re-processes changed pages, skips unchanged
- **Parallel asset download** (optional, TODO)

## Rollback

Before every sync, a snapshot is created:
```
mt_sync_backups/vault_backup_20260627_094521/
```

Restore:
```bash
rm -rf /path/to/vault
cp -r mt_sync_backups/vault_backup_20260627_094521 /path/to/vault
```

## Logs

```
mt_sync_logs/sync_abc12345.jsonl
```

Each line is a JSON record:
```json
{"ts": "2026-06-27T...", "session": "abc12345", "level": "OK", "event": "exported → Pages/Notion ID.md", "notion_id": "..."}
```

## Next steps

- [ ] Dashboard (query logs, sync stats)
- [ ] Graph visualization (backlinks)
- [ ] MOC auto-generation (from relations)
- [ ] Asset parallel download
- [ ] Obsidian Dataview integration
- [ ] Conflict resolution UI
- [ ] Web API endpoint (`/sync`, `/status`)

## License

MIT
