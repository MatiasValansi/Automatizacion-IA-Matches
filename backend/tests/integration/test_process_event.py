import pytest
from unittest.mock import MagicMock
from app.use_cases.process_event import ProcessEventUseCase
from app.use_cases.match_engine import MatchEngine
from app.use_cases.name_normalizer import NameNormalizer
from app.core.entities import FormResult, Interaction, Participant

def test_flujo_completo_del_evento():
    # 1. Setup: Mocks y dependencias
    mock_ai = MagicMock()
    
    # Simulamos que la IA extrae dos planillas que hacen match
    form_a = FormResult(
        owner=Participant(name="Matías"), #
        interactions=[Interaction(receptor_name="Sofía", interested=True)]
    )
    form_b = FormResult(
        owner=Participant(name="Sofia"), # Sin tilde para probar el normalizador
        interactions=[Interaction(receptor_name="Matias", interested=True)]
    )
    
    # Configuramos el Mock para que devuelva una planilla por cada llamada
    mock_ai.extract_from_image.side_effect = [form_a, form_b]
    
    # Instanciamos el motor real con su normalizador
    normalizer = NameNormalizer()
    engine = MatchEngine(normalizer=normalizer)
    
    # Creamos el Orquestador
    use_case = ProcessEventUseCase(ai_provider=mock_ai, match_engine=engine)

    # 2. Ejecución: Procesamos "dos imágenes" (bytes ficticios)
    matches = use_case.execute([b"img1", b"img2"])

    # 3. Verificación: ¡Debe haber un match a pesar de la tilde de Sofía!
    assert len(matches) == 1
    assert matches[0].person_a.name == "Matías"
    assert matches[0].person_b.name == "Sofia"