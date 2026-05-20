"""
Upscale profissional para fotos imobiliárias.

Pipeline: pré-denoise → upscale Lanczos → enhance por preset → unsharp mask controlada.
3 presets: natural_pro, strong_pro, luxury.
Mesma interface pública: upscale_file(image_path) → str.
"""

import os
import cv2
import numpy as np


UPSCALE_PRESETS = {
    "natural_pro": {
        "denoise_h": 3,           # leve — preserva textura
        "clahe_clip": 1.4,
        "clahe_blend": 0.18,
        "shadow_lift": 4.0,
        "highlight_protect": 3.0,
        "white_neutralize_b": -0.6,
        "sharpen_amount": 1.08,
        "sharpen_sigma": 1.4,
        "saturation": 1.01,
    },
    "strong_pro": {
        "denoise_h": 4,
        "clahe_clip": 1.8,
        "clahe_blend": 0.25,
        "shadow_lift": 6.0,
        "highlight_protect": 4.0,
        "white_neutralize_b": -0.8,
        "sharpen_amount": 1.12,
        "sharpen_sigma": 1.2,
        "saturation": 1.03,
    },
    "luxury": {
        "denoise_h": 5,           # mais limpo
        "clahe_clip": 1.5,
        "clahe_blend": 0.20,
        "shadow_lift": 5.0,
        "highlight_protect": 5.0,
        "white_neutralize_b": -1.0,
        "sharpen_amount": 1.06,   # suave — look premium
        "sharpen_sigma": 1.6,
        "saturation": 1.00,
    },
}


class ImageUpscaler:
    """Amplia e melhora fotos com pipeline profissional."""

    def __init__(self, factor: float = 2.0, preset: str = "natural_pro"):
        try:
            factor = float(factor)
        except Exception:
            factor = 2.0
        self.factor = max(1.0, min(4.0, factor))
        self.preset_name = preset if preset in UPSCALE_PRESETS else "natural_pro"
        self.cfg = UPSCALE_PRESETS[self.preset_name]

    def upscale_file(self, image_path: str) -> str:
        """Amplia e melhora a imagem, sobrescreve o arquivo."""
        img = cv2.imread(image_path)
        if img is None:
            return "Upscale: imagem não pôde ser lida"

        h, w = img.shape[:2]
        if self.factor <= 1.01:
            return "Upscale: fator 1x — ignorado"

        # ── 1. Pré-denoise (antes do upscale para não ampliar ruído) ──
        img = self._pre_denoise(img)

        # ── 2. Upscale Lanczos ──
        new_w, new_h = self._calc_size(w, h)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

        # ── 3. Enhance pós-upscale ──
        img = self._enhance_luminance(img)
        img = self._neutralize_whites(img)
        img = self._adjust_saturation(img)
        img = self._sharpen(img)

        # ── 4. Salvar ──
        ext = os.path.splitext(image_path)[1].lower()
        params = [cv2.IMWRITE_JPEG_QUALITY, 98] if ext in {".jpg", ".jpeg"} else []
        cv2.imwrite(image_path, img, params)

        return (f"Upscale [{self.preset_name}]: {w}x{h} → {new_w}x{new_h} "
                f"({self.factor:g}x)")

    # ── Etapas ────────────────────────────────────────────────────

    def _pre_denoise(self, img: np.ndarray) -> np.ndarray:
        """Non-local means leve — limpa ruído antes de ampliar."""
        h_val = self.cfg["denoise_h"]
        if h_val <= 0:
            return img
        return cv2.fastNlMeansDenoisingColored(img, None, h_val, h_val, 7, 21)

    def _enhance_luminance(self, img: np.ndarray) -> np.ndarray:
        """CLAHE suave + lift de sombras + proteção de altas-luzes."""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l, a, b = cv2.split(lab)

        # CLAHE no canal L
        clip = self.cfg["clahe_clip"]
        blend = self.cfg["clahe_blend"]
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l.astype(np.uint8)).astype(np.float32)
        l = l * (1.0 - blend) + l_clahe * blend

        # Lift sombras (só pixels escuros)
        shadow_mask = np.clip((100.0 - l) / 100.0, 0.0, 1.0)
        l += self.cfg["shadow_lift"] * shadow_mask

        # Protege altas-luzes (puxa brancos estourados)
        highlight_mask = np.clip((l - 220.0) / 35.0, 0.0, 1.0)
        l -= self.cfg["highlight_protect"] * highlight_mask

        l = np.clip(l, 0, 255)
        result = cv2.merge([l, a, b]).astype(np.uint8)
        return cv2.cvtColor(result, cv2.COLOR_LAB2BGR)

    def _neutralize_whites(self, img: np.ndarray) -> np.ndarray:
        """Corrige cast amarelo/azul em brancos — seletivo por luminosidade."""
        b_shift = self.cfg["white_neutralize_b"]
        if abs(b_shift) < 0.1:
            return img

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l, a, b = cv2.split(lab)

        # Só aplica em pixels claros (paredes, teto)
        light_mask = np.clip((l - 140.0) / 80.0, 0.0, 1.0)
        b += b_shift * light_mask
        a += (b_shift * 0.3) * light_mask  # compensação leve no canal a

        lab = cv2.merge([l, np.clip(a, 0, 255), np.clip(b, 0, 255)]).astype(np.uint8)
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _adjust_saturation(self, img: np.ndarray) -> np.ndarray:
        """Saturação leve e seletiva — protege pixels já saturados."""
        factor = self.cfg["saturation"]
        if abs(factor - 1.0) < 0.005:
            return img

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        s = hsv[:, :, 1]

        # Vibrance: satura mais os dessaturados
        low_mask = np.clip((90.0 - s) / 70.0, 0.0, 1.0)
        effective = 1.0 + (factor - 1.0) * (0.5 + 0.5 * low_mask)
        hsv[:, :, 1] = np.clip(s * effective, 0, 240)

        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    def _sharpen(self, img: np.ndarray) -> np.ndarray:
        """Unsharp mask controlada — preserva superfícies lisas."""
        amount = self.cfg["sharpen_amount"]
        sigma = self.cfg["sharpen_sigma"]

        blurred = cv2.GaussianBlur(img, (0, 0), sigma)
        sharpened = cv2.addWeighted(img, amount, blurred, 1.0 - amount, 0)

        # Blend adaptativo: aplica menos onde a imagem é lisa (paredes, céu)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        local_var = cv2.GaussianBlur(gray ** 2, (15, 15), 0) - cv2.GaussianBlur(gray, (15, 15), 0) ** 2
        detail_mask = np.clip(local_var / 600.0, 0.15, 1.0)  # mínimo 15% em áreas lisas
        detail_mask_3ch = np.stack([detail_mask] * 3, axis=-1)

        result = (sharpened.astype(np.float32) * detail_mask_3ch +
                  img.astype(np.float32) * (1.0 - detail_mask_3ch))
        return np.clip(result, 0, 255).astype(np.uint8)

    def _calc_size(self, w: int, h: int) -> tuple[int, int]:
        """Calcula tamanho final com limite de segurança."""
        new_w = int(round(w * self.factor))
        new_h = int(round(h * self.factor))
        max_side = 9000
        if max(new_w, new_h) > max_side:
            scale = max_side / max(new_w, new_h)
            new_w = int(round(new_w * scale))
            new_h = int(round(new_h * scale))
        return new_w, new_h
