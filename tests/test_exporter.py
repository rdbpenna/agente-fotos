"""
Testes do ImageExporter.

Cobre redimensionamento e geração de perfis de exportação.
"""

import sys
import os
import tempfile
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.exporter import ImageExporter
from utils.config import EXPORT_PROFILES


@pytest.fixture
def exp():
    return ImageExporter()


def _save_test_image(path: str, h=2000, w=3000):
    img = np.random.randint(50, 200, (h, w, 3), dtype=np.uint8)
    cv2.imwrite(path, img)


class TestResizeFit:
    def test_smaller_image_not_upscaled(self, exp):
        img = np.zeros((100, 150, 3), dtype=np.uint8)
        result = exp._resize_fit(img, 4000, 3000)
        assert result.shape == img.shape, "Imagens menores não devem ser ampliadas"

    def test_large_image_reduced(self, exp):
        img = np.zeros((3000, 4000, 3), dtype=np.uint8)
        result = exp._resize_fit(img, 1080, 1080)
        assert result.shape[0] <= 1080
        assert result.shape[1] <= 1080

    def test_aspect_ratio_preserved(self, exp):
        img = np.zeros((1000, 2000, 3), dtype=np.uint8)  # 2:1
        result = exp._resize_fit(img, 1080, 1080)
        ratio_in = 2000 / 1000
        ratio_out = result.shape[1] / result.shape[0]
        assert abs(ratio_in - ratio_out) < 0.01, "Proporção deve ser preservada"

    def test_exact_fit_dimensions(self, exp):
        img = np.zeros((3000, 4000, 3), dtype=np.uint8)
        result = exp._resize_fit(img, 4000, 3000)
        assert result.shape == img.shape, "Imagem com tamanho exato não deve ser alterada"


class TestExport:
    def test_creates_all_profiles(self, exp, tmp_path):
        src = str(tmp_path / "source.jpg")
        out_dir = str(tmp_path / "exports")
        _save_test_image(src)
        exported = exp.export(src, out_dir, "test_photo")
        assert len(exported) == len(EXPORT_PROFILES), (
            f"Esperado {len(EXPORT_PROFILES)} arquivos, gerado {len(exported)}"
        )
        for path in exported:
            assert os.path.exists(path), f"Arquivo exportado não encontrado: {path}"

    def test_instagram_profile_max_dimension(self, exp, tmp_path):
        src = str(tmp_path / "large.jpg")
        out_dir = str(tmp_path / "exports")
        _save_test_image(src, h=3000, w=4000)
        exported = exp.export(src, out_dir, "large_photo")
        ig_profile = EXPORT_PROFILES["instagram"]
        ig_path = next((p for p in exported if "_IG" in p), None)
        assert ig_path is not None, "Perfil Instagram não gerado"
        img = cv2.imread(ig_path)
        assert img.shape[0] <= ig_profile["max_height"]
        assert img.shape[1] <= ig_profile["max_width"]

    def test_missing_source_returns_empty(self, exp, tmp_path):
        result = exp.export("/nonexistent/image.jpg", str(tmp_path), "test")
        assert result == []
