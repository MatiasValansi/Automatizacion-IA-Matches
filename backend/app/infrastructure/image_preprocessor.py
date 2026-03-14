import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """
    Preprocesador: Corrección de perspectiva con margen superior expandido,
    seguida de mejora de tinta (Gamma, CLAHE y Nitidez).
    """

    # ── Parámetros de Detección de Hoja ──────────────────────────
    BLUR_KERNEL = (5, 5)
    CANNY_LOW = 50
    CANNY_HIGH = 200
    CONTOUR_AREA_RATIO = 0.2
    APPROX_EPSILON_FACTOR = 0.02
    TOP_MARGIN_EXPAND = 0.08      # 8 % de la altura total de la imagen (era 0.30, demasiado agresivo)

    # ── Parámetros de Mejora de Tinta (post-enderezado) ──────────
    GAMMA_CORRECTION = 0.7           # más agresivo para oscurecer trazos
    INK_CLAHE_CLIP = 3.0             # CLAHE agresivo para las X
    INK_CLAHE_TILE = (8, 8)
    HEADER_RATIO = 0.25
    HEADER_CLAHE_CLIP = 3.0
    HEADER_CLAHE_TILE = (2, 2)

    SHARPEN_KERNEL = np.array([
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0]
    ], dtype=np.float32)

    @classmethod
    def preprocess(cls, image_bytes: bytes) -> bytes:
        """Pipeline: decodifica → endereza (con margen superior) → mejora tinta → codifica."""
        img = cls._decode(image_bytes)
        if img is None:
            logger.error("[Preprocessor] No se pudo decodificar la imagen.")
            return image_bytes

        # 1. Corrección de perspectiva con margen superior expandido
        img = cls._deskew_with_margin(img)

        # 2. Mejora de tinta (solo después de enderezar)
        img = cls._adjust_gamma(img, cls.GAMMA_CORRECTION)
        img = cls._enhance_ink(img)
        img = cls._enhance_header_zone(img)

        return cls._encode(img)

    # ── Corrección de Perspectiva ─────────────────────────────────

    @classmethod
    def _deskew_with_margin(cls, img: np.ndarray) -> np.ndarray:
        """Detecta la hoja, expande los puntos superiores y aplica warpPerspective."""
        corners = cls._detect_paper(img)
        if corners is None:
            logger.info("[Preprocessor] No se detectó hoja; se omite corrección de perspectiva.")
            return img

        # Si la hoja ya ocupa >85% del frame, el warp solo introduce ruido/distorsión
        img_area = img.shape[0] * img.shape[1]
        sheet_area = cv2.contourArea(corners)
        if sheet_area / img_area > 0.85:
            logger.info("[Preprocessor] Hoja ocupa >85% del frame; se omite warp.")
            return img

        ordered = cls._order_corners(corners)
        expanded = cls._expand_top_corners(ordered, img.shape[0])

        return cls._perspective_transform(img, expanded)

    @classmethod
    def _detect_paper(cls, img: np.ndarray) -> Optional[np.ndarray]:
        """Detecta el contorno rectangular más grande (la hoja)."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, cls.BLUR_KERNEL, 0)
        edges = cv2.Canny(blurred, cls.CANNY_LOW, cls.CANNY_HIGH)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        img_area = img.shape[0] * img.shape[1]
        min_area = img_area * cls.CONTOUR_AREA_RATIO

        for cnt in sorted(contours, key=cv2.contourArea, reverse=True):
            if cv2.contourArea(cnt) < min_area:
                break
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, cls.APPROX_EPSILON_FACTOR * peri, True)
            if len(approx) == 4:
                logger.info(f"[Preprocessor] Hoja detectada (área={cv2.contourArea(cnt):.0f})")
                return approx.reshape(4, 2)

        return None

    @staticmethod
    def _order_corners(pts: np.ndarray) -> np.ndarray:
        """Ordena: [top-left, top-right, bottom-right, bottom-left]."""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        d = np.diff(pts, axis=1).flatten()
        rect[1] = pts[np.argmin(d)]
        rect[3] = pts[np.argmax(d)]
        return rect

    @classmethod
    def _expand_top_corners(cls, corners: np.ndarray, img_height: int) -> np.ndarray:
        """Desplaza top-left y top-right un 30 % de la altura total hacia arriba."""
        expanded = corners.copy()
        offset = img_height * cls.TOP_MARGIN_EXPAND
        expanded[0][1] = max(0, expanded[0][1] - offset)  # top-left Y
        expanded[1][1] = max(0, expanded[1][1] - offset)  # top-right Y
        return expanded

    @staticmethod
    def _perspective_transform(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """Aplica warpPerspective para enderezar la hoja."""
        tl, tr, br, bl = corners
        max_width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
        max_height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))

        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ], dtype=np.float32)

        matrix = cv2.getPerspectiveTransform(corners, dst)
        warped = cv2.warpPerspective(img, matrix, (max_width, max_height))
        logger.info(f"[Preprocessor] Perspectiva corregida → {max_width}×{max_height}")
        return warped

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
        clahe = cv2.createCLAHE(clipLimit=cls.INK_CLAHE_CLIP, tileGridSize=cls.INK_CLAHE_TILE)
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
