import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """
    Preprocesador: Mejora de tinta (Gamma, CLAHE y Nitidez) sobre la imagen original completa.
    """

    # ── Parámetros de Mejora de Tinta (BIROME) ──────────────────
    GAMMA_CORRECTION = 0.8           # < 1.0 oscurece el trazo de la birome
    HEADER_RATIO = 0.25              # Zona para el nombre del dueño
    HEADER_CLAHE_CLIP = 3.0
    HEADER_CLAHE_TILE = (2, 2)       # Grilla ultra fina para trazos pequeños

    SHARPEN_KERNEL = np.array([
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0]
    ], dtype=np.float32)

    @classmethod
    def preprocess(cls, image_bytes: bytes) -> bytes:
        """Pipeline: decodifica, mejora tinta y codifica (sin recorte de perspectiva)."""
        img = cls._decode(image_bytes)
        if img is None:
            logger.error("[Preprocessor] No se pudo decodificar la imagen.")
            return image_bytes

        img = cls._adjust_gamma(img, cls.GAMMA_CORRECTION)
        img = cls._enhance_ink(img)
        img = cls._enhance_header_zone(img)

        return cls._encode(img)

    # ── Métodos de Mejora Visual ────────────────────────────────

    @classmethod
    def _adjust_gamma(cls, image: np.ndarray, gamma: float) -> np.ndarray:
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 
                         for i in np.arange(0, 256)]).astype("uint8")
        return cv2.LUT(image, table)

    @classmethod
    def _enhance_ink(cls, img: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
        return cv2.filter2D(enhanced, -1, cls.SHARPEN_KERNEL)

    @classmethod
    def _enhance_header_zone(cls, img: np.ndarray) -> np.ndarray:
        h = img.shape[0]
        header_h = int(h * cls.HEADER_RATIO)
        header = img[:header_h].copy()
        body = img[header_h:]

        lab = cv2.cvtColor(header, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=cls.HEADER_CLAHE_CLIP, tileGridSize=cls.HEADER_CLAHE_TILE)
        l = clahe.apply(l)

        header_final = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
        return np.vstack([header_final, body])

    # ── Funciones Base ─────────────────────────────────────────

    @staticmethod
    def _decode(image_bytes: bytes) -> Optional[np.ndarray]:
        nparr = np.frombuffer(image_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    @staticmethod
    def _encode(image: np.ndarray) -> bytes:
        _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return buffer.tobytes()