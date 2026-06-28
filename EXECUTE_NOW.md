# MT.OS — Execute Agora

**Scan → Rename → Organize → Complete**

```bash
# 1. Setup (se não feito)
pip install -r mt_sync_engine/requirements.txt

# 2. Configure
export NOTION_TOKEN=your_token
export OBSIDIAN_VAULT_PATH=/path/to/vault

# 3. EXECUTE
python -m mt_sync_engine.quick_executor
```

---

## O que acontece:

```
1️⃣  SCANNING
   ✓ Varre todos os arquivos
   ✓ Detecta: nomes ruins, pastas vazias, duplicatas, arquivos temporários

2️⃣  CLASSIFYING
   ✓ Classifica em 11 domínios por contexto (não por tipo)
   ✓ Calcula confiança (ALTA, MEDIA, BAIXA)

3️⃣  PLANNING
   ✓ Cria plano de movimentação
   ✓ Safety checks (sem overwrites, sem conflitos)

4️⃣  RENAMING
   ✓ Renomeia para padrão: YYYY-MM-DD_Subject_V01.ext
   ✓ Sem espaços, sem caracteres inválidos

5️⃣  ORGANIZING
   ✓ Move para pasta correta baseado em contexto
   ✓ ALTA confidence: automático
   ✓ MEDIA: flag para revisão
   ✓ BAIXA: vai para 99_REVISÃO

6️⃣  ROLLBACK SAVED
   ✓ Se algo der errado: 1 comando restaura tudo
```

---

## Resultado:

```
Antes (Caos):
├── Downloads/
│   ├── Documento.pdf
│   ├── foto.jpg
│   ├── vídeo.mp4
│   └── relatório contrato.docx
└── Projects/
    └── ... (desordenado)

Depois (Organizado):
├── 00_Sistema/
├── 01_Entrada/
├── 02_Projetos/
├── 03_Pessoas/
├── 04_Conhecimento/     ← Documento.pdf vai aqui
│   ├── Livros/
│   ├── Papers/
│   └── Pesquisas/
├── 05_Conteúdo/
├── 06_Mídia/            ← foto.jpg, vídeo.mp4 vão aqui
│   ├── Fotos/
│   └── Vídeos/
├── 07_Empresa/          ← relatório, contrato vão aqui
│   └── Contratos/
└── 99_Revisão/          ← O que não se classificou
    └── Baixa_Confianca/
```

---

## Padrão de arquivo

**Antes:** `Documento.pdf`, `foto.jpg`, `relatório contrato.docx`
**Depois:** `2026-06-27_Documento_V01.pdf`, `2026-06-27_Foto_V01.jpg`

Sempre: `YYYY-MM-DD_Subject_V01.ext`

---

## Se algo der errado:

```bash
# Rollback (restaura estado anterior)
python -m mt_sync_engine.architecture_main --rollback
```

Simples. Rápido. Seguro.

---

## Next steps depois:

```bash
# 1. Revisar 99_REVISÃO (arquivos com baixa confiança)
# 2. Aprovar MEDIA flagged files
# 3. Sincronizar com Notion/Obsidian:
python -m mt_sync_engine.main

# 4. Schedule daily:
0 2 * * * python -m mt_sync_engine.main
```

---

**Status: Pronto. Execute agora.**
