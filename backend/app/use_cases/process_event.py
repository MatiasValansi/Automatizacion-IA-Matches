from __future__ import annotations
import base64
import logging
from typing import TYPE_CHECKING
from app.core.interfaces import AIProvider, MatchRepository
from app.use_cases.match_engine import MatchEngine
from app.use_cases.duplicate_detector import DuplicateDetector
from app.services.image_optimizer import ImageOptimizer
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

        for idx, img_bytes in enumerate(images):
            img_b64 = base64.b64encode(img_bytes).decode()

            # 1. Verificar cache
            cached = image_cache.get(img_b64)
            if cached is not None:
                all_results.append(cached)
                continue

            # 2. Optimizar imagen antes de enviar a Gemini
            optimized_b64 = ImageOptimizer.optimize_base64(img_b64)
            optimized_bytes = base64.b64decode(optimized_b64)

            # 3. Extraer datos con IA (con tolerancia a fallos)
            try:
                result = self.ai_provider.extract_from_image(optimized_bytes)
            except Exception as e:
                logger.error(
                    f"[ProcessEvent] Imagen {idx + 1}/{len(images)} falló: {e}"
                )
                failed_images.append(idx + 1)
                continue

            # 4. Guardar en cache
            image_cache.set(img_b64, result)
            all_results.append(result)

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

        # Fase de deduplicación: detectar nombres similares y unificarlos
        unified_results, duplicate_merges = self.duplicate_detector.detect_and_unify(
            all_results
        )

        # Fase de cruce (usa los nombres ya unificados)
        matches = self.match_engine.find_matches(unified_results)

        # Fase de persistencia: data cruda + matches + reporte de duplicados
        sheet_url = self.repository.save_matches(
            event_name, all_results, matches, duplicate_merges
        )

        return {
            "matches": matches,
            "sheet_url": sheet_url,
            "images_processed": len(all_results),
            "images_failed": len(failed_images),
            "failed_indices": failed_images,
            "duplicates_detected": len(duplicate_merges),
        }