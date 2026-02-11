from thefuzz import fuzz
import unicodedata

class NameNormalizer:
    """
    Servicio encargado de unificar criterios de nombres.
    Aplica el principio de Responsabilidad Única (SRP).
    """

    def __init__(self, threshold: int = 75):
        #threshold es el porcentaje mínimo de similitud para considerar dos nombres como iguales
        self.threshold = threshold

    def are_similar(self, name_a: str, name_b: str) -> bool:
        """
        Compara dos nombres y retorna True si superan el umbral de similitud.
        """
        # 1. Limpieza básica
        n1 = self._clean_string(name_a)
        n2 = self._clean_string(name_b)

        # 2. Cálculo de similitud (0 a 100)
        similarity = fuzz.ratio(n1, n2)
        
        return similarity >= self.threshold

    def _clean_string(self, text: str) -> str:
        """Normaliza tildes, quita espacios y pasa a minúsculas."""
        text = text.lower().strip()
        # Elimina acentos usando normalización Unicode
        text = "".join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )
        return text