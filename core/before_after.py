"""
Gerador de comparação Antes/Depois.

Cria imagens lado a lado mostrando o resultado do processamento.
Útil para portfólio, demonstração ao cliente, e controle de qualidade.

Modos de comparação:
  • side_by_side — duas imagens lado a lado
  • slider       — linha divisória vertical (imagem estática simulando slider)
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os


class BeforeAfterGenerator:
    """Gera imagens de comparação antes/depois."""

    def __init__(self, mode: str = "side_by_side",
                 max_width: int = 2000,
                 label_before: str = "ANTES",
                 label_after: str = "DEPOIS"):
        """
        Args:
            mode:         "side_by_side" ou "slider"
            max_width:    largura máxima da imagem final
            label_before: texto do label esquerdo
            label_after:  texto do label direito
        """
        self.mode = mode
        self.max_width = max_width
        self.label_before = label_before
        self.label_after = label_after

    def generate(self, before_path: str, after_path: str,
                 output_path: str) -> bool:
        """
        Gera imagem de comparação.

        Returns:
            True se gerou com sucesso.
        """
        before = cv2.imread(before_path)
        after = cv2.imread(after_path)

        if before is None or after is None:
            return False

        # Garante mesmo tamanho
        h = min(before.shape[0], after.shape[0])
        w = min(before.shape[1], after.shape[1])
        before = cv2.resize(before, (w, h))
        after = cv2.resize(after, (w, h))

        if self.mode == "slider":
            result = self._make_slider(before, after)
        else:
            result = self._make_side_by_side(before, after)

        cv2.imwrite(output_path, result, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return True

    def generate_batch(self, pairs: list[dict], output_dir: str) -> list[str]:
        """
        Gera comparações em lote.

        Args:
            pairs: lista de {"before": path, "after": path, "name": str}
            output_dir: pasta de saída

        Returns:
            Lista de caminhos gerados.
        """
        os.makedirs(output_dir, exist_ok=True)
        generated = []

        for pair in pairs:
            name = pair.get("name", os.path.basename(pair["before"]))
            base, ext = os.path.splitext(name)
            out_path = os.path.join(output_dir, f"{base}_comparacao.jpg")

            if self.generate(pair["before"], pair["after"], out_path):
                generated.append(out_path)

        return generated

    def _make_side_by_side(self, before: np.ndarray,
                           after: np.ndarray) -> np.ndarray:
        """Cria imagem lado a lado com labels."""
        h, w = before.shape[:2]
        gap = 4  # linha divisória

        # Redimensiona se necessário
        total_w = w * 2 + gap
        if total_w > self.max_width:
            scale = self.max_width / total_w
            w = int(w * scale)
            h = int(h * scale)
            before = cv2.resize(before, (w, h))
            after = cv2.resize(after, (w, h))
            total_w = w * 2 + gap

        # Canvas
        canvas = np.zeros((h + 50, total_w, 3), dtype=np.uint8)
        canvas[:, :] = (30, 30, 30)

        # Cola imagens
        canvas[:h, :w] = before
        canvas[:h, w + gap:] = after

        # Linha divisória branca
        canvas[:h, w:w + gap] = (200, 200, 200)

        # Labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.6, w / 800)
        thickness = max(1, int(font_scale * 2))

        # Label ANTES
        (tw, th), _ = cv2.getTextSize(self.label_before, font, font_scale, thickness)
        cv2.putText(canvas, self.label_before,
                    ((w - tw) // 2, h + 35),
                    font, font_scale, (180, 180, 180), thickness)

        # Label DEPOIS
        (tw, th), _ = cv2.getTextSize(self.label_after, font, font_scale, thickness)
        cv2.putText(canvas, self.label_after,
                    (w + gap + (w - tw) // 2, h + 35),
                    font, font_scale, (180, 180, 180), thickness)

        return canvas

    def _make_slider(self, before: np.ndarray,
                     after: np.ndarray) -> np.ndarray:
        """Cria efeito de slider vertical (50/50)."""
        h, w = before.shape[:2]

        if w * 1 > self.max_width:
            scale = self.max_width / w
            w = int(w * scale)
            h = int(h * scale)
            before = cv2.resize(before, (w, h))
            after = cv2.resize(after, (w, h))

        mid = w // 2
        canvas = np.zeros((h + 50, w, 3), dtype=np.uint8)
        canvas[:, :] = (30, 30, 30)

        # Metade esquerda = antes, metade direita = depois
        canvas[:h, :mid] = before[:, :mid]
        canvas[:h, mid:] = after[:, mid:]

        # Linha divisória
        cv2.line(canvas, (mid, 0), (mid, h), (255, 255, 255), 2)

        # Seta/indicador no meio
        arrow_y = h // 2
        cv2.arrowedLine(canvas, (mid - 30, arrow_y), (mid - 8, arrow_y),
                        (255, 255, 255), 2, tipLength=0.4)
        cv2.arrowedLine(canvas, (mid + 30, arrow_y), (mid + 8, arrow_y),
                        (255, 255, 255), 2, tipLength=0.4)

        # Labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.5, w / 1000)
        thickness = max(1, int(font_scale * 2))

        cv2.putText(canvas, self.label_before,
                    (20, h + 35), font, font_scale, (180, 180, 180), thickness)

        (tw, _), _ = cv2.getTextSize(self.label_after, font, font_scale, thickness)
        cv2.putText(canvas, self.label_after,
                    (w - tw - 20, h + 35), font, font_scale, (180, 180, 180), thickness)

        return canvas
