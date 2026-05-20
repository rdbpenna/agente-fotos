"""
Gerador de folha de contato (contact sheet).

Cria uma imagem grande com miniaturas de todas as fotos processadas,
organizada em grade — perfeito para enviar ao cliente como prévia
ou para uso interno de conferência rápida.

Também gera thumbnails individuais para navegação.
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class ContactSheetGenerator:
    """Gera folha de contato e thumbnails."""

    def __init__(self, thumb_size: tuple[int, int] = (300, 200),
                 columns: int = 4, padding: int = 10,
                 show_filename: bool = True,
                 show_classification: bool = True,
                 background_color: tuple = (30, 30, 30)):
        """
        Args:
            thumb_size:          tamanho de cada miniatura (largura, altura).
            columns:             número de colunas na grade.
            padding:             espaço entre miniaturas em pixels.
            show_filename:       exibe nome do arquivo embaixo.
            show_classification: exibe classe (interior/exterior) embaixo.
            background_color:    cor de fundo (R, G, B).
        """
        self.thumb_w, self.thumb_h = thumb_size
        self.columns = columns
        self.padding = padding
        self.show_filename = show_filename
        self.show_classification = show_classification
        self.bg_color = background_color

    def generate(self, images: list[dict], output_path: str,
                 title: str = "Fotos do Imóvel") -> bool:
        """
        Gera a folha de contato.

        Args:
            images: lista de dicts com:
                    {"path": str, "filename": str, "classification": str}
            output_path: onde salvar a folha de contato.
            title: título no topo da folha.

        Returns:
            True se gerou com sucesso.
        """
        if not images:
            return False

        n = len(images)
        rows = (n + self.columns - 1) // self.columns
        label_h = 40 if (self.show_filename or self.show_classification) else 0
        title_h = 60

        # Calcula dimensões da imagem final
        sheet_w = (self.thumb_w + self.padding) * self.columns + self.padding
        sheet_h = title_h + (self.thumb_h + label_h + self.padding) * rows + self.padding

        # Cria canvas com Pillow
        sheet = Image.new("RGB", (sheet_w, sheet_h), self.bg_color)
        draw = ImageDraw.Draw(sheet)

        # Fonte
        try:
            font_title = ImageFont.truetype("arial.ttf", 24)
            font_label = ImageFont.truetype("arial.ttf", 12)
        except (OSError, IOError):
            try:
                font_title = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
                font_label = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            except (OSError, IOError):
                font_title = ImageFont.load_default()
                font_label = ImageFont.load_default()

        # Título
        draw.text((self.padding, 15), title, fill=(255, 255, 255), font=font_title)

        # Gera miniaturas
        for idx, img_info in enumerate(images):
            row = idx // self.columns
            col = idx % self.columns

            x = self.padding + col * (self.thumb_w + self.padding)
            y = title_h + self.padding + row * (self.thumb_h + label_h + self.padding)

            # Carrega e redimensiona
            thumb = self._make_thumbnail(img_info["path"])
            if thumb is not None:
                sheet.paste(thumb, (x, y))

            # Label
            if label_h > 0:
                label_parts = []
                if self.show_filename:
                    name = img_info.get("filename", "")
                    if len(name) > 30:
                        name = name[:27] + "..."
                    label_parts.append(name)
                if self.show_classification:
                    cls = img_info.get("classification", "")
                    label_parts.append(f"[{cls}]")

                label_text = "  ".join(label_parts)
                draw.text((x + 4, y + self.thumb_h + 4),
                          label_text, fill=(180, 180, 180), font=font_label)

        sheet.save(output_path, "JPEG", quality=92)
        return True

    def generate_thumbnails(self, image_paths: list[str],
                            output_dir: str, size: tuple = (400, 300)) -> list[str]:
        """
        Gera thumbnails individuais para todas as imagens.

        Returns:
            Lista de caminhos dos thumbnails gerados.
        """
        os.makedirs(output_dir, exist_ok=True)
        generated = []

        for path in image_paths:
            filename = os.path.basename(path)
            base, ext = os.path.splitext(filename)
            thumb_path = os.path.join(output_dir, f"{base}_thumb.jpg")

            img = cv2.imread(path)
            if img is None:
                continue

            h, w = img.shape[:2]
            scale = min(size[0] / w, size[1] / h)
            if scale < 1.0:
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

            cv2.imwrite(thumb_path, img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            generated.append(thumb_path)

        return generated

    def _make_thumbnail(self, image_path: str) -> Image.Image | None:
        """Cria thumbnail PIL com tamanho exato, com letterbox se necessário."""
        try:
            img = Image.open(image_path)
            img.thumbnail((self.thumb_w, self.thumb_h), Image.LANCZOS)

            # Letterbox para tamanho exato
            thumb = Image.new("RGB", (self.thumb_w, self.thumb_h), (50, 50, 50))
            offset_x = (self.thumb_w - img.width) // 2
            offset_y = (self.thumb_h - img.height) // 2
            thumb.paste(img, (offset_x, offset_y))

            return thumb
        except Exception:
            return None
