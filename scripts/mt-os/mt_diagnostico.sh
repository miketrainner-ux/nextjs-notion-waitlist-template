#!/usr/bin/env bash
# MT.OS — DIAGNÓSTICO PRÉ-MIGRAÇÃO
# Roda antes do mt_migrate.sh para mapear exatamente o problema
# Execute: bash mt_diagnostico.sh

echo ""
echo "══════════════════════════════════════════"
echo "  MT.OS DIAGNÓSTICO — iCloud → Google Drive"
echo "══════════════════════════════════════════"
echo ""

ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs"

# 1. iCloud Drive
echo "── iCLOUD DRIVE ──────────────────────────"
if [ -d "$ICLOUD" ]; then
  echo "✅ Encontrado: $ICLOUD"
  TOTAL=$(find "$ICLOUD" -type f 2>/dev/null | wc -l | tr -d ' ')
  STUBS=$(find "$ICLOUD" -name "*.icloud" -type f 2>/dev/null | wc -l | tr -d ' ')
  REAL=$((TOTAL - STUBS))
  SIZE=$(du -sh "$ICLOUD" 2>/dev/null | cut -f1)
  echo "   Total arquivos : $TOTAL"
  echo "   Stubs (.icloud): $STUBS  ← ESTES SÃO O PROBLEMA"
  echo "   Arquivos reais : $REAL"
  echo "   Tamanho total  : $SIZE"
  echo ""
  echo "   Top 10 pastas por quantidade:"
  find "$ICLOUD" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | while read -r d; do
    COUNT=$(find "$d" -type f 2>/dev/null | wc -l | tr -d ' ')
    printf "   %5d  %s\n" "$COUNT" "$(basename "$d")"
  done | sort -rn | head -10
else
  echo "❌ iCloud Drive NÃO encontrado"
  echo "   → Abra Preferências do Sistema → Apple ID → iCloud → iCloud Drive ✓"
fi

echo ""
echo "── FERRAMENTAS ───────────────────────────"
for tool in rclone brew sqlite3 brctl; do
  if command -v "$tool" &>/dev/null; then
    echo "✅ $tool: $(command -v $tool)"
  else
    echo "❌ $tool: NÃO instalado"
  fi
done

echo ""
echo "── RCLONE REMOTES ────────────────────────"
if command -v rclone &>/dev/null; then
  REMOTES=$(rclone listremotes 2>/dev/null)
  if [ -z "$REMOTES" ]; then
    echo "❌ Nenhum remote configurado"
    echo "   → Execute: rclone config"
    echo "   → New remote → name: gdrive → Google Drive → autorize"
  else
    echo "$REMOTES" | while read -r r; do
      echo "   ✅ $r"
    done
    # Testa conectividade
    if rclone listremotes | grep -q "^gdrive:"; then
      if rclone lsf gdrive: --max-depth=1 &>/dev/null; then
        echo "   ✅ gdrive: conectado e acessível"
      else
        echo "   ❌ gdrive: configurado mas sem acesso (token expirado?)"
        echo "      → Execute: rclone config reconnect gdrive:"
      fi
    fi
  fi
else
  echo "❌ rclone não instalado → brew install rclone"
fi

echo ""
echo "── ESPAÇO DISPONÍVEL ─────────────────────"
df -h "$HOME" | tail -1 | awk '{printf "   Mac local: %s usados de %s (%s livre)\n", $3, $2, $4}'

echo ""
echo "── APPLE NOTES ───────────────────────────"
NOTES_DB="$HOME/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"
if [ -f "$NOTES_DB" ]; then
  NOTE_COUNT=$(sqlite3 "$NOTES_DB" "SELECT COUNT(*) FROM ZICCLOUDSYNCINGOBJECT WHERE ZTITLE1 IS NOT NULL;" 2>/dev/null || echo "?")
  echo "✅ Notes DB encontrado: ~$NOTE_COUNT notas"
else
  echo "⚠️  Notes DB não acessível diretamente (normal — usar AppleScript)"
fi

echo ""
echo "══════════════════════════════════════════"
echo "  PRÓXIMOS PASSOS:"
echo ""
echo "  1. Se stubs > 0:"
echo "     → Abra Finder → iCloud Drive"
echo "     → Clique direito na pasta raiz → 'Baixar agora'"
echo "     → Ou: brctl download ~/Library/Mobile\\ Documents/com~apple~CloudDocs"
echo ""
echo "  2. Se rclone não configurado:"
echo "     → rclone config"
echo "     → New remote → gdrive → Google Drive → autorize pelo browser"
echo ""
echo "  3. Quando tudo OK:"
echo "     → bash mt_migrate.sh --dry-run  (teste sem mover nada)"
echo "     → bash mt_migrate.sh            (migração real)"
echo ""
echo "  Fases separadas:"
echo "     → bash mt_migrate.sh --phase 1  (só baixar stubs)"
echo "     → bash mt_migrate.sh --phase 2  (só indexar)"
echo "     → bash mt_migrate.sh --phase 3  (só migrar)"
echo "══════════════════════════════════════════"
