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
    Delega la lógica de clustering y Regla de Oro al NameNormalizer.
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
        2. Delega la unificación inteligente al NameNormalizer.
        3. Convierte las decisiones en objetos DuplicateMerge.
        4. Reemplaza los nombres duplicados por su versión canónica.

        Returns:
            - unified_results: FormResults con nombres remapeados.
            - merges: Lista de decisiones para el reporte en Sheets.
        """
        all_names = self._collect_all_names(form_results)

        # Delegar toda la lógica de agrupamiento al normalizador
        result = self.normalizer.unify_names(all_names)

        # Construir merges solo para los nombres que cambiaron
        merges: list[DuplicateMerge] = []
        for canonical, variants in result.groups.items():
            for variant in variants:
                if variant != canonical:
                    score = self.normalizer.similarity_score(variant, canonical)
                    merges.append(
                        DuplicateMerge(
                            name_a=variant,
                            name_b=canonical,
                            canonical_name=canonical,
                            similarity_score=score,
                            decision=(
                                f"Se detectó que '{variant}' es probablemente la misma "
                                f"persona que '{canonical}' (similitud: {score}%). "
                                f"Se unificaron bajo el nombre '{canonical}'."
                            ),
                        )
                    )

        if not merges:
            return form_results, []

        logger.info(
            "[DuplicateDetector] Detectados %d duplicados → nombres unificados.",
            len(merges),
        )

        # Construir mapping solo con los que cambian
        name_mapping = {k: v for k, v in result.canonical_map.items() if k != v}

        # Remapear
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
