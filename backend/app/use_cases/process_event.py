from __future__ import annotations
from typing import TYPE_CHECKING
from app.core.interfaces import AIProvider, MatchRepository
from app.use_cases.match_engine import MatchEngine

# Evitamos colisiones de importación circular para el tipado
if TYPE_CHECKING:
    from app.core.entities import Match

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

    def execute(self, event_name: str, images: list[bytes]) -> list[Match]:
        """
        1. Extrae datos de las imágenes con Gemini.
        2. Procesa matches con el motor (incluye normalización).
        3. Persiste los resultados en la hoja de Google correspondiente.
        """
        # Fase de extracción
        all_results = [self.ai_provider.extract_from_image(img) for img in images]

        # Fase de cruce
        matches = self.match_engine.find_matches(all_results)

        # Fase de persistencia dinámica
        if matches:
            self.repository.save_matches(event_name, matches)

        return matches