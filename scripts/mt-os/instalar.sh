#!/bin/sh
# MT.OS — INSTALADOR SIMPLES
# sh instalar.sh

eval "$(/opt/homebrew/bin/brew shellenv zsh)" 2>/dev/null || true

# Garante que o diretório de logs existe antes de qualquer coisa
mkdir -p "$HOME/MT.OS/logs" "$HOME/MT.OS"

echo "Baixando script de migracao..."
curl -fsSL 'https://raw.githubusercontent.com/miketrainner-ux/nextjs-notion-waitlist-template/claude/mt-os-extraction-org-hzf9yq/scripts/mt-os/mt_migrate.sh' -o /tmp/mt_migrate.sh

echo "Iniciando migracao..."
bash /tmp/mt_migrate.sh
