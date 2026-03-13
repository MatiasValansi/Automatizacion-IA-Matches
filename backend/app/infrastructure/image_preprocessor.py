import logging
from typing import Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """
    Preprocesador avanzado: Corrección de perspectiva + Mejora de tinta (Gamma & CLAHE).
    """

    # ── Parámetros de detección ─────────────────────────────────
    BLUR_KERNEL = (5, 5)
    CANNY_LOW = 30
    CANNY_HIGH = 150
    CONTOUR_AREA_RATIO = 0.15 
    APPROX_EPSILON_FACTOR = 0.02 

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
        """Pipeline completo: decodifica, corrige perspectiva, mejora tinta y codifica."""
        img = cls._decode(image_bytes)
        if img is None:
            logger.error("[Preprocessor] No se pudo decodificar la imagen.")
            return image_bytes

        # 1. Intentar detectar el papel y corregir perspectiva
        contour = cls._detect_paper(img)
        if contour is not None:
            corners = cls._order_corners(contour)
            img = cls._perspective_transform(img, corners)
            logger.info("[Preprocessor] Perspectiva corregida.")
        
        # 2. Aplicar mejoras visuales para birome
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

    # ── Detección de Papel y Perspectiva ───────────────────────

    @classmethod
    def _detect_paper(cls, img: np.ndarray) -> Optional[np.ndarray]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, cls.BLUR_KERNEL, 0)
        edges = cv2.Canny(blurred, cls.CANNY_LOW, cls.CANNY_HIGH)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return None

        img_area = img.shape[0] * img.shape[1]
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True):
            if cv2.contourArea(cnt) < img_area * cls.CONTOUR_AREA_RATIO: break
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, cls.APPROX_EPSILON_FACTOR * peri, True)
            if len(approx) == 4:
                return approx.reshape(4, 2).astype(np.float32)
        return None

    @staticmethod
    def _order_corners(pts: np.ndarray) -> np.ndarray:
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        d = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(d)]
        rect[3] = pts[np.argmax(d)]
        return rect

    @staticmethod
    def _perspective_transform(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
        (tl, tr, br, bl) = corners
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
        M = cv2.getPerspectiveTransform(corners, dst)
        return cv2.warpPerspective(img, M, (maxWidth, maxHeight))

    # ── Funciones Base (Las que faltaban) ─────────────────────

    @staticmethod
    def _decode(image_bytes: bytes) -> Optional[np.ndarray]:
        nparr = np.frombuffer(image_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    @staticmethod
    def _encode(image: np.ndarray) -> bytes:
        _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return buffer.tobytes()