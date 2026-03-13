import logging
from typing import Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """
    Preprocesador optimizado para resaltar tinta de birome y corregir perspectiva.
    """

    # ── Parámetros de detección ─────────────────────────────────
    BLUR_KERNEL = (5, 5)
    CANNY_LOW = 30
    CANNY_HIGH = 150
    CONTOUR_AREA_RATIO = 0.15 
    APPROX_EPSILON_FACTOR = 0.02 

    # ── Parámetros de Mejora de Tinta (BIROME) ──────────────────
    CLAHE_CLIP_LIMIT = 1.5           # Moderado para el cuerpo
    CLAHE_TILE_SIZE = (8, 8)
    
    HEADER_RATIO = 0.25              # Subimos a 25% para asegurar capturar el nombre
    HEADER_CLAHE_CLIP = 3.0          # Más fuerza para el nombre del dueño
    HEADER_CLAHE_TILE = (2, 2)       # Grilla muy fina para trazos pequeños
    
    GAMMA_CORRECTION = 0.8           # < 1.0 oscurece el trazo de la birome
    
    # Kernel de nitidez (Unsharp Masking style)
    SHARPEN_KERNEL = np.array([
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0]
    ], dtype=np.float32)

    @classmethod
    def preprocess(cls, image_bytes: bytes) -> bytes:
        img = cls._decode(image_bytes)
        if img is None:
            return image_bytes

        # 1. Intentar corregir perspectiva
        contour = cls._detect_paper(img)
        if contour is not None:
            corners = cls._order_corners(contour)
            img = cls._perspective_transform(img, corners)
        
        # 2. Mejora Global (Tinta + Contraste)
        img = cls._adjust_gamma(img, cls.GAMMA_CORRECTION)
        img = cls._enhance_ink(img)
        
        # 3. Mejora Específica de Cabecera (Nombre del Dueño)
        img = cls._enhance_header_zone(img)
        
        return cls._encode(img)

    @classmethod
    def _adjust_gamma(cls, image: np.ndarray, gamma: float) -> np.ndarray:
        """Oscurece los medios tonos para que la birome resalte."""
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 
                         for i in np.arange(0, 256)]).astype("uint8")
        return cv2.LUT(image, table)

    @classmethod
    def _enhance_ink(cls, img: np.ndarray) -> np.ndarray:
        """Resalta el trazo en toda la hoja usando CLAHE en espacio LAB."""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        clahe = cv2.createCLAHE(clipLimit=cls.CLAHE_CLIP_LIMIT, tileGridSize=cls.CLAHE_TILE_SIZE)
        l = clahe.apply(l)
        
        lab = cv2.merge((l, a, b))
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # Nitidez para definir los bordes de las letras
        return cv2.filter2D(enhanced, -1, cls.SHARPEN_KERNEL)

    @classmethod
    def _enhance_header_zone(cls, img: np.ndarray) -> np.ndarray:
        """Tratamiento especial para el nombre del dueño en el tope."""
        h = img.shape[0]
        header_h = int(h * cls.HEADER_RATIO)
        
        header = img[:header_h].copy()
        body = img[header_h:]

        lab = cv2.cvtColor(header, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Usamos una grilla más pequeña (2,2) para detectar detalles mínimos de birome
        clahe = cv2.createCLAHE(clipLimit=cls.HEADER_CLAHE_CLIP, tileGridSize=cls.HEADER_CLAHE_TILE)
        l = clahe.apply(l)

        header_lab = cv2.merge((l, a, b))
        header_final = cv2.cvtColor(header_lab, cv2.COLOR_LAB2BGR)

        return np.vstack([header_final, body])

    # ── (Mantené tus funciones de _detect_paper, _order_corners, etc. igual) ──