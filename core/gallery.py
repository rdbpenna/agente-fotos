"""
Gerador de galeria HTML.

Cria uma página HTML bonita e responsiva com todas as fotos processadas.
Pode ser aberta diretamente no navegador — perfeita para enviar ao cliente
como prévia ou para visualização interna.

Funcionalidades:
  • Grid responsivo com lightbox (clique para ampliar)
  • Filtro por classificação
  • Design limpo e profissional
  • Funciona offline (sem dependências externas)
"""

import os
import base64
from datetime import datetime


class GalleryGenerator:
    """Gera galeria HTML com as fotos processadas."""

    def __init__(self, title: str = "Galeria de Fotos",
                 subtitle: str = "",
                 accent_color: str = "#2563eb",
                 show_filters: bool = True,
                 embed_thumbnails: bool = False):
        """
        Args:
            title:            título da galeria.
            subtitle:         subtítulo (ex: endereço do imóvel).
            accent_color:     cor destaque da interface.
            show_filters:     mostra filtros por classificação.
            embed_thumbnails: embute thumbnails em base64 (galeria portátil).
        """
        self.title = title
        self.subtitle = subtitle
        self.accent_color = accent_color
        self.show_filters = show_filters
        self.embed_thumbnails = embed_thumbnails

    def generate(self, images: list[dict], output_path: str,
                 images_folder: str = "") -> bool:
        """
        Gera a galeria HTML.

        Args:
            images: lista de dicts:
                    {"path": str, "filename": str, "classification": str}
            output_path: caminho do arquivo HTML de saída.
            images_folder: pasta relativa das imagens (para links).

        Returns:
            True se gerou com sucesso.
        """
        if not images:
            return False

        # Coleta classes para filtros
        classes = sorted(set(img.get("classification", "") for img in images))

        # Gera cards HTML
        cards_html = []
        for img in images:
            src = self._get_image_src(img, images_folder, output_path)
            cls = img.get("classification", "geral")
            fname = img.get("filename", "")

            cards_html.append(f'''
            <div class="card" data-class="{cls}">
                <img src="{src}" alt="{fname}" loading="lazy"
                     onclick="openLightbox(this.src, '{fname}')">
                <div class="card-info">
                    <span class="card-name">{fname}</span>
                    <span class="card-badge">{cls}</span>
                </div>
            </div>''')

        # Gera filtros
        filters_html = ""
        if self.show_filters and len(classes) > 1:
            btns = ['<button class="filter-btn active" onclick="filterCards(\'all\')">Todas</button>']
            for cls in classes:
                btns.append(
                    f'<button class="filter-btn" onclick="filterCards(\'{cls}\')">'
                    f'{cls.capitalize()}</button>'
                )
            filters_html = f'<div class="filters">{"".join(btns)}</div>'

        # Monta HTML completo
        html = self._build_html(
            cards="".join(cards_html),
            filters=filters_html,
            total=len(images),
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return True

    def _get_image_src(self, img: dict, images_folder: str,
                       html_path: str) -> str:
        """Retorna src da imagem (caminho relativo ou base64)."""
        if self.embed_thumbnails:
            try:
                with open(img["path"], "rb") as f:
                    data = base64.b64encode(f.read()).decode()
                return f"data:image/jpeg;base64,{data}"
            except Exception:
                pass

        # Caminho relativo
        if images_folder:
            return os.path.join(images_folder, img["filename"]).replace("\\", "/")

        # Calcula relativo ao HTML
        html_dir = os.path.dirname(os.path.abspath(html_path))
        img_abs = os.path.abspath(img["path"])
        try:
            rel = os.path.relpath(img_abs, html_dir)
            return rel.replace("\\", "/")
        except ValueError:
            # Drives diferentes no Windows: embute thumbnail compacto em base64
            return self._embed_thumbnail_base64(img["path"])

    @staticmethod
    def _embed_thumbnail_base64(path: str, max_px: int = 800) -> str:
        """Reduz e embute imagem como base64 (fallback para drives diferentes no Windows)."""
        try:
            import cv2
            img = cv2.imread(path)
            if img is None:
                raise ValueError("leitura falhou")
            h, w = img.shape[:2]
            scale = min(max_px / max(w, h, 1), 1.0)
            if scale < 1.0:
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 78])
            data = base64.b64encode(buf.tobytes()).decode()
            return f"data:image/jpeg;base64,{data}"
        except Exception:
            return path.replace("\\", "/")

    def _build_html(self, cards: str, filters: str, total: int) -> str:
        """Monta o HTML completo da galeria."""
        date = datetime.now().strftime("%d/%m/%Y %H:%M")

        return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self.title}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',system-ui,sans-serif; background:#111; color:#eee; }}
.header {{ padding:40px 30px 20px; text-align:center; }}
.header h1 {{ font-size:28px; font-weight:600; }}
.header p {{ color:#999; margin-top:6px; font-size:15px; }}
.meta {{ color:#666; font-size:13px; margin-top:10px; }}
.filters {{ display:flex; justify-content:center; gap:8px; padding:10px 20px 20px;
            flex-wrap:wrap; }}
.filter-btn {{ background:#222; border:1px solid #333; color:#aaa; padding:8px 18px;
               border-radius:20px; cursor:pointer; font-size:13px; transition:all .2s; }}
.filter-btn:hover {{ border-color:#555; color:#fff; }}
.filter-btn.active {{ background:{self.accent_color}; border-color:{self.accent_color};
                      color:#fff; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
         gap:12px; padding:0 20px 40px; max-width:1400px; margin:0 auto; }}
.card {{ background:#1a1a1a; border-radius:10px; overflow:hidden;
         transition:transform .2s, box-shadow .2s; }}
.card:hover {{ transform:translateY(-4px); box-shadow:0 8px 30px rgba(0,0,0,.5); }}
.card img {{ width:100%; aspect-ratio:4/3; object-fit:cover; cursor:pointer;
             transition:opacity .2s; }}
.card img:hover {{ opacity:.9; }}
.card-info {{ padding:10px 14px; display:flex; justify-content:space-between;
              align-items:center; }}
.card-name {{ font-size:12px; color:#888; overflow:hidden; text-overflow:ellipsis;
              white-space:nowrap; max-width:65%; }}
.card-badge {{ font-size:11px; background:#222; color:#aaa; padding:3px 10px;
               border-radius:12px; }}
.card.hidden {{ display:none; }}
.lightbox {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.95);
             z-index:100; justify-content:center; align-items:center;
             flex-direction:column; cursor:pointer; }}
.lightbox.open {{ display:flex; }}
.lightbox img {{ max-width:92vw; max-height:85vh; object-fit:contain;
                 border-radius:6px; }}
.lightbox .lb-name {{ color:#888; font-size:14px; margin-top:12px; }}
.footer {{ text-align:center; padding:20px; color:#444; font-size:12px; }}
</style>
</head>
<body>
<div class="header">
    <h1>{self.title}</h1>
    {"<p>" + self.subtitle + "</p>" if self.subtitle else ""}
    <p class="meta">{total} fotos &middot; Gerado em {date}</p>
</div>
{filters}
<div class="grid">{cards}</div>
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
    <img id="lb-img" src="" alt="">
    <span class="lb-name" id="lb-name"></span>
</div>
<div class="footer">
    Gerado pelo Agente de Fotos Imobili&aacute;rias
</div>
<script>
function filterCards(cls) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.card').forEach(c => {{
        c.classList.toggle('hidden', cls !== 'all' && c.dataset.class !== cls);
    }});
}}
function openLightbox(src, name) {{
    document.getElementById('lb-img').src = src;
    document.getElementById('lb-name').textContent = name;
    document.getElementById('lightbox').classList.add('open');
}}
function closeLightbox() {{
    document.getElementById('lightbox').classList.remove('open');
}}
document.addEventListener('keydown', e => {{ if(e.key==='Escape') closeLightbox(); }});
</script>
</body>
</html>'''
