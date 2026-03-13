"""
Tests para el NameNormalizer inteligente.

Cubre:
 - Similitud básica (acentos, mayúsculas, typos).
 - Rechazo de nombres distintos.
 - Unificación inteligente (canónico = nombre más largo).
 - Regla de Oro (iniciales de apellido distintas → NO unificar).
 - Registro de decisiones.
"""
import pytest
from app.use_cases.name_normalizer import NameNormalizer


# ── Similitud básica ─────────────────────────────────────────────────

class TestSimilitudBasica:

    def test_debe_identificar_nombres_similares_con_tilde(self):
        normalizer = NameNormalizer()
        assert normalizer.are_similar("Matías", "Matias") is True

    def test_debe_identificar_nombres_similares_con_mayusculas(self):
        normalizer = NameNormalizer()
        assert normalizer.are_similar("JUAN M", "juan m") is True

    def test_debe_identificar_nombres_similares_con_typo(self):
        normalizer = NameNormalizer()
        assert normalizer.are_similar("Sofia", "Sofua") is True

    def test_debe_rechazar_nombres_distintos(self):
        normalizer = NameNormalizer()
        assert normalizer.are_similar("Matias", "Marcos") is False


# ── Unificación inteligente ──────────────────────────────────────────

class TestUnificacionInteligente:

    def test_canonico_es_el_nombre_mas_largo(self):
        """'Jose L', 'José Luis' y 'Jose Luis Mastromano'
        deben unificarse bajo 'Jose Luis Mastromano'."""
        normalizer = NameNormalizer(threshold=60)
        names = ["Jose L", "José Luis", "Jose Luis Mastromano"]
        result = normalizer.unify_names(names)

        assert result.canonical_map["Jose L"] == "Jose Luis Mastromano"
        assert result.canonical_map["José Luis"] == "Jose Luis Mastromano"
        assert result.canonical_map["Jose Luis Mastromano"] == "Jose Luis Mastromano"

    def test_nombres_sin_duplicados_no_se_unifican(self):
        normalizer = NameNormalizer()
        names = ["Ana", "Marcos", "Lucía"]
        result = normalizer.unify_names(names)

        assert len(result.decisions) == 0
        for name in names:
            assert result.canonical_map[name] == name

    def test_lista_con_un_solo_nombre(self):
        normalizer = NameNormalizer()
        result = normalizer.unify_names(["Juan"])
        assert result.canonical_map == {"Juan": "Juan"}
        assert result.decisions == []

    def test_nombres_vacios_e_ilegibles_se_ignoran(self):
        normalizer = NameNormalizer()
        result = normalizer.unify_names(["", "[NOMBRE ILEGIBLE]", "Ana"])
        assert "Ana" in result.canonical_map
        assert "" not in result.canonical_map
        assert "[NOMBRE ILEGIBLE]" not in result.canonical_map


# ── Regla de Oro ─────────────────────────────────────────────────────

class TestReglaDeOro:

    def test_no_unifica_si_iniciales_de_apellido_difieren(self):
        """Juan M. vs Juan P. NO deben unificarse,
        aunque el nombre de pila sea el mismo."""
        normalizer = NameNormalizer(threshold=70)
        names = ["Juan M.", "Juan P."]
        result = normalizer.unify_names(names)

        assert result.canonical_map["Juan M."] == "Juan M."
        assert result.canonical_map["Juan P."] == "Juan P."

    def test_si_unifica_cuando_iniciales_coinciden(self):
        """Juan M. y Juan Martinez deberían unificarse."""
        normalizer = NameNormalizer(threshold=60)
        names = ["Juan M.", "Juan Martinez"]
        result = normalizer.unify_names(names)

        assert result.canonical_map["Juan M."] == "Juan Martinez"

    def test_sin_apellido_no_bloquea_unificacion(self):
        """Si uno de los nombres no tiene apellido detectable,
        la Regla de Oro no interfiere."""
        normalizer = NameNormalizer(threshold=70)
        names = ["Juan", "Juan M."]
        result = normalizer.unify_names(names)

        assert result.canonical_map["Juan"] == "Juan M."


# ── Registro de decisiones ───────────────────────────────────────────

class TestRegistroDecisiones:

    def test_unificacion_genera_decision(self):
        normalizer = NameNormalizer(threshold=60)
        names = ["Jose L", "Jose Luis Mastromano"]
        result = normalizer.unify_names(names)

        assert len(result.decisions) >= 1
        assert "Se unificó" in result.decisions[0]
        assert "JOSE L" in result.decisions[0]

    def test_regla_de_oro_genera_decision_de_no_unificacion(self):
        normalizer = NameNormalizer(threshold=70)
        names = ["Juan M.", "Juan P."]
        result = normalizer.unify_names(names)

        assert len(result.decisions) >= 1
        assert "NO se unificó" in result.decisions[0]
        assert "iniciales de apellido distintas" in result.decisions[0]
