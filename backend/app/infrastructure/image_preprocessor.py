"""
Preprocesador avanzado de imágenes para planillas con distorsión de perspectiva.

Combina múltiples estrategias de detección de bordes del papel y aplica
transformación de perspectiva (deskewing) + mejora de contraste para
maximizar la precisión del OCR con Gemini.

Pipeline:
  1. Detección de contorno del papel (Canny → Adaptive Threshold → Hough Lines)
  2. Transformación de perspectiva (warpPerspective)
  3. Post-procesamiento (contraste CLAHE + nitidez)
  4. Mejora de cabecera (CLAHE fuerte + binarización adaptativa en el 20 % superior)
"""

import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Preprocesador robusto con fallback en cadena para detectar
    la hoja de papel y corregir la perspectiva.
    """

    # ── Parámetros de detección ─────────────────────────────────

    BLUR_KERNEL = (5, 5)
    CANNY_LOW = 30
    CANNY_HIGH = 150
    CONTOUR_AREA_RATIO = 0.15        # mínimo 15 % del área de la imagen
    APPROX_EPSILON_FACTOR = 0.02     # tolerancia para aproximar polígonos
    ADAPTIVE_BLOCK_SIZE = 11         # bloque para threshold adaptativo
    ADAPTIVE_C = 2                   # constante para threshold adaptativo
    CLAHE_CLIP_LIMIT = 2.0           # límite de contraste CLAHE
    CLAHE_TILE_SIZE = (8, 8)         # tamaño de grilla CLAHE
    HEADER_RATIO = 0.20               # fracción superior de la imagen (cabecera)
    HEADER_CLAHE_CLIP = 4.0           # CLAHE más agresivo para cabecera
    HEADER_CLAHE_TILE = (4, 4)        # grilla más fina para cabecera
    HEADER_ADAPTIVE_BLOCK = 31        # bloque para binarización de cabecera
    HEADER_ADAPTIVE_C = 10            # constante para binarización de cabecera
    SHARPEN_KERNEL = np.array(       # kernel de nitidez suave
        [[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32
    )

    # ── Interfaz pública ────────────────────────────────────────

    @classmethod
    def preprocess(cls, image_bytes: bytes) -> bytes:
        """
        Pipeline completo de preprocesamiento:
          1. Decodifica la imagen.
          2. Intenta detectar el contorno del papel con 3 estrategias.
          3. Si encuentra contorno → warpPerspective.
          4. Aplica mejora de contraste y nitidez.
          5. Devuelve JPEG de alta calidad.

        Si no detecta contorno, aplica solo la mejora de contraste/nitidez
        sobre la imagen original.
        """
        img = cls._decode(image_bytes)
        if img is None:
            logger.warning("[Preprocessor] No se pudo decodificar la imagen")
            return image_bytes

        contour = cls._detect_paper(img)
        if contour is not None:
            corners = cls._order_corners(contour)
            img = cls._perspective_transform(img, corners)
            logger.info("[Preprocessor] Perspectiva corregida exitosamente")
        else:
            logger.info(
                "[Preprocessor] No se detectó contorno; "
                "se aplica solo mejora de contraste/nitidez"
            )

        img = cls._enhance(img)
        img = cls._enhance_header(img)
        return cls._encode(img)

    @classmethod
    def preprocess_batch(cls, images: list[bytes]) -> list[bytes]:
        """Aplica preprocess a un lote de imágenes."""
        return [cls.preprocess(img) for img in images]

    # ── Detección del papel (cadena de fallbacks) ───────────────

    @classmethod
    def _detect_paper(cls, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Intenta detectar el contorno rectangular de la hoja con
        tres estrategias en orden de robustez:

        1. Canny edge detection (rápido, funciona en imágenes limpias)
        2. Adaptive threshold (mejor para iluminación despareja)
        3. Hough lines (detecta líneas rectas y reconstruye el rectángulo)
        """
        for strategy_name, strategy_fn in [
            ("Canny", cls._detect_via_canny),
            ("AdaptiveThreshold", cls._detect_via_adaptive_threshold),
            ("HoughLines", cls._detect_via_hough_lines),
        ]:
            result = strategy_fn(img)
            if result is not None:
                logger.info(
                    f"[Preprocessor] Contorno detectado con estrategia: {strategy_name}"
                )
                return result
        return None

    @classmethod
    def _detect_via_canny(cls, img: np.ndarray) -> Optional[np.ndarray]:
        """Estrategia 1: Canny + findContours."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, cls.BLUR_KERNEL, 0)
        edges = cv2.Canny(blurred, cls.CANNY_LOW, cls.CANNY_HIGH)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=2)
        edges = cv2.erode(edges, kernel, iterations=1)

        return cls._find_quad_contour(img, edges)

    @classmethod
    def _detect_via_adaptive_threshold(
        cls, img: np.ndarray
    ) -> Optional[np.ndarray]:
        """Estrategia 2: Umbral adaptativo + morfología."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, cls.BLUR_KERNEL, 0)

        binary = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            cls.ADAPTIVE_BLOCK_SIZE,
            cls.ADAPTIVE_C,
        )

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)
        binary = cv2.dilate(binary, kernel, iterations=2)

        return cls._find_quad_contour(img, binary)

    @classmethod
    def _detect_via_hough_lines(
        cls, img: np.ndarray
    ) -> Optional[np.ndarray]:
        """
        Estrategia 3: Detecta líneas con HoughLines y reconstruye
        el rectángulo a partir de las intersecciones de las líneas
        horizontales y verticales dominantes.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, cls.BLUR_KERNEL, 0)
        edges = cv2.Canny(blurred, 50, 150)

        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=150)
        if lines is None or len(lines) < 4:
            return None

        h_lines = []
        v_lines = []
        for line in lines:
            rho, theta = line[0]
            # Horizontal: theta ≈ 0 o ≈ π
            if abs(theta) < np.pi / 6 or abs(theta - np.pi) < np.pi / 6:
                v_lines.append((rho, theta))
            # Vertical: theta ≈ π/2
            elif abs(theta - np.pi / 2) < np.pi / 6:
                h_lines.append((rho, theta))

        if len(h_lines) < 2 or len(v_lines) < 2:
            return None

        # Tomar las líneas horizontales extremas (top/bottom)
        h_lines.sort(key=lambda x: x[0])
        top_line = h_lines[0]
        bottom_line = h_lines[-1]

        # Tomar las líneas verticales extremas (left/right)
        v_lines.sort(key=lambda x: x[0])
        left_line = v_lines[0]
        right_line = v_lines[-1]

        # Calcular intersecciones
        corners = []
        for h in [top_line, bottom_line]:
            for v in [left_line, right_line]:
                pt = cls._line_intersection(h, v)
                if pt is not None:
                    corners.append(pt)

        if len(corners) != 4:
            return None

        # Validar que los puntos estén dentro de la imagen
        img_h, img_w = img.shape[:2]
        for x, y in corners:
            if x < -img_w * 0.1 or x > img_w * 1.1:
                return None
            if y < -img_h * 0.1 or y > img_h * 1.1:
                return None

        pts = np.array(corners, dtype=np.float32)

        # Validar área mínima
        area = cv2.contourArea(pts.reshape(-1, 1, 2).astype(np.int32))
        if area < img_h * img_w * cls.CONTOUR_AREA_RATIO:
            return None

        return pts

    # ── Utilidades de detección ─────────────────────────────────

    @classmethod
    def _find_quad_contour(
        cls, img: np.ndarray, edge_map: np.ndarray
    ) -> Optional[np.ndarray]:
        """
        Busca el contorno cuadrilátero más grande en un mapa de bordes.
        Retorna los 4 puntos o None.
        """
        contours, _ = cv2.findContours(
            edge_map, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return None

        img_area = img.shape[0] * img.shape[1]
        min_area = img_area * cls.CONTOUR_AREA_RATIO

        for cnt in sorted(contours, key=cv2.contourArea, reverse=True):
            if cv2.contourArea(cnt) < min_area:
                break

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(
                cnt, cls.APPROX_EPSILON_FACTOR * peri, True
            )

            if len(approx) == 4:
                return approx.reshape(4, 2).astype(np.float32)

        return None

    @staticmethod
    def _line_intersection(
        line1: tuple, line2: tuple
    ) -> Optional[tuple[float, float]]:
        """
        Calcula el punto de intersección de dos líneas en formato
        (rho, theta) de Hough.
        """
        rho1, theta1 = line1
        rho2, theta2 = line2

        cos1, sin1 = np.cos(theta1), np.sin(theta1)
        cos2, sin2 = np.cos(theta2), np.sin(theta2)

        det = cos1 * sin2 - cos2 * sin1
        if abs(det) < 1e-8:
            return None  # líneas paralelas

        x = (rho1 * sin2 - rho2 * sin1) / det
        y = (rho2 * cos1 - rho1 * cos2) / det
        return (x, y)

    # ── Ordenamiento de esquinas ────────────────────────────────

    @staticmethod
    def _order_corners(pts: np.ndarray) -> np.ndarray:
        """
        Ordena 4 puntos en sentido:
        [top-left, top-right, bottom-right, bottom-left].
        """
        pts = pts.astype(np.float32)
        rect = np.zeros((4, 2), dtype=np.float32)

        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]   # top-left
        rect[2] = pts[np.argmax(s)]   # bottom-right

        d = np.diff(pts, axis=1).flatten()
        rect[1] = pts[np.argmin(d)]   # top-right
        rect[3] = pts[np.argmax(d)]   # bottom-left

        return rect

    # ── Transformación de perspectiva ───────────────────────────

    @staticmethod
    def _perspective_transform(
        img: np.ndarray, corners: np.ndarray
    ) -> np.ndarray:
        """
        Aplica warpPerspective para obtener la vista cenital de la hoja.
        """
        tl, tr, br, bl = corners

        width_top = np.linalg.norm(tr - tl)
        width_bot = np.linalg.norm(br - bl)
        max_width = int(max(width_top, width_bot))

        height_left = np.linalg.norm(bl - tl)
        height_right = np.linalg.norm(br - tr)
        max_height = int(max(height_left, height_right))

        if max_width <= 0 or max_height <= 0:
            return img

        dst = np.array(
            [
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1],
            ],
            dtype=np.float32,
        )

        matrix = cv2.getPerspectiveTransform(corners, dst)
        warped = cv2.warpPerspective(img, matrix, (max_width, max_height))

        logger.info(
            f"[Preprocessor] Perspectiva aplicada → {max_width}×{max_height}"
        )
        return warped

    # ── Post-procesamiento (contraste + nitidez) ────────────────

    @classmethod
    def _enhance(cls, img: np.ndarray) -> np.ndarray:
        """
        Mejora la imagen post-deskew para maximizar legibilidad OCR:
        1. CLAHE (Contrast Limited Adaptive Histogram Equalization)
           en el canal L de LAB para ecualizar iluminación sin alterar color.
        2. Filtro de nitidez suave para realzar bordes de texto manuscrito.
        """
        # CLAHE en espacio LAB para ecualizar iluminación
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=cls.CLAHE_CLIP_LIMIT, tileGridSize=cls.CLAHE_TILE_SIZE
        )
        l_enhanced = clahe.apply(l_channel)

        lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
        img_enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        # Nitidez suave
        img_enhanced = cv2.filter2D(img_enhanced, -1, cls.SHARPEN_KERNEL)

        return img_enhanced

    # ── Mejora de cabecera ──────────────────────────────────────

    @classmethod
    def _enhance_header(cls, img: np.ndarray) -> np.ndarray:
        """
        Mejora la zona del encabezado (20 % superior) para resaltar
        el trazo de birome y eliminar sombras de celular:

        1. Extrae el ROI de cabecera.
        2. Aplica CLAHE fuerte sobre el canal L (LAB) para normalizar brillo.
        3. Binariza con umbral adaptativo para obtener trazo nítido B/N.
        4. Re-ensambla la cabecera mejorada con el cuerpo original.
        """
        h = img.shape[0]
        header_h = int(h * cls.HEADER_RATIO)
        if header_h < 10:
            return img

        header = img[:header_h].copy()
        body = img[header_h:]

        # --- CLAHE fuerte en espacio LAB ---
        lab = cv2.cvtColor(header, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=cls.HEADER_CLAHE_CLIP,
            tileGridSize=cls.HEADER_CLAHE_TILE,
        )
        l_ch = clahe.apply(l_ch)

        # --- Binarización adaptativa ---
        binary = cv2.adaptiveThreshold(
            l_ch,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            cls.HEADER_ADAPTIVE_BLOCK,
            cls.HEADER_ADAPTIVE_C,
        )

        # Convertir a BGR (3 canales) para re-ensamblar
        header_enhanced = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

        result = np.vstack([header_enhanced, body])
        logger.info(
            "[Preprocessor] Cabecera mejorada (top %d px de %d)",
            header_h,
            h,
        )
        return result

    # ── Codificación / Decodificación ───────────────────────────

    @staticmethod
    def _decode(image_bytes: bytes) -> Optional[np.ndarray]:
        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img

    @staticmethod
    def _encode(image: np.ndarray) -> bytes:
        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise RuntimeError("Error codificando imagen preprocesada")
        return buf.tobytes()
