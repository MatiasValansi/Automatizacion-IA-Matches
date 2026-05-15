"""
Tests unitarios para ProcessEventUseCase._clean_form_results.
No requieren I/O real — todos los adaptadores externos son mocks.
"""

import logging
import pytest
from unittest.mock import MagicMock

from app.core.entities import FormResult, Interaction, Participant
from app.use_cases.process_event import ProcessEventUseCase
from app.use_cases.name_normalizer import NameNormalizer
from app.use_cases.duplicate_detector import DuplicateDetector
from app.use_cases.match_engine import MatchEngine


def _make_use_case() -> ProcessEventUseCase:
    normalizer = NameNormalizer()
    mock_audit_repo = MagicMock()
    mock_audit_repo.get_audited_results.return_value = []
    engine = MatchEngine(normalizer=normalizer, audit_repo=mock_audit_repo)
    detector = DuplicateDetector(normalizer=normalizer)
    return ProcessEventUseCase(
        ai_provider=MagicMock(),
        match_engine=engine,
        repository=MagicMock(),
        audit_repo=mock_audit_repo,
        duplicate_detector=detector,
        name_normalizer=normalizer,
    )


class TestLimpiezaDatos:

    def test_propietario_no_detectado_genera_warning(self, caplog):
        """Cuando Gemini devuelve [PROPIETARIO NO DETECTADO] como owner,
        el pipeline debe loguear una advertencia de emisor sospechoso."""
        use_case = _make_use_case()
        forms = [
            FormResult(
                owner=Participant(name="[PROPIETARIO NO DETECTADO]"),
                interactions=[Interaction(receptor_name="Ana", interested=True)],
            ),
        ]
        with caplog.at_level(logging.WARNING, logger="app.use_cases.process_event"):
            use_case._clean_form_results(forms)

        assert any(
            "sospechoso" in msg.lower() or "[PROPIETARIO NO DETECTADO]" in msg
            for msg in caplog.messages
        ), f"Se esperaba warning de emisor sospechoso. Mensajes: {caplog.messages}"

    def test_propietario_ilegible_genera_warning(self, caplog):
        """El tag 'ilegible' como owner también debe generar warning."""
        use_case = _make_use_case()
        forms = [
            FormResult(
                owner=Participant(name="ilegible"),
                interactions=[Interaction(receptor_name="Pedro", interested=False)],
            ),
        ]
        with caplog.at_level(logging.WARNING, logger="app.use_cases.process_event"):
            use_case._clean_form_results(forms)

        assert any("sospechoso" in msg.lower() for msg in caplog.messages)

    def test_interaccion_ilegible_se_descarta(self):
        """Interacciones con receptor [NOMBRE ILEGIBLE] no deben pasar al pipeline."""
        use_case = _make_use_case()
        forms = [
            FormResult(
                owner=Participant(name="Juan"),
                interactions=[
                    Interaction(receptor_name="[NOMBRE ILEGIBLE]", interested=True),
                    Interaction(receptor_name="Ana", interested=True),
                ],
            ),
        ]
        result = use_case._clean_form_results(forms)

        assert len(result[0].interactions) == 1
        assert result[0].interactions[0].receptor_name == "Ana"

    def test_interaccion_vacia_se_descarta(self):
        """Interacciones con receptor vacío o None deben descartarse."""
        use_case = _make_use_case()
        forms = [
            FormResult(
                owner=Participant(name="Juan"),
                interactions=[
                    Interaction(receptor_name="", interested=False),
                    Interaction(receptor_name="Pedro", interested=False),
                ],
            ),
        ]
        result = use_case._clean_form_results(forms)

        assert len(result[0].interactions) == 1
        assert result[0].interactions[0].receptor_name == "Pedro"

    def test_owner_valido_no_genera_warning(self, caplog):
        """Un owner con nombre real no debe generar ningún warning."""
        use_case = _make_use_case()
        forms = [
            FormResult(
                owner=Participant(name="María García"),
                interactions=[Interaction(receptor_name="Juan", interested=True)],
            ),
        ]
        with caplog.at_level(logging.WARNING, logger="app.use_cases.process_event"):
            use_case._clean_form_results(forms)

        assert len(caplog.messages) == 0
