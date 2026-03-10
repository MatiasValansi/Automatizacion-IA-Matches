"""
Aplicamos Inversión de Dependencias (D). Definimos qué necesitamos, no cómo se hace.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from .entities import AuditRecord, DuplicateMerge, Match, FormResult


class AIProvider(ABC):
    @abstractmethod    
    def extract_from_image(self, image_bytes: bytes) -> FormResult:
        """
        Contrato (Interfaz) para cualquier proveedor de IA.
        Sigue el Principio de Inversión de Dependencias (D en SOLID).
        """
        pass

    @abstractmethod
    def extract_batch(self, images_list: list[bytes]) -> list[FormResult]:
        """Procesa un lote de imágenes en un solo request (máx. 25)."""
        pass    
    
class MatchRepository(ABC):
    @abstractmethod
    def save_matches(
        self,
        event_name: str,
        form_results: list[FormResult],
        matches: list[Match],
        duplicate_merges: list[DuplicateMerge] | None = None,
    ) -> str | None:
        """
        Envía la data cruda (form_results), los matches mutuos y
        las decisiones de deduplicación al repositorio,
        para persistirlos en pestañas separadas.
        Retorna la URL de la hoja creada, o None si falla.
        """
        pass


class AuditRepository(ABC):
    """
    Contrato para el repositorio de Auditoría IA.
    Permite persistir y leer los resultados de extracción de la IA,
    incluyendo las correcciones humanas.
    DIP: el MatchEngine depende de esta interfaz, no del adaptador concreto.
    """

    @abstractmethod
    def save_audit(
        self, event_name: str, records: list[AuditRecord]
    ) -> None:
        """Persiste los registros de extracción en la hoja 'Auditoría IA'."""
        pass

    @abstractmethod
    def get_audited_results(self, event_name: str) -> list[AuditRecord]:
        """
        Lee los registros auditados de la hoja 'Auditoría IA'.
        Incluye las correcciones humanas si las hubiera.
        """
        pass