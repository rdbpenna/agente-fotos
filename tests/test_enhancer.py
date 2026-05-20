"""
Testes dos métodos internos do ImageEnhancer.

Testa cada etapa com arrays NumPy sintéticos, sem dependência de arquivos.
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.enhancer import ImageEnhancer


@pytest.fixture
def enh():
    return ImageEnhancer()


def _gray_bgr(value: int, h=200, w=300) -> np.ndarray:
    """Imagem BGR uniforme com valor de cinza especificado."""
    return np.full((h, w, 3), value, dtype=np.uint8)


def _random_bgr(h=200, w=300, seed=42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(50, 200, (h, w, 3), dtype=np.uint8)


class TestWhiteBalance:
    def test_gray_image_unchanged(self, enh):
        img = _gray_bgr(128)
        result = enh._white_balance(img)
        assert result.dtype == np.uint8
        np.testing.assert_allclose(result.astype(float), img.astype(float), atol=2)

    def test_blue_cast_reduced(self, enh):
        img = _random_bgr()
        # Força cast azul: aumenta canal B
        img[:, :, 0] = np.clip(img[:, :, 0].astype(int) + 60, 0, 255).astype(np.uint8)
        result = enh._white_balance(img)
        blue_before = img[:, :, 0].mean()
        blue_after = result[:, :, 0].mean()
        assert blue_after < blue_before, "White balance deveria reduzir o cast azul"

    def test_output_shape_preserved(self, enh):
        img = _random_bgr(120, 160)
        result = enh._white_balance(img)
        assert result.shape == img.shape


class TestExposure:
    def test_dark_image_brightened(self, enh):
        img = _gray_bgr(60)
        result = enh._adjust_exposure(img)
        assert result.mean() > img.mean(), "Imagem escura deve ser clareada"

    def test_bright_image_dimmed_or_preserved(self, enh):
        img = _gray_bgr(200)
        result = enh._adjust_exposure(img)
        assert result.mean() <= img.mean() + 5

    def test_neutral_image_unchanged(self, enh):
        img = _gray_bgr(150)
        result = enh._adjust_exposure(img)
        np.testing.assert_allclose(result.astype(float), img.astype(float), atol=5)

    def test_output_range_valid(self, enh):
        for value in (20, 80, 150, 210):
            img = _gray_bgr(value)
            result = enh._adjust_exposure(img)
            assert result.min() >= 0
            assert result.max() <= 255


class TestContrast:
    def test_output_shape_preserved(self, enh):
        img = _random_bgr()
        result = enh._enhance_contrast(img)
        assert result.shape == img.shape

    def test_output_dtype_uint8(self, enh):
        img = _random_bgr()
        result = enh._enhance_contrast(img)
        assert result.dtype == np.uint8

    def test_contrast_increases_std(self, enh):
        import cv2
        img = _random_bgr()
        result = enh._enhance_contrast(img)
        gray_in = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std()
        gray_out = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY).std()
        assert gray_out >= gray_in * 0.95, "Contraste não deve reduzir desvio padrão significativamente"


class TestSharpen:
    def test_output_shape_preserved(self, enh):
        img = _random_bgr()
        result = enh._sharpen(img)
        assert result.shape == img.shape

    def test_output_dtype_uint8(self, enh):
        img = _random_bgr()
        assert enh._sharpen(img).dtype == np.uint8


class TestPerspective:
    def test_returns_same_shape(self, enh):
        img = _random_bgr(400, 600)
        result = enh._correct_perspective(img)
        assert result.shape == img.shape

    def test_uniform_image_unchanged(self, enh):
        img = _gray_bgr(128, 400, 600)
        result = enh._correct_perspective(img)
        assert result.shape == img.shape


class TestKeystone:
    def test_returns_same_shape(self, enh):
        img = _random_bgr(400, 600)
        result = enh._correct_keystone(img)
        assert result.shape == img.shape

    def test_output_dtype_uint8(self, enh):
        img = _random_bgr(400, 600)
        result = enh._correct_keystone(img)
        assert result.dtype == np.uint8

    def test_uniform_image_safe(self, enh):
        img = _gray_bgr(128, 400, 600)
        result = enh._correct_keystone(img)
        assert result.shape == img.shape
