from __future__ import annotations
import base64
import logging
from typing import TYPE_CHECKING
from app.core.entities import AuditRecord
from app.core.interfaces import AIProvider, AuditRepository, MatchRepository
from app.use_cases.match_engine import MatchEngine
from app.use_cases.duplicate_detector import DuplicateDetector
from app.services.image_optimizer import ImageOptimizer
from app.infrastructure.image_preprocessor import ImagePreprocessor
from app.services.result_cache import image_cache

# Evitamos colisiones de importación circular para el tipado
if TYPE_CHECKING:
    from app.core.entities import Match

logger = logging.getLogger(__name__)

class ProcessEventUseCase:
    """
    Orquestador del flujo de negocio. 
    Coordina la IA, la deduplicación, la auditoría,
    el motor de matches y la persistencia en Sheets.
    """

    def __init__(self, 
                 ai_provider: AIProvider, 
                 match_engine: MatchEngine, 
                 repository: MatchRepository,
                 audit_repo: AuditRepository,
                 duplicate_detector: DuplicateDetector):
        self.ai_provider = ai_provider
        self.match_engine = match_engine
        self.repository = repository
        self.audit_repo = audit_repo
        self.duplicate_detector = duplicate_detector

    def execute(self, event_name: str, images: list[bytes]) -> dict:
        """
        Flujo completo de procesamiento de un evento:

        FASE 1 – Extracción y Auditoría
          1. Verifica cache para cada imagen.
          2. Optimiza imágenes no cacheadas con ImageOptimizer.
          3. Extrae datos de las imágenes con Gemini.
          4. Cachea los resultados nuevos.
          5. Detecta nombres duplicados y unifica variantes.
          6. Persiste los resultados en la hoja 'Auditoría IA'.

        FASE 2 – Matches (post-auditoría)
          7. Lee los datos auditados (con posibles correcciones humanas).
          8. El motor de cruce calcula matches desde la auditoría.
          9. Persiste los matches en la hoja 'Matches'.

        Retorna un dict con toda la info relevante para el frontend.
        """
        all_results = []
        failed_images = []  # índices (1-based) de imágenes que fallaron
        pending_bytes: list[bytes] = []   # imágenes optimizadas a enviar por batch
        pending_indices: list[int] = []   # índice original de cada pending

        for idx, img_bytes in enumerate(images):
            img_b64 = base64.b64encode(img_bytes).decode()

            # 1. Verificar cache
            cached = image_cache.get(img_b64)
            if cached is not None:
                all_results.append(cached)
                continue

            # 2. Corregir perspectiva (deskew) + mejora contraste, luego optimizar
            deskewed_bytes = ImagePreprocessor.preprocess(img_bytes)
            deskewed_b64 = base64.b64encode(deskewed_bytes).decode()
            optimized_b64 = ImageOptimizer.optimize_base64(deskewed_b64)
            optimized_bytes = base64.b64decode(optimized_b64)
            pending_bytes.append(optimized_bytes)
            pending_indices.append(idx)

        # 3. Extraer datos con IA en batch (todas las no-cacheadas juntas)
        if pending_bytes:
            try:
                batch_results = self.ai_provider.extract_batch(pending_bytes)
                for i, result in enumerate(batch_results):
                    original_idx = pending_indices[i]
                    # 4. Guardar en cache
                    img_b64 = base64.b64encode(images[original_idx]).decode()
                    image_cache.set(img_b64, result)
                    all_results.append(result)
            except Exception as e:
                logger.error(f"[ProcessEvent] Batch falló: {e}")
                failed_images = [idx + 1 for idx in pending_indices]

        # Si no se pudo procesar ninguna imagen, lanzar error
        if not all_results:
            raise RuntimeError(
                f"No se pudo procesar ninguna imagen. "
                f"Fallaron: {len(failed_images)}/{len(images)}"
            )

        if failed_images:
            logger.warning(
                f"[ProcessEvent] {len(failed_images)} imagen(es) fallaron "
                f"(#{', #'.join(str(i) for i in failed_images)}). "
                f"Procesadas exitosamente: {len(all_results)}/{len(images)}"
            )

        # ── FASE 1: Unificación de nombres ─────────────────────────
        unified_results, duplicate_merges = self.duplicate_detector.detect_and_unify(
            all_results
        )

        # ── FASE 1b: Persistir en Auditoría IA ─────────────────────
        audit_records = self._form_results_to_audit_records(unified_results)
        self.audit_repo.save_audit(event_name, audit_records)

        # ── FASE 2: Matches desde datos auditados ──────────────────
        # El motor lee de 'Auditoría IA', priorizando correcciones
        # humanas sobre la extracción de la IA.
        matches = self.match_engine.find_matches_from_audit(event_name)

        # ── FASE 3: Persistencia de matches y data cruda ───────────
        sheet_url = self.repository.save_matches(
            event_name, unified_results, matches, duplicate_merges
        )

        return {
            "matches": matches,
            "sheet_url": sheet_url,
            "images_processed": len(all_results),
            "images_failed": len(failed_images),
            "failed_indices": failed_images,
            "duplicates_detected": len(duplicate_merges),
        }

    @staticmethod
    def _form_results_to_audit_records(
        form_results: list,
    ) -> list[AuditRecord]:
        """Convierte FormResults unificados en registros de auditoría."""
        records: list[AuditRecord] = []
        for form in form_results:
            for interaction in form.interactions:
                records.append(
                    AuditRecord(
                        extracted_name=form.owner.name,
                        voted_for=interaction.receptor_name,
                        interested=interaction.interested,
                        ai_confidence=interaction.confidence_score,
                    )
                )
        return records