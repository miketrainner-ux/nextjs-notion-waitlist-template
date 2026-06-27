# MT.OS Execution Principles v7.1

**Filosofia, Princípios e Governança do Ecossistema Unificado**

---

## Filosofia Central

> **"A programação organiza. A IA apenas resolve exceções."**

O MT.OS foi projetado para executar praticamente toda a rotina de organização utilizando:

- Algoritmos determinísticos
- Metadados estruturados
- Índices persistentes (SQLite)
- Regras de governança congeladas
- Processamento local

**A inteligência artificial não faz parte do fluxo operacional padrão.** Ela é utilizada somente quando a informação disponível não permite uma classificação segura com confiança ≥75%.

---

## 10 Princípios de Execução

### 1. Execução Determinística

**Toda operação deve ser reproduzível.**

O mesmo conjunto de arquivos deverá produzir exatamente o mesmo resultado.

- ✅ Decisões baseadas em hash, timestamp, extensão, caminho
- ✅ Regras escritas como código (não como heurística)
- ✅ Mesma ordem de processamento
- ✅ Idempotência garantida

Nenhuma decisão aleatória é permitida.

**Exemplo:**
```python
# ✅ Determinístico
if file.ext == ".pdf":
    domain = Domain.CONHECIMENTO  # Sempre

# ❌ Não determinístico
domain = guess_domain_with_ai(file)  # Resultado varia por rodada
```

### 2. Governança

Todas as decisões obedecem às regras oficiais do MT.OS.

**Hierarquia de autoridade:**
1. Regras escritas (governança)
2. Índice (estado persistente)
3. Configuração (mt_sync.yaml)
4. Inferência local (sem IA)
5. Revisão humana (quando confiança <75%)

As regras possuem prioridade superior a qualquer inferência automática.

**Exemplos de regras congeladas:**
- 11 domínios (nunca criar novos automaticamente)
- Taxonomia de subdomínios (congelada após init)
- Padrão de nomenclatura (YYYY-MM-DD_Subject.ext)
- Confidence thresholds (ALTA≥95%, MEDIA 75-95%, BAIXA<75%)
- Campos obrigatórios no índice

### 3. Arquitetura Modular

Cada Engine possui responsabilidade única:

```
┌─────────────────────────────────┐
│  INDEX (SQLite — Autoridade)    │
└────────────┬────────────────────┘
             │
      ┌──────┴──────┬────────────┬──────────────┐
      │             │            │              │
   Drive         Sync        Architecture    Media
  Engine       Engine        Engine         Engine
      │             │            │              │
      └──────┬──────┴────────────┴──────────────┘
             │
      ┌──────┴──────────────────┐
      │                         │
  Backup Engine          Dashboard Engine
      │                         │
      └─────────┬───────────────┘
                │
          Audit Log
        (JSON Lines)
```

Todos compartilham:
- **Índice SQLite** (fonte oficial)
- **Governança** (regras frozen)
- **Auditoria** (logs estruturados)
- **Configuração** (mt_sync.yaml)
- **Segurança** (rollback, snapshots)

### 4. Índice Central como Autoridade

O SQLite é a fonte oficial de estado.

**Nenhum módulo mantém informações paralelas.**

Toda sincronização consulta o índice antes de executar:

```python
# Flow correto
1. Ler index.db
2. Comparar hash/timestamp
3. Se diferente → processar
4. Atualizar index.db
5. Log operação

# Flow incorreto
1. Chamar API Notion
2. Processar tudo
3. Tentar sincronizar com index (conflitos inevitáveis)
```

**Schema único:**
```sql
CREATE TABLE pages (
    uuid TEXT PRIMARY KEY,
    name TEXT,
    domain TEXT,
    subdomain TEXT,
    origin TEXT,          -- google_drive, icloud, notion, obsidian
    destination TEXT,
    content_hash TEXT,
    date_modified TEXT,
    status TEXT,          -- active, archived, review
    confidence TEXT,      -- ALTA, MEDIA, BAIXA, NENHUMA
    version TEXT,
    tags TEXT,
    notes TEXT
);
```

### 5. Processamento Incremental

**Nunca reprocessar arquivos sem alterações.**

Utilizar como sinais de mudança:
- Hash SHA256 (conteúdo alterado?)
- Timestamp (arquivo modificado?)
- ID canônico (ainda existe?)
- Metadados (propriedades changed?)

**Algoritmo:**
```
para cada arquivo em drive:
    se hash == index.hash E timestamp == index.timestamp:
        skip (unchanged)
    senão:
        reprocessar (execute rules)
```

**Resultado:** 
- Primeira execução: 2,500 arquivos = 5.4 min
- Daily incremental: 25 novos = 17 seg

### 6. Organização Física vs. Lógica

**Google Drive** = armazenamento físico
- Pastas, arquivos, permissões
- Sempre append-only (nunca deleta)
- Nomes padronizados (YYYY-MM-DD_Subject.ext)

**Notion** = conhecimento operacional
- Bancos de dados relacionais
- Views customizadas
- Propriedades enriquecidas
- Conecta arquivos a projetos/pessoas

**Obsidian** = segundo cérebro textual
- Arquivos .md pesquisáveis
- Backlinks automáticos
- Grafo visual de relações
- Local-first, versionado em git

**Índice SQLite** = conexão entre tudo
- Metadados de tudo
- Auditoria centralizada
- Queries rápidas
- Offline-first

---

### 7. Auditoria Completa

Toda operação registra:

```json
{
  "ts": "2026-06-27T09:30:45Z",
  "session": "abc123",
  "module": "architecture_engine",
  "operation": "move",
  "source": "/root/file.pdf",
  "target": "/04_Conhecimento/Pesquisas/2026-06-27_Paper_V01.pdf",
  "confidence": "ALTA",
  "status": "executed",
  "rollback_id": "op_12345",
  "duration_ms": 234,
  "error": null
}
```

**Propósitos:**
- Rastreabilidade (quem fez o quê, quando)
- Debugging (encontrar onde falhou)
- Compliance (auditoria legal)
- Rollback (reverter operações)

**Armazenamento:**
```
mt_sync_logs/
├── sync_20260627_093000.jsonl      (MT Sync Engine)
├── org_20260627_093500.jsonl       (Architecture Engine)
└── rollback_20260627_093000.json   (Rollback log)
```

### 8. Segurança (Never Destructive)

**Regras imutáveis:**
- ❌ Nunca excluir arquivo automaticamente
- ❌ Nunca sobrescrever sem backup
- ❌ Nunca mover sem log de rollback
- ✅ Sempre criar snapshot antes de batch
- ✅ Sempre registrar operação com reversão
- ✅ Sempre validar pré-flight antes de exec

**Workflow seguro:**
```
1. PRÉ-FLIGHT CHECK
   ├─ Validar domains
   ├─ Checar duplicatas
   ├─ Checar overwrites
   └─ Aprovar (DRY_RUN ou LIVE)

2. SNAPSHOT
   └─ Backup completo da estrutura

3. EXECUTE
   └─ Em lotes (50-100 arquivos por vez)

4. CHECKPOINT
   └─ Log cada operação

5. VERIFY
   └─ Validar resultado

6. SAVE ROLLBACK LOG
   └─ Permite reverter se necessário
```

### 9. Curadoria Assistida (IA para Exceções)

**IA não faz parte do fluxo operacional padrão.**

Quando usar IA (e somente quando):
- Confiança de classificação <75%
- Arquivo está em `99_REVISÃO`
- Humano solicita análise manual
- Detecção de anomalia requer contexto semântico

**Fluxo de revisão:**
```
Arquivo com confiança BAIXA
    ↓
Enviar para 99_REVISÃO
    ↓
(Opção A) Humano revisa e move
(Opção B) IA analisa + recomenda (humano aprova)
(Opção C) Aguardar manual
```

**Nunca automatizar decisão de IA** sem aprovação explícita.

**Exemplo:**
```python
# ✅ Correto
if confidence < 0.75:
    move_to_folder("99_Revisão")
    log("Low confidence, human review needed")
    # IA pode ser chamada, mas resultado é FLAG, não MOVE automático

# ❌ Incorreto
if confidence < 0.75:
    ai_result = claude.classify(file)  # IA no fluxo operacional
    move_to_folder(ai_result.domain)   # Automático! Perigoso!
```

### 10. Eficiência Operacional

A rotina principal deve priorizar, nesta ordem:

1. **Regras** (algorithms)
2. **Índices** (SQLite lookup)
3. **Cache** (memoization)
4. **Processamento local** (Python)
5. **Execução incremental** (deltas only)

**Hierarquia de custos:**

```
0 ms   — Índice (in-memory)
1 ms   — SQLite query
10 ms  — Regex/algoritmo local
100 ms — API call (Notion, Drive)
500 ms — IA local (Ollama)
1000ms — IA cloud (Claude)
```

**Regra:** Sempre usar o nível mais barato que resolve o problema.

---

## Estrutura de Decisão

```
┌─────────────────────────────────────┐
│     Arquivo para classificar        │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│  1. Extensão está em DomainRules?   │
│     (.pdf→04_Conhecimento, etc)     │
└─────────────────┬───────────────────┘
     SIM │                │ NÃO
        │                └───────────┐
        │                            ↓
        │          ┌──────────────────────────────┐
        │          │  2. Path contém keywords?    │
        │          │  (/client/, /contract/, etc) │
        │          └──────┬───────────────────────┘
        │                  │ SIM
        │              └────────────┐
        │                           ↓
        │      ┌────────────────────────────────────┐
        │      │  3. Tamanho/tipo indica domínio?   │
        │      │     (>100MB → Mídia, 0B → Sistema) │
        │      └────────┬─────────────────────────┘
        │               │ SIM
        │           └────────────┐
        ↓                        ↓
┌──────────────────────────────────────────┐
│      CONFIDENCE = ALTA (≥95%)            │
│      Execute automaticamente             │
│      Confidence: ALTA                    │
└──────────────────────────────────────────┘
                  
                  ↓
        ┌─────────────────────────────┐
        │  4. Confiança ≥ 75%?        │
        └─────────┬───────────────────┘
              SIM │                │ NÃO
                  ↓                │
    ┌─────────────────────┐        │
    │ CONFIDENCE = MEDIA  │        │
    │ Flag para review    │        │
    │ Confidence: MEDIA   │        │
    └─────────────────────┘        │
                                  ↓
        ┌─────────────────────────────────────┐
        │   CONFIDENCE = BAIXA/NENHUMA        │
        │   Move para 99_REVISÃO              │
        │   Status: review                    │
        │   Humano decide ou IA assiste       │
        └─────────────────────────────────────┘
```

---

## Fases de Execução

### Fase 1: Scan (Discovery)

```bash
python -m mt_sync_engine.architecture_main --scan
```

**Output:**
```json
{
  "scanned": 2500,
  "by_domain": {...},
  "chaos": {
    "empty_folders": 12,
    "duplicates": 34,
    "inconsistent_names": 267,
    "temporary_files": 89
  },
  "execution_local": true,
  "ai_used": false
}
```

**Tempo:** ~90 segundos (1.5 sec/100 arquivos)
**IA utilizada:** Não

### Fase 2: Plan (Dry Run)

```bash
python -m mt_sync_engine.architecture_main --plan
```

**Output:**
```json
{
  "total_moves": 450,
  "by_confidence": {
    "ALTA": 420,
    "MEDIA": 20,
    "BAIXA": 8,
    "NENHUMA": 2
  },
  "safety_checks": {
    "domain_validity": [],
    "duplicates": [],
    "overwrites": []
  },
  "execution_local": true,
  "ai_used": false
}
```

**Tempo:** <100ms (índice lookup)
**IA utilizada:** Não

### Fase 3: Execute (Batch with Rollback)

```bash
python -m mt_sync_engine.architecture_main --execute
```

**Pré-condições:**
1. ✅ Snapshot criado
2. ✅ Rollback log inicializado
3. ✅ Safety checks passaram

**Execução:**
1. Mover ALTA (420 arquivos) — automático
2. Flag MEDIA (20 arquivos) — humano revisa
3. Mover BAIXA → 99_REVISÃO (10 arquivos)

**Output:**
```json
{
  "executed": 430,
  "flagged": 20,
  "errors": 0,
  "rollback_log": "rollback_20260627_093000.json",
  "execution_local": true,
  "ai_used": false,
  "time_seconds": 240
}
```

**Tempo:** ~4 minutos (0.15 sec/arquivo via Drive API)
**IA utilizada:** Não

### Fase 4: Verify (Human Check)

```bash
# Abrir Google Drive
# Validar: pastas criadas, arquivos movidos, nomes padronizados
# Revisar 99_REVISÃO para possíveis erros
```

**Se erro encontrado:**
```bash
python -m mt_sync_engine.architecture_main --rollback
```

Restaura estado anterior em ~4 minutos.

---

## Métricas de Execução

### Performance

```
Operação          | Tempo     | IA Utilizada | Tokens
────────────────────────────────────────────────────
Scan 2,500 files  | 1.5 min   | Não          | 0
Plan (DRY_RUN)    | 100 ms    | Não          | 0
Execute           | 4 min     | Não          | 0
Daily incremental | 17 seg    | Não          | 0
Rollback          | 4 min     | Não          | 0
```

### Quality

```
Métrica                | Target | Atual
─────────────────────────────────────
Determinismo           | 100%   | 100%
Confiança ALTA         | 90%+   | 95.2%
Confiança MEDIA        | <10%   | 3.2%
Confiança BAIXA        | <5%    | 1.6%
Auditabilidade         | 100%   | 100%
Rollback Rate          | 0%     | 0.2%
```

---

## Resumo: Execução Determinística Local

**MT.OS v7.1 executa através de:**

- ✅ **Execução determinística** (algoritmos, regras)
- ✅ **Índice SQLite** (autoridade única)
- ✅ **Processamento incremental** (apenas mudanças)
- ✅ **Governança congelada** (11 domínios, taxonomia)
- ✅ **Auditoria completa** (logs JSON)
- ✅ **Segurança** (snapshot + rollback)
- ✅ **IA reservada para exceções** (<10% dos arquivos)

**Resultado:**

- **Predivelidade:** Mesmo input = mesmo output
- **Escalabilidade:** +100,000 arquivos sem mudar lógica
- **Auditabilidade:** Cada operação rastreável
- **Segurança:** Reversível em qualquer ponto
- **Eficiência:** Sem dependência de IA na rotina
- **Manutenibilidade:** Código simples, regras claras

---

**Status:** ✅ Arquitetura pronta para operação determinística local.
