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
        """System prompt para la API de Gemini optimizado para planillas de Speed Dating."""
        return (
            "Sos un sistema experto de OCR para planillas de Speed Dating. "
            "Tu tarea es extraer con precisión los datos de tablas manuscritas, "
            "incluso cuando la imagen presenta inclinación o distorsión de perspectiva.\n\n"
            "JERARQUÍA ABSOLUTA — La ubicación espacial (arriba vs. tabla) tiene "
            "prioridad sobre cualquier otra lógica de inferencia.\n\n"
            "FLUJO ESTRICTO DE ANÁLISIS — seguí estos pasos en orden:\n\n"
            "PASO 1 — IDENTIFICACIÓN DEL PROPIETARIO (owner_name):\n"
            "1a. Buscá el campo 'Tu nombre y apellido:' EXCLUSIVAMENTE en la parte superior "
            "de la imagen (zona de encabezado, por encima de la tabla/grilla).\n"
            "1b. El texto manuscrito que encuentres ahí es el ÚNICO valor válido para owner_name.\n"
            "1c. PROHIBICIÓN ESTRICTA: Está terminantemente prohibido usar cualquier nombre "
            "que aparezca dentro de las celdas de la tabla (grilla) como owner_name. "
            "Los nombres de la tabla son EXCLUSIVAMENTE receptores de votos.\n"
            "1d. FALLBACK: Si no detectás ningún texto manuscrito en la zona superior "
            "del encabezado, devolvé obligatoriamente: '[PROPIETARIO NO DETECTADO]'.\n"
            "NUNCA devuelvas 'Participant' ni valores genéricos.\n\n"
            "PASO 2 — EXTRACCIÓN DE TABLA:\n"
            "Una vez identificado el emisor, procesá la tabla de la planilla.\n"
            "- Cada marca (X, ✓, check o tachadura) debe asociarse ESTRICTAMENTE a la fila "
            "de texto que está a su IZQUIERDA INMEDIATA en la MISMA fila horizontal de la tabla.\n"
            "- Si detectás inclinación, usá las líneas de la grilla como guía principal "
            "para la asociación fila↔marca (prioridad absoluta sobre coordenadas de píxeles).\n\n"
            "PASO 3 — LIMPIEZA DE TABLA Y REGLA DE OMISIÓN:\n"
            "- Solo incluí en la salida las filas donde la columna 'Nombre' contenga texto manuscrito real. "
            "Si una fila está vacía, solo tiene marcas sin nombre escrito, o el campo de nombre está en blanco, "
            "IGNORALA por completo y NO la incluyas en el JSON de salida.\n"
            "- Ignorá filas donde no haya un nombre de receptor escrito, aunque veas marcas de 'X'. "
            "No inventes filas.\n\n"
            "FORMATO DE SALIDA: JSON estrictamente válido."
        )

    def _get_batch_prompt(self, image_count: int) -> str:
        return (
            f"Recibís {image_count} imágenes de planillas de Speed Dating. "
            "Para CADA imagen, seguí el flujo estricto: primero identificá al propietario "
            "(owner_name) en el ENCABEZADO y luego extraé sus interacciones de la TABLA.\n"
            "Respondé SOLO un array JSON con exactamente un objeto por imagen, "
            "en el MISMO orden en que aparecen las imágenes:\n"
            '[{"owner_name": "str", '
            '"interactions": [{"receptor_name": "str", "interested": bool}]}]\n'
            "Reglas OBLIGATORIAS:\n"
            "- owner_name: SOLO el nombre manuscrito en el encabezado (campo 'Tu nombre y apellido:'). "
            "NUNCA uses un nombre que esté dentro de la tabla. "
            "Si no lo detectás, usá '[PROPIETARIO NO DETECTADO]'.\n"
            "- Los nombres dentro de la tabla son RECEPTORES, nunca el propietario.\n"
            "- Solo incluí filas donde la columna 'Nombre' tenga texto manuscrito real. "
            "Omití filas vacías o sin nombre escrito, aunque tengan marcas.\n"
            "- Sí/✓/marca = true, No/✗/vacío = false.\n"
            "- Nombres exactos como aparecen en la planilla.\n"
            "- Cada marca se asocia ÚNICAMENTE a la fila de texto a su izquierda inmediata. "
            "No reasignes marcas entre filas diferentes."
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