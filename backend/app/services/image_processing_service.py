# CAMINHO: backend/app/services/image_processing_service.py
"""
ImageProcessingService — pipeline de visão computacional para biometria de peixes.

Pipeline por imagem:
  1. rembg   → remove o fundo → máscara binária RGBA
  2. OpenCV  → detecta marcador ArUco → fator px/cm
               (fallback: fator informado manualmente pelo usuário)
  3. OpenCV  → contornos → bounding box em px e cm
  4. OpenCV  → área da máscara em px e cm²

Configuração via variáveis de ambiente (.env):
  ARUCO_MARKER_SIZE_CM=10.0     tamanho físico do lado do marcador em cm
  ARUCO_DICT=DICT_4X4_50        dicionário ArUco (ver lista abaixo)

Dicionários suportados:
  DICT_4X4_50, DICT_4X4_100, DICT_5X5_50, DICT_5X5_100,
  DICT_6X6_50, DICT_ARUCO_ORIGINAL
"""

import io
import logging
import os
from typing import Dict, Any, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Configuração ArUco (lida do .env) ─────────────────────────────────────────

ARUCO_MARKER_SIZE_CM: float = float(os.getenv("ARUCO_MARKER_SIZE_CM", "10.0"))

_ARUCO_DICT_MAP = {
    "DICT_4X4_50": 0,
    "DICT_4X4_100": 1,
    "DICT_5X5_50": 4,
    "DICT_5X5_100": 5,
    "DICT_6X6_50": 8,
    "DICT_6X6_100": 9,
    "DICT_ARUCO_ORIGINAL": 16,
}
_ARUCO_DICT_NAME: str = os.getenv("ARUCO_DICT", "DICT_4X4_50")

# ── Verificação de dependências opcionais ──────────────────────────────────────

try:
    from rembg import remove as rembg_remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    logger.warning("[img_proc] rembg não instalado — instale com: pip install rembg")

try:
    import cv2
    CV2_AVAILABLE = True
    # Verifica se o módulo ArUco está disponível (requer opencv-contrib-python)
    ARUCO_AVAILABLE = hasattr(cv2, "aruco")
    if not ARUCO_AVAILABLE:
        logger.warning("[img_proc] ArUco não disponível — instale opencv-contrib-python")
except ImportError:
    CV2_AVAILABLE = False
    ARUCO_AVAILABLE = False
    logger.warning("[img_proc] opencv não instalado — instale com: pip install opencv-contrib-python")

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ImageProcessingService:
    """Pipeline de processamento de imagem para biometria de peixe."""

    # ── Remoção de fundo ─────────────────────────────────────────────────────

    def remove_background(self, image_bytes: bytes) -> Tuple[np.ndarray, np.ndarray]:
        """
        Remove fundo usando rembg (U2Net).

        Returns:
            (img_rgba: ndarray H×W×4,  mask_binary: ndarray H×W uint8)
        Raises:
            RuntimeError se rembg não estiver instalado
        """
        if not REMBG_AVAILABLE:
            raise RuntimeError(
                "rembg não está instalado. Execute: pip install rembg"
            )
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow não está instalado. Execute: pip install Pillow")

        output_bytes = rembg_remove(image_bytes)
        img_rgba = PILImage.open(io.BytesIO(output_bytes)).convert("RGBA")
        img_array = np.array(img_rgba, dtype=np.uint8)

        # Canal alpha → máscara binária (0 ou 255)
        alpha = img_array[:, :, 3]
        mask = np.where(alpha > 127, np.uint8(255), np.uint8(0))

        return img_array, mask

    # ── Detecção de marcador ArUco ────────────────────────────────────────────

    def detect_aruco_scale(
        self,
        image_bytes: bytes,
        marker_size_cm: float = ARUCO_MARKER_SIZE_CM,
    ) -> Optional[float]:
        """
        Detecta o marcador ArUco e retorna o fator de escala em px/cm.
        Retorna None se nenhum marcador for encontrado.

        Args:
            image_bytes    : bytes da imagem original (antes de remover fundo)
            marker_size_cm : tamanho físico do lado do marcador em cm
        """
        if not CV2_AVAILABLE or not ARUCO_AVAILABLE:
            logger.warning("[img_proc] ArUco indisponível — usando fator manual")
            return None

        nparr = np.frombuffer(image_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            logger.warning("[img_proc] não foi possível decodificar a imagem para ArUco")
            return None

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Tenta múltiplos dicionários para maior robustez
        dict_ids_to_try = list(set([
            _ARUCO_DICT_MAP.get(_ARUCO_DICT_NAME, 0),
            0, 4, 8,   # DICT_4X4_50, DICT_5X5_50, DICT_6X6_50
        ]))

        for dict_id in dict_ids_to_try:
            try:
                aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
                params = cv2.aruco.DetectorParameters()
                detector = cv2.aruco.ArucoDetector(aruco_dict, params)
                corners, ids, _ = detector.detectMarkers(gray)
            except AttributeError:
                # Fallback para API antiga (OpenCV < 4.7)
                try:
                    aruco_dict = cv2.aruco.Dictionary_get(dict_id)
                    params = cv2.aruco.DetectorParameters_create()
                    corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)
                except Exception:
                    continue
            except Exception:
                continue

            if ids is not None and len(ids) > 0:
                corner = corners[0][0]   # shape: (4, 2) — 4 cantos em px
                # Média dos 4 lados do marcador para robustez
                sides = [
                    np.linalg.norm(corner[0] - corner[1]),
                    np.linalg.norm(corner[1] - corner[2]),
                    np.linalg.norm(corner[2] - corner[3]),
                    np.linalg.norm(corner[3] - corner[0]),
                ]
                avg_side_px = float(np.mean(sides))
                scale = avg_side_px / marker_size_cm
                logger.info(
                    "[img_proc] ArUco detectado: %.1f px/lado → escala=%.2f px/cm",
                    avg_side_px, scale,
                )
                return scale

        logger.info("[img_proc] nenhum marcador ArUco detectado na imagem")
        return None

    # ── Visualização: máscara + bounding box ─────────────────────────────────

    def generate_visualization(
        self,
        image_bytes: bytes,
        mask: np.ndarray,
    ) -> str:
        """
        Gera imagem de visualização com máscara (overlay verde) e bounding box
        (retângulo amarelo) sobrepostos à imagem original.

        Returns:
            String base64 do JPEG resultante, ou "" em caso de erro.
        """
        import base64

        if not CV2_AVAILABLE:
            return ""

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return ""

            h_img, w_img = img.shape[:2]

            # Redimensiona máscara se houver diferença (rembg preserva dimensões,
            # mas por segurança verificamos)
            if mask.shape[:2] != (h_img, w_img):
                mask = cv2.resize(mask, (w_img, h_img), interpolation=cv2.INTER_NEAREST)

            # ── Overlay da máscara (verde semi-transparente) ──────────────────
            overlay = img.copy()
            overlay[mask > 0] = (30, 180, 60)  # BGR verde
            img_viz = cv2.addWeighted(img, 0.55, overlay, 0.45, 0)

            # ── Bounding box e labels ─────────────────────────────────────────
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if contours:
                largest = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest)

                # Retângulo amarelo
                cv2.rectangle(img_viz, (x, y), (x + w, y + h), (0, 220, 255), 2)

                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = max(0.4, min(0.7, w_img / 1500))
                thickness = 1

                # Label largura (topo)
                lbl_w = f"W: {w}px"
                cv2.putText(
                    img_viz, lbl_w,
                    (x, max(y - 6, 14)),
                    font, font_scale, (0, 220, 255), thickness, cv2.LINE_AA,
                )
                # Label altura (lado direito)
                lbl_h = f"H: {h}px"
                cv2.putText(
                    img_viz, lbl_h,
                    (min(x + w + 4, w_img - 60), y + h // 2),
                    font, font_scale, (0, 220, 255), thickness, cv2.LINE_AA,
                )

            # ── Encode JPEG → base64 ──────────────────────────────────────────
            _, buffer = cv2.imencode(
                '.jpg', img_viz, [cv2.IMWRITE_JPEG_QUALITY, 85]
            )
            return base64.b64encode(buffer).decode('utf-8')

        except Exception as exc:
            logger.warning("[img_proc] generate_visualization falhou: %s", exc)
            return ""

    # ── Bounding box e área da máscara ────────────────────────────────────────

    def compute_metrics(
        self,
        mask: np.ndarray,
        scale_px_per_cm: float,
    ) -> Dict[str, Any]:
        """
        Calcula bounding box e área da máscara a partir da máscara binária.

        Args:
            mask           : máscara binária (0/255), shape H×W, dtype uint8
            scale_px_per_cm: fator de conversão pixels por centímetro

        Returns:
            dict com bbox_width_px, bbox_height_px, bbox_width_cm,
                      bbox_height_cm, mask_area_px, mask_area_cm2
        """
        if not CV2_AVAILABLE:
            raise RuntimeError("OpenCV não está instalado. Execute: pip install opencv-contrib-python")

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            raise ValueError("Nenhum contorno encontrado na máscara — verifique a qualidade da imagem")

        # Usa o maior contorno (corpo do peixe)
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)

        mask_area_px = float(cv2.countNonZero(mask))
        scale2 = scale_px_per_cm ** 2

        return {
            "bbox_width_px": float(w),
            "bbox_height_px": float(h),
            "bbox_width_cm": round(w / scale_px_per_cm, 4),
            "bbox_height_cm": round(h / scale_px_per_cm, 4),
            "mask_area_px": mask_area_px,
            "mask_area_cm2": round(mask_area_px / scale2, 4),
        }

    # ── Pipeline completo para uma imagem ─────────────────────────────────────

    def process_image(
        self,
        image_bytes: bytes,
        fator_manual: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executa o pipeline completo em uma imagem.

        Args:
            image_bytes  : bytes da imagem original
            fator_manual : px/cm informado pelo usuário (se None, usa ArUco)

        Returns:
            dict com todas as métricas + fator_conversao + warnings
        """
        warnings: list[str] = []

        # 1. Determinar fator de escala
        scale: Optional[float] = None

        if fator_manual and fator_manual > 0:
            scale = fator_manual
            logger.info("[img_proc] usando fator manual: %.4f px/cm", scale)
        else:
            scale = self.detect_aruco_scale(image_bytes)
            if scale is None:
                warnings.append(
                    "Marcador ArUco não detectado e fator manual não informado. "
                    "Métricas em cm não calculadas — apenas valores em pixels disponíveis."
                )
                logger.warning("[img_proc] sem escala disponível — métricas cm serão None")

        # 2. Remover fundo
        _, mask = self.remove_background(image_bytes)

        # 3. Calcular métricas
        if scale is not None:
            metrics = self.compute_metrics(mask, scale)
        else:
            # Sem escala: calcula apenas em pixels
            if CV2_AVAILABLE:
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    largest = max(contours, key=cv2.contourArea)
                    x, y, w, h = cv2.boundingRect(largest)
                    metrics = {
                        "bbox_width_px": float(w),
                        "bbox_height_px": float(h),
                        "bbox_width_cm": None,
                        "bbox_height_cm": None,
                        "mask_area_px": float(cv2.countNonZero(mask)),
                        "mask_area_cm2": None,
                    }
                else:
                    metrics = {}
            else:
                metrics = {}

        metrics["fator_conversao"] = scale
        metrics["warnings"] = warnings

        # Gera visualização com máscara + bounding box sobrepostos
        metrics["viz_b64"] = self.generate_visualization(image_bytes, mask)

        return metrics


# ── Singleton ──────────────────────────────────────────────────────────────────
image_processing_service = ImageProcessingService()
