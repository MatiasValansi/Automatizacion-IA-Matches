import os
import json
import time
import logging
from google import genai
from google.genai import types
from app.core.interfaces import AIProvider
from app.core.entities import FormResult, Interaction, Participant

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"
_MAX_BATCH_SIZE = 25
_MAX_RETRIES = 4
_MIN_REQUEST_INTERVAL = 4.2  # Free tier: 15 req/min → margen de seguridad


class GeminiAIProvider(AIProvider):
    """
    Implementación concreta de AIProvider usando el SDK oficial google-genai.
    Soporta procesamiento por lotes de hasta 25 imágenes por request
    para optimizar la cuota del Free Tier.
    """

    def __init__(self) -> None:
        self._client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY"),
        )
        self._last_request_time: float = 0
        self._request_count: int = 0

    # ── Interfaz pública ────────────────────────────────────────

    def extract_from_image(self, image_bytes: bytes) -> FormResult:
        """Procesa una sola imagen delegando al método batch."""
        return self.extract_batch([image_bytes])[0]

    def extract_batch(self, images_list: list[bytes]) -> list[FormResult]:
        """
        Procesa un lote de imágenes. Si len > 25, divide en chunks
        y consolida los resultados.
        """
        results: list[FormResult] = []
        for start in range(0, len(images_list), _MAX_BATCH_SIZE):
            chunk = images_list[start : start + _MAX_BATCH_SIZE]
            results.extend(self._process_chunk(chunk))
        return results

    # ── Lógica interna ──────────────────────────────────────────

    def _process_chunk(self, chunk: list[bytes]) -> list[FormResult]:
        """Envía un chunk (≤ 25 imágenes) en un solo request a Gemini."""
        contents: list[types.Part] = [
            types.Part.from_text(text=self.build_system_prompt()),
            types.Part.from_text(text=self._get_batch_prompt(len(chunk))),
        ]
        for img_bytes in chunk:
            contents.append(
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            )

        self._request_count += 1
        req_num = self._request_count

        for attempt in range(_MAX_RETRIES):
            try:
                self._throttle()
                response = self._client.models.generate_content(
                    model=_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                logger.info(
                    f"[GeminiAIProvider] ✅ Batch #{req_num} procesado "
                    f"({len(chunk)} imágenes)"
                )
                return self._map_batch(response.text, expected=len(chunk))

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    wait = (2 ** attempt) * 5
                    logger.warning(
                        f"[GeminiAIProvider] ⚠️ Rate limit (batch #{req_num}, "
                        f"intento {attempt + 1}/{_MAX_RETRIES}), "
                        f"esperando {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError(
            f"[GeminiAIProvider] ❌ Batch #{req_num} falló "
            f"tras {_MAX_RETRIES} intentos por rate limiting."
        )

    def _throttle(self) -> None:
        now = time.time()
        elapsed = now - self._last_request_time
        if self._last_request_time > 0 and elapsed < _MIN_REQUEST_INTERVAL:
            wait = _MIN_REQUEST_INTERVAL - elapsed
            logger.info(
                f"[GeminiAIProvider] ⏳ Throttle: esperando {wait:.1f}s"
            )
            time.sleep(wait)
        self._last_request_time = time.time()

    # ── Prompt ──────────────────────────────────────────────────

    @staticmethod
    def build_system_prompt() -> str:
        return (
            "Sos un experto en digitalización de formularios escritos a mano.\n"
            "Tu tarea es analizar la imagen de una 'Planilla de Votación'.\n\n"
            
            "### ESTRUCTURA DE LA HOJA:\n"
            "1. PROPIETARIO (owner_name): Es la persona que llena la planilla. "
            "Su nombre NO está dentro de la tabla de votos. Está escrito arriba, "
            "cerca de etiquetas como 'Tu nombre', 'Nombre y Apellido' o simplemente suelto en el encabezado.\n"
            "2. VOTOS (voted_people): Son las personas listadas DENTRO de la tabla.\n\n"
            
            "### REGLAS DE EXTRACCIÓN:\n"
            "- Identificá PRIMERO al dueño (owner_name). Si no es legible o está vacío, usá '[PROPIETARIO NO DETECTADO]'.\n"
            "- Para cada fila de la tabla, extraé el nombre del receptor y si marcaron 'SI' o 'NO'.\n"
            "- Sé extremadamente fiel a la caligrafía. No resumas nombres.\n\n"
            
            "### FORMATO DE SALIDA (JSON):\n"
            "{\n"
            "  'owner_name': 'Nombre del Dueño',\n"
            "  'matches': [\n"
            "    {'receptor_name': 'Persona 1', 'interested': true},\n"
            "    {'receptor_name': 'Persona 2', 'interested': false}\n"
            "  ]\n"
            "}"
        )

    def _get_batch_prompt(self, image_count: int) -> str:
        return (
            f"Analizá estas {image_count} planillas. Para cada una:\n"
            "1. Buscá el dueño en el encabezado (arriba de la tabla).\n"
            "2. Extraé la lista de nombres y votos de la tabla.\n\n"
            "Respondé con este formato JSON:\n"
            '[{"owner_name": "Nombre de Arriba", "interactions": [{"receptor_name": "Nombre en Tabla", "interested": bool}]}]'
        )
        

    # ── Mapping ─────────────────────────────────────────────────

    def _map_batch(self, raw_content: str, expected: int) -> list[FormResult]:
        """Convierte el array JSON en una lista de FormResult."""
        clean = raw_content.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)

        # Si Gemini devuelve un solo objeto en vez de array (batch=1)
        if isinstance(data, dict):
            data = [data]

        if len(data) != expected:
            logger.warning(
                f"[GeminiAIProvider] Se esperaban {expected} resultados, "
                f"se recibieron {len(data)}"
            )

        return [self._map_single(item) for item in data]

    @staticmethod
    def _map_single(data: dict) -> FormResult:
        owner = Participant(name=data["owner_name"])
        interactions = [
            Interaction(
                receptor_name=v["receptor_name"],
                interested=v["interested"],
            )
            for v in data["interactions"]
        ]
        return FormResult(owner=owner, interactions=interactions)