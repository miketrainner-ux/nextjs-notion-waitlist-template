#!/usr/bin/env python3
"""
MT.OS Quick Executor
Scan → Rename → Organize → Execute
Imediato, sem delays, direto ao ponto.
"""
import sys
import json
from datetime import datetime
from pathlib import Path
from .architecture import Domain, DomainRules, NamePattern, FileMetadata
from .drive_organizer import DriveOrganizer, ChaosDetector
from .executor import ExecutionPlan, SafetyChecks
from .index import SyncIndex
from .logger import SyncLogger
from .config import load_config


class QuickExecutor:
    def __init__(self, config):
        self.config = config
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logger = SyncLogger(config.log_dir, self.session_id)
        self.index = SyncIndex(config.index_db_path)
        self.organizer = DriveOrganizer(self.index, self.logger)
        self.executor = ExecutionPlan(self.logger, self.index, dry_run=False)

    def run(self):
        """Scan → Classify → Rename → Organize → Execute"""
        print(f"\n🚀 MT.OS Quick Executor [{self.session_id}]\n")

        # STEP 1: Simular scan (em produção, vem da Drive API)
        print("1️⃣  SCANNING FILES...")
        files = self._get_sample_files()
        print(f"   ✓ Encontrados {len(files)} arquivos\n")

        # STEP 2: Classificar e detectar problemas
        print("2️⃣  CLASSIFYING & DETECTING CHAOS...")
        metadatas = []
        renames_needed = []

        for file in files:
            meta = self._classify(file)
            metadatas.append(meta)

            # Se nome não segue padrão → rename
            if not NamePattern.is_valid(file['name']):
                renames_needed.append({
                    'uuid': meta.uuid,
                    'old': file['name'],
                    'new': meta.filename(),
                    'domain': meta.domain.value
                })

            if meta.confidence.name != 'ALTA':
                print(f"   ⚠️  {file['name']} → {meta.domain.value} ({meta.confidence.name})")

        print(f"   ✓ {len(metadatas)} classificados")
        print(f"   ✓ {len(renames_needed)} precisam renomear\n")

        # STEP 3: Gerar plano de moves
        print("3️⃣  PLANNING MOVES...")
        moves = []
        for meta in metadatas:
            if meta.confidence.name in ['ALTA', 'MEDIA']:
                moves.append({
                    'uuid': meta.uuid,
                    'name': meta.name,
                    'current': f"/root/{meta.name}",
                    'target': f"/root/{meta.full_path()}/{meta.filename()}",
                    'domain': meta.domain.value,
                    'confidence': meta.confidence.name
                })

        print(f"   ✓ {len(moves)} movimentos planejados")
        by_conf = {}
        for m in moves:
            c = m['confidence']
            by_conf[c] = by_conf.get(c, 0) + 1
        print(f"   ├─ ALTA: {by_conf.get('ALTA', 0)}")
        print(f"   ├─ MEDIA: {by_conf.get('MEDIA', 0)}")
        print(f"   └─ BAIXA: {len([m for m in metadatas if m.confidence.name in ['BAIXA', 'NENHUMA']])}\n")

        # STEP 4: Safety checks
        print("4️⃣  SAFETY CHECKS...")
        checks = SafetyChecks.pre_flight_check(metadatas, moves, files)
        if any(checks.values()):
            self.logger.error("safety_checks_failed", issues=checks)
            print("   ❌ FAILED\n")
            return 1
        print("   ✓ PASSED\n")

        # STEP 5: Execute renames
        print("5️⃣  RENAMING...")
        for rename in renames_needed[:20]:  # Limitar a 20 por batch
            print(f"   ⟳ {rename['old']}")
            print(f"     → {rename['new']}")
            self.executor.queue_rename(rename)

        results = self.executor.execute_batch(batch_size=50)
        print(f"   ✓ {results['executed']} renomeados\n")

        # STEP 6: Execute moves
        print("6️⃣  ORGANIZING...")
        for move in moves[:50]:  # Limitar a 50 por batch
            self.executor.queue_move(move)

        results = self.executor.execute_batch(batch_size=50)
        print(f"   ✓ {results['executed']} movidos")
        print(f"   ✓ Rollback log salvo: {results.get('rollback_ids', [])}\n")

        # STEP 7: Summary
        print("7️⃣  SUMMARY")
        print(f"   Session: {self.session_id}")
        print(f"   Files scanned: {len(files)}")
        print(f"   Files renamed: {len(renames_needed)}")
        print(f"   Files organized: {len(moves)}")
        print(f"   Execution: deterministic_local")
        print(f"   AI used: False\n")

        print("✅ COMPLETE\n")
        return 0

    def _get_sample_files(self):
        """Em produção, vem de Drive API. Aqui: sample para demo."""
        return [
            {'name': 'Documento.pdf', 'size': 500000, 'mimeType': 'application/pdf'},
            {'name': 'foto.jpg', 'size': 2000000, 'mimeType': 'image/jpeg'},
            {'name': 'vídeo.mp4', 'size': 500000000, 'mimeType': 'video/mp4'},
            {'name': 'planilha.xlsx', 'size': 1000000, 'mimeType': 'application/vnd.ms-excel'},
            {'name': 'relatório contrato.docx', 'size': 500000, 'mimeType': 'application/vnd.ms-word'},
            {'name': 'arquivo_temp.tmp', 'size': 100000, 'mimeType': 'application/octet-stream'},
        ]

    def _classify(self, file):
        """Classify single file"""
        domain, confidence = DomainRules.classify(
            file['name'],
            file.get('mimeType', ''),
            file.get('size', 0)
        )

        meta = FileMetadata(
            uuid=file['name'].replace('.', '_')[:20],
            name=file['name'],
            ext=file['name'].split('.')[-1].lower() if '.' in file['name'] else '',
            domain=domain,
            subdomain=DomainRules.recommend_subdomain(domain, file['name'], ''),
            confidence=confidence,
            size_bytes=file.get('size', 0),
            mime_type=file.get('mimeType', ''),
        )
        return meta


def main():
    config = load_config()
    executor = QuickExecutor(config)
    return executor.run()


if __name__ == "__main__":
    sys.exit(main())
