"""
Classificador de imagens imobiliárias.

Estratégia em duas camadas:
  1. Heurísticas rápidas com OpenCV (cor, bordas, brilho)
  2. (Opcional) MobileNetV2 pré-treinado via TensorFlow/ONNX para refinamento

Se o modelo de IA não estiver disponível, as heurísticas sozinhas
já produzem uma separação razoável para o MVP.
"""

import json
import cv2
import numpy as np
from utils.config import (
    CLASS_INTERIOR, CLASS_EXTERIOR, CLASS_DETAILS, CLASS_REVIEW,
    GREEN_THRESHOLD_PCT, SKY_BLUE_THRESHOLD_PCT,
    DETAIL_EDGE_DENSITY_MIN, MIN_BRIGHTNESS, MAX_BRIGHTNESS,
)

# Tenta importar ONNX Runtime para classificação com IA
_onnx_available = False
try:
    import onnxruntime as ort
    _onnx_available = True
except ImportError:
    pass


class ImageClassifier:
    """Classifica fotos de imóveis em: interior, exterior, detalhes, revisar."""

    def __init__(self, model_path: str | None = None,
                 classifier_profile_path: str | None = None):
        """
        Args:
            model_path:               caminho para modelo ONNX (opcional).
            classifier_profile_path:  caminho para perfil JSON de limiares aprendidos.
        """
        self.session = None
        if model_path and _onnx_available:
            try:
                self.session = ort.InferenceSession(model_path)
            except Exception:
                self.session = None

        # Limiares aprendidos (sobrescrevem os defaults de config.py quando presentes)
        self._learned: dict = {}
        if classifier_profile_path:
            try:
                raw = json.loads(
                    open(classifier_profile_path, encoding="utf-8").read()
                )
                self._learned = raw.get("thresholds", {})
            except Exception:
                pass

    # ── API pública ──────────────────────────────────────────────

    def classify(self, image_path: str) -> str:
        """
        Retorna a classe da imagem: interior | exterior | detalhes | revisar.
        """
        img = cv2.imread(image_path)
        if img is None:
            return CLASS_REVIEW

        # Primeiro verifica condições de revisão obrigatória
        if self._needs_review(img):
            return CLASS_REVIEW

        # Tenta modelo de IA (se disponível)
        if self.session is not None:
            result = self._classify_with_model(img)
            if result:
                return result

        # Fallback: heurísticas baseadas em cor e textura
        return self._classify_heuristic(img)

    # ── Verificação de qualidade ─────────────────────────────────

    def _needs_review(self, img: np.ndarray) -> bool:
        """Imagens muito escuras, muito claras ou corrompidas vão para revisão."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean_brightness = gray.mean()
        if mean_brightness < MIN_BRIGHTNESS or mean_brightness > MAX_BRIGHTNESS:
            return True

        # Imagem muito pequena (provável thumbnail ou ícone)
        h, w = img.shape[:2]
        if h < 200 or w < 200:
            return True

        return False

    # ── Heurísticas ──────────────────────────────────────────────

    def _classify_heuristic(self, img: np.ndarray) -> str:
        """
        Classificação por análise de cor e textura.

        Melhorias sobre a versão anterior:
        - Céu deve estar concentrado no terço superior (evita janelas ou objetos azuis).
        - Verde só conta como exterior se houver uma região contígua grande
          (evita plantas decorativas em vasos ou paredes internas).
        """
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, w = img.shape[:2]
        total = h * w

        # Limiares: valores aprendidos têm prioridade sobre defaults de config.py
        sky_thr = self._learned.get("sky_threshold", SKY_BLUE_THRESHOLD_PCT)
        sky_upper_thr = self._learned.get("sky_upper_threshold", SKY_BLUE_THRESHOLD_PCT * 1.5)
        green_con_thr = self._learned.get("green_contiguous_threshold", GREEN_THRESHOLD_PCT * 0.6)
        edge_thr = self._learned.get("edge_density_threshold", DETAIL_EDGE_DENSITY_MIN)

        # --- Céu com verificação de posição ---
        sky_mask = cv2.inRange(hsv, (95, 40, 150), (130, 255, 255))
        sky_pct = np.count_nonzero(sky_mask) / total * 100
        sky_upper_pct = np.count_nonzero(sky_mask[: h // 3, :]) / max((h // 3) * w, 1) * 100
        has_sky = sky_pct > sky_thr and sky_upper_pct > sky_upper_thr

        # --- Verde: região contígua grande = vegetação exterior ---
        green_mask = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
        green_pct = np.count_nonzero(green_mask) / total * 100

        has_large_green = False
        if green_pct > GREEN_THRESHOLD_PCT * 0.5:
            kernel = np.ones((9, 9), np.uint8)
            closed = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
            n, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
            if n > 1:
                largest_area = int(stats[1:, cv2.CC_STAT_AREA].max())
                has_large_green = largest_area / total * 100 > green_con_thr

        if has_sky or has_large_green or green_pct > GREEN_THRESHOLD_PCT * 1.8:
            return CLASS_EXTERIOR

        # --- Detalhes (close-up): alta densidade de bordas ---
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.count_nonzero(edges) / total

        if edge_density > edge_thr:
            return CLASS_DETAILS

        return CLASS_INTERIOR

    # ── Classificação com modelo ONNX ────────────────────────────

    def _classify_with_model(self, img: np.ndarray) -> str | None:
        """
        Usa modelo ONNX pré-treinado para classificar.
        Retorna None se não conseguir classificar.
        """
        try:
            # Pré-processa para input do modelo (224×224, normalizado)
            resized = cv2.resize(img, (224, 224))
            blob = resized.astype(np.float32) / 255.0
            blob = np.transpose(blob, (2, 0, 1))  # HWC → CHW
            blob = np.expand_dims(blob, axis=0)

            input_name = self.session.get_inputs()[0].name
            output = self.session.run(None, {input_name: blob})
            probs = output[0][0]

            # Mapeia índices para classes (ajuste conforme seu modelo)
            class_map = {0: CLASS_INTERIOR, 1: CLASS_EXTERIOR,
                         2: CLASS_DETAILS, 3: CLASS_REVIEW}
            predicted = int(np.argmax(probs))
            confidence = float(probs[predicted])

            # Só aceita se confiança > 60%
            if confidence > 0.6:
                return class_map.get(predicted, CLASS_REVIEW)
            return None
        except Exception:
            return None
