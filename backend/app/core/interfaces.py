"""
Aplicamos Inversión de Dependencias (D). Definimos qué necesitamos, no cómo se hace.
"""

from abc import ABC, abstractmethod
from .entities import FormResult

class AIProvider(ABC):
    @abstractmethod
    def extract_from_image(self, image_bytes: bytes) -> FormResult:
        pass

class MatchRepository(ABC):
    @abstractmethod
    def save_matches(self, matches: list):
        pass