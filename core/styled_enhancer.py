"""
Módulo de melhoria baseado em perfil de estilo aprendido.

Versão v16:
- modos de cor: natural, vibrant, luxury
- saturação por canal de matiz (hue-selective)
- vibrance: satura dessaturados sem explodir saturados
- neutralização de amarelo em paredes reforçada
- proteção de tons de madeira (laranja) e céu (azul)
"""

import cv2
import numpy as np
import math
import json

from utils.config import PERSPECTIVE_HOUGH_THRESHOLD, PERSPECTIVE_MAX_ANGLE_DEG


# ── Modos de cor ─────────────────────────────────────────────────
# Cada modo define multiplicadores que se aplicam POR CIMA dos
# presets de categoria e intensidade. Não substituem — modulam.
COLOR_MODE_PRESETS = {
    "natural": {
        "vibrance": 0.08,           # boost leve em dessaturados
        "saturation_mult": 1.00,    # sem mudança na saturação base
        "warmth": 0.0,              # sem shift de temperatura
        "neutralize_mult": 1.0,     # neutralização de amarelo normal
        "contrast_mult": 1.00,
        # limites por matiz (H em graus OpenCV 0-180):
        # orange/wood(8-22), yellow(22-35), green(35-85), cyan(85-100), blue(100-130)
        "hue_sat_limits": {
            "orange": 0.92,   # segura madeira
            "yellow": 0.85,   # segura paredes amarelas
            "green":  0.95,   # segura vegetação
            "blue":   1.00,   # céu normal
        },
    },
    "vibrant": {
        "vibrance": 0.18,
        "saturation_mult": 1.06,
        "warmth": 0.3,
        "neutralize_mult": 1.0,
        "contrast_mult": 1.04,
        "hue_sat_limits": {
            "orange": 0.95,
            "yellow": 0.88,
            "green":  1.05,   # verde mais rico
            "blue":   1.08,   # céu mais azul
        },
    },
    "luxury": {
        "vibrance": 0.12,
        "saturation_mult": 1.02,
        "warmth": -0.15,             # v17: era -0.4 — azulava demais
        "neutralize_mult": 1.3,     # paredes mais brancas
        "contrast_mult": 1.06,
        "hue_sat_limits": {
            "orange": 0.88,   # madeira discreta
            "yellow": 0.80,   # mínimo amarelo
            "green":  0.92,   # verde sóbrio
            "blue":   1.04,   # céu elegante
        },
    },
}


INTENSITY_PRESETS = {
    # Diferenças propositalmente mais fortes na v8.
    # Na v7 o seletor mudava pouco, principalmente sem perfil treinado.
    "suave": {
        "shadow": 0.45,
        "mid": 0.40,
        "contrast": 0.60,
        "saturation": 0.50,
        "sharpness": 0.70,
        "highlight_protection": 1.35,
        "style_weight": 0.35,
    },
    "normal": {
        "shadow": 1.15,
        "mid": 1.10,
        "contrast": 1.10,
        "saturation": 1.05,
        "sharpness": 1.00,
        "highlight_protection": 1.00,
        "style_weight": 0.65,
    },
    "forte": {
        "shadow": 1.90,
        "mid": 1.70,
        "contrast": 1.55,
        "saturation": 1.35,
        "sharpness": 1.35,
        "highlight_protection": 0.82,
        "style_weight": 0.90,
    },
}

CATEGORY_PRESETS = {
    "interior": {
        "shadow_boost": 8.0,
        "mid_boost": 4.0,
        "highlight_pull": 9.0,          # era 7.0 — protege mais os brancos
        "contrast": 1.10,
        "saturation": 1.02,             # era 1.04 — interior precisa ser neutro
        "max_saturation": 1.08,         # teto por categoria (novo)
        "neutralize_ab": (-0.8, -1.6),  # v17: era (-1.2, -2.5) — azulava brancos
    },
    "exterior": {
        "shadow_boost": 4.0,
        "mid_boost": 3.0,
        "highlight_pull": 5.5,          # era 4.5 — protege céu estourado
        "contrast": 1.14,               # era 1.16 — menos HDR
        "saturation": 1.04,             # era 1.08 — verde/céu fica artificial com mais
        "max_saturation": 1.12,         # teto por categoria (novo)
        "neutralize_ab": (0.0, -0.3),   # v17: era (0, -0.5)
    },
    "detalhes": {
        "shadow_boost": 5.0,
        "mid_boost": 3.0,
        "highlight_pull": 6.0,          # era 5.0
        "contrast": 1.12,               # era 1.14
        "saturation": 1.02,             # era 1.05 — cor fiel sem exagero
        "max_saturation": 1.08,         # teto por categoria (novo)
        "neutralize_ab": (-0.3, -0.5),  # v17: era (-0.5, -0.8)
    },
    "revisar": {
        "shadow_boost": 3.0,
        "mid_boost": 2.0,
        "highlight_pull": 8.0,
        "contrast": 1.06,
        "saturation": 1.01,             # era 1.02 — mínimo possível
        "max_saturation": 1.06,         # teto por categoria (novo)
        "neutralize_ab": (-0.5, -0.8),  # v17: era (-0.8, -1.2)
    },
}


class StyledEnhancer:
    """Aplica melhorias baseadas em perfil de estilo aprendido, com travas."""

    def __init__(self, profile: dict, intensity: str = "normal", color_mode: str = "natural"):
        self.p = profile or {}
        self.intensity = self._normalize_intensity(intensity)
        self.intensity_cfg = INTENSITY_PRESETS[self.intensity]
        self.color_mode = self._normalize_color_mode(color_mode)
        self.color_cfg = COLOR_MODE_PRESETS[self.color_mode]
        self.log: list[str] = []

    @classmethod
    def from_file(cls, profile_path: str, intensity: str = "normal",
                  color_mode: str = "natural") -> "StyledEnhancer":
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data.get("parametros", {}), intensity=intensity, color_mode=color_mode)

    @staticmethod
    def _normalize_intensity(value: str | None) -> str:
        if not value:
            return "normal"
        v = str(value).lower().strip()
        mapping = {
            "leve": "suave", "suave": "suave", "soft": "suave",
            "normal": "normal", "medio": "normal", "médio": "normal",
            "forte": "forte", "strong": "forte",
        }
        return mapping.get(v, "normal")

    @staticmethod
    def _normalize_color_mode(value: str | None) -> str:
        if not value:
            return "natural"
        v = str(value).lower().strip()
        if v in COLOR_MODE_PRESETS:
            return v
        mapping = {
            "vibrante": "vibrant", "vibrant": "vibrant", "vivo": "vibrant",
            "luxo": "luxury", "luxury": "luxury", "luxuoso": "luxury",
            "natural": "natural", "neutro": "natural",
        }
        return mapping.get(v, "natural")

    def enhance(self, image_path: str, output_path: str, category: str = "interior") -> list[str]:
        self.log = []
        img = cv2.imread(image_path)
        if img is None:
            self.log.append("ERRO: não foi possível ler a imagem")
            return self.log

        category = self._normalize_category(category)
        h, w = img.shape[:2]
        self.log.append(
            f"Imagem carregada: {w}x{h} px | preset={category} | intensidade={self.intensity} | cor={self.color_mode}"
        )

        before_mean, before_clip = self._luminance_stats(img)
        if before_clip > 6.0:
            self.log.append(
                f"REVISAR: imagem original já tem clipping alto ({before_clip:.1f}%)"
            )

        img = self._apply_color_correction(img, category)
        img = self._apply_natural_real_estate_preset(img, category)
        img = self._apply_controlled_learned_style(img, category)
        img = self._apply_safety_pass(img, before_clip)
        img = self._apply_real_estate_grade_blend(img)
        img = self._apply_sharpness(img)
        img = self._correct_perspective(img)
        img = self._correct_keystone(img)

        after_mean, after_clip = self._luminance_stats(img)
        if after_clip > max(4.0, before_clip + 2.0):
            self.log.append(
                f"REVISAR: clipping final alto ({after_clip:.1f}%). Resultado pode exigir ajuste manual."
            )
        if after_mean < 55 or after_mean > 220:
            self.log.append(
                f"REVISAR: brilho médio final fora do ideal ({after_mean:.0f})"
            )

        cv2.imwrite(output_path, img, [cv2.IMWRITE_JPEG_QUALITY, 98])
        self.log.append(f"Imagem salva: {output_path}")
        return self.log

    # ── Utilidades ───────────────────────────────────────────────

    def _normalize_category(self, category: str | None) -> str:
        c = (category or "interior").lower().strip()
        if c in CATEGORY_PRESETS:
            return c
        if "extern" in c or "fachada" in c or "drone" in c:
            return "exterior"
        if "detal" in c:
            return "detalhes"
        if "revis" in c:
            return "revisar"
        return "interior"

    def _category_cfg(self, category: str) -> dict:
        return CATEGORY_PRESETS.get(category, CATEGORY_PRESETS["interior"])

    def _luminance_stats(self, img: np.ndarray) -> tuple[float, float]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        return float(gray.mean()), float((gray >= 245).mean() * 100.0)

    def _lab_masks(self, l_channel: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        l = l_channel.astype(np.float32)
        shadows = np.clip((155.0 - l) / 155.0, 0.0, 1.0)
        mids = np.clip(1.0 - np.abs(l - 128.0) / 85.0, 0.0, 1.0)
        highlights = np.clip((l - 178.0) / 62.0, 0.0, 1.0)
        whites = np.clip((l - 220.0) / 35.0, 0.0, 1.0)
        return shadows, mids, highlights, whites

    # ── 1. Cor ───────────────────────────────────────────────────

    def _apply_color_correction(self, img: np.ndarray, category: str) -> np.ndarray:
        style_weight = self.intensity_cfg["style_weight"]
        r_off = float(self.p.get("canal_r_offset", 0.0)) * style_weight * 0.55
        g_off = float(self.p.get("canal_g_offset", 0.0)) * style_weight * 0.55
        b_off = float(self.p.get("canal_b_offset", 0.0)) * style_weight * 0.55

        # Limites para o perfil aprendido não dominar a imagem.
        r_off = float(np.clip(r_off, -8, 8))
        g_off = float(np.clip(g_off, -8, 8))
        b_off = float(np.clip(b_off, -8, 8))

        if abs(r_off) < 0.5 and abs(g_off) < 0.5 and abs(b_off) < 0.5:
            self.log.append("Cor: sem ajuste do estilo aprendido")
            return img

        result = img.astype(np.float32)
        result[:, :, 0] += b_off
        result[:, :, 1] += g_off
        result[:, :, 2] += r_off
        result = np.clip(result, 0, 255).astype(np.uint8)
        self.log.append(f"Cor estilo: R:{r_off:+.1f} G:{g_off:+.1f} B:{b_off:+.1f}")
        return result

    # ── 2. Preset base Natural Imobiliário ───────────────────────

    def _apply_natural_real_estate_preset(self, img: np.ndarray, category: str) -> np.ndarray:
        cfg = self._category_cfg(category)
        inten = self.intensity_cfg
        mean_l, clipped_pct = self._luminance_stats(img)

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l, a, b = cv2.split(lab)
        shadows, mids, highlights, whites = self._lab_masks(l)

        # Escala automática: quanto mais clara, menos clareia e mais protege.
        exposure_scale = 1.0
        if mean_l > 175:
            exposure_scale = 0.40
        elif mean_l > 160:
            exposure_scale = 0.62
        elif mean_l > 145:
            exposure_scale = 0.82
        if clipped_pct > 1.5:
            exposure_scale *= 0.80

        shadow_boost = cfg["shadow_boost"] * inten["shadow"] * exposure_scale
        mid_boost = cfg["mid_boost"] * inten["mid"] * exposure_scale
        highlight_pull = cfg["highlight_pull"] * inten["highlight_protection"]
        white_pull = (4.0 + clipped_pct * 0.9) * inten["highlight_protection"]

        l += shadow_boost * shadows
        l += mid_boost * mids
        l -= highlight_pull * highlights
        l -= white_pull * whites

        # Neutralização seletiva de paredes/brancos via canais LAB.
        # Aplica mais forte em pixels claros (paredes, teto) e menos em escuros
        # (móveis, chão de madeira) para não acinzentar tudo.
        # O modo de cor modula a intensidade (luxury = mais neutro, vibrant = normal).
        neutralize_mult = self.color_cfg["neutralize_mult"]
        a_shift, b_shift = cfg["neutralize_ab"]
        light_mask = np.clip((l - 120.0) / 100.0, 0.0, 1.0)
        a += a_shift * neutralize_mult * light_mask
        b += b_shift * neutralize_mult * light_mask

        # Warmth do modo de cor: shift global leve no canal b (+ = quente, - = frio)
        warmth = self.color_cfg["warmth"]
        if abs(warmth) > 0.1:
            b += warmth

        result = cv2.cvtColor(
            cv2.merge([
                np.clip(l, 0, 255),
                np.clip(a, 0, 255),
                np.clip(b, 0, 255),
            ]).astype(np.uint8),
            cv2.COLOR_LAB2BGR,
        )

        self.log.append(
            f"Natural Imobiliário: sombras=+{shadow_boost:.1f}, meios=+{mid_boost:.1f}, luzes=-{highlight_pull:.1f}"
        )

        # Contraste local com blend para não parecer HDR artificial.
        result = self._apply_local_contrast(result, category)
        result = self._apply_saturation(result, category)
        return result

    def _apply_local_contrast(self, img: np.ndarray, category: str) -> np.ndarray:
        cfg = self._category_cfg(category)
        inten = self.intensity_cfg
        mean_l, clipped_pct = self._luminance_stats(img)

        contrast_target = cfg["contrast"] * inten["contrast"] * self.color_cfg["contrast_mult"]
        if mean_l > 170 or clipped_pct > 2.0:
            contrast_target = min(contrast_target, 1.10)
        max_contrast = 1.10 if self.intensity == "suave" else (1.20 if self.intensity == "normal" else 1.30)  # v17: era 1.12/1.26/1.38
        contrast_target = float(np.clip(contrast_target, 1.02, max_contrast))

        clip_limit = 1.7 + (contrast_target - 1.0) * 3.2
        clip_limit = float(np.clip(clip_limit, 1.6, 2.8))

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        enhanced_l = clahe.apply(l)
        enhanced = cv2.cvtColor(cv2.merge([enhanced_l, a, b]), cv2.COLOR_LAB2BGR)

        blend = 0.28 + (inten["contrast"] - 0.60) * 0.22
        if self.intensity == "forte":
            blend += 0.10
        if mean_l > 170:
            blend *= 0.82
        blend = float(np.clip(blend, 0.15, 0.50))   # v17: era 0.18-0.70
        result = cv2.addWeighted(enhanced, blend, img, 1.0 - blend, 0)
        self.log.append(f"Contraste local: clip={clip_limit:.2f}, blend={blend:.2f}")
        return result

    def _apply_saturation(self, img: np.ndarray, category: str) -> np.ndarray:
        """Saturação com vibrance e limites por matiz (hue-selective)."""
        cfg = self._category_cfg(category)
        inten = self.intensity_cfg
        color = self.color_cfg
        learned = float(self.p.get("saturacao_fator", 1.0))
        style_weight = inten["style_weight"]

        # Fator base = categoria × intensidade × modo de cor
        target = cfg["saturation"] * inten["saturation"] * color["saturation_mult"]
        target += (learned - 1.0) * style_weight * 0.25

        max_sat = cfg.get("max_saturation", 1.10)
        if self.intensity == "forte":
            max_sat += 0.06
        target = float(np.clip(target, 0.98, max_sat))

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        h_chan = hsv[:, :, 0]  # 0-180 no OpenCV
        s = hsv[:, :, 1]

        # ── Vibrance: satura mais os dessaturados, segura os já saturados ──
        vibrance = color["vibrance"]
        low_sat_mask = np.clip((100.0 - s) / 80.0, 0.0, 1.0)  # 1.0 se S<20, 0 se S>100
        vibrance_boost = 1.0 + vibrance * low_sat_mask          # até +vibrance nos cinzas

        # ── Limites por matiz (protege madeira, paredes, verde, céu) ──
        hue_limits = color["hue_sat_limits"]
        hue_factor = np.ones_like(s)

        # Laranja/madeira: H 8-22
        orange_mask = np.clip(1.0 - np.abs(h_chan - 15.0) / 7.0, 0.0, 1.0)
        hue_factor *= 1.0 - orange_mask * (1.0 - hue_limits["orange"])

        # Amarelo/parede: H 22-35
        yellow_mask = np.clip(1.0 - np.abs(h_chan - 28.0) / 7.0, 0.0, 1.0)
        hue_factor *= 1.0 - yellow_mask * (1.0 - hue_limits["yellow"])

        # Verde/vegetação: H 35-85
        green_mask = np.clip(1.0 - np.abs(h_chan - 60.0) / 25.0, 0.0, 1.0)
        hue_factor *= 1.0 - green_mask * (1.0 - hue_limits["green"])

        # Azul/céu: H 100-130
        blue_mask = np.clip(1.0 - np.abs(h_chan - 115.0) / 15.0, 0.0, 1.0)
        hue_factor *= 1.0 - blue_mask * (1.0 - hue_limits["blue"])

        # ── Proteção de pixels já muito saturados ──
        already_high = np.clip((s - 120.0) / 80.0, 0.0, 1.0)
        protection = 1.0 - already_high * 0.4

        # Combina tudo
        effective = target * vibrance_boost * hue_factor * protection
        hsv[:, :, 1] = np.clip(s * effective, 0, 240)

        result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        self.log.append(f"Saturação: base={target:.3f}, vibrance={vibrance:.2f}, mode={self.color_mode}")
        return result

    # ── 3. Estilo aprendido controlado ───────────────────────────

    def _apply_controlled_learned_style(self, img: np.ndarray, category: str) -> np.ndarray:
        inten = self.intensity_cfg
        style_weight = inten["style_weight"]

        learned_shadow = float(self.p.get("sombras_offset", 0.0)) * style_weight * 0.35
        learned_mid = float(self.p.get("meios_tons_offset", 0.0)) * style_weight * 0.30
        learned_high = float(self.p.get("altas_luzes_offset", 0.0)) * style_weight * 0.25
        learned_brightness = float(self.p.get("brilho_offset", 0.0)) * style_weight * 0.16

        learned_shadow = float(np.clip(learned_shadow, -5, 8))
        learned_mid = float(np.clip(learned_mid + learned_brightness, -4, 7))
        learned_high = float(np.clip(learned_high, -8, 2))

        if abs(learned_shadow) < 0.6 and abs(learned_mid) < 0.6 and abs(learned_high) < 0.6:
            self.log.append("Estilo aprendido: influência pequena/ignorada")
            return img

        mean_l, clipped_pct = self._luminance_stats(img)
        if mean_l > 165 or clipped_pct > 1.0:
            # Evita que o estilo aprendido force luz em imagem já clara.
            learned_mid = min(learned_mid, 2.0)
            learned_high = min(learned_high, -2.0)

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l, a, b = cv2.split(lab)
        shadows, mids, highlights, whites = self._lab_masks(l)

        l += learned_shadow * shadows
        l += learned_mid * mids
        l += learned_high * highlights
        l -= max(0.0, clipped_pct - 0.5) * 1.2 * whites

        result = cv2.cvtColor(
            cv2.merge([np.clip(l, 0, 255), a, b]).astype(np.uint8),
            cv2.COLOR_LAB2BGR,
        )
        self.log.append(
            f"Estilo aprendido controlado: sombras={learned_shadow:+.1f}, meios={learned_mid:+.1f}, luzes={learned_high:+.1f}"
        )
        return result

    # ── 4. Segurança final ───────────────────────────────────────

    def _apply_safety_pass(self, img: np.ndarray, before_clip: float) -> np.ndarray:
        mean_l, clip = self._luminance_stats(img)
        if clip <= max(2.2, before_clip + 1.4) and mean_l <= 215:
            self.log.append(f"Segurança: clipping ok ({clip:.1f}%)")
            return img

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l, a, b = cv2.split(lab)
        _, _, highlights, whites = self._lab_masks(l)

        pull = min(12.0, 4.0 + clip * 0.9)
        l -= pull * highlights
        l -= (pull * 0.9) * whites
        result = cv2.cvtColor(
            cv2.merge([np.clip(l, 0, 255), a, b]).astype(np.uint8),
            cv2.COLOR_LAB2BGR,
        )
        new_mean, new_clip = self._luminance_stats(result)
        self.log.append(
            f"Segurança aplicada: clipping {clip:.1f}% → {new_clip:.1f}%"
        )
        return result

    # ── 5. Grade imobiliário final (módulo do parceiro) ──────────

    def _apply_real_estate_grade_blend(self, img: np.ndarray, blend: float = 0.28) -> np.ndarray:
        """
        Aplica o grade imobiliário especializado (real_estate_grade.py) com
        blend parcial para não duplicar os ajustes já feitos pelo pipeline.
        """
        try:
            from core.real_estate_grade import grade_real_estate
            graded = grade_real_estate(img)
            result = cv2.addWeighted(graded, blend, img, 1.0 - blend, 0)
            self.log.append(f"Grade imobiliário v2: blend={blend:.0%}")
            return result
        except Exception as exc:
            self.log.append(f"Grade imobiliário v2: ignorado ({exc})")
            return img

    # ── 6. Nitidez ───────────────────────────────────────────────

    def _apply_sharpness(self, img: np.ndarray) -> np.ndarray:
        learned = float(self.p.get("nitidez_fator", 1.0))
        amount = 1.02 + (self.intensity_cfg["sharpness"] - 0.70) * 0.12   # v17: era *0.20
        amount += max(0.0, min(0.06, (learned - 1.0) * 0.05))             # v17: era 0.12/0.08
        amount = float(np.clip(amount, 1.03, 1.12))                       # v17: era 1.05-1.20

        gaussian = cv2.GaussianBlur(img, (0, 0), 1.2)                     # v17: era 0.9 — mais suave
        result = cv2.addWeighted(img, amount, gaussian, 1.0 - amount, 0)
        self.log.append(f"Nitidez: amount={amount:.2f}")
        return result

    # ── 6. Perspectiva ───────────────────────────────────────────

    def _correct_perspective(self, img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, PERSPECTIVE_HOUGH_THRESHOLD)

        if lines is None:
            self.log.append("Perspectiva: sem linhas detectadas")
            return img

        angles = []
        for line in lines:
            rho, theta = line[0]
            angle_deg = math.degrees(theta) - 90
            if abs(angle_deg) < PERSPECTIVE_MAX_ANGLE_DEG:
                angles.append(angle_deg)

        if not angles:
            self.log.append("Perspectiva: sem inclinação relevante")
            return img

        median_angle = float(np.median(angles))
        if abs(median_angle) < 0.3:
            self.log.append(f"Perspectiva: inclinação mínima ({median_angle:.2f}°)")
            return img

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        result = cv2.warpAffine(
            img,
            M,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        self.log.append(f"Perspectiva corrigida: {median_angle:.2f}°")
        return result

    # ── 7. Keystone ──────────────────────────────────────────────

    def _correct_keystone(self, img: np.ndarray) -> np.ndarray:
        """
        Detecta e corrige convergência de verticais (efeito keystone).
        Ocorre quando a câmera é inclinada para cima/baixo, fazendo paredes
        convergirem no topo ou na base. Aplica warp de perspectiva inverso.
        """
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 40, 120, apertureSize=3)

        min_len = max(h // 6, 60)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60,
                                 minLineLength=min_len, maxLineGap=20)
        if lines is None:
            self.log.append("Keystone: sem linhas detectadas")
            return img

        cx = w / 2.0
        left_angles: list[float] = []
        right_angles: list[float] = []

        for line in lines:
            x1, y1, x2, y2 = line[0]
            dy = float(y2 - y1)
            if abs(dy) < 1:
                continue
            # ângulo em relação à vertical: 0 = perfeitamente vertical
            angle = math.degrees(math.atan2(float(x2 - x1), dy))
            if abs(angle) > 8.0:  # aceita até 8° de desvio da vertical
                continue
            x_mid = (x1 + x2) / 2.0
            if x_mid < cx:
                left_angles.append(angle)
            else:
                right_angles.append(angle)

        if len(left_angles) < 2 or len(right_angles) < 2:
            self.log.append("Keystone: linhas insuficientes")
            return img

        left_med = float(np.median(left_angles))
        right_med = float(np.median(right_angles))
        # convergência positiva = paredes fecham no topo (câmera inclinada para cima)
        convergence = left_med - right_med

        if abs(convergence) < 1.5:
            self.log.append(f"Keystone: convergência mínima ({convergence:.1f}°) — ignorada")
            return img

        convergence = max(-10.0, min(10.0, convergence))
        shift = math.tan(math.radians(abs(convergence) / 2)) * h

        src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        if convergence > 0:
            dst_pts = np.float32([[-shift, 0], [w + shift, 0], [w, h], [0, h]])
        else:
            dst_pts = np.float32([[0, 0], [w, 0], [w + shift, h], [-shift, h]])

        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        result = cv2.warpPerspective(img, M, (w, h), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REPLICATE)
        self.log.append(f"Keystone corrigido: convergência {convergence:.1f}°, shift {shift:.0f}px")
        return result
