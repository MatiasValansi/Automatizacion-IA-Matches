"""
Motor de Cruce de Matches.

Responsabilidad Única (SRP): Detectar matches mutuos a partir de
resultados de formularios ya procesados.

No depende de infraestructura — es una función pura del dominio.
"""

from app.core.entities import FormResult, Match, Participant


class MatchEngine:
    """Detecta matches mutuos entre participantes."""

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
        """
        Construye un grafo dirigido: { voter_name: {candidate_name, ...} }
        Solo incluye aristas donde interested == True.
        """
        graph: dict[str, set[str]] = {}

        for form in form_results:
            voter_name = form.owner.name
            interested_in: set[str] = set()

            for interaction in form.interactions:
                if interaction.interested:
                    interested_in.add(interaction.receptor_name)

            if interested_in:
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

    @staticmethod
    def _index_participants(
        form_results: list[FormResult],
    ) -> dict[str, Participant]:
        """Crea un índice name -> Participant para lookup O(1)."""
        index: dict[str, Participant] = {}
        for form in form_results:
            index[form.owner.name] = form.owner
        return index