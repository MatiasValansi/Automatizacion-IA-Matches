from app.core.interfaces import AIProvider
from app.use_cases.match_engine import MatchEngine
from app.core.entities import Match

class ProcessEventUseCase:
    """
    Director de Orquesta: Coordina el flujo completo del evento.
    Sigue el principio de Responsabilidad Única (SRP).
    """

    def __init__(self, ai_provider: AIProvider, match_engine: MatchEngine):
        # Inyectamos las dependencias para que el caso de uso no esté "acoplado"
        self.ai_provider = ai_provider
        self.match_engine = match_engine

    def execute(self, event_name: str, images: list[bytes]) -> list[Match]:
        # 1. IA extrae datos
        all_results = [self.ai_provider.extract_from_image(img) for img in images]

        # 2. Motor encuentra matches
        matches = self.match_engine.find_matches(all_results)

        # 3. Guardamos usando el nombre del evento como identificador
        if matches:
            self.repository.save_matches(event_name, matches)

        return matches