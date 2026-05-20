from __future__ import annotations

import cv2
import numpy as np


def _clip_u8(img: np.ndarray) -> np.ndarray:
    return np.clip(img, 0, 255).astype(np.uint8)


def mild_white_balance(img_bgr: np.ndarray) -> np.ndarray:
    """
    White balance leve.
    Não força cinza total, porque isso deixa imóvel lavado.
    """
    img = img_bgr.astype(np.float32)

    avg_b = np.mean(img[:, :, 0])
    avg_g = np.mean(img[:, :, 1])
    avg_r = np.mean(img[:, :, 2])
    avg = (avg_b + avg_g + avg_r) / 3.0

    scale_b = np.clip(avg / max(avg_b, 1), 0.94, 1.06)
    scale_g = np.clip(avg / max(avg_g, 1), 0.96, 1.04)
    scale_r = np.clip(avg / max(avg_r, 1), 0.94, 1.08)

    corrected = img.copy()
    corrected[:, :, 0] *= scale_b
    corrected[:, :, 1] *= scale_g
    corrected[:, :, 2] *= scale_r

    # mistura parcial para não ficar artificial
    out = img * 0.45 + corrected * 0.55
    return _clip_u8(out)


def add_warmth(img_bgr: np.ndarray) -> np.ndarray:
    """
    Traz um pouco de calor natural, bom para banheiro/imóvel.
    """
    img = img_bgr.astype(np.float32)

    img[:, :, 0] *= 0.985  # azul um pouco menor
    img[:, :, 1] *= 1.005
    img[:, :, 2] *= 1.025  # vermelho um pouco maior

    return _clip_u8(img)


def open_shadows_clean(img_bgr: np.ndarray) -> np.ndarray:
    """
    Abre sombras de forma mais natural.
    """
    img = img_bgr.astype(np.float32) / 255.0

    gray = cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

    shadow_mask = 1.0 - np.clip((gray - 0.18) / 0.45, 0, 1)
    shadow_mask = cv2.GaussianBlur(shadow_mask, (0, 0), 7)

    lift = 0.16 * shadow_mask[..., None]
    img = img + lift * (1.0 - img)

    return _clip_u8(img * 255)


def protect_highlights(original_bgr: np.ndarray, edited_bgr: np.ndarray) -> np.ndarray:
    """
    Evita luz/janela estourada demais.
    """
    original = original_bgr.astype(np.float32)
    edited = edited_bgr.astype(np.float32)

    gray = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    mask = np.clip((gray - 0.72) / 0.25, 0, 1)
    mask = cv2.GaussianBlur(mask, (0, 0), 5)
    mask = mask[..., None]

    out = edited * (1.0 - 0.45 * mask) + original * (0.45 * mask)
    return _clip_u8(out)


def contrast_real_estate(img_bgr: np.ndarray) -> np.ndarray:
    """
    Contraste local sem pesar.
    """
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=1.35, tileGridSize=(8, 8))
    l2 = clahe.apply(l)

    # mistura para não ficar HDR artificial
    l_final = cv2.addWeighted(l, 0.45, l2, 0.55, 0)

    lab2 = cv2.merge([l_final, a, b])
    return cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)


def clean_brightness_curve(img_bgr: np.ndarray) -> np.ndarray:
    """
    Curva de brilho: mais claro, mas sem lavar.
    """
    img = img_bgr.astype(np.float32) / 255.0

    # gamma menor clareia tons médios
    img = np.power(img, 0.92)

    # micro contraste
    img = (img - 0.5) * 1.06 + 0.5

    return _clip_u8(img * 255)


def controlled_color(img_bgr: np.ndarray) -> np.ndarray:
    """
    Aumenta cor de forma controlada.
    Protege vermelho/laranja/madeira para não ficar radioativo.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    # vibrance: aumenta mais onde tem pouca saturação
    vibrance = 1.0 + 0.26 * (1.0 - s / 255.0)
    s = s * vibrance

    # controle de vermelho/laranja/madeira
    red_orange = ((h <= 18) | (h >= 170)) | ((h >= 19) & (h <= 36))
    s[red_orange] *= 0.90

    # deixa tons frios/vidro/azul levemente mais limpos
    blue_cyan = ((h >= 85) & (h <= 115))
    s[blue_cyan] *= 1.04

    s = np.clip(s, 0, 220)
    v = np.clip(v * 1.015, 0, 255)

    hsv[:, :, 1] = s
    hsv[:, :, 2] = v

    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def sharpen_natural(img_bgr: np.ndarray) -> np.ndarray:
    """
    Nitidez leve para foto imobiliária.
    """
    blur = cv2.GaussianBlur(img_bgr, (0, 0), 1.15)
    sharp = cv2.addWeighted(img_bgr, 1.28, blur, -0.28, 0)
    return _clip_u8(sharp)


def grade_real_estate(img_bgr: np.ndarray) -> np.ndarray:
    """
    Preset imobiliário v2:
    - mais claro;
    - menos cinza/lavado;
    - levemente mais quente;
    - mais contraste local;
    - cor mais viva, controlada;
    - highlights protegidos.
    """
    original = img_bgr.copy()

    img = mild_white_balance(img_bgr)
    img = add_warmth(img)
    img = open_shadows_clean(img)
    img = clean_brightness_curve(img)
    img = contrast_real_estate(img)
    img = controlled_color(img)
    img = protect_highlights(original, img)
    img = sharpen_natural(img)

    return img
