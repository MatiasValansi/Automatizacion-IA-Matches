"""
Se realizan test de cuando un nombre sería similar a otro y cuando no, para validar el funcionamiento del normalizador de nombres.
"""
import pytest
from app.use_cases.name_normalizer import NameNormalizer

def test_debe_identificar_nombres_similares_como_iguales():
    normalizer = NameNormalizer()
    
    # Caso 1: Con y sin tilde
    assert normalizer.are_similar("Matías", "Matias") is True
    
    # Caso 2: Diferencia de mayúsculas
    assert normalizer.are_similar("JUAN", "juan") is True
    
    # Caso 3: Error tipográfico leve
    assert normalizer.are_similar("Sofia", "Sofua") is True

def test_debe_rechazar_nombres_distintos():
    normalizer = NameNormalizer()
    
    assert normalizer.are_similar("Matias", "Marcos") is False