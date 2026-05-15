"""Tests unitarios para IllegibleResolver."""
import pytest
from app.core.entities import FormResult, Interaction, Participant
from app.use_cases.illegible_resolver import IllegibleResolver
from app.use_cases.name_normalizer import ILEGIBLE_TAG


def make_form(owner: str, voted_for: list[str]) -> FormResult:
    return FormResult(
        owner=Participant(name=owner),
        interactions=[
            Interaction(receptor_name=n, interested=True) for n in voted_for
        ],
    )


resolver = IllegibleResolver()


class TestCasoSimple:
    def test_un_ilegible_un_faltante_se_resuelve(self):
        """El caso más común: 1 ilegible + 1 persona sin planilla propia."""
        forms = [
            make_form("Ana",        ["Carlos", "Luis"]),
            make_form("Luis",       ["Carlos", "Ana"]),
            make_form(ILEGIBLE_TAG, ["Ana", "Luis"]),   # Carlos sin nombre
        ]
        resolved, resolutions = resolver.resolve(forms)

        owners = {f.owner.name for f in resolved}
        assert "Carlos" in owners
        assert ILEGIBLE_TAG not in owners
        assert len(resolutions) == 1
        assert resolutions[0]["resolved_as"] == "Carlos"
        assert resolutions[0]["confidence"] == 0.9

    def test_sin_ilegibles_no_cambia_nada(self):
        forms = [
            make_form("Ana",   ["Luis"]),
            make_form("Luis",  ["Ana"]),
        ]
        resolved, resolutions = resolver.resolve(forms)
        assert len(resolved) == len(forms)
        assert resolutions == []

    def test_ilegible_sin_candidatos_se_mantiene(self):
        """Si todos los votados tienen planilla propia, no hay candidatos."""
        forms = [
            make_form("Ana",        ["Luis"]),
            make_form("Luis",       ["Ana"]),
            make_form(ILEGIBLE_TAG, ["Ana", "Luis"]),
        ]
        resolved, resolutions = resolver.resolve(forms)
        owners = {f.owner.name for f in resolved}
        assert ILEGIBLE_TAG in owners  # no se pudo resolver
        assert resolutions == []


class TestCasoMultiple:
    def test_dos_ilegibles_dos_candidatos(self):
        """Con solapamiento de votos, el resolver asigna cada ilegible al candidato correcto."""
        # Carlos fue votado por Ana y Luis
        # María fue votada por Pedro y Sofía
        forms = [
            make_form("Ana",   ["Carlos", "Pedro"]),
            make_form("Luis",  ["Carlos", "Ana"]),
            make_form("Pedro", ["María", "Ana"]),
            make_form("Sofía", ["María", "Luis"]),
            # Ilegible 1: votó a Ana y Luis → probablemente Carlos
            make_form(ILEGIBLE_TAG, ["Ana", "Luis"]),
            # Ilegible 2: votó a Pedro y Sofía → probablemente María
            make_form(ILEGIBLE_TAG, ["Pedro", "Sofía"]),
        ]
        resolved, resolutions = resolver.resolve(forms)
        owners = {f.owner.name for f in resolved}
        assert "Carlos" in owners
        assert "María" in owners
        assert ILEGIBLE_TAG not in owners
        assert len(resolutions) == 2

    def test_resueltos_participan_en_matches(self):
        """Después de resolver, la persona ilegible puede tener match mutuo."""
        forms = [
            make_form("Ana",        ["Carlos"]),
            make_form("Luis",       ["Carlos"]),
            make_form(ILEGIBLE_TAG, ["Ana"]),   # Carlos votó a Ana
        ]
        resolved, _ = resolver.resolve(forms)

        carlos_form = next(f for f in resolved if f.owner.name == "Carlos")
        ana_form = next(f for f in resolved if f.owner.name == "Ana")

        # Carlos votó a Ana
        assert any(i.receptor_name == "Ana" for i in carlos_form.interactions)
        # Ana votó a Carlos → hay match mutuo posible
        assert any(i.receptor_name == "Carlos" for i in ana_form.interactions)
