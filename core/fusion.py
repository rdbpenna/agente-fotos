from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def load_image_bgr(path: str | Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"Não foi possível abrir a imagem: {path}")
    return img


def brightness_score(img_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))


def sort_by_exposure(image_paths: list[str | Path]) -> list[Path]:
    scored = []
    for p in image_paths:
        img = load_image_bgr(p)
        scored.append((brightness_score(img), Path(p)))
    scored.sort(key=lambda x: x[0])
    return [p for _, p in scored]


def resize_to_match(images: list[np.ndarray]) -> list[np.ndarray]:
    if not images:
        return images

    h, w = images[0].shape[:2]
    resized = []

    for img in images:
        if img.shape[:2] != (h, w):
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        resized.append(img)

    return resized


def align_images(images: list[np.ndarray]) -> list[np.ndarray]:
    """
    Alinha exposições do mesmo ângulo.
    Usa AlignMTB, que é comum em HDR/exposure fusion.
    """
    if len(images) < 2:
        return images

    images = resize_to_match(images)

    try:
        align_mtb = cv2.createAlignMTB()
        aligned = images.copy()
        align_mtb.process(images, aligned)
        return aligned
    except Exception:
        # Se falhar, continua sem alinhamento.
        return images


def exposure_fusion(image_paths: list[str | Path]) -> np.ndarray:
    """
    Faz exposure fusion natural usando MergeMertens.
    Retorna imagem BGR uint8.
    """
    if len(image_paths) < 2:
        raise ValueError("Exposure fusion precisa de pelo menos 2 imagens.")

    ordered_paths = sort_by_exposure(image_paths)
    images = [load_image_bgr(p) for p in ordered_paths]
    images = resize_to_match(images)
    images = align_images(images)

    merge = cv2.createMergeMertens(
        contrast_weight=1.0,
        saturation_weight=0.65,
        exposure_weight=1.0,
    )

    fusion = merge.process(images)

    # MergeMertens retorna float 0-1.
    fusion = np.clip(fusion * 255.0, 0, 255).astype(np.uint8)

    return fusion
