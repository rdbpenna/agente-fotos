"""
Testes do classificador de imagens imobiliárias.

Usa imagens sintéticas (NumPy) para cobrir os casos mais comuns
sem precisar de arquivos reais no repositório.
"""

import sys
import os
import tempfile

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.classifier import ImageClassifier
from utils.config import CLASS_INTERIOR, CLASS_EXTERIOR, CLASS_DETAILS, CLASS_REVIEW


def _save_bgr(arr: np.ndarray, path: str):
    cv2.imwrite(path, arr)


def _sky_image() -> np.ndarray:
    """Imagem com céu azul dominante no topo (exterior)."""
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    img[:300, :] = (180, 100, 60)   # azul-céu (BGR) no terço superior
    img[300:, :] = (60, 100, 60)    # grama embaixo
    return img


def _indoor_plant_image() -> np.ndarray:
    """Imagem interior com planta decorativa pequena (interior, não exterior)."""
    img = np.full((600, 800, 3), (200, 190, 180), dtype=np.uint8)  # paredes bege
    # Pequena mancha verde espalhada (planta em vaso)
    for y in range(250, 350, 30):
        for x in range(350, 450, 30):
            img[y:y+15, x:x+15] = (40, 140, 40)   # verde (BGR)
    return img


def _large_grass_image() -> np.ndarray:
    """Imagem com gramado cobrindo metade da imagem (exterior)."""
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    img[:200, :] = (120, 80, 30)    # céu
    img[200:, :] = (40, 160, 40)    # gramado grande contíguo
    return img


def _room_image() -> np.ndarray:
    """Cômodo neutro sem elementos exteriores (interior)."""
    img = np.full((600, 800, 3), (210, 200, 195), dtype=np.uint8)
    return img


def _dark_image() -> np.ndarray:
    """Imagem muito escura → revisar."""
    return np.full((600, 800, 3), 15, dtype=np.uint8)


def _bright_image() -> np.ndarray:
    """Imagem estourada → revisar."""
    return np.full((600, 800, 3), 250, dtype=np.uint8)


def _tiny_image() -> np.ndarray:
    """Imagem minúscula (thumbnail) → revisar."""
    return np.full((100, 100, 3), 128, dtype=np.uint8)


def _detail_image() -> np.ndarray:
    """Grade/textura com muitas bordas (detalhes)."""
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    for i in range(0, 600, 8):
        img[i, :] = 200
    for j in range(0, 800, 8):
        img[:, j] = 200
    return img


@pytest.fixture
def clf():
    return ImageClassifier()


class TestReview:
    def test_dark_image_goes_to_review(self, clf, tmp_path):
        p = str(tmp_path / "dark.jpg")
        _save_bgr(_dark_image(), p)
        assert clf.classify(p) == CLASS_REVIEW

    def test_bright_image_goes_to_review(self, clf, tmp_path):
        p = str(tmp_path / "bright.jpg")
        _save_bgr(_bright_image(), p)
        assert clf.classify(p) == CLASS_REVIEW

    def test_tiny_image_goes_to_review(self, clf, tmp_path):
        p = str(tmp_path / "tiny.jpg")
        _save_bgr(_tiny_image(), p)
        assert clf.classify(p) == CLASS_REVIEW

    def test_missing_file_goes_to_review(self, clf):
        assert clf.classify("/nonexistent/path/img.jpg") == CLASS_REVIEW


class TestExterior:
    def test_sky_in_top_third_is_exterior(self, clf, tmp_path):
        p = str(tmp_path / "sky.jpg")
        _save_bgr(_sky_image(), p)
        assert clf.classify(p) == CLASS_EXTERIOR

    def test_large_grass_field_is_exterior(self, clf, tmp_path):
        p = str(tmp_path / "grass.jpg")
        _save_bgr(_large_grass_image(), p)
        assert clf.classify(p) == CLASS_EXTERIOR


class TestInterior:
    def test_plain_room_is_interior(self, clf, tmp_path):
        p = str(tmp_path / "room.jpg")
        _save_bgr(_room_image(), p)
        assert clf.classify(p) == CLASS_INTERIOR

    def test_indoor_plant_is_not_exterior(self, clf, tmp_path):
        """Planta decorativa espalhada em vários pontos não deve ser exterior."""
        p = str(tmp_path / "plant_room.jpg")
        _save_bgr(_indoor_plant_image(), p)
        result = clf.classify(p)
        assert result != CLASS_EXTERIOR, (
            f"Planta interior foi classificada como exterior: {result}"
        )


class TestDetails:
    def test_high_edge_density_is_details(self, clf, tmp_path):
        p = str(tmp_path / "detail.jpg")
        _save_bgr(_detail_image(), p)
        assert clf.classify(p) == CLASS_DETAILS
