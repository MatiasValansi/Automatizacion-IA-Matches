import os
import json
import time
from google import genai
from google.genai import types
from app.core.interfaces import AIProvider
from app.core.entities import FormResult, Interaction, Participant

# google-genai SDK oficial → usa v1beta por defecto (soporta todos los modelos)
# Modelos verificados disponibles en esta API key (sin gemini-1.5, fue removido)
# Cuotas free tier: 15 req/min por modelo
_MODEL_FALLBACK = [    
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-001",
]

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

    def extract_from_image(self, image_bytes: bytes) -> FormResult:
        """
        Toma los bytes de una imagen, los envía a Gemini y devuelve un FormResult.
        Reintenta con modelos alternativos si hay error de cuota (429).
        """
        contents = [
            types.Part.from_text(text=self._get_system_prompt()),
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        ]

        last_error = None
        for model_name in _MODEL_FALLBACK:
            for attempt in range(3):
                try:
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=contents,
                    )
                    print(f"[GeminiAIProvider] Respuesta obtenida con '{model_name}'")
                    return self._map_to_entity(response.text)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        wait = (2 ** attempt) * 5  # 5s, 10s, 20s
                        print(f"[GeminiAIProvider] Cuota agotada en '{model_name}' (intento {attempt + 1}), esperando {wait}s...")
                        time.sleep(wait)
                        last_error = e
                    elif "404" in error_str or "NOT_FOUND" in error_str:
                        # Modelo no disponible en esta región/plan, pasar al siguiente
                        print(f"[GeminiAIProvider] Modelo '{model_name}' no disponible (404), probando siguiente...")
                        last_error = e
                        break  # salir del loop de reintentos para este modelo
                    else:
                        raise
            else:
                # El bucle interno terminó sin break (agotó reintentos por cuota)
                print(f"[GeminiAIProvider] Modelo '{model_name}' agotado, probando siguiente...")
                continue

        raise RuntimeError(
            f"Todos los modelos de Gemini fallaron. Último error: {last_error}"
        )

    def _get_system_prompt(self) -> str:
        return """
        Actúa como un experto en OCR y extracción de datos. 
        Analiza la planilla de Speed Dating adjunta.
        
        Extrae:
        1. El nombre de la persona dueña de la planilla.
        2. La lista de personas con las que habló y si marcó 'Sí' o 'No'.

        Devuelve ÚNICAMENTE un JSON con esta estructura exacta:
        {
            "owner_name": "Nombre del dueño",
            "votes": [
                {"target_name": "Nombre", "is_interested": true},
                {"target_name": "Nombre", "is_interested": false}
            ]
        }
        """

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