"""
Detector de Nombres Duplicados.

Responsabilidad Única (SRP): Escanear todos los FormResult de un evento,
detectar nombres que refieren a la misma persona (variantes, typos, acentos)
y generar un reporte con las decisiones de unificación.

Principio Abierto/Cerrado (OCP): El umbral y la estrategia de similitud
se inyectan vía NameNormalizer, sin modificar esta clase.
"""

from __future__ import annotations

import logging
from collections import Counter

from app.core.entities import (
    DuplicateMerge,
    FormResult,
    Interaction,
    Participant,
)
from app.use_cases.name_normalizer import NameNormalizer

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """
    Detecta nombres duplicados/similares entre todas las planillas de un evento.
    Aplica clustering por similitud fuzzy (Union-Find) para unificar variantes
    de un mismo nombre.
    """

    def __init__(self, normalizer: NameNormalizer):
        self.normalizer = normalizer

    # ── API pública ───────────────────────────────────────────────────

    def detect_and_unify(
        self, form_results: list[FormResult]
    ) -> tuple[list[FormResult], list[DuplicateMerge]]:
        """
        Flujo completo:
        1. Recolecta todos los nombres que aparecen en las planillas.
        2. Compara pares y clusteriza los similares (Union-Find).
        3. Genera un reporte de decisiones (DuplicateMerge).
        4. Remplaza los nombres duplicados por su versión canónica.

        Returns:
            - unified_results: FormResults con nombres remapeados.
            - merges: Lista de decisiones para el reporte en Sheets.
        """
        all_names = self._collect_all_names(form_results)
        name_counts = Counter(all_names)
        unique_names = list(name_counts.keys())

        if len(unique_names) < 2:
            return form_results, []

        # Fase 1 — clustering
        name_mapping, merges = self._cluster_names(unique_names, name_counts)

        if not merges:
            return form_results, []

        logger.info(
            "[DuplicateDetector] Detectados %d duplicados → nombres unificados.",
            len(merges),
        )

        # Fase 2 — remapeo
        unified = self._apply_mapping(form_results, name_mapping)

        return unified, merges

    # ── Internals ─────────────────────────────────────────────────────

    def _collect_all_names(self, form_results: list[FormResult]) -> list[str]:
        """Recolecta cada aparición de nombre (owners + targets)."""
        names: list[str] = []
        for form in form_results:
            names.append(form.owner.name)
            for interaction in form.interactions:
                names.append(interaction.receptor_name)
        return names

    def _cluster_names(
        self,
        unique_names: list[str],
        name_counts: Counter,
    ) -> tuple[dict[str, str], list[DuplicateMerge]]:
        """
        Compara todos los pares y los agrupa con Union-Find.
        Retorna el mapping original→canónico y la lista de merges.
        """
        parent: dict[str, str] = {n: n for n in unique_names}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path compression
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra == rb:
                return
            # El nombre más frecuente (o más largo si empatan) queda como raíz.
            if (name_counts[ra], len(ra)) >= (name_counts[rb], len(rb)):
                parent[rb] = ra
            else:
                parent[ra] = rb

        merges: list[DuplicateMerge] = []

        for i in range(len(unique_names)):
            for j in range(i + 1, len(unique_names)):
                name_a = unique_names[i]
                name_b = unique_names[j]

                score = self.normalizer.similarity_score(name_a, name_b)

                if score >= self.normalizer.threshold:
                    # Antes de unir, guardamos la decisión
                    # El canónico es el que quedará como raíz tras union
                    union(name_a, name_b)
                    canonical = find(name_a)  # post-union root
                    other = name_b if canonical == name_a else name_a

                    merges.append(
                        DuplicateMerge(
                            name_a=name_a,
                            name_b=name_b,
                            canonical_name=canonical,
                            similarity_score=score,
                            decision=(
                                f"Se detectó que '{other}' es probablemente la misma "
                                f"persona que '{canonical}' (similitud: {score}%). "
                                f"Se unificaron bajo el nombre '{canonical}'."
                            ),
                        )
                    )

        # Construir mapping final: solo los nombres que cambian
        name_mapping: dict[str, str] = {}
        for name in unique_names:
            root = find(name)
            if root != name:
                name_mapping[name] = root

        return name_mapping, merges

    def _apply_mapping(
        self,
        form_results: list[FormResult],
        name_mapping: dict[str, str],
    ) -> list[FormResult]:
        """
        Aplica el mapeo de nombres a todos los FormResults, reemplazando
        nombres duplicados por su versión canónica.
        """
        remapped: list[FormResult] = []

        for form in form_results:
            owner_name = name_mapping.get(form.owner.name, form.owner.name)
            new_owner = Participant(name=owner_name, phone=form.owner.phone)

            new_interactions: list[Interaction] = []
            for interaction in form.interactions:
                target = name_mapping.get(
                    interaction.receptor_name, interaction.receptor_name
                )
                new_interactions.append(
                    Interaction(
                        receptor_name=target,
                        interested=interaction.interested,
                    )
                )

            remapped.append(FormResult(owner=new_owner, interactions=new_interactions))

        return remapped
