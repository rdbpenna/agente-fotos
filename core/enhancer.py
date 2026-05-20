"""
Módulo de melhorias automáticas de imagem.

Aplica, em sequência:
  1. Balanço de branco (Gray World)
  2. Correção de exposição
  3. Melhoria de contraste (CLAHE)
  4. Redução de ruído (Non-Local Means)
  5. Nitidez (Unsharp Mask)
  6. Correção de perspectiva (endireitamento horizontal)

Cada etapa pode ser habilitada/desabilitada individualmente.
"""

import cv2
import numpy as np
import math
from utils.config import (
    EXPOSURE_FACTOR,
    CLAHE_CLIP_LIMIT, CLAHE_GRID_SIZE,
    SHARPEN_AMOUNT, SHARPEN_RADIUS,
    DENOISE_STRENGTH, DENOISE_TEMPLATE_WS, DENOISE_SEARCH_WS,
    WHITE_BALANCE_ENABLED,
    PERSPECTIVE_HOUGH_THRESHOLD, PERSPECTIVE_MAX_ANGLE_DEG,
)


class ImageEnhancer:
    """Pipeline de melhorias automáticas para fotos imobiliárias."""

    def __init__(self):
        self.log: list[str] = []  # registro das operações realizadas

    def enhance(self, image_path: str, output_path: str) -> list[str]:
        """
        Processa uma imagem e salva o resultado.

        Returns:
            Lista de strings descrevendo cada operação realizada.
        """
        self.log = []
        img = cv2.imread(image_path)
        if img is None:
            self.log.append("ERRO: não foi possível ler a imagem")
            return self.log

        original_shape = img.shape[:2]
        self.log.append(f"Imagem carregada: {original_shape[1]}x{original_shape[0]} px")

        # 1. Balanço de branco
        if WHITE_BALANCE_ENABLED:
            img = self._white_balance(img)

        # 2. Exposição
        img = self._adjust_exposure(img)

        # 3. Contraste (CLAHE)
        img = self._enhance_contrast(img)

        # 4. Redução de ruído
        img = self._denoise(img)

        # 5. Nitidez
        img = self._sharpen(img)

        # 6. Correção de perspectiva
        img = self._correct_perspective(img)

        # 7. Correção de keystone
        img = self._correct_keystone(img)

        # Salva resultado
        cv2.imwrite(output_path, img, [cv2.IMWRITE_JPEG_QUALITY, 98])
        self.log.append(f"Imagem salva em: {output_path}")
        return self.log

    # ── 1. Balanço de branco (Gray World) ────────────────────────

    def _white_balance(self, img: np.ndarray) -> np.ndarray:
        """
        Algoritmo Gray World: assume que a média das cores deve ser cinza neutro.
        Corrige desvios de temperatura de cor (fotos amareladas/azuladas).
        """
        result = img.astype(np.float32)
        avg_b = result[:, :, 0].mean()
        avg_g = result[:, :, 1].mean()
        avg_r = result[:, :, 2].mean()
        avg_gray = (avg_b + avg_g + avg_r) / 3.0

        if avg_b > 0:
            result[:, :, 0] *= avg_gray / avg_b
        if avg_g > 0:
            result[:, :, 1] *= avg_gray / avg_g
        if avg_r > 0:
            result[:, :, 2] *= avg_gray / avg_r

        result = np.clip(result, 0, 255).astype(np.uint8)
        self.log.append("Balanço de branco aplicado (Gray World)")
        return result

    # ── 2. Exposição ─────────────────────────────────────────────

    def _adjust_exposure(self, img: np.ndarray) -> np.ndarray:
        """
        Ajusta exposição baseado no brilho médio da imagem.
        Fotos subexpostas recebem boost; fotos já claras são preservadas.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean_brightness = gray.mean()

        # Calcula fator adaptativo: só corrige se está escuro
        if mean_brightness < 120:
            factor = EXPOSURE_FACTOR + (120 - mean_brightness) / 300.0
        elif mean_brightness > 180:
            factor = 1.0 - (mean_brightness - 180) / 500.0
        else:
            factor = 1.0
            self.log.append(f"Exposição OK (brilho médio: {mean_brightness:.0f}) — sem ajuste")
            return img

        result = cv2.convertScaleAbs(img, alpha=factor, beta=0)
        self.log.append(f"Exposição ajustada (fator: {factor:.2f}, brilho: {mean_brightness:.0f})")
        return result

    # ── 3. Contraste (CLAHE) ─────────────────────────────────────

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        """
        CLAHE (Contrast Limited Adaptive Histogram Equalization)
        aplicado no canal L do espaço LAB — preserva cores naturais.
        """
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=CLAHE_CLIP_LIMIT,
            tileGridSize=CLAHE_GRID_SIZE,
        )
        l_enhanced = clahe.apply(l_channel)

        lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
        result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        self.log.append(f"Contraste melhorado (CLAHE clip={CLAHE_CLIP_LIMIT})")
        return result

    # ── 4. Redução de ruído ──────────────────────────────────────

    def _denoise(self, img: np.ndarray) -> np.ndarray:
        """
        Non-Local Means Denoising — remove ruído preservando bordas.
        Usa versão colorida para melhor resultado.
        """
        result = cv2.fastNlMeansDenoisingColored(
            img,
            None,
            DENOISE_STRENGTH,
            DENOISE_STRENGTH,
            DENOISE_TEMPLATE_WS,
            DENOISE_SEARCH_WS,
        )
        self.log.append(f"Redução de ruído aplicada (h={DENOISE_STRENGTH})")
        return result

    # ── 5. Nitidez (Unsharp Mask) ────────────────────────────────

    def _sharpen(self, img: np.ndarray) -> np.ndarray:
        """
        Unsharp Mask: realça bordas sem criar artefatos visíveis.
        """
        gaussian = cv2.GaussianBlur(img, (0, 0), SHARPEN_RADIUS)
        result = cv2.addWeighted(img, SHARPEN_AMOUNT, gaussian, 1 - SHARPEN_AMOUNT, 0)
        self.log.append(f"Nitidez aplicada (fator: {SHARPEN_AMOUNT})")
        return result

    # ── 6. Correção de perspectiva ───────────────────────────────

    def _correct_perspective(self, img: np.ndarray) -> np.ndarray:
        """
        Detecta linhas horizontais/verticais dominantes e corrige
        pequenas inclinações (até ±MAX_ANGLE graus).
        Ideal para endireitar fotos de cômodos levemente tortas.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        lines = cv2.HoughLines(edges, 1, np.pi / 180, PERSPECTIVE_HOUGH_THRESHOLD)
        if lines is None:
            self.log.append("Perspectiva: nenhuma linha dominante detectada")
            return img

        # Coleta ângulos das linhas próximas da horizontal
        angles = []
        for line in lines:
            rho, theta = line[0]
            angle_deg = math.degrees(theta) - 90  # converte para desvio da horizontal
            if abs(angle_deg) < PERSPECTIVE_MAX_ANGLE_DEG:
                angles.append(angle_deg)

        if not angles:
            self.log.append("Perspectiva: sem inclinação significativa detectada")
            return img

        # Ângulo mediano (robusto a outliers)
        median_angle = float(np.median(angles))

        if abs(median_angle) < 0.3:
            self.log.append(f"Perspectiva: inclinação mínima ({median_angle:.2f}°) — ignorada")
            return img

        # Rotaciona para corrigir
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        result = cv2.warpAffine(
            img, rotation_matrix, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

        self.log.append(f"Perspectiva corrigida: rotação de {median_angle:.2f}°")
        return result

    # ── 7. Keystone ──────────────────────────────────────────────

    def _correct_keystone(self, img: np.ndarray) -> np.ndarray:
        """
        Detecta e corrige convergência de verticais (efeito keystone).
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
            angle = math.degrees(math.atan2(float(x2 - x1), dy))
            if abs(angle) > 8.0:
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
        self.log.append(f"Keystone corrigido: convergência {convergence:.1f}°")
        return result
