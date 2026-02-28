import os
import json
import time
import logging
from google import genai
from google.genai import types
from app.core.interfaces import AIProvider
from app.core.entities import FormResult, Interaction, Participant

logger = logging.getLogger(__name__)

# google-genai SDK oficial → usa v1beta por defecto (soporta todos los modelos)
# Modelos verificados disponibles en esta API key (sin gemini-1.5, fue removido)
# Cuotas free tier: 15 req/min por modelo
_MODEL_FALLBACK = [    
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-001",
]

# Throttling: mínimo segundos entre requests para no saturar la cuota (15 req/min)
_MIN_REQUEST_INTERVAL = 4.5

class GeminiAIProvider(AIProvider):
    """
    Implementación concreta de AIProvider usando el SDK oficial google-genai.
    Usa v1beta (default) que soporta todos los modelos Gemini en el free tier.
    Reintenta automáticamente con modelos alternativos ante errores 429 o 404.
    """

    def __init__(self):
        self._client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY"),
        )
        self._last_request_time: float = 0

    def _throttle(self) -> None:
        """Espera lo necesario para respetar el intervalo mínimo entre requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            wait = _MIN_REQUEST_INTERVAL - elapsed
            print(f"[GeminiAIProvider] Throttling: esperando {wait:.1f}s antes de la próxima request")
            time.sleep(wait)
        self._last_request_time = time.time()

    def extract_from_image(self, image_bytes: bytes) -> FormResult:
        """
        Toma los bytes de una imagen, los envía a Gemini y devuelve un FormResult.
        Aplica throttling automático y reintenta con modelos alternativos ante 429/404.
        """
        contents = [
            types.Part.from_text(text=self._get_system_prompt()),
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        ]

        last_error = None
        for model_name in _MODEL_FALLBACK:
            for attempt in range(3):
                try:
                    self._throttle()
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=contents,
                    )
                    print(f"[GeminiAIProvider] ✅ Respuesta obtenida con '{model_name}'")
                    return self._map_to_entity(response.text)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        wait = (2 ** attempt) * 5  # 5s, 10s, 20s
                        print(f"[GeminiAIProvider] ⚠️ Cuota agotada en '{model_name}' (intento {attempt + 1}), esperando {wait}s...")
                        time.sleep(wait)
                        last_error = e
                    elif "404" in error_str or "NOT_FOUND" in error_str:
                        print(f"[GeminiAIProvider] ⚠️ Modelo '{model_name}' no disponible (404), probando siguiente...")
                        last_error = e
                        break
                    else:
                        raise
            else:
                print(f"[GeminiAIProvider] ⚠️ Modelo '{model_name}' agotado, probando siguiente...")
                continue

        raise RuntimeError(
            f"Todos los modelos de Gemini fallaron. Último error: {last_error}"
        )

    def _get_system_prompt(self) -> str:
        return (
            'Extraé de esta planilla de Speed Dating el dueño y sus votos. '
            'Respondé SOLO JSON: {"owner_name":"str","votes":[{"target_name":"str","is_interested":bool}]}. '
            'Reglas: incluí todos los nombres visibles; Sí/✓/marca=true, No/✗/vacío=false; '
            'nombres exactos como aparecen en la planilla.'
        )

    def _map_to_entity(self, raw_content: str) -> FormResult:
        """Convierte el texto JSON de la IA en una entidad FormResult."""
        # Limpieza básica por si la IA devuelve markdown (```json ... ```)
        clean_json = raw_content.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        
        owner = Participant(name=data["owner_name"])
        interactions = [
            Interaction(receptor_name=v["target_name"], interested=v["is_interested"])
            for v in data["votes"]
        ]
        
        return FormResult(owner=owner, interactions=interactions)