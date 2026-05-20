"""
Treinamento de classificador por exemplos rotulados.

Aprende limiares personalizados a partir de imagens manualmente rotuladas.
Não requer nenhuma dependência de ML — usa apenas estatísticas descritivas.

Fluxo:
    trainer = ClassifierTrainer()
    trainer.add_example("sala.jpg", "interior")
    trainer.add_example("fachada.jpg", "exterior")
    profile = trainer.train()
    trainer.save(profile, "classifier_profile.json")

O JSON resultante pode ser carregado pelo ImageClassifier para substituir
os limiares padrão de config.py pelos valores aprendidos nos exemplos.
"""

import json
import cv2
import numpy as np
from pathlib import Path

from utils.config import (
    CLASS_INTERIOR, CLASS_EXTERIOR, CLASS_DETAILS, CLASS_REVIEW,
)

_VALID_CLASSES = {CLASS_INTERIOR, CLASS_EXTERIOR, CLASS_DETAILS, CLASS_REVIEW}
_FEATURE_NAMES = [
    "sky_pct", "sky_upper_pct",
    "green_pct", "largest_green_pct",
    "edge_density", "brightness",
]


def _extract_features(img_path: str) -> dict | None:
    """Extrai as features usadas pelo classificador heurístico."""
    img = cv2.imread(img_path)
    if img is None:
        return None

    h, w = img.shape[:2]
    total = h * w

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    sky_mask = cv2.inRange(hsv, (95, 40, 150), (130, 255, 255))
    sky_pct = np.count_nonzero(sky_mask) / total * 100
    sky_upper_pct = np.count_nonzero(sky_mask[: h // 3, :]) / max((h // 3) * w, 1) * 100

    green_mask = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
    green_pct = np.count_nonzero(green_mask) / total * 100

    largest_green_pct = 0.0
    if green_pct > 0.5:
        kernel = np.ones((9, 9), np.uint8)
        closed = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
        n, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
        if n > 1:
            largest_area = int(stats[1:, cv2.CC_STAT_AREA].max())
            largest_green_pct = largest_area / total * 100

    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.count_nonzero(edges) / total)
    brightness = float(gray.mean())

    return {
        "sky_pct":            sky_pct,
        "sky_upper_pct":      sky_upper_pct,
        "green_pct":          green_pct,
        "largest_green_pct":  largest_green_pct,
        "edge_density":       edge_density,
        "brightness":         brightness,
    }


class ClassifierTrainer:
    """Aprende limiares de classificação a partir de exemplos rotulados."""

    def __init__(self):
        self._examples: list[dict] = []

    def add_example(self, image_path: str, label: str) -> bool:
        """
        Adiciona um exemplo rotulado.

        Args:
            image_path: caminho para a imagem.
            label:      "interior" | "exterior" | "detalhes" | "revisar"

        Returns:
            True se a imagem foi lida com sucesso.
        """
        if label not in _VALID_CLASSES:
            raise ValueError(f"Classe inválida '{label}'. Opções: {sorted(_VALID_CLASSES)}")
        features = _extract_features(image_path)
        if features is None:
            return False
        self._examples.append({"path": image_path, "label": label, "features": features})
        return True

    def count(self) -> dict[str, int]:
        """Contagem de exemplos por classe."""
        counts: dict[str, int] = {}
        for ex in self._examples:
            counts[ex["label"]] = counts.get(ex["label"], 0) + 1
        return counts

    def train(self) -> dict:
        """
        Deriva limiares adaptativos a partir dos exemplos.

        Returns:
            Dicionário de perfil serializável em JSON.

        Raises:
            RuntimeError: se houver menos de 2 exemplos.
        """
        if len(self._examples) < 2:
            raise RuntimeError("São necessários pelo menos 2 exemplos rotulados para treinar.")

        by_class: dict[str, list[dict]] = {}
        for ex in self._examples:
            by_class.setdefault(ex["label"], []).append(ex["features"])

        class_stats: dict[str, dict] = {}
        for cls, feat_list in by_class.items():
            stats: dict[str, dict] = {}
            for feat in _FEATURE_NAMES:
                vals = [f[feat] for f in feat_list]
                stats[feat] = {
                    "mean": float(np.mean(vals)),
                    "std":  float(np.std(vals)),
                    "p25":  float(np.percentile(vals, 25)),
                    "p75":  float(np.percentile(vals, 75)),
                }
            class_stats[cls] = stats

        thresholds: dict[str, float] = {}
        ext = by_class.get(CLASS_EXTERIOR, [])
        int_ = by_class.get(CLASS_INTERIOR, [])
        det = by_class.get(CLASS_DETAILS, [])

        def _sep(a_list, b_list, feat, pa=25, pb=75) -> float:
            """Ponto médio entre percentil inferior de A e superior de B."""
            a_vals = [f[feat] for f in a_list] if a_list else [0.0]
            b_vals = [f[feat] for f in b_list] if b_list else [0.0]
            return float((np.percentile(a_vals, pa) + np.percentile(b_vals, pb)) / 2)

        if ext:
            thresholds["sky_threshold"] = _sep(ext, int_, "sky_pct")
            thresholds["sky_upper_threshold"] = _sep(ext, int_, "sky_upper_pct")
            thresholds["green_contiguous_threshold"] = _sep(ext, int_, "largest_green_pct")

        if det:
            others = int_ + ext
            thresholds["edge_density_threshold"] = _sep(det, others, "edge_density")

        return {
            "version":      1,
            "n_examples":   len(self._examples),
            "class_counts": {cls: len(exs) for cls, exs in by_class.items()},
            "thresholds":   thresholds,
            "class_stats":  class_stats,
        }

    def save(self, profile: dict, output_path: str) -> None:
        """Salva perfil em JSON."""
        Path(output_path).write_text(
            json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def clear(self) -> None:
        self._examples.clear()
