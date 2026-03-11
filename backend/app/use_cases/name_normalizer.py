from thefuzz import fuzz
import unicodedata

ILEGIBLE_TAG = "[NOMBRE ILEGIBLE]"

class NameNormalizer:
    """
    Servicio encargado de unificar criterios de nombres.
    Aplica el principio de Responsabilidad Única (SRP).
    """

    def __init__(self, threshold: int = 80):
        #threshold es el porcentaje mínimo de similitud para considerar dos nombres como iguales
        self.threshold = threshold

    def similarity_score(self, name_a: str, name_b: str) -> int:
        """
        Calcula y retorna el score de similitud (0-100) entre dos nombres
        después de limpiarlos.
        """
        n1 = self._clean_string(name_a)
        n2 = self._clean_string(name_b)
        return fuzz.ratio(n1, n2)

    def are_similar(self, name_a: str, name_b: str) -> bool:
        """
        Compara dos nombres y retorna True si superan el umbral de similitud.
        """
        return self.similarity_score(name_a, name_b) >= self.threshold
    
    def normalize(self, text: str) -> str:
        """Método público que el MatchEngine usará para limpiar llaves."""
        if not text:
            return ""
        # Reutilizamos tu lógica de limpieza
        return self._clean_string(text)

    def normalize_display(self, text: str) -> str:
        """Normaliza un nombre para presentación: Title Case, trim espacios.
        Preserva [NOMBRE ILEGIBLE] sin modificar."""
        if not text:
            return ""
        text = text.strip()
        if text == ILEGIBLE_TAG:
            return text
        return " ".join(text.split()).title()

    def _clean_string(self, text: str) -> str:
        """Normaliza tildes, quita espacios y pasa a minúsculas."""
        text = text.lower().strip()
        # Elimina acentos usando normalización Unicode
        text = "".join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )
        return text