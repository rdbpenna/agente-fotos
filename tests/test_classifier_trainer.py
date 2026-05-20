"""
Testes do ClassifierTrainer.

Usa arrays NumPy sintéticos para simular fotos de cada classe
sem depender de arquivos reais.
"""

import sys
import os
import json
import tempfile
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.classifier_trainer import ClassifierTrainer, _extract_features
from utils.config import CLASS_INTERIOR, CLASS_EXTERIOR, CLASS_DETAILS, CLASS_REVIEW


def _write_synthetic(path: str, h: int, w: int, bgr: tuple[int, int, int]):
    """Cria imagem sólida com a cor BGR informada."""
    img = np.full((h, w, 3), bgr, dtype=np.uint8)
    cv2.imwrite(path, img)


def _write_random(path: str, h=300, w=400):
    rng = np.random.default_rng(0)
    img = rng.integers(60, 200, (h, w, 3), dtype=np.uint8)
    cv2.imwrite(path, img)


class TestExtractFeatures:
    def test_missing_file_returns_none(self):
        assert _extract_features("/nonexistent/path.jpg") is None

    def test_all_features_present(self, tmp_path):
        path = str(tmp_path / "img.jpg")
        _write_random(path)
        feats = _extract_features(path)
        assert feats is not None
        expected_keys = {"sky_pct", "sky_upper_pct", "green_pct",
                         "largest_green_pct", "edge_density", "brightness"}
        assert expected_keys.issubset(feats.keys())

    def test_features_in_valid_range(self, tmp_path):
        path = str(tmp_path / "img.jpg")
        _write_random(path)
        feats = _extract_features(path)
        assert 0 <= feats["sky_pct"] <= 100
        assert 0 <= feats["green_pct"] <= 100
        assert 0 <= feats["edge_density"] <= 1
        assert 0 <= feats["brightness"] <= 255


class TestTrainer:
    def test_invalid_label_raises(self, tmp_path):
        t = ClassifierTrainer()
        path = str(tmp_path / "img.jpg")
        _write_random(path)
        with pytest.raises(ValueError):
            t.add_example(path, "invalid_class")

    def test_missing_file_returns_false(self):
        t = ClassifierTrainer()
        assert t.add_example("/nonexistent/file.jpg", CLASS_INTERIOR) is False

    def test_add_and_count(self, tmp_path):
        t = ClassifierTrainer()
        for i in range(3):
            p = str(tmp_path / f"int_{i}.jpg")
            _write_random(p)
            t.add_example(p, CLASS_INTERIOR)
        for i in range(2):
            p = str(tmp_path / f"ext_{i}.jpg")
            _write_random(p)
            t.add_example(p, CLASS_EXTERIOR)
        counts = t.count()
        assert counts[CLASS_INTERIOR] == 3
        assert counts[CLASS_EXTERIOR] == 2

    def test_train_requires_minimum_examples(self):
        t = ClassifierTrainer()
        with pytest.raises(RuntimeError):
            t.train()

    def test_train_returns_valid_profile(self, tmp_path):
        t = ClassifierTrainer()
        for i in range(2):
            p = str(tmp_path / f"a_{i}.jpg")
            _write_random(p)
            t.add_example(p, CLASS_INTERIOR)
        for i in range(2):
            p = str(tmp_path / f"b_{i}.jpg")
            _write_random(p)
            t.add_example(p, CLASS_EXTERIOR)
        profile = t.train()
        assert profile["version"] == 1
        assert profile["n_examples"] == 4
        assert "class_stats" in profile
        assert "thresholds" in profile

    def test_save_creates_valid_json(self, tmp_path):
        t = ClassifierTrainer()
        for i in range(2):
            p = str(tmp_path / f"img_{i}.jpg")
            _write_random(p)
            t.add_example(p, CLASS_INTERIOR)
        for i in range(2):
            p = str(tmp_path / f"ext_{i}.jpg")
            _write_random(p)
            t.add_example(p, CLASS_EXTERIOR)
        profile = t.train()
        out = str(tmp_path / "profile.json")
        t.save(profile, out)
        assert os.path.exists(out)
        loaded = json.loads(open(out, encoding="utf-8").read())
        assert loaded["version"] == 1

    def test_clear_resets_examples(self, tmp_path):
        t = ClassifierTrainer()
        p = str(tmp_path / "img.jpg")
        _write_random(p)
        t.add_example(p, CLASS_INTERIOR)
        assert sum(t.count().values()) == 1
        t.clear()
        assert sum(t.count().values()) == 0
