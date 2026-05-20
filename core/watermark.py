"""
Módulo de marca d'água.

Adiciona marca d'água nas fotos exportadas:
  • Imagem (logo PNG com transparência)
  • Texto (nome da empresa, telefone, etc.)

Posições: canto inferior direito, inferior esquerdo, centro, etc.
Opacidade configurável.
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os


class Watermarker:
    """Aplica marca d'água em imagens."""

    def __init__(self, config: dict | None = None):
        """
        Args:
            config: dicionário com configurações da marca d'água.
                Chaves aceitas:
                    mode: "image" | "text"
                    image_path: caminho do logo PNG (modo image)
                    text: texto da marca d'água (modo text)
                    font_size: tamanho da fonte (modo text, padrão 28)
                    opacity: opacidade 0.0-1.0 (padrão 0.4)
                    position: "bottom-right" | "bottom-left" | "center" |
                              "top-right" | "top-left" (padrão "bottom-right")
                    margin: margem em pixels (padrão 30)
                    color: tupla (R, G, B) para texto (padrão branco)
        """
        self.config = config or {}
        self.enabled = bool(self.config)

    def apply(self, image_path: str, output_path: str | None = None) -> bool:
        """
        Aplica marca d'água na imagem.

        Args:
            image_path: caminho da imagem.
            output_path: onde salvar (se None, sobrescreve).

        Returns:
            True se aplicou, False se não (desabilitado ou erro).
        """
        if not self.enabled:
            return False

        if output_path is None:
            output_path = image_path

        mode = self.config.get("mode", "text")

        try:
            if mode == "image":
                return self._apply_image_watermark(image_path, output_path)
            else:
                return self._apply_text_watermark(image_path, output_path)
        except Exception:
            return False

    def _apply_text_watermark(self, image_path: str, output_path: str) -> bool:
        """Adiciona texto como marca d'água usando Pillow."""
        img = Image.open(image_path).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        text = self.config.get("text", "© Imóveis")
        font_size = self.config.get("font_size", 28)
        opacity = self.config.get("opacity", 0.4)
        color = self.config.get("color", (255, 255, 255))
        position = self.config.get("position", "bottom-right")
        margin = self.config.get("margin", 30)

        # Tenta carregar fonte do sistema, senão usa padrão
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

        # Calcula tamanho do texto
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        # Calcula posição
        x, y = self._calc_position(img.size, (tw, th), position, margin)

        # Desenha com opacidade
        alpha = int(255 * opacity)
        draw.text((x, y), text, font=font, fill=(*color, alpha))

        # Mescla
        result = Image.alpha_composite(img, overlay).convert("RGB")
        result.save(output_path, "JPEG", quality=95)
        return True

    def _apply_image_watermark(self, image_path: str, output_path: str) -> bool:
        """Adiciona logo como marca d'água."""
        logo_path = self.config.get("image_path", "")
        if not logo_path or not os.path.exists(logo_path):
            return False

        img = Image.open(image_path).convert("RGBA")
        logo = Image.open(logo_path).convert("RGBA")

        opacity = self.config.get("opacity", 0.4)
        position = self.config.get("position", "bottom-right")
        margin = self.config.get("margin", 30)

        # Redimensiona logo para no máximo 15% da largura da imagem
        max_logo_w = int(img.width * 0.15)
        if logo.width > max_logo_w:
            ratio = max_logo_w / logo.width
            logo = logo.resize((max_logo_w, int(logo.height * ratio)), Image.LANCZOS)

        # Ajusta opacidade
        r, g, b, a = logo.split()
        a = a.point(lambda p: int(p * opacity))
        logo = Image.merge("RGBA", (r, g, b, a))

        # Calcula posição
        x, y = self._calc_position(img.size, logo.size, position, margin)

        # Cola logo
        img.paste(logo, (x, y), logo)
        img.convert("RGB").save(output_path, "JPEG", quality=95)
        return True

    @staticmethod
    def _calc_position(img_size: tuple, wm_size: tuple,
                       position: str, margin: int) -> tuple[int, int]:
        """Calcula coordenadas (x, y) para a marca d'água."""
        iw, ih = img_size
        ww, wh = wm_size

        positions = {
            "bottom-right": (iw - ww - margin, ih - wh - margin),
            "bottom-left":  (margin, ih - wh - margin),
            "top-right":    (iw - ww - margin, margin),
            "top-left":     (margin, margin),
            "center":       ((iw - ww) // 2, (ih - wh) // 2),
        }

        return positions.get(position, positions["bottom-right"])
