from __future__ import annotations
import base64
import logging
from typing import TYPE_CHECKING
from app.core.interfaces import AIProvider, MatchRepository
from app.use_cases.match_engine import MatchEngine
from app.services.image_optimizer import ImageOptimizer
from app.services.result_cache import image_cache

# Evitamos colisiones de importación circular para el tipado
if TYPE_CHECKING:
    from app.core.entities import Match

logger = logging.getLogger(__name__)

class ProcessEventUseCase:
    """
    Orquestador del flujo de negocio. 
    Coordina la IA, el motor de matches y la persistencia en Sheets.
    """

    def __init__(self, 
                 ai_provider: AIProvider, 
                 match_engine: MatchEngine, 
                 repository: MatchRepository): # <--- AQUÍ ESTABA EL ERROR
        self.ai_provider = ai_provider
        self.match_engine = match_engine
        self.repository = repository

    def execute(self, event_name: str, images: list[bytes]) -> dict:
        """
        1. Verifica cache para cada imagen.
        2. Optimiza imágenes no cacheadas con ImageOptimizer.
        3. Extrae datos de las imágenes con Gemini.
        4. Cachea los resultados nuevos.
        5. Procesa matches con el motor (incluye normalización).
        6. Persiste los resultados en la hoja de Google correspondiente.
        Retorna un dict con toda la info relevante para el frontend.
        """
        all_results = []
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

            # 3. Extraer datos con IA
            result = self.ai_provider.extract_from_image(optimized_bytes)

            # 4. Guardar en cache
            image_cache.set(img_b64, result)
            all_results.append(result)

        # Fase de cruce
        matches = self.match_engine.find_matches(all_results)

        # Fase de persistencia: siempre guarda data cruda + matches (aunque no haya matches mutuos)
        sheet_url = self.repository.save_matches(event_name, all_results, matches)

        return {
            "matches": matches,
            "sheet_url": sheet_url,
            "images_processed": len(images),
        }