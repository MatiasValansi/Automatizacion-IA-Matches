"""
BDD Tests para el Motor de Cruce de Matches.
Sigue el ciclo RED -> GREEN -> REFACTOR.
"""

from pytest_bdd import scenarios, given, when, then, parsers
from app.core.entities import FormResult, Interaction, Participant, Match
from app.use_cases.match_engine import MatchEngine
from app.use_cases.name_normalizer import NameNormalizer
import pytest
import os
from pathlib import Path

# ... (tus otros imports)

# Calculamos la ruta absoluta al archivo .feature relativa a este archivo de test
BASE_DIR = Path(__file__).resolve().parent
FEATURE_FILE = BASE_DIR / ".." / "features" / "matches.feature"

# Vincula los escenarios usando la ruta calculada
scenarios(FEATURE_FILE)



@pytest.fixture
def engine():
    # Creamos el normalizador y se lo inyectamos al motor
    normalizer = NameNormalizer(threshold=85)
    return MatchEngine(normalizer=normalizer)

# ── Fixtures compartidos ─────────────────────────────────────────────

class MatchContext:
    """Objeto de contexto para transportar estado entre steps."""

    def __init__(self) -> None:
        self.form_results: list[FormResult] = []
        self.matches: list[Match] = []
        self._participants: dict[str, Participant] = {}

    def get_or_create_participant(self, name: str) -> Participant:
        if name not in self._participants:
            self._participants[name] = Participant(name=name)
        return self._participants[name]

    def get_form_result(self, participant: Participant) -> FormResult:
        for form in self.form_results:
            if form.owner == participant:
                return form
        new_form = FormResult(owner=participant)
        self.form_results.append(new_form)
        return new_form



@pytest.fixture
def context() -> MatchContext:
    return MatchContext()


# ── GIVEN ─────────────────────────────────────────────────────────────

@given(
    parsers.re(r'que "(?P<voter>.+)" votó "(?P<vote>.+)" a "(?P<candidate>.+)"'),
    target_fixture="context",
)
def voter_voted_for_candidate(
    context: MatchContext, voter: str, vote: str, candidate: str
) -> MatchContext:
    """Registra el voto de un participante hacia otro."""
    participant = context.get_or_create_participant(voter)
    # Aseguramos que el candidato también exista en el registro
    context.get_or_create_participant(candidate)

    interested = vote.strip().lower() == "si"
    interaction = Interaction(receptor_name=candidate, interested=interested)

    form_result = context.get_form_result(participant)
    form_result.interactions.append(interaction)

    return context


# ── WHEN ──────────────────────────────────────────────────────────────

@when("el motor de cruce procesa las respuestas", target_fixture="context")
def engine_processes_responses(context: MatchContext, engine: MatchEngine) -> MatchContext:
    """Ejecuta el caso de uso puro de detección de matches usando el motor inyectado."""
    # Ahora usamos el engine que ya viene con el normalizador configurado
    context.matches = engine.find_matches(context.form_results)
    return context


# ── THEN ──────────────────────────────────────────────────────────────

@then(
    parsers.re(r'se debe identificar un match entre "(?P<person_a>.+)" y "(?P<person_b>.+)"')
)
def match_should_be_identified(
    context: MatchContext, person_a: str, person_b: str
) -> None:
    """Verifica que el match mutuo fue detectado."""
    matched_pairs: set[frozenset[str]] = {
        frozenset({m.person_a.name, m.person_b.name}) for m in context.matches
    }
    expected_pair = frozenset({person_a, person_b})

    assert expected_pair in matched_pairs, (
        f"Match esperado entre '{person_a}' y '{person_b}' no encontrado.\n"
        f"Matches detectados: {[{m.person_a.name, m.person_b.name} for m in context.matches]}"
    )
    
@then("no se debe identificar ningún match")
def no_match_identified(context: MatchContext) -> None:
    """
    Verifica que la lista de matches esté vacía.
    Esto confirma que el motor filtró correctamente la falta de reciprocidad.
    """
    assert len(context.matches) == 0, f"Se encontraron {len(context.matches)} matches inesperados."
    
@then('se debe identificar un match entre "Matías" y "Sofía"')
def verificar_match_con_tildes(context: MatchContext) -> None:
    assert len(context.matches) == 1
    # Verificamos que, a pesar de las tildes, el motor los unió
    match = context.matches[0]
    nombres = [match.person_a.name, match.person_b.name]
    assert "Matías" in nombres or "Matias" in nombres
    assert "Sofía" in nombres or "Sofia" in nombres    