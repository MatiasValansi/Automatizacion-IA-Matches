"""
Aplicamos Inversión de Dependencias (D). Definimos qué necesitamos, no cómo se hace.
"""

from abc import ABC, abstractmethod
from .entities import Match
from .entities import FormResult

class AIProvider(ABC):
    @abstractmethod    
    def extract_from_image(self, image_bytes: bytes) -> FormResult:
        """
        Contrato (Interfaz) para cualquier proveedor de IA.
        Sigue el Principio de Inversión de Dependencias (D en SOLID).
        """
        pass    
    
class MatchRepository(ABC):
    @abstractmethod
    def save_matches(
        self,
        event_name: str,
        form_results: list[FormResult],
        matches: list[Match],
    ) -> str | None:
        """
        Envía tanto la data cruda (form_results) como los matches mutuos
        al repositorio, para persistirlos en pestañas separadas.
        Retorna la URL de la hoja creada, o None si falla.
        """
        pass