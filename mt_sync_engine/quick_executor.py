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
                    'target': f"/root/{meta.domain.value}/{meta.subdomain}/{meta.filename()}",
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
        """Classified files from MT.OS Drive scan (2026-06-28). Replace with live Drive API call in production."""
        return [
            # 80_PERSONAL
            {'name': 'travel_insurance_Oliveira_31023341808.pdf', 'driveId': '1rXkDj1IlCRWMVk9_p11JF1lDpg2dZCrO', 'size': 320000, 'mimeType': 'application/pdf', 'createdTime': '2023-10-01T00:00:00Z'},
            {'name': 'certificado_de_elegibilidade_31023341808.pdf', 'driveId': '1GuwSYBVh6H14T_PriAle37nf3gOQiBZy', 'size': 280000, 'mimeType': 'application/pdf', 'createdTime': '2023-10-01T00:00:00Z'},
            {'name': 'certificado_de_elegibilidade_27239184838.pdf', 'driveId': '11kA_u16oZZ_l81yfBgXG2oTVgacSHldQ', 'size': 280000, 'mimeType': 'application/pdf', 'createdTime': '2023-10-01T00:00:00Z'},
            {'name': 'Comprovante-LATAM-LA9578375EKLU.pdf', 'driveId': '1EHejl1qMawSvvA_vGnSHt8grqLtMwxV0', 'size': 150000, 'mimeType': 'application/pdf', 'createdTime': '2023-09-15T00:00:00Z'},
            {'name': '00001565-Certificado -SP CITY MARATHON 2022.pdf', 'driveId': '1eBBLFPq9o9uPnUi7WcF-UJfS-FyPHYMT', 'size': 500000, 'mimeType': 'application/pdf', 'createdTime': '2022-03-01T00:00:00Z'},
            # 20_PROJECTS/MT Sports
            {'name': 'Perfect Trainer | Aplicativo para Personal Trainers.pdf', 'driveId': '1kKoFSxNumyzmU8M32PmQn7Pj3q-Ln1nx', 'size': 1200000, 'mimeType': 'application/pdf', 'createdTime': '2023-05-10T00:00:00Z'},
            {'name': 'Afundo Lateral c_ Clean + Retrocesso com Ketlebell.mp4', 'driveId': '1jcKEdbth1zGYL_CRSBuSs0pfHDl5D51l', 'size': 85000000, 'mimeType': 'video/mp4', 'createdTime': '2022-08-20T00:00:00Z'},
            {'name': 'Empurra: Puxa [ Band + Peso ] .mp4', 'driveId': '1vraBYFJPLHRlKQ1BgaUx9uwVOEUKYnhl', 'size': 78000000, 'mimeType': 'video/mp4', 'createdTime': '2022-08-20T00:00:00Z'},
            {'name': 'Ketlebell Press.mov', 'driveId': '1BamqLBHBS5lhaSBlrlSURF0I4iYewOJn', 'size': 62000000, 'mimeType': 'video/quicktime', 'createdTime': '2022-08-20T00:00:00Z'},
            {'name': '00000249-COOKIE CUTTER.docx', 'driveId': '10tJHwpY9m4GqPuxmINy08Ic_cZNeI4jW', 'size': 45000, 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'createdTime': '2023-01-15T00:00:00Z'},
            {'name': '00000370-Michael - Potência.docx', 'driveId': '1seKZAC4xwS0Fwx3OD6ONcV9RuDDpMtm_', 'size': 52000, 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'createdTime': '2023-02-10T00:00:00Z'},
            {'name': '00000506-Michael Pré-Fadiga.docx', 'driveId': '1z1DaWlplFEwYLkL3jPyISIu0c-2Ny-UZ', 'size': 48000, 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'createdTime': '2023-03-05T00:00:00Z'},
            {'name': '00000136-Training Session Rotinas Santiago.pdf', 'driveId': '1vFc7IhbEiQhNN4v3kRnK-m5RC0XePYE5', 'size': 380000, 'mimeType': 'application/pdf', 'createdTime': '2022-12-01T00:00:00Z'},
            {'name': '00001002-V9 Kettlebell NRRU Clubbell.pdf', 'driveId': '1LiCykwvUL73HXUo0lFKSMZw9mMjob5Rb', 'size': 4200000, 'mimeType': 'application/pdf', 'createdTime': '2023-06-01T00:00:00Z'},
            # 40_KNOWLEDGE
            {'name': '00001207-Long-Term Effects of Habitual Barefoot review.pdf', 'driveId': '1l0pZQgmoHITBhRhG8AXq-oURIWGtlkZw', 'size': 1800000, 'mimeType': 'application/pdf', 'createdTime': '2023-07-01T00:00:00Z'},
            {'name': '00001203-Barefoot Versus Shoe Running From the Past to.pdf', 'driveId': '1q_xv_KXh2_2DmPvaTm5xRKUVqIRRHu-C', 'size': 2100000, 'mimeType': 'application/pdf', 'createdTime': '2023-07-01T00:00:00Z'},
            {'name': '00001206-From barefoot hunter gathering to shod.pdf', 'driveId': '1Wo4hu3UhNAUGVzVrVGo55GcxTqkGXiRA', 'size': 1950000, 'mimeType': 'application/pdf', 'createdTime': '2023-07-01T00:00:00Z'},
            {'name': '00001202-THE FOOT CORE SYSTEM.pdf', 'driveId': '1tZ-g395p-T63nTpv56RM2n7pj71jf9eO', 'size': 2300000, 'mimeType': 'application/pdf', 'createdTime': '2023-07-01T00:00:00Z'},
            {'name': '00000135-livro-digital-treinamento-do-core-em-3d.pdf', 'driveId': '1pKQAsLC2ER-SZOZQClWACfqfvqcGo6Pn', 'size': 8500000, 'mimeType': 'application/pdf', 'createdTime': '2022-11-01T00:00:00Z'},
            {'name': 'Criatividade-e-Inovacao-Francis-2018.pdf', 'driveId': '1bok4nLmwusCf53MwPvW2PCzXPn12PPPY', 'size': 3200000, 'mimeType': 'application/pdf', 'createdTime': '2022-09-15T00:00:00Z'},
        ]

    def _classify(self, file):
        """Classify single file"""
        domain, confidence = DomainRules.classify(
            file['name'],
            file.get('mimeType', ''),
            file.get('size', 0)
        )
        name = file['name']
        ext = name.split('.')[-1].lower() if '.' in name else ''
        meta = FileMetadata(
            uuid=file.get('driveId', name.replace('.', '_')[:20]),
            name=name,
            ext=ext,
            domain=domain,
            subdomain=DomainRules.recommend_subdomain(domain, name, ''),
            confidence=confidence,
            size_bytes=file.get('size', 0),
            mime_type=file.get('mimeType', ''),
            date_created=file.get('createdTime', ''),
        )
        return meta


def main():
    config = load_config()
    executor = QuickExecutor(config)
    return executor.run()


if __name__ == "__main__":
    sys.exit(main())
