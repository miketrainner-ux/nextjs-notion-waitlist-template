#!/usr/bin/env bash
# MT.OS — APPLE NOTES → OBSIDIAN
# Converte notas exportadas (HTML) para Markdown com frontmatter YAML
# Execute: bash mt_notes_obsidian.sh [--vault /caminho/vault]
# ─────────────────────────────────────────────────────────────

set -euo pipefail

NOTES_SRC="$HOME/MT.OS/notes_export"
VAULT="${HOME}/MT.OS/obsidian-vault"
LOG_DIR="$HOME/MT.OS/logs"
DB_PATH="$HOME/MT.OS/index.db"

while [[ $# -gt 0 ]]; do
  case $1 in
    --vault) VAULT="$2"; shift 2 ;;
    *) echo "Arg desconhecido: $1"; exit 1 ;;
  esac
done

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_DIR/obsidian_$(date +%Y%m%d).log"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*" | tee -a "$LOG_DIR/obsidian_$(date +%Y%m%d).log"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_DIR/obsidian_$(date +%Y%m%d).log"; }

# ─── DEPENDÊNCIAS ─────────────────────────────────────────────
check_deps() {
  if ! command -v pandoc &>/dev/null; then
    log "Instalando pandoc (conversor HTML → Markdown)..."
    brew install pandoc
  fi
  ok "pandoc: $(pandoc --version | head -1)"
}

# ─── ESTRUTURA DO VAULT ────────────────────────────────────────
create_vault_structure() {
  log "Criando estrutura do vault Obsidian em: $VAULT"

  mkdir -p \
    "$VAULT/00 Inbox" \
    "$VAULT/01 Notas/Apple Notes" \
    "$VAULT/02 Projetos" \
    "$VAULT/03 Areas" \
    "$VAULT/04 Recursos" \
    "$VAULT/05 Arquivo" \
    "$VAULT/.obsidian"

  # Config mínimo do Obsidian
  cat > "$VAULT/.obsidian/app.json" << 'JSON'
{
  "defaultViewMode": "preview",
  "foldIndent": true,
  "showLineNumber": false,
  "spellcheck": false,
  "strictLineBreaks": false,
  "showFrontmatter": false
}
JSON

  # Habilita plugins essenciais
  cat > "$VAULT/.obsidian/core-plugins.json" << 'JSON'
["file-explorer","global-search","graph","backlink","outgoing-link","tag-pane","daily-notes","templates","starred","markdown-importer"]
JSON

  ok "Vault criado: $VAULT"
}

# ─── EXPORTAR NOTAS DO APPLE NOTES ────────────────────────────
export_apple_notes() {
  log "Exportando Apple Notes via AppleScript..."
  mkdir -p "$NOTES_SRC"

  osascript << 'APPLESCRIPT'
tell application "Notes"
  set notesList to every note
  repeat with aNote in notesList
    try
      set noteTitle to name of aNote
      set noteBody  to body of aNote
      set noteMod   to modification date of aNote
      set noteCreate to creation date of aNote

      -- Sanitiza nome do arquivo
      set safeName to do shell script "echo " & quoted form of noteTitle & " | tr '/:*?\"<>|\\\\' '_' | sed 's/^[[:space:]]*//' | cut -c1-120"
      if safeName is "" then set safeName to "nota-sem-titulo"

      -- Formato da data
      set dateStr to do shell script "date -j -f '%A, %B %e, %Y at %I:%M:%S %p' " & quoted form of ((noteMod as string)) & " '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S'"

      set fileName to (POSIX path of (path to home folder)) & "MT.OS/notes_export/" & safeName & ".html"
      set fileRef to open for access POSIX file fileName with write permission
      set eof of fileRef to 0
      write noteBody to fileRef
      close access fileRef
    on error errMsg
      -- continua para próxima nota
    end try
  end repeat
end tell
APPLESCRIPT

  NOTE_COUNT=$(find "$NOTES_SRC" -name "*.html" 2>/dev/null | wc -l | tr -d ' ')
  ok "Apple Notes exportadas: $NOTE_COUNT arquivos HTML"
}

# ─── CONVERTER HTML → MARKDOWN OBSIDIAN ───────────────────────
convert_to_markdown() {
  log "Convertendo HTML → Markdown com frontmatter..."

  CONVERTED=0
  SKIPPED=0
  ERRORS=0

  find "$NOTES_SRC" -name "*.html" 2>/dev/null | while IFS= read -r html_file; do
    BASENAME=$(basename "$html_file" .html)
    OUT_FILE="$VAULT/01 Notas/Apple Notes/${BASENAME}.md"

    # Skip se já convertido e mais recente
    if [ -f "$OUT_FILE" ] && [ "$OUT_FILE" -nt "$html_file" ]; then
      SKIPPED=$((SKIPPED + 1))
      continue
    fi

    # Detecta data pelo nome do arquivo (se houver padrão)
    FILE_DATE=$(stat -f"%Sm" -t"%Y-%m-%d" "$html_file" 2>/dev/null || date +%Y-%m-%d)
    FILE_MTIME=$(stat -f"%Sm" -t"%Y-%m-%dT%H:%M:%S" "$html_file" 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)

    # Converte HTML → Markdown via pandoc
    MD_BODY=$(pandoc \
      --from=html \
      --to=commonmark \
      --wrap=none \
      --strip-comments \
      "$html_file" 2>/dev/null) || { ERRORS=$((ERRORS + 1)); continue; }

    # Detecta tags simples do conteúdo
    TAGS=$(echo "$MD_BODY" | grep -oE '#[a-zA-Z][a-zA-Z0-9_-]+' | head -5 | tr '\n' ' ' | sed 's/ $//' || echo "")

    # Monta frontmatter YAML
    {
      echo "---"
      echo "title: \"${BASENAME}\""
      echo "created: ${FILE_DATE}"
      echo "modified: ${FILE_MTIME}"
      echo "source: apple-notes"
      echo "type: note"
      [ -n "$TAGS" ] && echo "tags: [${TAGS}]" || echo "tags: []"
      echo "---"
      echo ""
      echo "$MD_BODY"
    } > "$OUT_FILE"

    CONVERTED=$((CONVERTED + 1))

    # Registra no índice SQLite
    if [ -f "$DB_PATH" ]; then
      NAME_ESC="${BASENAME//\'/\'\'}"
      OUT_ESC="${OUT_FILE//\'/\'\'}"
      sqlite3 "$DB_PATH" \
        "INSERT OR IGNORE INTO files (name, origin_path, dest_path, type, status)
         VALUES ('$NAME_ESC.md', '$OUT_ESC', '$OUT_ESC', 'note', 'DONE');" 2>/dev/null || true
    fi

    [ $((CONVERTED % 50)) -eq 0 ] && log "  Convertidas: $CONVERTED notas..."
  done

  ok "Conversão concluída: $CONVERTED convertidas, $SKIPPED já existiam, $ERRORS erros"
}

# ─── CRIAR NOTA ÍNDICE ────────────────────────────────────────
create_index_note() {
  log "Criando nota índice do vault..."

  TOTAL_NOTES=$(find "$VAULT" -name "*.md" ! -name "_INDEX.md" 2>/dev/null | wc -l | tr -d ' ')
  TODAY=$(date +%Y-%m-%d)

  cat > "$VAULT/_INDEX.md" << EOF
---
title: "MT.OS — Índice do Vault"
created: ${TODAY}
type: index
tags: [mt-os, sistema, índice]
---

# MT.OS — Vault Obsidian

> Gerado automaticamente pelo MT.OS em ${TODAY}

## Estrutura

\`\`\`
00 Inbox/          ← notas brutas, ainda não processadas
01 Notas/          ← notas organizadas (Apple Notes migradas aqui)
02 Projetos/       ← notas por projeto ativo
03 Areas/          ← áreas de responsabilidade contínua
04 Recursos/       ← referências, livros, cursos
05 Arquivo/        ← material inativo
\`\`\`

## Status

- Total de notas: **${TOTAL_NOTES}**
- Última atualização: **${TODAY}**
- Fonte principal: Apple Notes

## Como usar

- Pesquisar tudo: \`Cmd + Shift + F\`
- Ver grafo: \`Cmd + Shift + G\`
- Nova nota rápida: \`Cmd + N\`

EOF

  ok "Nota índice criada: $VAULT/_INDEX.md"
}

# ─── SINCRONIZAR COM GOOGLE DRIVE ─────────────────────────────
sync_to_drive() {
  if ! command -v rclone &>/dev/null; then
    warn "rclone não instalado. Vault não sincronizado com Drive."
    return 0
  fi
  if ! rclone listremotes | grep -q "^gdrive:"; then
    warn "rclone remote 'gdrive' não configurado. Vault não sincronizado."
    return 0
  fi

  log "Sincronizando vault com Google Drive..."
  rclone copy "$VAULT" "gdrive:MT.OS-Obsidian" \
    --transfers=4 \
    --retries=5 \
    --exclude=".obsidian/**" \
    --stats=15s \
    2>/dev/null
  ok "Vault sincronizado: gdrive:MT.OS-Obsidian"
}

# ─── RELATÓRIO ────────────────────────────────────────────────
report() {
  TOTAL=$(find "$VAULT" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  SIZE=$(du -sh "$VAULT" 2>/dev/null | cut -f1)

  echo ""
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}  OBSIDIAN — CONCLUÍDO${NC}"
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo "  vault:          $VAULT"
  echo "  notas totais:   $TOTAL arquivos .md"
  echo "  tamanho:        $SIZE"
  echo "  drive:          gdrive:MT.OS-Obsidian"
  echo ""
  echo "  Para abrir no Obsidian:"
  echo "  → File → Open Vault → $VAULT"
  echo ""
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ─── MAIN ─────────────────────────────────────────────────────
main() {
  echo ""
  echo -e "\033[0;34m╔═══════════════════════════════════════════╗\033[0m"
  echo -e "\033[0;34m║   MT.OS — NOTES → OBSIDIAN                ║\033[0m"
  echo -e "\033[0;34m╚═══════════════════════════════════════════╝\033[0m"
  echo ""

  mkdir -p "$LOG_DIR"
  check_deps
  create_vault_structure
  export_apple_notes
  convert_to_markdown
  create_index_note
  sync_to_drive
  report
}

main "$@"
