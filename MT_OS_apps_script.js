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

/**
 * ============================================================
 * DESIGN SYSTEM MT.OS — Cores + Ícones por categoria
 * ============================================================
 *
 * REQUER habilitar Advanced Drive Service:
 *   No editor → Serviços (+) → Drive API → Adicionar (id: Drive)
 *
 * Cores: paleta oficial Drive (folderColorRgb).
 * Ícones: emojis universais prefixados ao nome da pasta.
 *
 * EXECUTE em ordem:
 *   1) aplicarCoresMTOS()    — pinta 11 mães + sub-mães-chave
 *   2) aplicarIconesMTOS()   — prefixa emoji ao nome
 *
 * SEGURANÇA: só altera metadata (cor) e nome (prefixo emoji).
 * Não move, não deleta, não toca conteúdo. DRY_RUN respeitado.
 *
 * LÓGICA SEMÂNTICA DE CORES:
 *   AZUL   = sistema/infra (frio, estável)
 *   ROXO   = inbox/transição (em processamento)
 *   LARANJA= projetos ativos (energia, prazo)
 *   VERDE  = áreas da vida (crescimento contínuo)
 *   AMARELO= conhecimento (sabedoria, atenção)
 *   VERMELHO=criação (paixão, output autoral)
 *   ROSA   = mídia (visual, sensorial)
 *   CINZA  = negócio (formal, profissional)
 *   MARROM = pessoal (íntimo, terra)
 *   CINZA-CLARO=arquivo (dormente)
 *   AREIA  = revisão (atenção requerida)
 */

const MTOS_DESIGN = {
  // ===== 11 MÃES OFICIAIS =====
  '1B6aUQRoESqp8o2tarlse5zCgd12Arc5Q': { nome: '00_SYSTEM',    icone: '⚙️', cor: '#4986e7' },
  '1CJImEH2p6phjfuYWDCGXt_pQLgczcvex': { nome: '10_INBOX',     icone: '📥', cor: '#b99aff' },
  '12gIwX4N0fL-0-erA-KStNvTP6SyvZG__': { nome: '20_PROJECTS',  icone: '🚀', cor: '#ff7537' },
  '1e5BK2bCjDsqzkl08j6DqFHiXo-y02WJX': { nome: '40_KNOWLEDGE', icone: '📚', cor: '#ffad46' },
  '15N8xPKHgfnOww38XZXdmhLYv6VKMiuYY': { nome: '50_CREATION',  icone: '🎨', cor: '#f83a22' },
  '1Sg3jseMMEDuMo9Fc_Ffr7hDqHlXzIE-A': { nome: '60_MEDIA',     icone: '🎬', cor: '#f691b2' },
  '1g6VsRP42__bKHOj2tqHPPeg-fg2EsGkT': { nome: '70_BUSINESS',  icone: '💼', cor: '#8f8f8f' },
  '1g2HGeIiFgKf32IeeUJ1mvHO2MFpOcJHO': { nome: '80_PERSONAL',  icone: '❤️', cor: '#ac725e' },
  '1b2pFAIL6Cgc6e_t-B-GrZFTkTEwB9QFe': { nome: '90_ARCHIVE',   icone: '📦', cor: '#cabdbf' },
  '156bSZj5fqG0pi7SFNFLriuX0hhLPmtnl': { nome: '99_REVIEW',    icone: '⚠️', cor: '#fbe983' },

  // ===== 30_AREAS — três tons de verde =====
  '1sKg_cI7ZnP8Ql6YafIOFyfSs7XEwzqM8': { nome: 'Corpo',      icone: '💪', cor: '#16a765' },
  '1pggTB9hPdF7f50-Zzt7f74GWW1I4fqp0': { nome: 'Mente',      icone: '🧠', cor: '#42d692' },
  '1JS6C8Y9czSd2Zyn2poafQ964C3c94VL2': { nome: 'Observador', icone: '👁️', cor: '#b3dc6c' },

  // ===== 20_PROJECTS — sub-marcas (laranja/coral) =====
  '1eXAXMf-Mb1Edl2qlMw8x3MHDPdSxSnf1': { nome: 'MT.OS',                       icone: '🧬', cor: '#ff7537' },
  '1RMPhZV0J2QbRd2oAAhteyclJdcvZuPHo': { nome: 'MT Sports',                   icone: '🏃', cor: '#ff7537' },
  '1S2ag8jqfISHo6f71Gyg5ducQhuIZPkKR': { nome: 'Clientes',                    icone: '🤝', cor: '#ff7537' },
  '1SUn6jcqVWq1KCqHyXk1BwkIUVLeX55l6': { nome: 'Michael Trainer Inteligente', icone: '🤖', cor: '#fa573c' },

  // ===== 40_KNOWLEDGE — saberes =====
  '1u1Bw8iJyiHA9tiqvMHwy1YLR1xNVpwOQ': { nome: 'Livros',       icone: '📖', cor: '#fad165' },
  '1osFiWei1Ths_GO9Kao1ZB2V7cIdC5-3c': { nome: 'Matricologia', icone: '🌐', cor: '#fbe983' },

  // ===== 60_MEDIA — Fotos =====
  '1XnU-r5_jas_YWvbQnH_-RdcUtXyMT7B0': { nome: 'Fotos', icone: '📸', cor: '#f691b2' },

  // ===== 70_BUSINESS — Financeiro =====
  '11LmyhhlH_wVdCmdYvEzlObIrBk_rW6L-': { nome: 'Financeiro', icone: '💰', cor: '#cabdbf' },

  // ===== 90_ARCHIVE — Repositório Permanente =====
  '1Qt0CTYoPTdkplGMXO0SiXntVe1oWU4Xe': { nome: 'Repositório Permanente', icone: '🗄️', cor: '#cabdbf' },
};

function aplicarCoresMTOS() {
  log_(`\n${'='.repeat(60)}`);
  log_(`MT.OS Design — Cores ${CONFIG.DRY_RUN ? '(DRY RUN)' : '(REAL)'}`);
  log_(`${'='.repeat(60)}\n`);
  let ok = 0, erro = 0, dry = 0;
  for (const [id, spec] of Object.entries(MTOS_DESIGN)) {
    try {
      if (CONFIG.DRY_RUN) {
        log_(`  [DRY] ${spec.nome.padEnd(40)} → ${spec.cor}`);
        dry++; continue;
      }
      Drive.Files.update({ folderColorRgb: spec.cor }, id);
      log_(`  ✓ ${spec.nome.padEnd(40)} → ${spec.cor}`);
      ok++;
    } catch (e) {
      erro++;
      log_(`  ❌ ${spec.nome}: ${e.message}`);
    }
  }
  log_(`\nOK: ${ok} | DRY: ${dry} | Erros: ${erro} | Total: ${Object.keys(MTOS_DESIGN).length}`);
}

function aplicarIconesMTOS() {
  log_(`\n${'='.repeat(60)}`);
  log_(`MT.OS Design — Ícones ${CONFIG.DRY_RUN ? '(DRY RUN)' : '(REAL)'}`);
  log_(`${'='.repeat(60)}\n`);
  let ok = 0, ja = 0, erro = 0, dry = 0;
  for (const [id, spec] of Object.entries(MTOS_DESIGN)) {
    try {
      const pasta = DriveApp.getFolderById(id);
      const nomeAtual = pasta.getName();
      if (nomeAtual.indexOf(spec.icone) === 0) { ja++; continue; }
      const limpo = nomeAtual.replace(/^[\p{Emoji}\s]+/u, '').trim() || spec.nome;
      const novoNome = `${spec.icone}  ${limpo}`;
      if (CONFIG.DRY_RUN) {
        log_(`  [DRY] "${nomeAtual}" → "${novoNome}"`);
        dry++; continue;
      }
      pasta.setName(novoNome);
      log_(`  ✓ ${novoNome}`);
      ok++;
    } catch (e) {
      erro++;
      log_(`  ❌ ${spec.nome}: ${e.message}`);
    }
  }
  log_(`\nOK: ${ok} | Já tinham: ${ja} | DRY: ${dry} | Erros: ${erro}`);
}

function aplicarDesignCompleto() {
  aplicarCoresMTOS();
  aplicarIconesMTOS();
}
