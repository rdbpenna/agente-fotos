
"""
Treinador de perfil HDR/Bracketing imobiliário.

Treina/calibra um perfil JSON a partir de:
  3/5 fotos bracketadas (-1, 0, +1 etc.) -> 1 referência final editada pelo fotógrafo

A ideia não é treinar uma rede neural pesada. É calibrar o acabamento HDR:
exposição, contraste, black point, saturação, warmth/tint e luminosidade alvo.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from core.bracketing import BracketingProcessor
from core.raw_support import is_raw_file, read_raw_rgb


SUPPORTED_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".cr3", ".cr2", ".nef", ".arw", ".dng", ".raf", ".rw2", ".orf")


@dataclass
class HdrTrainingGroup:
    bracket_paths: list[str]
    reference_path: str
    name: str = ""


class HdrBracketTrainer:
    def __init__(self):
        self.groups: list[HdrTrainingGroup] = []
        self.profile: dict | None = None

    def add_group(self, bracket_paths: list[str], reference_path: str, name: str | None = None):
        bracket_paths = [str(p) for p in bracket_paths if p and os.path.exists(p)]
        if len(bracket_paths) < 3:
            raise ValueError("Um grupo HDR precisa ter pelo menos 3 imagens bracketadas.")
        if not os.path.exists(reference_path):
            raise ValueError("A imagem de referência final não existe.")
        self.groups.append(HdrTrainingGroup(
            bracket_paths=bracket_paths,
            reference_path=str(reference_path),
            name=name or Path(reference_path).stem,
        ))

    def train(self, progress_callback=None) -> dict:
        if not self.groups:
            raise ValueError("Nenhum grupo HDR adicionado ao treinamento.")

        corrections = []
        reference_targets = []
        processor = BracketingProcessor(group_size=3, fusion_preset="imobiliario_claro")

        with tempfile.TemporaryDirectory(prefix="hdr_train_") as tmp:
            for idx, group in enumerate(self.groups, 1):
                if progress_callback:
                    progress_callback(f"Treinando HDR: fusionando grupo {idx}/{len(self.groups)}...")

                fused_path = os.path.join(tmp, f"group_{idx:03d}_fused.jpg")
                processor.fuse_group(group.bracket_paths, fused_path)

                fused = self._read_bgr(fused_path)
                ref = self._read_bgr(group.reference_path)
                if fused is None or ref is None:
                    continue

                fused, ref = self._resize_pair(fused, ref, max_side=1200)

                fused_stats = self._stats(fused)
                ref_stats = self._stats(ref)

                reference_targets.append(ref_stats)
                corrections.append({
                    "l_mean_delta": ref_stats["l_mean"] - fused_stats["l_mean"],
                    "l_std_ratio": _safe_ratio(ref_stats["l_std"], fused_stats["l_std"], 0.65, 1.55),
                    "sat_ratio": _safe_ratio(ref_stats["sat_mean"], fused_stats["sat_mean"], 0.70, 1.60),
                    "a_delta": ref_stats["a_mean"] - fused_stats["a_mean"],
                    "b_delta": ref_stats["b_mean"] - fused_stats["b_mean"],
                    "black_delta": ref_stats["black_p"] - fused_stats["black_p"],
                    "white_delta": ref_stats["white_p"] - fused_stats["white_p"],
                })

        if not corrections:
            raise ValueError("Não foi possível gerar estatísticas de treino HDR.")

        avg_correction = _avg_dicts(corrections)
        avg_target = _avg_dicts(reference_targets)

        # Limites conservadores para não criar perfil destrutivo.
        avg_correction["l_mean_delta"] = float(np.clip(avg_correction["l_mean_delta"], -0.18, 0.24))
        avg_correction["l_std_ratio"] = float(np.clip(avg_correction["l_std_ratio"], 0.78, 1.35))
        avg_correction["sat_ratio"] = float(np.clip(avg_correction["sat_ratio"], 0.80, 1.35))
        avg_correction["a_delta"] = float(np.clip(avg_correction["a_delta"], -0.08, 0.08))
        avg_correction["b_delta"] = float(np.clip(avg_correction["b_delta"], -0.08, 0.10))

        self.profile = {
            "type": "hdr_bracketing_profile",
            "version": 1,
            "name": "Perfil HDR Imobiliário Treinado",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "groups": len(self.groups),
            "base_preset": "imobiliario_claro",
            "targets": avg_target,
            "corrections": avg_correction,
            "notes": [
                "Perfil treinado por calibração de estatísticas visuais.",
                "Entrada: grupo de 3/5 bracketadas; saída: referência final editada.",
                "Use este JSON em Estilo (opcional) junto com Bracketing/HDR ativo.",
            ],
        }
        return self.profile

    def save_profile(self, path: str):
        if not self.profile:
            raise ValueError("Nenhum perfil HDR treinado para salvar.")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.profile, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _read_bgr(path: str):
        try:
            if is_raw_file(path):
                rgb = read_raw_rgb(path, half_size=False)
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            return cv2.imread(path, cv2.IMREAD_COLOR)
        except Exception:
            return None

    @staticmethod
    def _resize_pair(a, b, max_side=1200):
        def resize(img):
            h, w = img.shape[:2]
            scale = min(1.0, max_side / max(h, w))
            if scale < 1.0:
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            return img
        a = resize(a)
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
        return a, b

    @staticmethod
    def _stats(img) -> dict:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l = lab[:, :, 0] / 255.0
        a = (lab[:, :, 1] - 128.0) / 128.0
        b = (lab[:, :, 2] - 128.0) / 128.0
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        sat = hsv[:, :, 1] / 255.0
        return {
            "l_mean": float(np.mean(l)),
            "l_std": float(np.std(l)),
            "sat_mean": float(np.mean(sat)),
            "a_mean": float(np.mean(a)),
            "b_mean": float(np.mean(b)),
            "black_p": float(np.percentile(l, 2.0)),
            "white_p": float(np.percentile(l, 98.0)),
        }


def _safe_ratio(num, den, lo, hi):
    if abs(den) < 1e-6:
        return 1.0
    return float(np.clip(num / den, lo, hi))


def _avg_dicts(items: list[dict]) -> dict:
    keys = items[0].keys()
    return {k: float(np.mean([x[k] for x in items])) for k in keys}


def find_bracket_images(folder: str, max_count: int = 5) -> list[str]:
    if not folder or not os.path.isdir(folder):
        return []
    files = []
    for name in sorted(os.listdir(folder), key=_natural_sort_key):
        path = os.path.join(folder, name)
        if os.path.isfile(path) and Path(path).suffix.lower() in SUPPORTED_IMAGE_EXTS:
            files.append(path)
    return files[:max_count]


def _natural_sort_key(text: str):
    import re
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", str(text))]
