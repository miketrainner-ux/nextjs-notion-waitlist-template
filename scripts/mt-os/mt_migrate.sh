#!/usr/bin/env bash
# MT.OS — MIGRAÇÃO iCLOUD → GOOGLE DRIVE
# Versão: 2.1 — Definitivo
# Autor: MT.OS
# Execute: bash mt_migrate.sh [--dry-run] [--phase 1|2|3|all] [--check]
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── CONFIGURAÇÃO ──────────────────────────────────────────────
ICLOUD_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
GDRIVE_REMOTE="gdrive"
GDRIVE_INBOX="gdrive:📥 INBOX/iCloud-Migration"
GDRIVE_REVIEW="gdrive:99_Sistema/Revisao-Migracao"
LOG_DIR="$HOME/MT.OS/logs"
DB_PATH="$HOME/MT.OS/index.db"
BATCH_SIZE=50
DRY_RUN=false
PHASE="all"
CHECK_MODE=false
LOCK_FILE="/tmp/mt_migrate.lock"

# ── PARSE ARGS ────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --phase)   PHASE="$2"; shift 2 ;;
    --check)   CHECK_MODE=true; shift ;;
    *) echo "Arg desconhecido: $1"; exit 1 ;;
  esac
done

# ── CORES ─────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_DIR/migrate_$(date +%Y%m%d).log"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*" | tee -a "$LOG_DIR/migrate_$(date +%Y%m%d).log"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_DIR/migrate_$(date +%Y%m%d).log"; }
err()  { echo -e "${RED}[ERR]${NC} $*" | tee -a "$LOG_DIR/migrate_$(date +%Y%m%d).log"; }

# ── LOCK (evita rodar dois ao mesmo tempo) ─────────────────────
if [ -f "$LOCK_FILE" ]; then
  PID=$(cat "$LOCK_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    err "Já rodando (PID $PID). Abortando."
    exit 1
  else
    rm -f "$LOCK_FILE"
  fi
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# ─────────────────────────────────────────────────────────────
# PRE-FLIGHT
# ─────────────────────────────────────────────────────────────
preflight() {
  log "=== PRE-FLIGHT CHECK ==="
  mkdir -p "$LOG_DIR" "$HOME/MT.OS"

  # Homebrew
  if ! command -v brew &>/dev/null; then
    warn "Homebrew não encontrado. Instalando..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi

  # rclone
  if ! command -v rclone &>/dev/null; then
    log "Instalando rclone..."
    brew install rclone
    ok "rclone instalado"
  else
    ok "rclone: $(rclone version | head -1)"
  fi

  # sqlite3
  if ! command -v sqlite3 &>/dev/null; then
    brew install sqlite
  fi
  ok "sqlite3: $(sqlite3 --version)"

  # Verifica rclone remote
  if ! rclone listremotes | grep -q "^${GDRIVE_REMOTE}:"; then
    err "Remote '${GDRIVE_REMOTE}' não configurado no rclone."
    echo ""
    echo -e "${YELLOW}Execute agora:${NC}"
    echo "  rclone config"
    echo "  → New remote → name: gdrive → Google Drive → siga autenticação"
    echo ""
    echo "Depois rode este script novamente."
    exit 1
  fi
  ok "rclone remote '${GDRIVE_REMOTE}' OK"

  # Verifica iCloud Drive
  if [ ! -d "$ICLOUD_ROOT" ]; then
    err "iCloud Drive não encontrado em: $ICLOUD_ROOT"
    err "Certifique-se que iCloud Drive está ativado em Preferências do Sistema"
    exit 1
  fi
  ok "iCloud Drive: $ICLOUD_ROOT"

  # Conta arquivos (inclui stubs)
  TOTAL_FILES=$(find "$ICLOUD_ROOT" -type f 2>/dev/null | wc -l | tr -d ' ')
  log "Arquivos encontrados (incluindo stubs): $TOTAL_FILES"
}

# ─────────────────────────────────────────────────────────────
# FASE 0 — SNAPSHOT DE SEGURANÇA
# ─────────────────────────────────────────────────────────────
snapshot() {
  log "=== FASE 0: SNAPSHOT ==="
  SNAP_FILE="$HOME/MT.OS/logs/snapshot_$(date +%Y%m%d_%H%M%S).txt"
  log "Criando inventário de segurança em: $SNAP_FILE"
  find "$ICLOUD_ROOT" \( -type f -o -type l \) \
    -exec stat -f "%z %m %N" {} \; 2>/dev/null \
    | sort > "$SNAP_FILE"
  SNAP_COUNT=$(wc -l < "$SNAP_FILE" | tr -d ' ')
  ok "Snapshot criado: $SNAP_COUNT entradas → $SNAP_FILE"
}

# ─────────────────────────────────────────────────────────────
# FASE 1 — FORÇAR DOWNLOAD DOS STUBS iCLOUD
# ─────────────────────────────────────────────────────────────
phase1_download_stubs() {
  log "=== FASE 1: FORÇAR DOWNLOAD iCLOUD ==="
  log "Identificando arquivos não baixados (stubs .icloud)..."

  # Conta stubs
  STUB_COUNT=$(find "$ICLOUD_ROOT" -name "*.icloud" -type f 2>/dev/null | wc -l | tr -d ' ')
  log "Stubs encontrados: $STUB_COUNT"

  if [ "$STUB_COUNT" -eq 0 ]; then
    ok "Nenhum stub encontrado. Todos os arquivos já baixados."
    return 0
  fi

  log "Iniciando download forçado de $STUB_COUNT stubs..."
  log "Isso pode demorar dependendo da velocidade da internet."

  # Método 1: brctl (mais confiável no macOS moderno)
  if command -v brctl &>/dev/null; then
    log "Usando brctl para forçar download..."
    find "$ICLOUD_ROOT" -name "*.icloud" -type f 2>/dev/null | while IFS= read -r stub; do
      # Converte path do stub para path real
      DIR=$(dirname "$stub")
      BASENAME=$(basename "$stub" .icloud)
      REAL_FILE="$DIR/${BASENAME#.}"
      brctl download "$REAL_FILE" 2>/dev/null || true
    done
  fi

  # Método 2: open + xattr (fallback)
  log "Forçando download via xattr (fallback)..."
  find "$ICLOUD_ROOT" -name "*.icloud" -type f 2>/dev/null | while IFS= read -r stub; do
    DIR=$(dirname "$stub")
    BASENAME=$(basename "$stub" .icloud)
    REAL_FILE="$DIR/${BASENAME#.}"
    # Tenta abrir para triggerar download
    xattr -d com.apple.icloud.itemName "$stub" 2>/dev/null || true
    # Registra para monitoramento
    echo "$REAL_FILE" >> "$LOG_DIR/pending_downloads.txt"
  done

  # Aguarda downloads (com timeout)
  log "Aguardando downloads completarem (máx 30 min)..."
  TIMEOUT=1800
  ELAPSED=0
  INTERVAL=30
  while true; do
    REMAINING=$(find "$ICLOUD_ROOT" -name "*.icloud" -type f 2>/dev/null | wc -l | tr -d ' ')
    if [ "$REMAINING" -eq 0 ]; then
      ok "Todos os arquivos baixados!"
      break
    fi
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
      warn "Timeout atingido. $REMAINING stubs restantes."
      warn "Os stubs restantes serão ignorados nesta rodada."
      # Lista o que não baixou
      find "$ICLOUD_ROOT" -name "*.icloud" -type f 2>/dev/null \
        >> "$LOG_DIR/stubs_nao_baixados_$(date +%Y%m%d).txt"
      break
    fi
    log "Aguardando... $REMAINING stubs restantes ($ELAPSED/${TIMEOUT}s)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
  done
}

# ─────────────────────────────────────────────────────────────
# FASE 2 — ÍNDICE SQLite
# ─────────────────────────────────────────────────────────────
phase2_index() {
  log "=== FASE 2: ÍNDICE SQLite ==="

  # Cria/atualiza schema
  sqlite3 "$DB_PATH" <<'SQL'
CREATE TABLE IF NOT EXISTS files (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  hash        TEXT,
  name        TEXT NOT NULL,
  origin_path TEXT NOT NULL UNIQUE,
  dest_path   TEXT,
  size_bytes  INTEGER,
  created_at  TEXT,
  modified_at TEXT,
  ext         TEXT,
  type        TEXT,
  project     TEXT,
  person      TEXT,
  status      TEXT DEFAULT 'PENDING',
  gdrive_id   TEXT,
  error       TEXT,
  indexed_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_status   ON files(status);
CREATE INDEX IF NOT EXISTS idx_hash     ON files(hash);
CREATE INDEX IF NOT EXISTS idx_origin   ON files(origin_path);
CREATE TABLE IF NOT EXISTS migration_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         TEXT DEFAULT (datetime('now')),
  phase      TEXT,
  action     TEXT,
  file_path  TEXT,
  result     TEXT,
  details    TEXT
);
SQL
  ok "Schema SQLite criado/verificado: $DB_PATH"

  # Indexa arquivos (excluindo stubs)
  log "Indexando arquivos reais (excluindo stubs)..."
  INDEXED=0
  SKIPPED=0

  find "$ICLOUD_ROOT" -type f ! -name "*.icloud" 2>/dev/null | while IFS= read -r filepath; do
    # Verifica se já indexado
    EXISTS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files WHERE origin_path='$filepath';")
    if [ "$EXISTS" -gt 0 ]; then
      SKIPPED=$((SKIPPED + 1))
      continue
    fi

    NAME=$(basename "$filepath")
    EXT="${NAME##*.}"
    SIZE=$(stat -f%z "$filepath" 2>/dev/null || echo 0)
    MOD=$(stat -f%Sm -t "%Y-%m-%dT%H:%M:%S" "$filepath" 2>/dev/null || echo "")
    # Hash MD5 apenas para arquivos < 100MB (performance)
    if [ "$SIZE" -lt 104857600 ]; then
      HASH=$(md5 -q "$filepath" 2>/dev/null || echo "")
    else
      HASH="LARGE_FILE_$(echo "$filepath" | md5 -q)"
    fi

    # Escapa aspas simples
    NAME_ESC="${NAME//\'/\'\'}"
    PATH_ESC="${filepath//\'/\'\'}"

    sqlite3 "$DB_PATH" \
      "INSERT OR IGNORE INTO files (hash, name, origin_path, size_bytes, modified_at, ext, status)
       VALUES ('$HASH', '$NAME_ESC', '$PATH_ESC', $SIZE, '$MOD', '$EXT', 'PENDING');"

    INDEXED=$((INDEXED + 1))
    if [ $((INDEXED % 100)) -eq 0 ]; then
      log "  Indexados: $INDEXED arquivos..."
    fi
  done

  TOTAL=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files;")
  ok "Índice: $TOTAL arquivos registrados"
}

# ─────────────────────────────────────────────────────────────
# FASE 3 — MIGRAÇÃO → GOOGLE DRIVE
# ─────────────────────────────────────────────────────────────
phase3_migrate() {
  log "=== FASE 3: MIGRAÇÃO → GOOGLE DRIVE ==="

  RCLONE_FLAGS=(
    "--transfers=8"
    "--checkers=16"
    "--drive-chunk-size=128M"
    "--retries=10"
    "--retries-sleep=10s"
    "--low-level-retries=20"
    "--stats=30s"
    "--stats-one-line"
    "--log-level=INFO"
    "--log-file=$LOG_DIR/rclone_$(date +%Y%m%d_%H%M%S).log"
    "--ignore-existing"
    "--no-traverse"
    "--drive-stop-on-upload-limit"
  )

  if [ "$DRY_RUN" = true ]; then
    RCLONE_FLAGS+=("--dry-run")
    warn "MODO DRY-RUN — nenhum arquivo será movido"
  fi

  # Migração em lotes de BATCH_SIZE
  PENDING=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files WHERE status='PENDING';")
  log "Arquivos para migrar: $PENDING"

  MIGRATED=0
  ERRORS=0
  OFFSET=0

  while true; do
    BATCH=$(sqlite3 "$DB_PATH" \
      "SELECT id, origin_path, name, ext FROM files
       WHERE status='PENDING' LIMIT $BATCH_SIZE OFFSET $OFFSET;" \
      2>/dev/null)

    [ -z "$BATCH" ] && break

    while IFS='|' read -r fid fpath fname fext; do
      [ -z "$fpath" ] && continue

      # Determina destino baseado na extensão/nome
      DEST_FOLDER=$(classify_file "$fname" "$fext" "$fpath")

      if [ "$DRY_RUN" = true ]; then
        log "  [DRY] $fname → $DEST_FOLDER"
        continue
      fi

      # Copia com rclone
      SRC_DIR=$(dirname "$fpath")
      FNAME=$(basename "$fpath")

      if rclone copyto "$fpath" "${GDRIVE_REMOTE}:${DEST_FOLDER}/${FNAME}" \
          "${RCLONE_FLAGS[@]}" 2>/dev/null; then
        sqlite3 "$DB_PATH" \
          "UPDATE files SET status='DONE', dest_path='${DEST_FOLDER}/${FNAME}' WHERE id=$fid;"
        MIGRATED=$((MIGRATED + 1))
      else
        sqlite3 "$DB_PATH" \
          "UPDATE files SET status='ERROR', error='rclone copy failed' WHERE id=$fid;"
        ERRORS=$((ERRORS + 1))
        warn "Erro: $fname → $GDRIVE_REVIEW"
        # Move para revisão em vez de falhar
        rclone copyto "$fpath" "${GDRIVE_REMOTE}:99_Sistema/Revisao-Migracao/${FNAME}" \
          --retries=3 2>/dev/null || true
      fi

    done <<< "$BATCH"

    OFFSET=$((OFFSET + BATCH_SIZE))
    log "Progresso: $MIGRATED migrados, $ERRORS erros (offset $OFFSET/$PENDING)"
  done

  ok "Migração concluída: $MIGRATED arquivos, $ERRORS erros"
  echo "$MIGRATED|$ERRORS" > /tmp/mt_migrate_result.txt
}

# ─────────────────────────────────────────────────────────────
# CLASSIFICADOR (simples, sem IA, baseado em regras)
# ─────────────────────────────────────────────────────────────
classify_file() {
  local name="$1" ext="$2" path="$3"
  local ext_lower="${ext,,}"

  # Por tipo de arquivo
  case "$ext_lower" in
    jpg|jpeg|png|gif|webp|heic|heif|raw|cr2|nef|arw)
      echo "06_Mídia/Fotos" ;;
    mp4|mov|avi|mkv|m4v|wmv|mts)
      echo "06_Mídia/Videos" ;;
    mp3|m4a|aac|wav|flac|aiff|opus)
      echo "06_Mídia/Audios" ;;
    pdf)
      # PDF: verifica se parece documento ou livro
      if echo "$name" | grep -qiE 'livro|book|chapter|cap[ií]tulo'; then
        echo "04_Conhecimento/Livros"
      else
        echo "03_Documentos/PDFs"
      fi
      ;;
    doc|docx|odt)
      echo "03_Documentos/Word" ;;
    xls|xlsx|csv|numbers)
      echo "03_Documentos/Planilhas" ;;
    ppt|pptx|key)
      echo "03_Documentos/Apresentacoes" ;;
    md|txt|rtf)
      echo "04_Conhecimento/Notas" ;;
    zip|rar|7z|tar|gz)
      echo "07_Arquivos/Comprimidos" ;;
    sh|py|js|ts|json|yaml|yml|toml)
      echo "08_Engenharia/Codigo" ;;
    *)
      echo "📥 INBOX/iCloud-Migration/Sem-Classificacao" ;;
  esac
}

# ─────────────────────────────────────────────────────────────
# RELATÓRIO FINAL
# ─────────────────────────────────────────────────────────────
report() {
  log "=== RELATÓRIO FINAL ==="

  TOTAL=$(sqlite3 "$DB_PATH"    "SELECT COUNT(*) FROM files;")
  DONE=$(sqlite3 "$DB_PATH"     "SELECT COUNT(*) FROM files WHERE status='DONE';")
  PENDING=$(sqlite3 "$DB_PATH"  "SELECT COUNT(*) FROM files WHERE status='PENDING';")
  ERRORS=$(sqlite3 "$DB_PATH"   "SELECT COUNT(*) FROM files WHERE status='ERROR';")

  echo ""
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}  EXECUÇÃO CONCLUÍDA${NC}"
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo "  arquivos processados: $TOTAL"
  echo "  migrados:             $DONE"
  echo "  pendentes:            $PENDING"
  echo "  revisão:              $ERRORS"
  echo "  log:                  $LOG_DIR/"
  echo "  índice:               $DB_PATH"
  echo ""
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

  if [ "$ERRORS" -gt 0 ]; then
    warn "Arquivos com erro foram copiados para: gdrive:99_Sistema/Revisao-Migracao"
    warn "Verifique: sqlite3 $DB_PATH \"SELECT name, error FROM files WHERE status='ERROR';\""
  fi
}

# ─────────────────────────────────────────────────────────────
# APPLE NOTES — EXPORTAÇÃO (AppleScript)
# ─────────────────────────────────────────────────────────────
export_notes() {
  log "=== EXPORTANDO APPLE NOTES ==="
  NOTES_DIR="$HOME/MT.OS/notes_export"
  mkdir -p "$NOTES_DIR"

  osascript << 'APPLESCRIPT'
tell application "Notes"
  set notesList to every note
  repeat with aNote in notesList
    set noteTitle to name of aNote
    set noteBody to body of aNote
    set noteDate to modification date of aNote
    -- Sanitize filename
    set safeName to do shell script "echo " & quoted form of noteTitle & " | tr '/:*?\"<>|\\\\' '_' | cut -c1-100"
    set fileName to (POSIX path of (path to home folder)) & "MT.OS/notes_export/" & safeName & ".html"
    set fileRef to open for access POSIX file fileName with write permission
    set eof of fileRef to 0
    write noteBody to fileRef
    close access fileRef
  end repeat
end tell
APPLESCRIPT

  NOTE_COUNT=$(find "$NOTES_DIR" -name "*.html" | wc -l | tr -d ' ')
  ok "Apple Notes exportadas: $NOTE_COUNT notas → $NOTES_DIR"

  if [ "$NOTE_COUNT" -gt 0 ] && [ "$DRY_RUN" = false ]; then
    log "Enviando notas para Google Drive..."
    rclone copy "$NOTES_DIR" "${GDRIVE_REMOTE}:04_Conhecimento/Notas/AppleNotes" \
      --transfers=4 --retries=5 --stats=10s 2>/dev/null
    ok "Notas enviadas para Drive"
  fi
}

# ─────────────────────────────────────────────────────────────
# --check: O QUE JÁ FOI COPIADO
# ─────────────────────────────────────────────────────────────
check_copied() {
  log "=== CHECK — O QUE JÁ FOI COPIADO ==="

  if [ ! -f "$DB_PATH" ]; then
    warn "Índice não encontrado ($DB_PATH). Rode primeiro sem --check para indexar."
    exit 0
  fi

  TOTAL=$(sqlite3    "$DB_PATH" "SELECT COUNT(*) FROM files;")
  DONE=$(sqlite3     "$DB_PATH" "SELECT COUNT(*) FROM files WHERE status='DONE';")
  PENDING=$(sqlite3  "$DB_PATH" "SELECT COUNT(*) FROM files WHERE status='PENDING';")
  ERRORS=$(sqlite3   "$DB_PATH" "SELECT COUNT(*) FROM files WHERE status='ERROR';")

  # Bytes copiados
  BYTES_DONE=$(sqlite3 "$DB_PATH" \
    "SELECT COALESCE(SUM(size_bytes),0) FROM files WHERE status='DONE';")
  BYTES_ALL=$(sqlite3 "$DB_PATH" \
    "SELECT COALESCE(SUM(size_bytes),0) FROM files;")

  human_size() {
    local b=$1
    if   [ "$b" -ge 1073741824 ]; then printf "%.1f GB" "$(echo "scale=1; $b/1073741824" | bc)"
    elif [ "$b" -ge 1048576 ];    then printf "%.1f MB" "$(echo "scale=1; $b/1048576"    | bc)"
    elif [ "$b" -ge 1024 ];       then printf "%.1f KB" "$(echo "scale=1; $b/1024"       | bc)"
    else printf "%d B" "$b"; fi
  }

  PCT=0
  [ "$TOTAL" -gt 0 ] && PCT=$(( DONE * 100 / TOTAL ))

  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BLUE}  RELATÓRIO — O QUE JÁ FOI COPIADO${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  printf "  Total indexado : %d arquivos (%s)\n" "$TOTAL" "$(human_size $BYTES_ALL)"
  printf "  ✅ Copiados     : %d arquivos (%s) — %d%%\n" "$DONE" "$(human_size $BYTES_DONE)" "$PCT"
  printf "  ⏳ Pendentes    : %d arquivos\n" "$PENDING"
  printf "  ❌ Com erro     : %d arquivos\n" "$ERRORS"
  echo ""

  # Barra de progresso visual
  BAR_DONE=$(( PCT / 5 ))
  BAR_EMPTY=$(( 20 - BAR_DONE ))
  printf "  Progresso: ["
  printf '%0.s█' $(seq 1 $BAR_DONE 2>/dev/null)
  printf '%0.s░' $(seq 1 $BAR_EMPTY 2>/dev/null)
  printf "] %d%%\n" "$PCT"
  echo ""

  # Lista últimos 10 copiados
  echo "  Últimos 10 copiados:"
  sqlite3 "$DB_PATH" \
    "SELECT name, dest_path, size_bytes FROM files
     WHERE status='DONE' ORDER BY rowid DESC LIMIT 10;" \
    | while IFS='|' read -r n d s; do
        printf "    ✅ %-40s → %s\n" "$n" "$d"
      done

  echo ""

  # Lista erros (se houver)
  if [ "$ERRORS" -gt 0 ]; then
    echo "  Arquivos com erro (máx 10):"
    sqlite3 "$DB_PATH" \
      "SELECT name, error FROM files WHERE status='ERROR' LIMIT 10;" \
      | while IFS='|' read -r n e; do
          printf "    ❌ %-40s — %s\n" "$n" "$e"
        done
    echo ""
    echo "  Para reprocessar os erros:"
    echo "    sqlite3 $DB_PATH \"UPDATE files SET status='PENDING' WHERE status='ERROR';\""
    echo "    bash mt_migrate.sh --phase 3"
  fi

  # Verifica Drive ao vivo (opcional — pode ser lento)
  if command -v rclone &>/dev/null && rclone listremotes | grep -q "^gdrive:"; then
    log "Verificando Drive ao vivo (amostra de 20 arquivos DONE)..."
    MISSING=0
    sqlite3 "$DB_PATH" \
      "SELECT dest_path FROM files WHERE status='DONE' AND dest_path IS NOT NULL LIMIT 20;" \
      | while IFS= read -r dest; do
          if ! rclone lsf "${GDRIVE_REMOTE}:${dest}" &>/dev/null; then
            warn "  Não encontrado no Drive: $dest"
            MISSING=$((MISSING + 1))
          fi
        done
    if [ "$MISSING" -eq 0 ]; then
      ok "Amostra Drive: todos os 20 verificados existem no destino"
    else
      warn "$MISSING arquivos da amostra não encontrados no Drive — rode --phase 3 para recopiar"
      # Marca como PENDING para reprocessar
      sqlite3 "$DB_PATH" \
        "UPDATE files SET status='PENDING' WHERE status='DONE' AND dest_path IN (
           SELECT dest_path FROM files WHERE status='DONE' LIMIT 20
         );" 2>/dev/null || true
    fi
  fi

  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
main() {
  echo ""
  echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║   MT.OS — MIGRAÇÃO iCLOUD → GOOGLE DRIVE ║${NC}"
  echo -e "${BLUE}║   Fase: $PHASE$(printf '%*s' $((36 - ${#PHASE})) '')║${NC}"
  echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
  echo ""

  # --check encerra aqui (não precisa de preflight completo)
  if [ "$CHECK_MODE" = true ]; then
    mkdir -p "$LOG_DIR"
    check_copied
    exit 0
  fi

  preflight
  snapshot

  case "$PHASE" in
    1|all)
      phase1_download_stubs
      ;;&
    2|all)
      phase2_index
      ;;&
    notes|all)
      export_notes
      ;;&
    3|all)
      phase3_migrate
      ;;
  esac

  report
}

main "$@"
