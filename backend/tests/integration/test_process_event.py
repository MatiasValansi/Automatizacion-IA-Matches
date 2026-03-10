import pytest
from unittest.mock import MagicMock
from app.use_cases.process_event import ProcessEventUseCase
from app.use_cases.match_engine import MatchEngine
from app.use_cases.name_normalizer import NameNormalizer
from app.use_cases.duplicate_detector import DuplicateDetector
from app.core.entities import FormResult, Interaction, Participant

def test_flujo_completo_del_evento():
    # 1. Setup: Mocks y dependencias
    mock_ai = MagicMock()
    mock_repo = MagicMock()
    mock_repo.save_matches.return_value = "https://docs.google.com/spreadsheets/d/fake"
    
    # Simulamos que la IA extrae dos planillas que hacen match
    form_a = FormResult(
        owner=Participant(name="Matías"),
        interactions=[Interaction(receptor_name="Sofía", interested=True)]
    )
    form_b = FormResult(
        owner=Participant(name="Sofia"), # Sin tilde para probar el normalizador
        interactions=[Interaction(receptor_name="Matias", interested=True)]
    )
    
    # Configuramos el Mock para que devuelva ambas planillas en batch
    mock_ai.extract_batch.return_value = [form_a, form_b]
    
    # Instanciamos el motor real con su normalizador
    normalizer = NameNormalizer()
    engine = MatchEngine(normalizer=normalizer)
    duplicate_detector = DuplicateDetector(normalizer=normalizer)
    
    # Creamos el Orquestador con todas sus dependencias
    use_case = ProcessEventUseCase(
        ai_provider=mock_ai,
        match_engine=engine,
        repository=mock_repo,
        duplicate_detector=duplicate_detector,
    )

    # 2. Ejecución: Procesamos "dos imágenes" (bytes ficticios)
    result = use_case.execute("Evento Test", [b"img1", b"img2"])

    # 3. Verificación: ¡Debe haber un match a pesar de la tilde de Sofía!
    assert len(result["matches"]) == 1
    assert result["images_processed"] == 2
    assert result["sheet_url"] is not None

    # 4. Verificar que el repositorio recibió los nombres UNIFICADOS
    call_args = mock_repo.save_matches.call_args
    saved_form_results = call_args[0][1]  # segundo argumento posicional
    saved_names = set()
    for form in saved_form_results:
        saved_names.add(form.owner.name)
        for interaction in form.interactions:
            saved_names.add(interaction.receptor_name)

    # "Sofia" y "Sofía" deben estar unificados bajo un solo nombre
    sofia_variants = [n for n in saved_names if "sof" in n.lower()]
    assert len(sofia_variants) == 1, (
        f"El repositorio recibió variantes no unificadas de Sofía: {sofia_variants}"
    )
    # "Matias" y "Matías" deben estar unificados bajo un solo nombre
    matias_variants = [n for n in saved_names if "mat" in n.lower()]
    assert len(matias_variants) == 1, (
        f"El repositorio recibió variantes no unificadas de Matías: {matias_variants}"
    )


def test_pipeline_unifica_nombres_antes_de_matches_y_planilla():
    """
    Verifica el pipeline completo:
    1° Se unifican nombres duplicados (HERNAN SARA, HERNAN SABA → HERNAN SARA)
    2° Se calculan matches SOBRE datos unificados
    3° El repositorio recibe datos con nombres canónicos
    """
    mock_ai = MagicMock()
    mock_repo = MagicMock()
    mock_repo.save_matches.return_value = "https://docs.google.com/spreadsheets/d/fake"

    # Simula 3 planillas con variantes del mismo nombre en targets
    form_maria = FormResult(
        owner=Participant(name="MARIA PILOTTO"),
        interactions=[
            Interaction(receptor_name="HERNAN SARA", interested=True),
            Interaction(receptor_name="JAVIER", interested=True),
        ],
    )
    form_tamara = FormResult(
        owner=Participant(name="TAMARA ARABELLO"),
        interactions=[
            Interaction(receptor_name="HERNAN-SAEA", interested=True),  # variante
            Interaction(receptor_name="JAVIER", interested=False),
        ],
    )
    form_hernan = FormResult(
        owner=Participant(name="Hernan Sara"),  # variante como owner
        interactions=[
            Interaction(receptor_name="MARIA PILOTTO", interested=True),
            Interaction(receptor_name="TAMARA ARABELLO", interested=False),
        ],
    )

    mock_ai.extract_batch.return_value = [form_maria, form_tamara, form_hernan]

    normalizer = NameNormalizer(threshold=85)
    engine = MatchEngine(normalizer=normalizer)
    duplicate_detector = DuplicateDetector(normalizer=normalizer)
    use_case = ProcessEventUseCase(
        ai_provider=mock_ai,
        match_engine=engine,
        repository=mock_repo,
        duplicate_detector=duplicate_detector,
    )

    result = use_case.execute("Evento Test 2", [b"img1", b"img2", b"img3"])

    # Debe haber match entre MARIA PILOTTO y HERNAN SARA (mutual yes)
    assert len(result["matches"]) >= 1

    # El repositorio debe recibir nombres unificados
    call_args = mock_repo.save_matches.call_args
    saved_forms = call_args[0][1]

    all_names = set()
    for form in saved_forms:
        all_names.add(form.owner.name)
        for interaction in form.interactions:
            all_names.add(interaction.receptor_name)

    # Todas las variantes de HERNAN deben estar unificadas bajo UN solo nombre
    hernan_variants = [n for n in all_names if "hernan" in n.lower() or "saea" in n.lower()]
    assert len(hernan_variants) == 1, (
        f"Se esperaba un solo nombre para Hernan pero se encontraron: {hernan_variants}"
    )

    # Verificar que se detectaron duplicados
    assert result["duplicates_detected"] >= 1