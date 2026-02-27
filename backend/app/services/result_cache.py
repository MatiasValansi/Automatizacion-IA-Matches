import hashlib
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ResultCache:
    """Cache en memoria para evitar reprocesar imágenes idénticas con la API de Gemini."""

    def __init__(self, ttl_minutes: int = 60):
        self._cache: dict[str, dict[str, Any]] = {}
        self._ttl_seconds = ttl_minutes * 60

    def _make_key(self, image_base64: str) -> str:
        """Genera un hash MD5 de los primeros 10000 caracteres del base64."""
        snippet = image_base64[:10000]
        return hashlib.md5(snippet.encode()).hexdigest()

    def get(self, image_base64: str) -> Optional[dict]:
        """Busca un resultado en cache. Devuelve None si no existe o expiró."""
        key = self._make_key(image_base64)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > self._ttl_seconds:
            del self._cache[key]
            return None
        logger.info(f"[ResultCache] Cache HIT para imagen (key={key[:8]}...)")
        return entry["value"]

    def set(self, image_base64: str, result: Any) -> None:
        """Almacena un resultado en cache asociado a la imagen."""
        key = self._make_key(image_base64)
        self._cache[key] = {
            "value": result,
            "timestamp": time.time(),
        }

    def clear(self) -> None:
        """Limpia todo el cache."""
        self._cache.clear()


# Instancia global exportada
image_cache = ResultCache()
