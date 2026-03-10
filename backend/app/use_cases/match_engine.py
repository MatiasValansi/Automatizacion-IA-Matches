"""
Motor de Cruce de Matches.

Responsabilidad Única (SRP): Detectar matches mutuos a partir de
resultados de formularios ya procesados.

Inversión de Dependencias (DIP): depende de la interfaz AuditRepository,
no de la implementación concreta de Google Sheets.
"""
from collections import defaultdict

from app.core.entities import AuditRecord, FormResult, Interaction, Match, Participant
from app.core.interfaces import AuditRepository
from app.use_cases.name_normalizer import NameNormalizer


class MatchEngine:    
    """Detecta matches mutuos entre participantes."""

    def __init__(self, normalizer: NameNormalizer, audit_repo: AuditRepository):
        self.normalizer = normalizer
        self.audit_repo = audit_repo

    # ── Flujo principal: lee de Auditoría IA ────────────────────
    def find_matches_from_audit(self, event_name: str) -> list[Match]:
        """
        1. Lee los registros auditados (incluye correcciones humanas).
        2. Reconstruye FormResults priorizando Corrección_Humana > IA.
        3. Ejecuta el algoritmo de cruce sobre datos auditados.
        """
        audit_records = self.audit_repo.get_audited_results(event_name)
        form_results = self._build_form_results_from_audit(audit_records)
        return self.find_matches(form_results)

    # ── Algoritmo puro (sin I/O) ───────────────────────────────
    def find_matches(self, form_results: list[FormResult]) -> list[Match]:
        """
        Algoritmo:
        1. Construye un grafo dirigido de interés (A -> B).
        2. Detecta aristas bidireccionales (A -> B AND B -> A).
        3. Retorna matches únicos sin duplicados.

        Complejidad: O(n·m) donde n = participantes, m = interacciones promedio.
        """
        interest_graph = self._build_interest_graph(form_results)
        return self._detect_mutual_matches(interest_graph, form_results)

    def _build_interest_graph(
        self, form_results: list[FormResult]
    ) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {}

        for form in form_results:
            # NORMALIZAMOS el nombre del dueño de la planilla
            voter_name = self.normalizer.normalize(form.owner.name)
            interested_in: set[str] = set()

            for interaction in form.interactions:
                if interaction.interested:
                    # NORMALIZAMOS el nombre de la persona votada
                    target_name = self.normalizer.normalize(interaction.receptor_name)
                    interested_in.add(target_name)

            if interested_in:
                # Mergeamos intereses si el owner ya existe (posible tras unificación)
                if voter_name in graph:
                    graph[voter_name] |= interested_in
                else:
                    graph[voter_name] = interested_in

        return graph

    def _detect_mutual_matches(
        self,
        interest_graph: dict[str, set[str]],
        form_results: list[FormResult],
    ) -> list[Match]:
        """
        Detecta aristas bidireccionales en el grafo de interés.
        Usa un set de pares ya procesados para evitar duplicados
        (A,B) y (B,A) generan un solo Match.
        """
        participants_by_name = self._index_participants(form_results)
        seen_pairs: set[frozenset[str]] = set()
        matches: list[Match] = []

        for person_a_name, interests in interest_graph.items():
            for person_b_name in interests:
                pair_key = frozenset({person_a_name, person_b_name})

                if pair_key in seen_pairs:
                    continue

                # Verificar reciprocidad: B también votó "Sí" a A
                if person_b_name in interest_graph and person_a_name in interest_graph[person_b_name]:
                    match = Match(
                        person_a=participants_by_name[person_a_name],
                        person_b=participants_by_name[person_b_name],
                    )
                    matches.append(match)
                    seen_pairs.add(pair_key)

        return matches

    def _index_participants(
        self, form_results: list[FormResult],
    ) -> dict[str, Participant]:
        index: dict[str, Participant] = {}
        for form in form_results:
            # Usamos el traductor para que la llave sea "limpia"
            clean_name = self.normalizer.normalize(form.owner.name)
            # Conservamos la primera ocurrencia (nombre canónico post-dedup)
            if clean_name not in index:
                index[clean_name] = form.owner
        return index

    # ── Conversión Auditoría → FormResult ───────────────────────
    @staticmethod
    def _resolve_interest(record: AuditRecord) -> bool:
        """Prioriza Corrección_Humana sobre la decisión de la IA."""
        if record.human_correction and record.human_correction.strip():
            return record.human_correction.strip().upper() == "SI"
        return record.interested

    def _build_form_results_from_audit(
        self, records: list[AuditRecord]
    ) -> list[FormResult]:
        """
        Agrupa los AuditRecords por dueño de planilla y reconstruye
        los FormResult con las interacciones ya corregidas.
        """
        groups: dict[str, list[AuditRecord]] = defaultdict(list)
        for record in records:
            groups[record.extracted_name].append(record)

        form_results: list[FormResult] = []
        for owner_name, owner_records in groups.items():
            interactions = [
                Interaction(
                    receptor_name=r.voted_for,
                    interested=self._resolve_interest(r),
                    confidence_score=r.ai_confidence,
                )
                for r in owner_records
            ]
            form_results.append(
                FormResult(
                    owner=Participant(name=owner_name),
                    interactions=interactions,
                )
            )
        return form_results