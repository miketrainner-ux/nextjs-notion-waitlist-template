/**
 * MT.OS Google Drive Organizer
 * Execute via: https://script.google.com → New Project → paste → Run organize()
 *
 * What this does:
 *  1. Scans source folders (unorganized buckets found during Drive scan)
 *  2. Classifies each file using keyword/path/extension rules (SmartClassifier logic)
 *  3. Moves files to the correct MT.OS domain folder
 *  4. Skips iCloud system files (plist, sqlite-wal, shadow, indexScores, etc.)
 *  5. Deduplicates: files in Bucket C (1xV7Kt3...) are identical to Bucket B → moves to trash
 *  6. Logs every operation to a Google Sheet named "MT.OS Log"
 */

// ── MT.OS Destination Folder IDs ──────────────────────────────────────────────
const DOMAINS = {
  D00: '1B6aUQRoESqp8o2tarlse5zCgd12Arc5Q', // 00_SYSTEM
  D10: '1CJImEH2p6phjfuYWDCGXt_pQLgczcvex', // 10_INBOX
  D20: '12gIwX4N0fL-0-erA-KStNvTP6SyvZG__', // 20_PROJECTS
  D40: '1e5BK2bCjDsqzkl08j6DqFHiXo-y02WJX', // 40_KNOWLEDGE
  D50: '15N8xPKHgfnOww38XZXdmhLYv6VKMiuYY', // 50_CREATION
  D60: '1Sg3jseMMEDuMo9Fc_Ffr7hDqHlXzIE-A', // 60_MEDIA
  D70: '1g6VsRP42__bKHOj2tqHPPeg-fg2EsGkT', // 70_BUSINESS
  D80: '1g2HGeIiFgKf32IeeUJ1mvHO2MFpOcJHO', // 80_PERSONAL
  D90: '1b2pFAIL6Cgc6e_t-B-GrZFTkTEwB9QFe', // 90_ARCHIVE
  D99: '156bSZj5fqG0pi7SFNFLriuX0hhLPmtnl', // 99_REVIEW

  // Level-2 subfolders (created on-demand by the hierarchy builder)
  MT_OS:      '1eXAXMf-Mb1Edl2qlMw8x3MHDPdSxSnf1', // 20/MT.OS
  MT_SPORTS:  '1RMPhZV0J2QbRd2oAAhteyclJdcvZuPHo', // 20/MT Sports
  CLIENTES:   '1S2ag8jqfISHo6f71Gyg5ducQhuIZPkKR', // 20/Clientes
};

// ── Source buckets to process ─────────────────────────────────────────────────
const SOURCE_FOLDERS = [
  '1cO7TYi548uYiHL9ORx2ypT9ITXDZgRfZ', // Bucket A – mixed user files
  '1hisErPSpYCr0gMP64QdycFcgBvV_PBr',  // Bucket B – WhatsApp export (~2300 files)
];

// Exact duplicates of Bucket B → send to trash instead of moving
const DUPLICATE_FOLDERS = [
  '1xV7Kt3BJX8vCRhM9cA5oI0b09yPY0rF-', // Bucket C – identical copy of Bucket B
];

// ── System file extensions/names to NEVER touch ───────────────────────────────
const SYSTEM_EXTENSIONS = new Set([
  'plist','sqlite','sqlite-wal','sqlite-shm','sqlite-lock',
  'cloudphotodb','cloudphotodb-wal','cloudphotodb-shm',
  'db','shadow','indexScores','indexIds','indexDirectory',
  'indexGroups','indexArrays','indexBigDates','indexPostings',
  'indexTermIds','indexCompactDirectory','indexHead',
  'directoryStoreFile','shadowIndexDirectory','shadowIndexTermIds',
  'shadowIndexArrays','shadowIndexHead','shadowIndexCompactDirectory',
  'shadowIndexGroups','header','toc','journal','plj','lock',
  'indexCounts','ivf-vector-indexes','partitions','state',
]);

const SYSTEM_NAME_PATTERNS = [
  /^live\.\d+\./i, /^dbStr-/i, /^clientstatesmetafile$/i,
  /^indexState$/i, /^analyticsCountData$/i, /Photos\.sqlite/i,
  /^psi\.sqlite/i, /\.plist$/i, /\.plj$/i,
  /^skg_events_/i, /^HistoryToken/i, /^Album/i,
  /^PhotoAnalysis/i, /^appPrivateData/i,
];

// ── Classification rules (keyword → destination folder ID) ────────────────────
const KEYWORD_RULES = [
  // 80_PERSONAL – certificates, travel, personal docs
  { words: ['certificado','certificate','marathon','city marathon'],     dest: DOMAINS.D80, label:'80_PERSONAL' },
  { words: ['travel_insurance','seguro','elegibilidade','elegibility'],  dest: DOMAINS.D80, label:'80_PERSONAL' },
  { words: ['comprovante','latam','voo','boarding'],                     dest: DOMAINS.D80, label:'80_PERSONAL' },

  // 70_BUSINESS – financial docs
  { words: ['extrato','poupanca','poupança','bancario','nf-e','nota fiscal','contrato'],
                                                                         dest: DOMAINS.D70, label:'70_BUSINESS' },

  // 20_PROJECTS/MT Sports – personal training
  { words: ['ketlebell','kettlebell','afundo','retrocesso','empurra','puxa',
            'personal trainer','personal training','training session','rotinas',
            'cookie cutter','pre-fadiga','pré-fadiga','potência','potencia',
            'mywellness','perfect trainer','nrru','clubbell','v9'],       dest: DOMAINS.MT_SPORTS, label:'20/MT Sports' },

  // 40_KNOWLEDGE – research papers, ebooks
  { words: ['barefoot','shod','foot core','footwear','kinematics','biomechanical',
            'habitual','hunter gathering','prospective','running injuries',
            'criatividade','inovacao','inovação'],                        dest: DOMAINS.D40, label:'40_KNOWLEDGE' },
  { words: ['ebook','livro','treinamento do core'],                      dest: DOMAINS.D40, label:'40_KNOWLEDGE' },
];

const MIME_RULES = [
  // Videos
  { pattern: /^video\//,   dest: DOMAINS.D60, label:'60_MEDIA' },
  // Images
  { pattern: /^image\//,   dest: DOMAINS.D60, label:'60_MEDIA' },
  // Audio
  { pattern: /^audio\//,   dest: DOMAINS.D60, label:'60_MEDIA' },
];

// ── Helpers ────────────────────────────────────────────────────────────────────
function isSystemFile(file) {
  const name = file.getName();
  const ext  = name.includes('.') ? name.split('.').pop().toLowerCase() : '';

  if (SYSTEM_EXTENSIONS.has(ext)) return true;
  for (const re of SYSTEM_NAME_PATTERNS) {
    if (re.test(name)) return true;
  }
  return false;
}

function classify(file) {
  const name     = file.getName().toLowerCase();
  const mimeType = file.getMimeType();

  // Keyword rules (highest priority)
  for (const rule of KEYWORD_RULES) {
    for (const word of rule.words) {
      if (name.includes(word)) return { folderId: rule.dest, label: rule.label };
    }
  }

  // WhatsApp PHOTO/VIDEO/STICKER numbered pattern → 60_MEDIA
  if (/^\d{5,}-(?:photo|video|sticker|audio)-\d{4}/i.test(name)) {
    return { folderId: DOMAINS.D60, label: '60_MEDIA' };
  }

  // MIME-type rules
  for (const rule of MIME_RULES) {
    if (rule.pattern.test(mimeType)) return { folderId: rule.dest, label: rule.label };
  }

  // Default: 99_REVIEW
  return { folderId: DOMAINS.D99, label: '99_REVIEW' };
}

// ── Logging sheet ─────────────────────────────────────────────────────────────
function getLogSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet() ||
    SpreadsheetApp.create('MT.OS Log');
  let sheet = ss.getSheetByName('Operations');
  if (!sheet) {
    sheet = ss.insertSheet('Operations');
    sheet.appendRow(['Timestamp','Action','File Name','From','To','Domain','Notes']);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function logOp(sheet, action, file, fromId, toId, domain, notes='') {
  sheet.appendRow([
    new Date().toISOString(),
    action,
    file.getName(),
    fromId,
    toId || '',
    domain || '',
    notes,
  ]);
}

// ── Main: organize() ──────────────────────────────────────────────────────────
function organize() {
  const log     = getLogSheet();
  let moved     = 0;
  let trashed   = 0;
  let skipped   = 0;
  let reviewed  = 0;

  // Phase 1: Trash exact duplicates (Bucket C)
  Logger.log('Phase 1: Trashing duplicate folders...');
  for (const folderId of DUPLICATE_FOLDERS) {
    try {
      const folder = DriveApp.getFolderById(folderId);
      const files  = folder.getFiles();
      while (files.hasNext()) {
        const f = files.next();
        if (isSystemFile(f)) { skipped++; continue; }
        f.setTrashed(true);
        logOp(log, 'TRASH', f, folderId, null, 'DUPLICATE');
        trashed++;
      }
      Logger.log(`  Trashed ${trashed} duplicates from ${folder.getName()}`);
    } catch (e) {
      Logger.log('  Error accessing folder ' + folderId + ': ' + e.message);
    }
  }

  // Phase 2: Classify & move files from source folders
  Logger.log('Phase 2: Classifying and moving files...');
  for (const folderId of SOURCE_FOLDERS) {
    try {
      const folder = DriveApp.getFolderById(folderId);
      const files  = folder.getFiles();
      Logger.log(`  Processing: ${folder.getName()} (${folderId})`);

      while (files.hasNext()) {
        const f = files.next();

        if (isSystemFile(f)) {
          skipped++;
          continue;
        }

        const { folderId: destId, label } = classify(f);
        const destFolder = DriveApp.getFolderById(destId);

        f.moveTo(destFolder);
        logOp(log, 'MOVE', f, folderId, destId, label);

        if (label === '99_REVIEW') reviewed++;
        else moved++;

        // Yield every 50 ops to avoid timeout
        if ((moved + reviewed) % 50 === 0) {
          Logger.log(`    ${moved + reviewed} files processed...`);
          Utilities.sleep(500);
        }
      }
    } catch (e) {
      Logger.log('  Error: ' + e.message);
    }
  }

  const summary = `DONE — Moved: ${moved} | To 99_REVIEW: ${reviewed} | Trashed (dups): ${trashed} | System skipped: ${skipped}`;
  Logger.log(summary);
  logOp(log, 'SUMMARY', {getName: () => summary}, '', '', '');
}

/**
 * Optional: run this first to do a DRY RUN (no actual moves, just logs what WOULD happen).
 * Change organize() to dryRun() in the Run menu to preview.
 */
function dryRun() {
  const log = getLogSheet();
  let count = 0;
  for (const folderId of [...SOURCE_FOLDERS, ...DUPLICATE_FOLDERS]) {
    try {
      const folder = DriveApp.getFolderById(folderId);
      const files  = folder.getFiles();
      while (files.hasNext()) {
        const f = files.next();
        if (isSystemFile(f)) continue;
        const { folderId: destId, label } = classify(f);
        const action = DUPLICATE_FOLDERS.includes(folderId) ? 'WOULD_TRASH' : `WOULD_MOVE → ${label}`;
        logOp(log, action, f, folderId, destId, label, 'DRY RUN');
        count++;
      }
    } catch (e) {
      Logger.log('Error: ' + e.message);
    }
  }
  Logger.log(`Dry run complete: ${count} files would be processed.`);
}
