"""
Módulo de preprocesamiento de imágenes con OpenCV.
Corrige la distorsión de perspectiva (paralaje/inclinación) en planillas
fotografiadas, enderezándolas antes de enviarlas a la IA.
"""

import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Aplica corrección de perspectiva (deskewing) a imágenes de planillas."""

    # ── Parámetros de detección ─────────────────────────────────

    BLUR_KERNEL = (5, 5)
    CANNY_LOW = 50
    CANNY_HIGH = 200
    CONTOUR_AREA_RATIO = 0.2      # mínimo 20 % del área de la imagen
    APPROX_EPSILON_FACTOR = 0.02  # tolerancia para aproximar polígonos
    OUTPUT_MARGIN = 10            # px de margen al recortar

    # ── Interfaz pública ────────────────────────────────────────

    @staticmethod
    def deskew(image_bytes: bytes) -> bytes:
        """
        Recibe bytes JPEG/PNG, detecta la hoja de papel y aplica
        transformación de perspectiva. Devuelve la imagen corregida
        como bytes JPEG.  Si no logra detectar el contorno, devuelve
        la imagen original sin modificar.
        """
        img = ImageProcessor._decode(image_bytes)
        if img is None:
            logger.warning("[ImageProcessor] No se pudo decodificar la imagen")
            return image_bytes

        contour = ImageProcessor._find_paper_contour(img)
        if contour is None:
            logger.info(
                "[ImageProcessor] No se detectó contorno de hoja; "
                "se devuelve la imagen original"
            )
            return image_bytes

        corners = ImageProcessor._order_corners(contour)
        warped = ImageProcessor._perspective_transform(img, corners)

        return ImageProcessor._encode(warped)

    @staticmethod
    def deskew_batch(images: list[bytes]) -> list[bytes]:
        """Aplica deskew a un lote de imágenes."""
        return [ImageProcessor.deskew(img) for img in images]

    # ── Decodificación / Codificación ───────────────────────────

    @staticmethod
    def _decode(image_bytes: bytes) -> Optional[np.ndarray]:
        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img

    @staticmethod
    def _encode(image: np.ndarray) -> bytes:
        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise RuntimeError("Error codificando imagen corregida")
        return buf.tobytes()

    # ── Detección del contorno de la hoja ───────────────────────

    @staticmethod
    def _find_paper_contour(img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta el contorno rectangular más grande de la imagen
        (presumiblemente la hoja de papel).

        Pipeline:
        1. Escala de grises + desenfoque gaussiano
        2. Detección de bordes Canny
        3. Dilatación para cerrar huecos
        4. findContours + filtrado por área y forma cuadrilátera
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, ImageProcessor.BLUR_KERNEL, 0)
        edges = cv2.Canny(
            blurred,
            ImageProcessor.CANNY_LOW,
            ImageProcessor.CANNY_HIGH,
        )

        # Dilatar para unir bordes discontinuos
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None

        img_area = img.shape[0] * img.shape[1]
        min_area = img_area * ImageProcessor.CONTOUR_AREA_RATIO

        # Ordenar por área descendente y buscar el primer cuadrilátero
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True):
            if cv2.contourArea(cnt) < min_area:
                break

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(
                cnt, ImageProcessor.APPROX_EPSILON_FACTOR * peri, True
            )

            if len(approx) == 4:
                logger.info(
                    "[ImageProcessor] Contorno de hoja detectado "
                    f"(área={cv2.contourArea(cnt):.0f}, "
                    f"img_area={img_area})"
                )
                return approx.reshape(4, 2)

        return None

    # ── Ordenamiento de esquinas ────────────────────────────────

    @staticmethod
    def _order_corners(pts: np.ndarray) -> np.ndarray:
        """
        Ordena las 4 esquinas en sentido:
        [top-left, top-right, bottom-right, bottom-left].
        """
        rect = np.zeros((4, 2), dtype=np.float32)

        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]   # top-left:     menor suma x+y
        rect[2] = pts[np.argmax(s)]   # bottom-right: mayor suma x+y

        d = np.diff(pts, axis=1).flatten()
        rect[1] = pts[np.argmin(d)]   # top-right:    menor diferencia y-x
        rect[3] = pts[np.argmax(d)]   # bottom-left:  mayor diferencia y-x

        return rect

    # ── Transformación de perspectiva ───────────────────────────

    @staticmethod
    def _perspective_transform(
        img: np.ndarray, corners: np.ndarray
    ) -> np.ndarray:
        """
        Calcula las dimensiones del rectángulo destino y aplica
        warpPerspective para obtener la vista cenital de la hoja.
        """
        tl, tr, br, bl = corners

        # Ancho = máximo entre distancia top y distancia bottom
        width_top = np.linalg.norm(tr - tl)
        width_bot = np.linalg.norm(br - bl)
        max_width = int(max(width_top, width_bot))

        # Alto = máximo entre distancia left y distancia right
        height_left = np.linalg.norm(bl - tl)
        height_right = np.linalg.norm(br - tr)
        max_height = int(max(height_left, height_right))

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
            f"[ImageProcessor] Perspectiva corregida → {max_width}×{max_height}"
        )
        return warped
