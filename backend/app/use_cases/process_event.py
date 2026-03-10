from __future__ import annotations
import base64
import logging
from typing import TYPE_CHECKING
from app.core.interfaces import AIProvider, MatchRepository
from app.use_cases.match_engine import MatchEngine
from app.use_cases.duplicate_detector import DuplicateDetector
from app.services.image_optimizer import ImageOptimizer
from app.infrastructure.image_processor import ImageProcessor
from app.services.result_cache import image_cache

# Evitamos colisiones de importación circular para el tipado
if TYPE_CHECKING:
    from app.core.entities import Match

logger = logging.getLogger(__name__)

class ProcessEventUseCase:
    """
    Orquestador del flujo de negocio. 
    Coordina la IA, la deduplicación, el motor de matches y la persistencia en Sheets.
    """

    def __init__(self, 
                 ai_provider: AIProvider, 
                 match_engine: MatchEngine, 
                 repository: MatchRepository,
                 duplicate_detector: DuplicateDetector):
        self.ai_provider = ai_provider
        self.match_engine = match_engine
        self.repository = repository
        self.duplicate_detector = duplicate_detector

    def execute(self, event_name: str, images: list[bytes]) -> dict:
        """
        1. Verifica cache para cada imagen.
        2. Optimiza imágenes no cacheadas con ImageOptimizer.
        3. Extrae datos de las imágenes con Gemini.
        4. Cachea los resultados nuevos.
        5. Detecta nombres duplicados y unifica variantes.
        6. Procesa matches con el motor (incluye normalización).
        7. Persiste los resultados en la hoja de Google correspondiente.
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

            # 2. Corregir perspectiva (deskew) y luego optimizar
            deskewed_bytes = ImageProcessor.deskew(img_bytes)
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
        # Primero se analizan TODOS los nombres (owners + targets) y se
        # unifican variantes/typos bajo un nombre canónico.
        # Esto debe ocurrir ANTES de cualquier cálculo de votos o matches.
        unified_results, duplicate_merges = self.duplicate_detector.detect_and_unify(
            all_results
        )

        # ── FASE 2: Detección de matches (sobre datos unificados) ─────
        # El motor de cruce opera exclusivamente sobre los FormResults
        # ya unificados, garantizando que los votos de cada persona
        # se agrupan bajo su nombre canónico.
        matches = self.match_engine.find_matches(unified_results)

        # ── FASE 3: Persistencia (planilla + matches + duplicados) ────
        # Se envían los datos UNIFICADOS al repositorio para que las
        # planillas reflejen los nombres canónicos, no los originales.
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