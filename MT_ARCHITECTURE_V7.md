# MT.OS Architecture Engine v7.0

**Unified logical architecture for Google Drive, iCloud, Notion, Obsidian.**

## Overview

MT.OS v7.0 = MT Sync Engine v0.1 + Architecture Organizer + Index-Driven Classification

```
┌─────────────────────────────────────────────────────────────┐
│                     INDEX (SQLite)                          │
│  UUID | Name | Domain | Subdomain | Project | Tags | ...   │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
    Google Drive   iCloud Drive    Notion
        │              │              │
        └──────────────┼──────────────┘
                       ↓
               Obsidian Vault
                       ↓
               Backups + Logs
```

### Principle: Index-Driven Architecture

- **Index** (SQLite) = Single source of truth for metadata
- **Drive** (Google/iCloud) = Physical storage only
- **Notion** = Relational knowledge layer
- **Obsidian** = Read-only second brain

## Domains (11 Frozen)

```
00_Sistema       → System files, config, exports
01_Entrada       → Inbox, downloads, unprocessed
02_Projetos      → All projects + clients
03_Pessoas       → People, families, contacts
04_Conhecimento  → Books, papers, courses, research
05_Conteúdo      → Content creation, articles, manifestos
06_Mídia         → Photos, videos, audio, assets
07_Empresa       → Business, finance, contracts, HR
08_Pessoal       → Personal, health, goals, certificates
09_Arquivo       → Completed projects, old versions, legacy
99_Revisão       → Unclassified, duplicates, conflicts
```

**Rule:** Domains are frozen. No new domains can be created automatically.

## Subdomains (Scalable)

Only create subdomains when there's sufficient volume.

Example:

```
02_Projetos
├── MT.OS
├── Michael Training
├── Centro Esportivo
└── Aplicativos

03_Pessoas
├── Documentos
├── Fotos
├── Vídeos
└── Contratos
```

## Naming Convention

**Mandatory pattern:** `YYYY-MM-DD_Subject.ext` or `YYYY-MM-DD_Project_Subject_V01.ext`

Example:
- ✅ `2026-06-27_Estrategia_Anual.pdf`
- ✅ `2026-06-27_MTSync_Roadmap_V02.md`
- ❌ `My Document.pdf` (wrong)
- ❌ `projeto.xlsx` (wrong)

## Classification Rules (Deterministic)

**No AI in routine classification.** Sequence:

1. **Extension** (exact match) → Domain
   - `.pdf` → 04_Conhecimento
   - `.mp4`, `.mov` → 06_Mídia
   - `.xlsx` → 07_Empresa

2. **Path keywords** (regex) → Domain
   - `/client/` → 03_Pessoas
   - `/contract/` → 07_Empresa
   - `/research/` → 04_Conhecimento

3. **File size** → Domain
   - `>100MB` → 06_Mídia (likely video)
   - `0 bytes` → 00_Sistema (temp/config)

4. **Fallback** → 99_Revisão (human review)

**Confidence levels:**
- `ALTA` (≥95%) — automatic move, no review
- `MEDIA` (75-95%) — automatic move, flag for review
- `BAIXA` (50-75%) — send to 99_REVISÃO
- `NENHUMA` (<50%) — send to 99_REVISÃO

Only `ALTA` confidence moves are auto-executed. `MEDIA` requires flag review. `BAIXA`/`NENHUMA` → human.

## Chaos Detection

Automatic identification:

- ❌ Empty folders → consolidate or delete
- ❌ Duplicate filenames → flag for dedup
- ❌ Inconsistent naming → flag for rename
- ❌ Wrong extensions → flag for correction
- ❌ Temporary files (`.tmp`, `~`, `.bak`) → mark for deletion
- ❌ Orphaned files (no category) → → 99_REVISÃO

## Workflow: Scan → Plan → Execute → Verify

### 1. Scan

```bash
python -m mt_sync_engine.architecture_main --scan
```

Output:
```json
{
  "scanned": 2500,
  "by_domain": {
    "00_Sistema": 150,
    "06_Mídia": 800,
    ...
  },
  "chaos": {
    "empty_folders": 12,
    "duplicates": 34,
    "inconsistent_names": 267,
    "temporary_files": 89
  }
}
```

### 2. Plan (Dry Run)

```bash
python -m mt_sync_engine.architecture_main --plan
```

Output:
```json
{
  "total_moves": 450,
  "by_confidence": {
    "ALTA": 420,
    "MEDIA": 20,
    "BAIXA": 8,
    "REVISAO": 2
  },
  "plan": [
    {
      "uuid": "...",
      "name": "Document.pdf",
      "current": "/root/Downloads/",
      "target": "/root/04_Conhecimento/Pesquisas/2026-06-27_Document_V01.pdf",
      "confidence": "ALTA"
    },
    ...
  ]
}
```

### 3. Execute (with Rollback)

```bash
python -m mt_sync_engine.architecture_main --execute
```

Execution:
1. Create snapshot of Drive (backup)
2. Execute ALTA confidence moves (~420)
3. Flag MEDIA moves for human review
4. Move BAIXA/NENHUMA → 99_REVISÃO
5. Save rollback log
6. Verify each move

Output:
```json
{
  "executed": 420,
  "flagged_for_review": 20,
  "sent_to_review": 10,
  "errors": 0,
  "rollback_log": "mt_sync_logs/rollback_20260627_093045.json"
}
```

### 4. Verify

Check Google Drive:
- ✅ Files moved to correct locations
- ✅ Filenames standardized
- ✅ Duplicates consolidated
- ✅ Rollback log saved

### 5. Rollback (if needed)

```bash
python -m mt_sync_engine.architecture_main --rollback
```

Restores **all files** to original locations in reverse order.

## Safety Guarantees

### No Destructive Operations

- ❌ Never delete files
- ❌ Never overwrite files
- ❌ Never move without logging
- ✅ Always create backups first
- ✅ Always save rollback logs
- ✅ Always validate before execution

### Pre-Flight Checks

Before any execution:

1. **Domain validity** — all targets in 11 approved domains
2. **No duplicates** — no two moves to same location
3. **No overwrites** — no move overwrites existing file
4. **Confidence threshold** — only move if ≥75% sure

Fail any check → abort execution, detailed report.

## Integration with MT Sync Engine

```
MT Sync Engine (Notion ↔ Obsidian)
         ↑
         │
  Architecture Engine (Google Drive ↔ Index)
         │
         ↓
      Index (SQLite)
         ↑
         │
    Unified Metadata
    (tags, projects, persons)
```

**Index** serves both engines:
- MT Sync Engine: track Notion ↔ Obsidian
- Architecture Engine: track Drive ↔ Index

## Use Cases

### Case 1: First-Time Organization

```bash
# 1. Scan chaos
python -m mt_sync_engine.architecture_main --scan

# 2. Generate plan
python -m mt_sync_engine.architecture_main --plan > plan.json

# 3. Review plan (human: check MEDIA/BAIXA/REVISÃO)
less plan.json

# 4. Execute (with dry run first)
python -m mt_sync_engine.architecture_main --execute --dry-run

# 5. Execute for real
python -m mt_sync_engine.architecture_main --execute

# 6. Verify in Google Drive
```

### Case 2: Daily Incremental Sync

```bash
# Runs every night: detect new chaos, move ALTA files, flag MEDIA
0 2 * * * python -m mt_sync_engine.architecture_main --plan --execute
```

### Case 3: Manual Review of Low-Confidence Files

```bash
# Files in 99_REVISÃO are reviewed by human
# After human decision, they're moved to correct domain
# (either via GUI or by updating index)
```

## Performance

```
Scan Drive:       ~2,500 files in 1.4 min
Classify:         ~150 files/sec (deterministic)
Generate plan:    <100ms (index lookup)
Execute moves:    ~20 files/sec (API rate limited)
Full execution:   ~2,500 files in ~4 minutes
Rollback:         Same as execution
```

## Example: First Run

**Before:**
```
Google Drive (Chaos)
├── Downloads/
│   ├── Document.pdf
│   ├── Foto.jpg
│   ├── .tmp_file
│   └── ... (1000+ random files)
├── Projects/
│   ├── project1/
│   ├── project2/
│   └── old_project/
└── ... (no structure)
```

**After (with v7.0):**
```
Google Drive (Organized)
├── 00_Sistema/
│   └── Exports/
├── 02_Projetos/
│   ├── MT.OS/
│   ├── Michael Training/
│   └── Centro Esportivo/
├── 04_Conhecimento/
│   ├── Pesquisas/
│   └── Papers/
├── 06_Mídia/
│   ├── Fotos/
│   └── Vídeos/
└── 99_Revisão/
    └── (20-30 files needing manual decision)
```

**Index (SQLite):**
```
UUID | Name | Domain | Subdomain | Tags | Project | Person | ...
... (2,500 rows, indexed by hash/date/project)
```

**Result:**
- ✅ 2,470 files auto-organized (ALTA)
- ⚠️ 20 files flagged (MEDIA)
- 🔍 10 files in 99_REVISÃO (BAIXA/NENHUMA)
- 📊 Perfect auditability via rollback log
- 🎯 Searchable via index + tags

## Roadmap

### v7.0 (current)
- ✅ Frozen 11-domain architecture
- ✅ Deterministic classification
- ✅ Chaos detection
- ✅ Dry-run + rollback
- ✅ Index-driven metadata

### v7.1
- [ ] iCloud sync (same structure)
- [ ] Notion integration (domain ↔ database mapping)
- [ ] Web dashboard (visualize org)

### v7.2
- [ ] Semantic search (local embeddings for 99_REVISÃO)
- [ ] Auto-consolidation of duplicates
- [ ] Color coding in Drive (domain → color)

### v8.0
- [ ] Bidirectional sync (Drive → Notion → Obsidian)
- [ ] Automated insights (Claude: "Top 5 growing projects")
- [ ] Team collaboration (permission mapping)

## Philosophy

> **"The index organizes. The drive stores. The AI reviews exceptions."**

- Index = Single source of truth
- Drive = Append-only storage (never delete)
- IA = Only for edge cases (<10% of files)

**Zero-token operations for routine work.** IA only when determinism isn't enough.
