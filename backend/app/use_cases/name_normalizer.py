"""
Normalizador Inteligente de Nombres.

Responsabilidad: Recibir una lista de nombres crudos de un evento,
agrupar variantes que refieran a la misma persona y elegir el nombre
canónico (el más largo y completo).

Reglas clave:
 - Similitud difusa con threshold configurable (default 80 %).
 - Normalización de acentos y mayúsculas antes de comparar.
 - Regla de Oro: NO unificar si las iniciales de apellido son distintas
   (ej: "Juan M." vs "Juan P.").
 - Registro de cada decisión de unificación.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from thefuzz import fuzz

logger = logging.getLogger(__name__)

ILEGIBLE_TAG = "[NOMBRE ILEGIBLE]"


# ── Resultado de la unificación ──────────────────────────────────────

@dataclass
class UnificationResult:
    """Resultado completo del proceso de unificación de nombres."""
    canonical_map: dict[str, str]          # original → canónico
    groups: dict[str, list[str]]           # canónico → [variantes]
    decisions: list[str] = field(default_factory=list)  # log de decisiones


# ── Clase principal ──────────────────────────────────────────────────

class NameNormalizer:
    """
    Servicio de normalización inteligente de nombres.

    Flujo de unificación:
      1. Limpia acentos y casing para comparar.
      2. Compara todos los pares con similitud difusa.
      3. Aplica la Regla de Oro (iniciales de apellido distintas → no unificar).
      4. Agrupa con Union-Find y elige el canónico (nombre más largo).
      5. Devuelve el mapping, los grupos y el registro de decisiones.
    """

    def __init__(self, threshold: int = 80):
        self.threshold = threshold

    # ── API pública existente (compatibilidad) ───────────────────

    def similarity_score(self, name_a: str, name_b: str) -> int:
        """Calcula el score de similitud (0-100) entre dos nombres limpios.
        Usa fuzz.ratio (comparación estricta caracter a caracter)."""
        n1 = self._clean(name_a)
        n2 = self._clean(name_b)
        return fuzz.ratio(n1, n2)

    def _unification_score(self, name_a: str, name_b: str) -> int:
        """Score de similitud optimizado para unificación.
        Usa token_set_ratio que maneja bien nombres parciales/abreviados
        (ej: 'Jose L' vs 'Jose Luis Mastromano' → score alto)."""
        n1 = self._clean(name_a)
        n2 = self._clean(name_b)
        return fuzz.token_set_ratio(n1, n2)

    def are_similar(self, name_a: str, name_b: str) -> bool:
        """True si los nombres superan el umbral de similitud."""
        return self.similarity_score(name_a, name_b) >= self.threshold

    def normalize(self, text: str) -> str:
        """Limpia un nombre para usarlo como clave de comparación."""
        if not text:
            return ""
        return self._clean(text)

    def normalize_display(self, text: str) -> str:
        """Normaliza para presentación: Title Case, trim.
        Preserva [NOMBRE ILEGIBLE] sin modificar."""
        if not text:
            return ""
        text = text.strip()
        if text == ILEGIBLE_TAG:
            return text
        return " ".join(text.split()).title()

    # ── API nueva: unificación inteligente ───────────────────────

    def unify_names(self, names: list[str]) -> UnificationResult:
        """
        Recibe una lista de nombres (con posibles repeticiones) y agrupa
        las variantes que refieran a la misma persona.

        Retorna un UnificationResult con:
          - canonical_map: {nombre_original: nombre_canónico}
          - groups: {nombre_canónico: [variantes]}
          - decisions: lista legible de decisiones tomadas
        """
        # Descartar vacíos e ilegibles, quedarnos con únicos preservando orden
        unique: list[str] = list(dict.fromkeys(
            n for n in names if n and n.strip() and n != ILEGIBLE_TAG
        ))

        if len(unique) < 2:
            identity = {n: n for n in unique}
            groups = {n: [n] for n in unique}
            return UnificationResult(canonical_map=identity, groups=groups)

        # Union-Find
        parent: dict[str, str] = {n: n for n in unique}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra == rb:
                return
            # El nombre más largo queda como raíz (nombre canónico).
            # Si empatan en largo, el primero en aparecer gana.
            if len(ra) >= len(rb):
                parent[rb] = ra
            else:
                parent[ra] = rb

        decisions: list[str] = []

        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                a, b = unique[i], unique[j]

                # Ya están en el mismo grupo → saltar
                if find(a) == find(b):
                    continue

                score = self._unification_score(a, b)
                if score < self.threshold:
                    continue

                # ── Regla de Oro ──────────────────────────────────
                if self._have_conflicting_surname_initials(a, b):
                    clean_a = self._clean(a).upper()
                    clean_b = self._clean(b).upper()
                    decisions.append(
                        f"NO se unificó {clean_a} con {clean_b}: "
                        f"iniciales de apellido distintas (similitud: {score}%)."
                    )
                    logger.debug(
                        "[NameNormalizer] Regla de Oro bloqueó unión: '%s' vs '%s'",
                        a, b,
                    )
                    continue

                # Unir
                union(a, b)
                canonical = find(a)
                other = b if canonical == a else a
                clean_canonical = self._clean(canonical).upper()
                clean_other = self._clean(other).upper()

                decisions.append(
                    f"Se unificó {clean_other} con {clean_canonical} "
                    f"por alta similitud fonética/estructural (similitud: {score}%)."
                )

        # Construir mapa y grupos finales
        canonical_map: dict[str, str] = {}
        groups: dict[str, list[str]] = {}

        for name in unique:
            root = find(name)
            canonical_map[name] = root
            groups.setdefault(root, []).append(name)

        return UnificationResult(
            canonical_map=canonical_map,
            groups=groups,
            decisions=decisions,
        )

    # ── Regla de Oro ─────────────────────────────────────────────

    @staticmethod
    def _extract_surname_initial(name: str) -> str | None:
        """
        Extrae la inicial del apellido si se puede deducir.
        Reconoce patrones como:
          'Juan M'   → 'M'
          'Juan M.'  → 'M'
          'Juan Martinez' → 'M'
        Retorna None si el nombre tiene una sola parte (solo nombre de pila).
        """
        parts = name.strip().split()
        if len(parts) < 2:
            return None
        last = parts[-1].rstrip(".")
        if not last:
            return None
        return last[0].upper()

    def _have_conflicting_surname_initials(
        self, name_a: str, name_b: str
    ) -> bool:
        """
        Retorna True si ambos nombres muestran una inicial de apellido
        y esas iniciales son DISTINTAS.

        Solo aplica cuando ambos tienen la misma cantidad de partes.
        Si uno tiene más partes (ej: 'Jose L' vs 'Jose Luis Mastromano'),
        la última parte del más corto podría ser segundo nombre, no apellido.
        Si alguno no tiene apellido detectable, no hay conflicto.
        """
        clean_a = self._clean(name_a)
        clean_b = self._clean(name_b)

        parts_a = clean_a.split()
        parts_b = clean_b.split()

        # Solo aplicar cuando ambos tienen la misma estructura
        if len(parts_a) != len(parts_b):
            return False

        init_a = self._extract_surname_initial(clean_a)
        init_b = self._extract_surname_initial(clean_b)

        if init_a is None or init_b is None:
            return False

        return init_a != init_b

    # ── Limpieza interna ─────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        """Elimina acentos, normaliza espacios y pasa a minúsculas."""
        text = text.lower().strip()
        text = "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )
        # Normalizar espacios múltiples
        text = re.sub(r"\s+", " ", text)
        return text
