import pytest
from unittest.mock import MagicMock, patch
from app.infrastructure.ai.gemini_provider import GeminiAIProvider
from app.core.entities import FormResult

def test_gemini_provider_extrae_datos_correctamente():
    # 1. Setup: Simulamos la respuesta que daría Gemini
    mock_response_content = """
    {
        "owner_name": "Matias",
        "votes": [
            {"target_name": "Sofia", "is_interested": true},
            {"target_name": "Juan", "is_interested": false}
        ]
    }
    """
    
    # Creamos un mock del objeto que devuelve LangChain
    mock_response = MagicMock()
    mock_response.content = mock_response_content

    # 2. Ejecución: Parcheamos ChatGoogleGenerativeAI para que no llame a la API real
    with patch("app.infrastructure.ai.gemini_provider.ChatGoogleGenerativeAI") as MockLLM:
        # Configuramos el mock para que devuelva nuestra respuesta simulada
        MockLLM.return_value.invoke.return_value = mock_response
        
        provider = GeminiAIProvider()
        # Pasamos bytes vacíos ya que la IA está mockeada
        result = provider.extract_from_image(b"fake_image_bytes")

        # 3. Validaciones (Assertions)
        assert isinstance(result, FormResult)
        assert result.owner.name == "Matias"
        assert len(result.interactions) == 2
        assert result.interactions[0].receptor_name == "Sofia"
        assert result.interactions[0].interested is True