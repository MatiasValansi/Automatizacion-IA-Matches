"""
Tests unitarios para el DuplicateDetector.
Verifica la detección de nombres duplicados/similares y la unificación correcta.
"""

import pytest
from app.core.entities import FormResult, Interaction, Participant, DuplicateMerge
from app.use_cases.name_normalizer import NameNormalizer
from app.use_cases.duplicate_detector import DuplicateDetector


@pytest.fixture
def detector():
    normalizer = NameNormalizer(threshold=85)
    return DuplicateDetector(normalizer=normalizer)


# ── Detección de duplicados ───────────────────────────────────────────


class TestDetectDuplicates:
    """Casos donde el detector debe encontrar y unificar nombres."""

    def test_detecta_nombre_con_typo(self, detector):
        """'Carlos Musica' y 'Carlos Musicaa' → misma persona."""
        forms = [
            FormResult(
                owner=Participant(name="Carlos Musica"),
                interactions=[
                    Interaction(receptor_name="Ana López", interested=True)
                ],
            ),
            FormResult(
                owner=Participant(name="Ana López"),
                interactions=[
                    Interaction(receptor_name="Carlos Musicaa", interested=True)
                ],
            ),
        ]

        unified, merges = detector.detect_and_unify(forms)

        assert len(merges) == 1
        assert merges[0].similarity_score >= 85
        assert "Carlos Music" in merges[0].canonical_name

    def test_detecta_nombre_con_acento_diferente(self, detector):
        """'Sofía' y 'Sofia' → misma persona."""
        forms = [
            FormResult(
                owner=Participant(name="Sofía"),
                interactions=[
                    Interaction(receptor_name="Juan", interested=True)
                ],
            ),
            FormResult(
                owner=Participant(name="Juan"),
                interactions=[
                    Interaction(receptor_name="Sofia", interested=True)
                ],
            ),
        ]

        unified, merges = detector.detect_and_unify(forms)

        assert len(merges) == 1
        # Verifica que el nombre se unificó correctamente
        assert merges[0].canonical_name in ("Sofía", "Sofia")

    def test_detecta_nombre_con_mayusculas(self, detector):
        """'MATIAS' y 'Matias' → misma persona."""
        forms = [
            FormResult(
                owner=Participant(name="MATIAS"),
                interactions=[
                    Interaction(receptor_name="Laura", interested=True)
                ],
            ),
            FormResult(
                owner=Participant(name="Laura"),
                interactions=[
                    Interaction(receptor_name="Matias", interested=True)
                ],
            ),
        ]

        unified, merges = detector.detect_and_unify(forms)

        assert len(merges) == 1

    def test_unifica_nombre_en_form_results(self, detector):
        """Verifica que el remapeo se aplica correctamente en los FormResults."""
        forms = [
            FormResult(
                owner=Participant(name="Carlos Musica"),
                interactions=[
                    Interaction(receptor_name="Ana", interested=True)
                ],
            ),
            FormResult(
                owner=Participant(name="Ana"),
                interactions=[
                    Interaction(receptor_name="Carlos Musicaa", interested=True)
                ],
            ),
        ]

        unified, merges = detector.detect_and_unify(forms)

        # Recolecta todos los nombres post-unificación
        all_names = set()
        for form in unified:
            all_names.add(form.owner.name)
            for interaction in form.interactions:
                all_names.add(interaction.receptor_name)

        # No debe haber dos variantes de Carlos
        carlos_names = [n for n in all_names if "Carlos" in n or "carlos" in n]
        assert len(carlos_names) == 1, (
            f"Se esperaba un solo 'Carlos' pero se encontraron: {carlos_names}"
        )

    def test_elige_nombre_mas_largo_como_canonico(self, detector):
        """El nombre más largo (más completo) debería ser el canónico."""
        forms = [
            FormResult(
                owner=Participant(name="Marcos"),
                interactions=[
                    Interaction(receptor_name="Carlos M", interested=True),
                    Interaction(receptor_name="Laura", interested=False),
                ],
            ),
            FormResult(
                owner=Participant(name="Laura"),
                interactions=[
                    Interaction(receptor_name="Carlos Musica", interested=True),
                ],
            ),
            FormResult(
                owner=Participant(name="Carlos Musica"),
                interactions=[
                    Interaction(receptor_name="Marcos", interested=True),
                ],
            ),
        ]

        _, merges = detector.detect_and_unify(forms)

        assert len(merges) == 1
        # "Carlos Musica" es el más largo/completo → canónico
        assert merges[0].canonical_name == "Carlos Musica"


# ── No detectar falsos positivos ─────────────────────────────────────


class TestNoDuplicates:
    """Casos donde los nombres son distintos y NO deben unificarse."""

    def test_no_detecta_nombres_distintos(self, detector):
        """'Matias' y 'Marcos' → personas diferentes."""
        forms = [
            FormResult(
                owner=Participant(name="Matias"),
                interactions=[
                    Interaction(receptor_name="Marcos", interested=True)
                ],
            ),
            FormResult(
                owner=Participant(name="Marcos"),
                interactions=[
                    Interaction(receptor_name="Matias", interested=True)
                ],
            ),
        ]

        unified, merges = detector.detect_and_unify(forms)

        assert len(merges) == 0

    def test_no_duplicates_con_una_sola_planilla(self, detector):
        """Con un solo form no hay nada que deduplicar entre owners."""
        forms = [
            FormResult(
                owner=Participant(name="Ana"),
                interactions=[
                    Interaction(receptor_name="Pedro", interested=True),
                    Interaction(receptor_name="Luis", interested=False),
                ],
            ),
        ]

        unified, merges = detector.detect_and_unify(forms)

        assert len(merges) == 0
        assert unified == forms

    def test_sin_planillas_no_falla(self, detector):
        """Lista vacía → sin errores, sin merges."""
        unified, merges = detector.detect_and_unify([])

        assert len(merges) == 0
        assert len(unified) == 0


# ── Estructura del reporte ────────────────────────────────────────────


class TestMergeReport:
    """Verifica que el reporte generado tenga la estructura correcta."""

    def test_merge_contiene_campos_obligatorios(self, detector):
        forms = [
            FormResult(
                owner=Participant(name="Sofia"),
                interactions=[
                    Interaction(receptor_name="Juan", interested=True)
                ],
            ),
            FormResult(
                owner=Participant(name="Juan"),
                interactions=[
                Interaction(receptor_name="Sofiia", interested=True)  # typo
                ],
            ),
        ]

        _, merges = detector.detect_and_unify(forms)

        assert len(merges) >= 1
        merge = merges[0]
        assert isinstance(merge, DuplicateMerge)
        assert merge.name_a != ""
        assert merge.name_b != ""
        assert merge.canonical_name != ""
        assert 0 < merge.similarity_score <= 100
        assert "similitud" in merge.decision.lower() or "unificaron" in merge.decision.lower()

    def test_decision_es_legible(self, detector):
        """El texto de la decisión debe ser comprensible para un humano."""
        forms = [
            FormResult(
                owner=Participant(name="Matías V"),
                interactions=[
                    Interaction(receptor_name="Pedro", interested=True)
                ],
            ),
            FormResult(
                owner=Participant(name="Pedro"),
                interactions=[
                    Interaction(receptor_name="Matias V", interested=True)
                ],
            ),
        ]

        _, merges = detector.detect_and_unify(forms)

        assert len(merges) == 1
        decision = merges[0].decision
        # Debe mencionar ambos nombres y el porcentaje
        assert "%" in decision
        assert merges[0].canonical_name in decision
