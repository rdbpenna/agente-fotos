"""
Upscale com Real-ESRGAN via ONNX Runtime.

Pipeline: tile-based inference → stitch → resize ao fator solicitado.
Modelo: RealESRGAN_x4plus (nativo 4x, ~66MB ONNX).
Fallback: Lanczos se o modelo não estiver disponível.
"""

import os
import cv2
import numpy as np
import logging

logger = logging.getLogger("agente.upscaler")

# Caminho do modelo ONNX relativo à raiz do projeto
_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
_MODEL_PATH = os.path.join(_MODEL_DIR, "realesrgan-x4plus.onnx")

# Sessão ONNX carregada uma vez (lazy)
_ort_session = None


def _get_session():
    """Carrega o modelo ONNX uma única vez (singleton)."""
    global _ort_session
    if _ort_session is not None:
        return _ort_session

    if not os.path.isfile(_MODEL_PATH):
        logger.warning(f"Modelo ONNX não encontrado em {_MODEL_PATH} — usando fallback Lanczos")
        return None

    try:
        import onnxruntime as ort
        providers = ["CPUExecutionProvider"]
        # Usa GPU se disponível
        if "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")
        _ort_session = ort.InferenceSession(_MODEL_PATH, providers=providers)
        logger.info(f"Real-ESRGAN carregado ({os.path.getsize(_MODEL_PATH) / 1024 / 1024:.0f}MB)")
        return _ort_session
    except ImportError:
        logger.warning("onnxruntime não instalado — usando fallback Lanczos")
        return None
    except Exception as e:
        logger.error(f"Erro ao carregar modelo ONNX: {e}")
        return None


def _esrgan_tile(session, tile_bgr: np.ndarray) -> np.ndarray:
    """Processa um tile pelo modelo Real-ESRGAN. Input/output BGR uint8."""
    # BGR → RGB, uint8 → float32 [0,1], HWC → NCHW
    rgb = cv2.cvtColor(tile_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    tensor = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]  # [1, 3, H, W]

    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: tensor})[0]  # [1, 3, H*4, W*4]

    # NCHW → HWC, float32 [0,1] → uint8, RGB → BGR
    result = np.clip(output[0], 0, 1)
    result = np.transpose(result, (1, 2, 0))  # HWC
    result = (result * 255.0).round().astype(np.uint8)
    return cv2.cvtColor(result, cv2.COLOR_RGB2BGR)


def _esrgan_upscale(img_bgr: np.ndarray, tile_size: int = 256, tile_pad: int = 16) -> np.ndarray:
    """
    Upscale 4x com Real-ESRGAN usando processamento por tiles.
    Tiles evitam OOM em imagens grandes. Overlap (tile_pad) evita artefatos nas bordas.
    """
    session = _get_session()
    if session is None:
        return None

    h, w = img_bgr.shape[:2]
    scale = 4
    out_h, out_w = h * scale, w * scale
    output = np.zeros((out_h, out_w, 3), dtype=np.uint8)

    # Calcula grid de tiles
    tiles_y = max(1, (h + tile_size - 1) // tile_size)
    tiles_x = max(1, (w + tile_size - 1) // tile_size)

    for ty in range(tiles_y):
        for tx in range(tiles_x):
            # Coordenadas do tile no input (com padding)
            y_start = ty * tile_size
            x_start = tx * tile_size
            y_end = min(y_start + tile_size, h)
            x_end = min(x_start + tile_size, w)

            # Expande com padding para evitar artefatos de borda
            y_start_pad = max(0, y_start - tile_pad)
            x_start_pad = max(0, x_start - tile_pad)
            y_end_pad = min(h, y_end + tile_pad)
            x_end_pad = min(w, x_end + tile_pad)

            tile = img_bgr[y_start_pad:y_end_pad, x_start_pad:x_end_pad]

            # Inferência
            try:
                result_tile = _esrgan_tile(session, tile)
            except Exception as e:
                logger.error(f"Erro no tile ({tx},{ty}): {e}")
                # Fallback: Lanczos para este tile
                th, tw = tile.shape[:2]
                result_tile = cv2.resize(tile, (tw * scale, th * scale),
                                         interpolation=cv2.INTER_LANCZOS4)

            # Recorta o padding do resultado (escala 4x)
            crop_top = (y_start - y_start_pad) * scale
            crop_left = (x_start - x_start_pad) * scale
            crop_bottom = crop_top + (y_end - y_start) * scale
            crop_right = crop_left + (x_end - x_start) * scale

            cropped = result_tile[crop_top:crop_bottom, crop_left:crop_right]

            # Cola no output
            out_y = y_start * scale
            out_x = x_start * scale
            ch, cw = cropped.shape[:2]
            output[out_y:out_y + ch, out_x:out_x + cw] = cropped

    return output


class ImageUpscaler:
    """Upscale com Real-ESRGAN (IA) + fallback Lanczos."""

    def __init__(self, factor: float = 2.0, preset: str = "natural_pro"):
        try:
            factor = float(factor)
        except Exception:
            factor = 2.0
        self.factor = max(1.0, min(4.0, factor))
        self.preset_name = preset

    def upscale_file(self, image_path: str) -> str:
        """Upscale a imagem, sobrescreve o arquivo. Retorna log string."""
        img = cv2.imread(image_path)
        if img is None:
            return "Upscale: imagem não pôde ser lida"

        h, w = img.shape[:2]
        if self.factor <= 1.01:
            return "Upscale: fator 1x — ignorado"

        # Tenta Real-ESRGAN (sempre 4x nativo)
        esrgan_result = _esrgan_upscale(img)

        if esrgan_result is not None:
            # O modelo gera 4x. Se o fator solicitado é diferente, redimensiona.
            if abs(self.factor - 4.0) > 0.1:
                target_w = int(round(w * self.factor))
                target_h = int(round(h * self.factor))
                target_w, target_h = self._clamp_size(target_w, target_h)
                esrgan_result = cv2.resize(esrgan_result, (target_w, target_h),
                                           interpolation=cv2.INTER_LANCZOS4)
            else:
                target_w, target_h = esrgan_result.shape[1], esrgan_result.shape[0]
                target_w, target_h = self._clamp_size(target_w, target_h)
                if (target_w, target_h) != (esrgan_result.shape[1], esrgan_result.shape[0]):
                    esrgan_result = cv2.resize(esrgan_result, (target_w, target_h),
                                               interpolation=cv2.INTER_LANCZOS4)

            method = "Real-ESRGAN"
            final = esrgan_result
        else:
            # Fallback: Lanczos + unsharp mask leve
            target_w = int(round(w * self.factor))
            target_h = int(round(h * self.factor))
            target_w, target_h = self._clamp_size(target_w, target_h)
            final = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
            # Unsharp mask leve para compensar suavização do Lanczos
            blur = cv2.GaussianBlur(final, (0, 0), 1.2)
            final = cv2.addWeighted(final, 1.06, blur, -0.06, 0)
            method = "Lanczos (fallback)"

        # Salvar
        ext = os.path.splitext(image_path)[1].lower()
        params = [cv2.IMWRITE_JPEG_QUALITY, 98] if ext in {".jpg", ".jpeg"} else []
        cv2.imwrite(image_path, final, params)

        final_h, final_w = final.shape[:2]
        return f"Upscale [{method}]: {w}x{h} → {final_w}x{final_h} ({self.factor:g}x)"

    @staticmethod
    def _clamp_size(w: int, h: int, max_side: int = 9000) -> tuple[int, int]:
        """Limita tamanho máximo para segurança."""
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            w = int(round(w * scale))
            h = int(round(h * scale))
        return w, h
