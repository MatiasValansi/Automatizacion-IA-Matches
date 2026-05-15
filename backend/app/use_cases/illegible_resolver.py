"""
IllegibleResolver: asigna un nombre real a planillas cuyo propietario
el OCR no pudo leer.

Estrategia de cruce:
  Cada participante debería tener su propia planilla.
  Si "Carlos" aparece como receptor en planillas de otros pero
  no tiene planilla propia con nombre legible, y existe una planilla
  con propietario ilegible, es muy probable que esa planilla sea la de Carlos.

Algoritmo:
  1. Separa planillas legibles de ilegibles.
  2. Detecta "faltantes": personas votadas por otros que no tienen planilla propia.
  3. Para cada planilla ilegible, elige el mejor candidato faltante:
       - Si hay un único candidato → asignación directa (confianza 0.90).
       - Si hay varios → score por solapamiento: cuántos votantes del candidato
         también aparecen como receptores de la planilla ilegible.
  4. Si la confianza supera el umbral mínimo, reemplaza el nombre.
"""
from __future__ import annotations

import logging
from app.core.entities import FormResult, Participant
from app.use_cases.name_normalizer import ILEGIBLE_TAG

logger = logging.getLogger(__name__)


class IllegibleResolver:
    """Resuelve planillas con propietario ilegible por cruce con otras planillas."""

    MIN_CONFIDENCE = 0.5

    def resolve(
        self, form_results: list[FormResult]
    ) -> tuple[list[FormResult], list[dict]]:
        """
        Retorna (formularios_resueltos, lista_de_resoluciones).
        Planillas ilegibles que no se pueden resolver se mantienen sin cambio.
        """
        legible, illegible = self._split(form_results)

        if not illegible:
            return form_results, []

        # Personas votadas en cualquier planilla que no tienen planilla propia
        legible_owners = {f.owner.name for f in legible}
        all_voted_for = {
            inter.receptor_name
            for f in form_results
            for inter in f.interactions
            if inter.receptor_name and not inter.receptor_name.startswith("[")
        }
        candidates = list(all_voted_for - legible_owners)

        if not candidates:
            logger.warning(
                "[IllegibleResolver] %d planilla(s) ilegible(s) sin candidatos "
                "identificables en las demás planillas.",
                len(illegible),
            )
            return form_results, []

        resolved: list[FormResult] = list(legible)
        resolutions: list[dict] = []
        remaining = list(candidates)

        for form in illegible:
            name, confidence = self._best_match(form, legible, remaining)

            if name and confidence >= self.MIN_CONFIDENCE:
                resolved.append(
                    FormResult(
                        owner=Participant(name=name, phone=form.owner.phone),
                        interactions=form.interactions,
                    )
                )
                remaining.remove(name)
                resolutions.append({"resolved_as": name, "confidence": round(confidence, 2)})
                logger.info(
                    "[IllegibleResolver] Planilla ilegible resuelta como '%s' "
                    "(confianza: %.0f%%)",
                    name,
                    confidence * 100,
                )
            else:
                resolved.append(form)
                logger.warning(
                    "[IllegibleResolver] No se pudo resolver planilla ilegible. "
                    "Candidatos evaluados: %s",
                    remaining,
                )

        return resolved, resolutions

    # ── Privados ─────────────────────────────────────────────────────

    @staticmethod
    def _split(
        forms: list[FormResult],
    ) -> tuple[list[FormResult], list[FormResult]]:
        legible, illegible = [], []
        for f in forms:
            (illegible if (f.owner.name or "").startswith("[") else legible).append(f)
        return legible, illegible

    def _best_match(
        self,
        illeg_form: FormResult,
        legible_forms: list[FormResult],
        candidates: list[str],
    ) -> tuple[str | None, float]:
        if not candidates:
            return None, 0.0

        # Un único candidato: asignación directa con alta confianza
        if len(candidates) == 1:
            return candidates[0], 0.9

        illeg_voted_for = {inter.receptor_name for inter in illeg_form.interactions}

        scores: dict[str, float] = {}
        for candidate in candidates:
            # Quiénes de las planillas legibles votaron a este candidato
            candidate_voters = {
                f.owner.name
                for f in legible_forms
                for inter in f.interactions
                if inter.receptor_name == candidate
            }
            if not candidate_voters:
                scores[candidate] = 0.0
                continue

            # Score: solapamiento entre votantes del candidato y
            # personas a quienes la planilla ilegible votó
            overlap = candidate_voters & illeg_voted_for
            scores[candidate] = len(overlap) / max(
                len(candidate_voters), len(illeg_voted_for)
            )

        best = max(scores, key=lambda k: scores[k])
        return best, scores[best]
