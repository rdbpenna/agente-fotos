"""
Exportação de contact sheet em PDF usando Pillow.
Gera páginas A4 landscape com grade de miniaturas.
"""
from __future__ import annotations

import math
import os


def export_contact_sheet_pdf(
    image_paths: list[str],
    output_path: str,
    title: str = "Fotos do Imóvel",
    cols: int = 3,
) -> str:
    """Gera PDF com grade de miniaturas. Retorna caminho do arquivo salvo."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise RuntimeError("Pillow não encontrado. Instale com: pip install Pillow")

    if not image_paths:
        raise ValueError("Nenhuma imagem para exportar.")

    # A4 landscape a 150 dpi
    PAGE_W, PAGE_H = 1754, 1240
    MARGIN = 60
    GAP = 16
    HEADER_H = 52
    BG = (18, 28, 44)
    CELL_BG = (28, 42, 64)

    usable_w = PAGE_W - MARGIN * 2
    cell_w = (usable_w - GAP * (cols - 1)) // cols
    cell_h = int(cell_w * 3 / 4)
    rows_per_page = max(1, (PAGE_H - MARGIN * 2 - HEADER_H - GAP) // (cell_h + GAP))
    imgs_per_page = cols * rows_per_page

    chunks = [image_paths[i:i + imgs_per_page] for i in range(0, len(image_paths), imgs_per_page)]
    total_pages = len(chunks)

    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_small = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font_title = ImageFont.load_default()
        font_small = font_title

    pages: list[Image.Image] = []

    for page_idx, chunk in enumerate(chunks):
        page = Image.new("RGB", (PAGE_W, PAGE_H), BG)
        draw = ImageDraw.Draw(page)

        # Header
        draw.text((MARGIN, MARGIN), title, fill=(230, 237, 245), font=font_title)
        page_label = f"Página {page_idx + 1}/{total_pages}  ·  {len(image_paths)} foto(s)"
        draw.text((MARGIN, MARGIN + 28), page_label, fill=(90, 110, 140), font=font_small)

        for idx, img_path in enumerate(chunk):
            col = idx % cols
            row = idx // cols
            cx = MARGIN + col * (cell_w + GAP)
            cy = MARGIN + HEADER_H + GAP + row * (cell_h + GAP)

            # Cell background
            draw.rectangle([cx, cy, cx + cell_w, cy + cell_h], fill=CELL_BG)

            try:
                img = Image.open(img_path).convert("RGB")
                img.thumbnail((cell_w, cell_h), Image.LANCZOS)
                ox = cx + (cell_w - img.width) // 2
                oy = cy + (cell_h - img.height) // 2
                page.paste(img, (ox, oy))
            except Exception:
                draw.text((cx + 8, cy + cell_h // 2), "Erro", fill=(200, 60, 60), font=font_small)

            # Filename caption
            name = os.path.basename(img_path)
            if len(name) > 28:
                name = name[:25] + "…"
            draw.text((cx + 4, cy + cell_h + 2), name, fill=(80, 100, 130), font=font_small)

        pages.append(page)

    if not pages:
        raise ValueError("Nenhuma página gerada.")

    pages[0].save(
        output_path,
        "PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=150,
    )
    return output_path
