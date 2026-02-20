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

    def execute(self, images: list[bytes]) -> list[Match]:
        """
        Flujo de ejecución:
        1. Recibe una lista de imágenes (fotos de las planillas).
        2. Usa la IA para extraer la información de cada una.
        3. Pasa los resultados al motor para encontrar los matches.
        """
        all_results = []

        # 1. Fase de Extracción (Infrastructure -> Core)
        for image_bytes in images:
            # Gemini procesa la imagen y nos devuelve un FormResult
            form_result = self.ai_provider.extract_from_image(image_bytes)
            all_results.append(form_result)

        # 2. Fase de Cruce (Pure Domain Logic)
        # El motor ya tiene inyectado el Normalizer, así que los nombres se limpian solos
        matches = self.match_engine.find_matches(all_results)

        return matches