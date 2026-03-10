import json
import pytest
from unittest.mock import MagicMock, patch
from app.infrastructure.ai.gemini_provider import GeminiAIProvider
from app.core.entities import FormResult


def test_gemini_provider_extract_batch():
    """Verifica que extract_batch mapea correctamente la respuesta JSON."""
    response_json = json.dumps([
        {
            "owner_name": "Matias",
            "votes": [
                {"target_name": "Sofia", "is_interested": True},
                {"target_name": "Juan", "is_interested": False},
            ],
        },
        {
            "owner_name": "Sofia",
            "votes": [
                {"target_name": "Matias", "is_interested": True},
            ],
        },
    ])

    mock_response = MagicMock()
    mock_response.text = response_json

    with patch("app.infrastructure.ai.gemini_provider.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        provider = GeminiAIProvider()
        results = provider.extract_batch([b"img1", b"img2"])

        assert len(results) == 2
        assert isinstance(results[0], FormResult)
        assert results[0].owner.name == "Matias"
        assert len(results[0].interactions) == 2
        assert results[0].interactions[0].interested is True
        assert results[1].owner.name == "Sofia"


def test_gemini_provider_extract_from_image_delegates_to_batch():
    """extract_from_image debe delegar a extract_batch."""
    response_json = json.dumps([{
        "owner_name": "Matias",
        "votes": [{"target_name": "Sofia", "is_interested": True}],
    }])

    mock_response = MagicMock()
    mock_response.text = response_json

    with patch("app.infrastructure.ai.gemini_provider.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        provider = GeminiAIProvider()
        result = provider.extract_from_image(b"fake_image")

        assert isinstance(result, FormResult)
        assert result.owner.name == "Matias"