/**
 * ============================================================
 * MT.OS — Reorganizador de Pastas do Google Drive
 * ============================================================
 *
 * COMO USAR:
 *
 * 1. Suba o arquivo MT_OS_roteamento_v2.csv para a raiz do seu Drive.
 *    (https://drive.google.com → arrastar arquivo)
 *
 * 2. Acesse https://script.google.com → "Novo projeto".
 *
 * 3. Apague o código padrão e cole TODO este arquivo.
 *
 * 4. Configure abaixo (CONFIG):
 *      - CSV_NAME: nome exato do arquivo CSV no Drive
 *      - DRY_RUN: true para apenas simular (RECOMENDADO na 1ª execução)
 *      - MIN_CONFIANCA: % mínima para mover (ex: 80 = só alta confiança)
 *      - DESTINOS_PERMITIDOS: lista branca de destinos (vazio = todos)
 *      - MAX_PASTAS_POR_RUN: limite de pastas por execução (segurança)
 *
 * 5. Salve (Ctrl+S) → Executar → função `migrarMTOS`.
 *    Na 1ª vez vai pedir autorização. Aceitar.
 *
 * 6. Veja o log em "Execuções" (menu lateral).
 *    Erros e progresso ficam no log.
 *
 * 7. Quando estiver confortável: mude DRY_RUN para false e execute de novo.
 *
 * ============================================================
 * GARANTIAS DE SEGURANÇA
 * ============================================================
 *  ✓ NUNCA deleta nada — usa addFolder + removeFolder (mover, não apagar)
 *  ✓ Nunca toca em arquivos, só em pastas
 *  ✓ Pula pasta se já estiver no destino correto
 *  ✓ Pula pasta se source/destino não existirem mais
 *  ✓ Loga erro por linha sem abortar o run inteiro
 *  ✓ Limite por run pra você ir aos poucos
 *  ✓ MIN_CONFIANCA filtra fase 1 (só alta confiança) da fase 2 (média)
 * ============================================================
 */

// ============== CONFIG ==============
const CONFIG = {
  CSV_NAME: 'MT_OS_roteamento_v2.csv',
  RENAME_CSV_NAME: 'MT_OS_renomeacao.csv',
  DRY_RUN: true,
  MIN_CONFIANCA: 80,                  // % mínima p/ migrar pastas
  RENAME_CONFIANCAS: ['ALTA', 'MÉDIA'],  // níveis aceitos p/ renomear arquivos
  DESTINOS_PERMITIDOS: [],
  DESTINOS_BLOQUEADOS: [],
  MAX_PASTAS_POR_RUN: 200,
  MAX_RENOMEACOES_POR_RUN: 100,
  LOG_A_CADA: 25,
};
// ====================================

function migrarMTOS() {
  const t0 = Date.now();
  log_(`\n${'='.repeat(60)}`);
  log_(`MT.OS Reorganizador — ${CONFIG.DRY_RUN ? 'DRY RUN (simulação)' : 'EXECUÇÃO REAL'}`);
  log_(`Filtro: confiança ≥ ${CONFIG.MIN_CONFIANCA}%`);
  log_(`${'='.repeat(60)}\n`);

  const rows = lerCsv_(CONFIG.CSV_NAME);
  log_(`CSV carregado: ${rows.length} linhas`);

  const elegiveis = rows.filter(r => filtroLinha_(r));
  log_(`Elegíveis após filtro: ${elegiveis.length}`);
  const lote = elegiveis.slice(0, CONFIG.MAX_PASTAS_POR_RUN);
  log_(`Processando ${lote.length} nesta execução\n`);

  const stats = { ok: 0, jaNoDestino: 0, sourceNotFound: 0, destNotFound: 0, erro: 0, dryRun: 0 };

  for (let i = 0; i < lote.length; i++) {
    const r = lote[i];
    try {
      const res = moverPasta_(r);
      stats[res] = (stats[res] || 0) + 1;
    } catch (e) {
      stats.erro++;
      log_(`  ❌ ERRO em ${r.old_id} (${r.old_name}): ${e.message}`);
    }
    if ((i + 1) % CONFIG.LOG_A_CADA === 0) {
      log_(`  ... ${i + 1}/${lote.length} processadas`);
    }
  }

  const dt = ((Date.now() - t0) / 1000).toFixed(1);
  log_(`\n${'='.repeat(60)}`);
  log_(`Concluído em ${dt}s`);
  log_(`Movidas com sucesso: ${stats.ok}`);
  log_(`Já estavam no destino: ${stats.jaNoDestino || 0}`);
  log_(`Source não encontrado: ${stats.sourceNotFound || 0}`);
  log_(`Destino não encontrado: ${stats.destNotFound || 0}`);
  log_(`Dry-run (não executou): ${stats.dryRun || 0}`);
  log_(`Erros: ${stats.erro}`);
  log_(`Restantes elegíveis na fila: ${elegiveis.length - lote.length}`);
  log_(`${'='.repeat(60)}`);
}

function filtroLinha_(r) {
  const conf = parseInt(String(r.confianca).replace('%', ''), 10) || 0;
  if (conf < CONFIG.MIN_CONFIANCA) return false;
  if (!r.destino_id) return false;
  if (CONFIG.DESTINOS_PERMITIDOS.length && !CONFIG.DESTINOS_PERMITIDOS.some(d => r.destino_mtos.startsWith(d))) return false;
  if (CONFIG.DESTINOS_BLOQUEADOS.some(d => r.destino_mtos.startsWith(d))) return false;
  return true;
}

function moverPasta_(r) {
  let pasta;
  try { pasta = DriveApp.getFolderById(r.old_id); }
  catch (e) { return 'sourceNotFound'; }

  let destino;
  try { destino = DriveApp.getFolderById(r.destino_id); }
  catch (e) { return 'destNotFound'; }

  const paisAtuais = pasta.getParents();
  let paiId = null;
  if (paisAtuais.hasNext()) paiId = paisAtuais.next().getId();
  if (paiId === r.destino_id) return 'jaNoDestino';

  if (CONFIG.DRY_RUN) {
    log_(`  [DRY] "${r.old_name}" → ${r.destino_mtos}`);
    return 'dryRun';
  }

  // Move: adiciona ao novo pai e remove dos pais antigos
  destino.addFolder(pasta);
  const paisRm = pasta.getParents();
  while (paisRm.hasNext()) {
    const p = paisRm.next();
    if (p.getId() !== r.destino_id) p.removeFolder(pasta);
  }
  return 'ok';
}

function lerCsv_(nome) {
  const arqs = DriveApp.getFilesByName(nome);
  if (!arqs.hasNext()) throw new Error(`CSV não encontrado no Drive: "${nome}". Faça upload primeiro.`);
  const csv = arqs.next().getBlob().getDataAsString('UTF-8');
  const linhas = Utilities.parseCsv(csv);
  const header = linhas.shift();
  return linhas.map(l => {
    const obj = {};
    header.forEach((h, i) => obj[h] = l[i]);
    return obj;
  });
}

function log_(msg) {
  console.log(msg);
}

/**
 * Função auxiliar: roda só uma linha pelo ID, útil pra testar caso a caso.
 */
function testarUmaLinha(folderId) {
  const rows = lerCsv_(CONFIG.CSV_NAME);
  const r = rows.find(x => x.old_id === folderId);
  if (!r) { log_(`ID não encontrado no CSV: ${folderId}`); return; }
  log_(`Linha: ${JSON.stringify(r, null, 2)}`);
  log_(`Resultado: ${moverPasta_(r)}`);
}

/**
 * ============================================================
 * RENOMEAR ARQUIVOS — lê MT_OS_renomeacao.csv e aplica nomes novos.
 * ============================================================
 * Filtros: CONFIG.RENAME_CONFIANCAS (default: ALTA + MÉDIA)
 *          CONFIG.DRY_RUN
 *          CONFIG.MAX_RENOMEACOES_POR_RUN
 *
 * Garantias:
 *  ✓ Só renomeia (setName) — não move, não deleta, não toca conteúdo
 *  ✓ Pula se nome já está como o sugerido
 *  ✓ Pula se arquivo não existe mais
 *  ✓ Pula se nome sugerido está vazio ou igual ao atual
 */
function renomearArquivos() {
  const t0 = Date.now();
  log_(`\n${'='.repeat(60)}`);
  log_(`MT.OS Renomeação — ${CONFIG.DRY_RUN ? 'DRY RUN' : 'EXECUÇÃO REAL'}`);
  log_(`Confiança aceita: ${CONFIG.RENAME_CONFIANCAS.join(', ')}`);
  log_(`${'='.repeat(60)}\n`);

  const rows = lerCsv_(CONFIG.RENAME_CSV_NAME);
  log_(`CSV carregado: ${rows.length} linhas`);

  const elegiveis = rows.filter(r => filtroRename_(r));
  log_(`Elegíveis após filtro: ${elegiveis.length}`);
  const lote = elegiveis.slice(0, CONFIG.MAX_RENOMEACOES_POR_RUN);
  log_(`Processando ${lote.length} nesta execução\n`);

  const stats = { ok: 0, jaRenomeado: 0, sourceNotFound: 0, nomeIgual: 0, vazio: 0, erro: 0, dryRun: 0 };

  for (let i = 0; i < lote.length; i++) {
    const r = lote[i];
    try {
      const res = renomearArquivo_(r);
      stats[res] = (stats[res] || 0) + 1;
    } catch (e) {
      stats.erro++;
      log_(`  ❌ ERRO em ${r.file_id} (${r.nome_antigo}): ${e.message}`);
    }
    if ((i + 1) % CONFIG.LOG_A_CADA === 0) {
      log_(`  ... ${i + 1}/${lote.length}`);
    }
  }

  const dt = ((Date.now() - t0) / 1000).toFixed(1);
  log_(`\n${'='.repeat(60)}`);
  log_(`Concluído em ${dt}s`);
  log_(`Renomeados com sucesso: ${stats.ok}`);
  log_(`Já tinham o nome novo: ${stats.jaRenomeado || 0}`);
  log_(`Nome novo vazio/igual: ${(stats.nomeIgual || 0) + (stats.vazio || 0)}`);
  log_(`Source não encontrado: ${stats.sourceNotFound || 0}`);
  log_(`Dry-run (não executou): ${stats.dryRun || 0}`);
  log_(`Erros: ${stats.erro}`);
  log_(`Restantes na fila: ${elegiveis.length - lote.length}`);
  log_(`${'='.repeat(60)}`);
}

function filtroRename_(r) {
  if (!r.file_id || !r.nome_novo_sugerido) return false;
  const conf = String(r.confianca || '').toUpperCase();
  return CONFIG.RENAME_CONFIANCAS.some(c => conf.indexOf(c) === 0);
}

function renomearArquivo_(r) {
  let arq;
  try { arq = DriveApp.getFileById(r.file_id); }
  catch (e) { return 'sourceNotFound'; }

  const nomeAtual = arq.getName();
  const nomeNovo = String(r.nome_novo_sugerido || '').trim();
  if (!nomeNovo) return 'vazio';
  if (nomeAtual === nomeNovo) return 'jaRenomeado';

  if (CONFIG.DRY_RUN) {
    log_(`  [DRY] "${nomeAtual.substring(0, 40)}" → "${nomeNovo.substring(0, 50)}"`);
    return 'dryRun';
  }

  arq.setName(nomeNovo);
  return 'ok';
}

/**
 * Prévia de renomeações: mostra distribuição por confiança e quantos serão tocados.
 */
function previaRenomeacao() {
  const rows = lerCsv_(CONFIG.RENAME_CSV_NAME);
  const eleg = rows.filter(r => filtroRename_(r));
  const byConf = {};
  rows.forEach(r => {
    const k = String(r.confianca || '').split(' ')[0] || 'desconhecida';
    byConf[k] = (byConf[k] || 0) + 1;
  });
  log_(`\nTotal no CSV: ${rows.length}`);
  log_(`Elegíveis com filtro atual (${CONFIG.RENAME_CONFIANCAS.join(',')}): ${eleg.length}`);
  log_(`\nDistribuição por confiança:`);
  Object.entries(byConf).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => log_(`  ${v.toString().padStart(5)}  ${k}`));
}

/**
 * Função auxiliar: lista quantas pastas elegíveis existem por destino.
 */
function previaDistribuicao() {
  const rows = lerCsv_(CONFIG.CSV_NAME);
  const eleg = rows.filter(r => filtroLinha_(r));
  const counts = {};
  eleg.forEach(r => counts[r.destino_mtos] = (counts[r.destino_mtos] || 0) + 1);
  log_(`\nPrévia com filtro atual (conf>=${CONFIG.MIN_CONFIANCA}%):`);
  Object.entries(counts).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => log_(`  ${v.toString().padStart(5)}  →  ${k}`));
  log_(`Total elegível: ${eleg.length} de ${rows.length}`);
}
