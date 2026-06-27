# MT.OS — Estratégia de Sincronização e Preservação

## Visão

Construir um ecossistema de conhecimento distribuído onde:

- **Apple Notes** = captura imediata (origem)
- **Notion** = sistema operacional relacional (vivo, conectável)
- **Obsidian** = segundo cérebro versionado (pesquisável, permanente)
- **Google Drive** = cofre seguro (arquivos, media, backup)
- **MT Sync Engine** = orquestrador silencioso (zero AI na rotina)

## Fluxo de Dados

```
Apple Notes (Captura)
    │
    ├─→ MANUAL: digitação, voice memo, screenshot
    │
Notion (Sistema Vivo)
    │
    ├─→ Curadoria manual
    ├─→ Relações criadas (pages, databases, views)
    ├─→ Propriedades enriquecidas
    │
MT Sync Engine (Automação)
    │
    ├─→ Scan: lista todas as páginas
    ├─→ Compare: hash vs index
    ├─→ Export: blocks → markdown
    ├─→ Write: .md → Obsidian vault
    ├─→ Backup: snapshot antes de tudo
    ├─→ Log: JSON lines (auditoria)
    │
Obsidian (Segundo Cérebro)
    │
    ├─→ Pesquisa local
    ├─→ Backlinks automáticos
    ├─→ MOCs (mapa de conteúdo)
    ├─→ Grafo visual
    ├─→ Versionado (git)
    │
Google Drive (Cofre)
    │
    ├─→ PDFs, imagens, media
    ├─→ Backups automáticos
    ├─→ Permissões granulares
    ├─→ Compartilhamento seguro
```

## Princípios

### 1. Programação antes de IA

| Tarefa | Solução | Tokens |
|--------|---------|--------|
| Exportar Notion | API + Python | 0 |
| Comparar hashes | SQLite | 0 |
| Gerar Markdown | Regex + Determinístico | 0 |
| Criar backlinks | Link extractor | 0 |
| Detectar mudanças | Timestamp comparison | 0 |
| **Sumarizar artigo** | Claude | ~500 |
| **Descobrir conexões** | Claude | ~800 |
| **Gerar insights** | Claude | ~1000 |

**Meta:** 95%+ das operações sem IA. IA = curadoria e descoberta, não automação.

### 2. Incremental, nunca rebuild

```python
# ❌ NUNCA:
for page in all_notion_pages:
    export_and_write(page)  # 2,500+ Notion API calls

# ✅ SEMPRE:
for page in changed_pages:  # apenas 20-50
    if page.hash != index.hash:
        export_and_write(page)
```

**Resultado:** ~30 pages/min (Notion rate limit) vs destrução de cache.

### 3. Taxonomia Congelada

Após primeira sincronização, a estrutura é **IMUTÁVEL**:

```
Obsidian Vault
├── 00_System
├── 10_Inbox
├── 20_Projects
├── 30_Areas
├── 40_Knowledge
├── 50_Creation
├── 60_Media
├── 70_Business
├── 80_Personal
├── 90_Archive
└── 99_Review
```

**Nenhuma página é movida automaticamente.** Mudanças de categoria = manual ou AI-assisted (fora do loop).

### 4. Preservação Total

Tudo é clonado:
- ✅ Páginas
- ✅ Databases (as relações)
- ✅ Propriedades (metadados)
- ✅ PDFs, imagens, assets
- ✅ Links internos → backlinks
- ✅ Timestamps

Nada é descartado ou resumido automaticamente.

### 5. Auditoria Completa

Antes de escrever: **snapshot** da vault inteira.

Operações registradas como JSON lines:
```json
{"ts": "2026-06-27T09:30:45Z", "session": "abc123", "level": "OK", "event": "exported → Pages/Notion-ID.md", "notion_id": "..."}
```

Rollback: restaurar snapshot + replay logs.

## Arquitetura do MT Sync Engine

### Componentes

| Módulo | Responsabilidade | Tokens |
|--------|-----------------|--------|
| `config.py` | Load YAML + env vars | 0 |
| `index.py` | SQLite: ID → hash/path | 0 |
| `logger.py` | JSON lines audit trail | 0 |
| `notion_client.py` | Notion API wrapper | 0 |
| `obsidian_writer.py` | Generate .md files | 0 |
| `sync.py` | Orchestration pipeline | 0 |
| `dashboard.py` | Monitor & stats | 0 |
| **Curation layer** | (Future) IA para insights | ~500/mês |

### Fluxo de Sincronização

```
1. SCAN NOTION (Notion API)
   - GET /databases/{id}/query
   - GET /pages/{id}
   - GET /blocks/{id}/children

2. COMPARE WITH INDEX (SQLite)
   - SELECT * FROM pages WHERE hash != ?
   - Result: ~5-10% changed

3. EXPORT (Python → Markdown)
   - Block → MD converter
   - Rich text → bold/italic/links
   - No IA involved

4. WRITE (Filesystem)
   - Create folders if needed
   - Write .md with frontmatter
   - Update index

5. BACKUP (Snapshot)
   - cp -r vault → vault_backup_{ts}

6. LOG (JSON)
   - Append records to session log
```

### Performance

```
Notion API rate limit: 3 req/s → 1 request every 333ms
Incremental sync: 50 changed pages → ~17 seconds
Full rebuild: 2,500 pages → ~14 minutes
Index lookup: SQLite → <1ms
```

## Casos de Uso

### 1. Daily Sync (automático)

```bash
# Rodar a cada madrugada
0 2 * * * python -m mt_sync_engine.main >> ~/logs/sync.log 2>&1
```

Custo: ~0 tokens (código puro)

### 2. Manual Full Rebuild

```bash
python -m mt_sync_engine.main --full-rebuild
```

Custo: 0 tokens

### 3. Dry Run (validação)

```bash
python -m mt_sync_engine.main --dry-run
```

Mostra o que seria sincronizado sem escrever.

### 4. Curation (IA-assisted, FORA do loop)

Quando usuário pede:

> "Sumarize o artigo sobre neurociência"

Então:
```python
# Não automático. Manual:
claude.summarize(obsidian.read("40_Knowledge/Neurociência/Paper.md"))
# Resultado vai para 40_Knowledge/Resumos/
```

**Jamais IA no pipeline automático.**

## Roadmap

### v0.2 (próximas 2 semanas)

- [ ] Asset parallel download (PDFs, imagens)
- [ ] MOC auto-generation from relations
- [ ] Obsidian graph.json export
- [ ] Conflict resolution (duplicates detection)

### v0.3

- [ ] Web API (`/sync`, `/status`, `/logs`)
- [ ] Webhook support (Notion changes → trigger sync)
- [ ] Google Drive integration (upload backups)

### v0.4

- [ ] Dataview integration (Obsidian plugins)
- [ ] Semantic search (local embedding model)
- [ ] Backlink strength scoring

### v1.0

- [ ] Full multi-vault support
- [ ] Team collaboration (permissions mapping)
- [ ] Analytics dashboard

## Governança

### Congelado

- ✅ Taxonomy
- ✅ Notion IDs (canonical)
- ✅ Property names
- ✅ Folder structure

### Mutável

- ❌ Notion content (usuário edita em Notion)
- ❌ Obsidian local notes (usuário cria em Obsidian)
- ✅ Sync parameters (batch size, rate limit)

### Nunca automático

- ❌ Classificação de novo conteúdo (sem IA)
- ❌ Exclusão de páginas
- ❌ Renomeação em massa
- ❌ Mudança de categoria (sem confirmação)

## Métricas

```json
{
  "session_id": "abc123",
  "duration_seconds": 45,
  "scanned": 2500,
  "unchanged": 2380,
  "exported": 120,
  "assets_downloaded": 34,
  "errors": 0,
  "conflicts": 2,
  "tokens_spent": 0,
  "index_size_mb": 12
}
```

## Filosofia Final

> "O conhecimento é preservado, não recriado. A programação executa. A automação sincroniza. A IA amplia a inteligência."

MT.OS não é um sistema "smart" que toma decisões. É um sistema **confiável e auditado** que:

1. Copia fielmente (preservação)
2. Rastreia tudo (auditoria)
3. Permite rollback (segurança)
4. Respeita a taxonomia (governança)
5. Reserva IA para curadoria, não execução (eficiência)

**Meta permanente:** consumir praticamente zero tokens em sincronizações rotineiras.
