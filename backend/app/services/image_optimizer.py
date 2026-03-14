import base64
import logging
from io import BytesIO

from PIL import Image

logger = logging.getLogger(__name__)


class ImageOptimizer:
    """Optimiza imágenes antes de enviarlas a la API de Gemini para reducir tokens."""

    MAX_DIMENSION = 2048   # era 1024 — checkboxes quedaban de 8-12px, ilegibles
    JPEG_QUALITY = 92      # era 80

    @staticmethod
    def optimize_base64(image_base64: str) -> str:
        """
        Recibe una imagen en base64, la redimensiona y comprime.
        Devuelve la imagen optimizada en base64.
        Si falla, devuelve la imagen original.
        """
        try:
            original_size = len(image_base64)
            raw = base64.b64decode(image_base64)
            img = Image.open(BytesIO(raw))

            # Convertir RGBA/P a RGB (necesario para JPEG)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Redimensionar manteniendo aspecto si excede MAX_DIMENSION
            w, h = img.size
            max_dim = max(w, h)
            if max_dim > ImageOptimizer.MAX_DIMENSION:
                ratio = ImageOptimizer.MAX_DIMENSION / max_dim
                new_size = (int(w * ratio), int(h * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            # Guardar como JPEG con calidad 80
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=ImageOptimizer.JPEG_QUALITY)
            optimized_b64 = base64.b64encode(buffer.getvalue()).decode()

            new_size_len = len(optimized_b64)
            reduction = (1 - new_size_len / original_size) * 100
            logger.info(
                f"[ImageOptimizer] Imagen optimizada: {reduction:.1f}%% reducción "
                f"({original_size} → {new_size_len} chars b64)"
            )

            return optimized_b64
        except Exception as e:
            logger.warning(
                f"[ImageOptimizer] Error optimizando imagen, usando original: {e}"
            )
            return image_base64

    @staticmethod
    def optimize_batch(images_base64: list) -> list:
        """Optimiza una lista de imágenes en base64."""
        return [ImageOptimizer.optimize_base64(img) for img in images_base64]
