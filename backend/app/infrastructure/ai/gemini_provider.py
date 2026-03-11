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
        """System prompt rediseñado para forzar la jerarquía visual y evitar el desplazamiento de nombres."""
        return (
            "Sos un experto en digitalización de formularios. Tu prioridad absoluta es la INTEGRIDAD DE LA IDENTIDAD.\n\n"
            "REGLA DE ORO: La planilla tiene dos zonas físicamente separadas. NO MEZCLES INFORMACIÓN ENTRE ELLAS.\n\n"
            "ZONA 1: ENCABEZADO (Identificación del Dueño)\n"
            "1. Buscá el logo 'eventio' o el texto impreso 'Tu nombre y apellido:'.\n"
            "2. El texto escrito a mano que está INMEDIATAMENTE a la derecha o debajo de esa etiqueta es el 'owner_name'.\n"
            "3. Este nombre está FÍSICAMENTE ARRIBA de la cuadrícula de la tabla.\n"
            "4. Si no hay nada escrito en este espacio específico del encabezado, el resultado DEBE SER '[PROPIETARIO NO DETECTADO]'.\n\n"
            "ZONA 2: TABLA DE INTERACCIONES (Receptores)\n"
            "1. Bajá la mirada hasta encontrar la cuadrícula (grilla) con las columnas 'Nombre', 'Si', 'No'.\n"
            "2. Los nombres que están DENTRO de las celdas de esta tabla son los 'receptor_name'.\n"
            "3. PROHIBICIÓN CRÍTICA: El primer nombre de la tabla (ej. 'Jose L.') NUNCA es el dueño. Es el primer receptor.\n"
            "4. Si un nombre aparece dentro de un recuadro de la tabla, tenés prohibido asignarlo a 'owner_name'.\n\n"
            "REGLAS DE FILTRADO:\n"
            "- Si una fila de la tabla no tiene un nombre escrito, IGNORALA (aunque tenga una X).\n"
            "- Si el nombre del receptor es ilegible, usá '[NOMBRE ILEGIBLE]'.\n"
            "- Sé extremadamente preciso con las iniciales (ej. 'Maria A.' vs 'Maria P.').\n\n"
            "RESPUESTA: JSON estrictamente válido."
        )

    def _get_batch_prompt(self, image_count: int) -> str:
        return (
            f"Analizá estas {image_count} planillas de forma independiente. "
            "Seguí este proceso para cada una:\n"
            "1. Escaneá el encabezado: Extraé el nombre del dueño (owner_name) que está arriba de la tabla.\n"
            "2. Escaneá la tabla: Extraé los nombres dentro de las filas (receptor_name) y sus marcas (interested: true/false).\n\n"
            "Formato de respuesta:\n"
            '[{"owner_name": "NOMBRE_DEL_ENCABEZADO", '
            '"interactions": [{"receptor_name": "NOMBRE_EN_TABLA", "interested": bool}]}]\n\n'
            "CONDICIÓN DETERMINANTE:\n"
            "- El 'owner_name' es el que escribe la planilla (arriba).\n"
            "- El primer nombre de la tabla (usualmente en la primera fila de la grilla) es SIEMPRE un receptor.\n"
            "- Si confundís el primer nombre de la tabla con el dueño, el sistema fallará. No lo hagas."
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