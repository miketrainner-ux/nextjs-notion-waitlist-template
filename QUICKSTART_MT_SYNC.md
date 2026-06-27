# MT Sync Engine — Quickstart

## Pré-requisitos

- Python 3.10+
- Notion token (API)
- Obsidian vault (local folder)
- ~5 min de setup

## 1. Install

```bash
pip install -r mt_sync_engine/requirements.txt
```

## 2. Get Notion Token

1. Go to https://www.notion.com/my-integrations
2. Create a new integration
3. Copy the "Internal Integration Token"

## 3. Configure

Copy the example config:

```bash
cp mt_sync_engine/mt_sync.yaml.example mt_sync.yaml
```

Edit `mt_sync.yaml`:

```yaml
notion_token: "secret_xxx..."  # Paste your token
obsidian_vault_path: "/Users/you/Library/Mobile Documents/iCloud~md~obsidian/Documents/MT"
```

**Or use env vars:**

```bash
export NOTION_TOKEN=secret_xxx...
export OBSIDIAN_VAULT_PATH=/path/to/vault
```

## 4. Test (Dry Run)

```bash
python -m mt_sync_engine.main --dry-run
```

Output:
```json
{
  "session": "abc123",
  "scanned": 42,
  "unchanged": 39,
  "exported": 3,
  "errors": 0
}
```

## 5. First Sync

```bash
python -m mt_sync_engine.main
```

Files written to Obsidian vault:
```
Obsidian/
├── 00_System/
├── 10_Inbox/
├── 20_Projects/
└── ... (rest of structure)
```

## 6. Monitor

Check what synced:

```bash
python -m mt_sync_engine.dashboard
```

Timeline of events:

```bash
python -m mt_sync_engine.dashboard --timeline
```

## 7. Schedule (macOS/Linux)

Add to crontab (2 AM daily):

```bash
crontab -e
```

```
0 2 * * * cd ~/projects/mt-sync && python -m mt_sync_engine.main >> ~/logs/sync.log 2>&1
```

Windows (Task Scheduler):

```
Program: C:\Python\python.exe
Arguments: -m mt_sync_engine.main
Start in: C:\Users\you\mt-sync
```

## 8. Verify Obsidian

1. Open Obsidian
2. Create new vault at `/path/to/vault`
3. Wait for files to appear
4. Enable graph view: `Ctrl+G` (Cmd+G on Mac)

## Next Steps

1. ✅ Share Obsidian folder via Syncthing/iCloud/OneDrive
2. ✅ Add to `.gitignore`: `.obsidian/cache/`, `.obsidian/workspace`
3. ✅ Commit `.obsidian/plugins.json` for dataview/kanban sync
4. ✅ Schedule daily sync via cron
5. ❌ Do NOT edit Notion files directly in Obsidian (edit in Notion first)

## Troubleshooting

### "NOTION_TOKEN not set"
```bash
export NOTION_TOKEN=your_token_here
echo $NOTION_TOKEN  # Verify
```

### "obsidian_vault_path does not exist"
```bash
mkdir -p /path/to/vault
```

### "Connection timeout"
- Check internet
- Verify token is valid (try `curl -H "Authorization: Bearer $NOTION_TOKEN" https://api.notion.com/v1/users/me`)

### "No pages found"
- Verify your Notion workspace has pages
- Check if you need `--full-rebuild` (first time)

### "Can't find my Notion content"
Check the sync logs:
```bash
python -m mt_sync_engine.dashboard --all
```

## FAQ

**Q: Does it delete my Notion data?**
A: No. MT Sync Engine only READ from Notion and WRITE to Obsidian.

**Q: Can I edit in Obsidian and sync back to Notion?**
A: Not yet. Current direction is Notion → Obsidian only. Bidirectional is v0.4+.

**Q: How often should I sync?**
A: Daily (2 AM default). Or manually: `python -m mt_sync_engine.main`

**Q: What if something breaks?**
A: Restore from snapshot:
```bash
rm -rf /path/to/vault
cp -r mt_sync_backups/vault_backup_20260627_094521 /path/to/vault
```

**Q: Can I share my vault?**
A: Yes. Obsidian supports: Obsidian Sync, iCloud, Syncthing, git, OneDrive, Google Drive, Dropbox.

**Q: Does it use AI?**
A: No. Pure Python, APIs, SQLite. IA is reserved for curation (outside the sync loop).

**Q: How much does it cost?**
A: Zero tokens in routine sync. Notion API is free (3 req/sec limit). Obsidian is free.

## Performance

- **Scan:** ~2,500 pages in 1.4 minutes
- **Compare:** <100ms (SQLite hash lookup)
- **Export:** ~30 pages/min (API rate limit)
- **Write:** ~100 files/sec (local disk)
- **Total:** Full rebuild = ~14 minutes for 2,500 pages

Incremental sync (typical): 50 changed pages = ~17 seconds

## Support

Logs: `mt_sync_logs/sync_*.jsonl`

Report issues with:
- `mt_sync_logs/sync_[session_id].jsonl` (attach to issue)
- Output of `python -m mt_sync_engine.main --dry-run`
- Python version: `python --version`
