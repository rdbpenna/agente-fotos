"""
Entrega ao cliente: ZIP e galeria de prova HTML.
"""
from __future__ import annotations

import base64
import os
import zipfile
from pathlib import Path
from typing import Callable


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif"}


def _collect_images(folder: str) -> list[str]:
    found = []
    for root, _, files in os.walk(folder):
        for f in sorted(files):
            if Path(f).suffix.lower() in _IMAGE_EXTS:
                found.append(os.path.join(root, f))
    return found


def create_delivery_zip(
    source_folder: str,
    output_zip: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> str:
    """
    Empacota todas as imagens de source_folder (recursivo) num ZIP.
    Retorna o caminho do ZIP gerado.
    """
    images = _collect_images(source_folder)
    if not images:
        raise ValueError(f"Nenhuma imagem encontrada em: {source_folder}")

    Path(output_zip).parent.mkdir(parents=True, exist_ok=True)
    total = len(images)

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for idx, img_path in enumerate(images):
            arcname = os.path.relpath(img_path, source_folder)
            zf.write(img_path, arcname)
            if progress_cb:
                progress_cb(idx + 1, total)

    return output_zip


def create_proof_gallery(
    image_paths: list[str],
    output_html: str,
    title: str = "Galeria de Prova",
    photographer: str = "",
    property_address: str = "",
    watermark_text: str = "PROVA — NÃO UTILIZAR SEM APROVAÇÃO",
) -> str:
    """
    Gera uma galeria HTML de prova para enviar ao cliente.
    Fotos com caminho relativo ao HTML. Inclui checkbox de aprovação por foto
    e botão para imprimir/exportar lista de aprovadas.
    """
    if not image_paths:
        raise ValueError("Nenhuma imagem para a galeria.")

    html_dir = Path(output_html).parent
    html_dir.mkdir(parents=True, exist_ok=True)

    # Gera paths relativos ao HTML
    rel_paths: list[tuple[str, str]] = []
    for p in image_paths:
        try:
            rel = os.path.relpath(p, str(html_dir)).replace("\\", "/")
        except ValueError:
            rel = p.replace("\\", "/")
        rel_paths.append((rel, os.path.basename(p)))

    n = len(image_paths)
    info_parts = [x for x in [photographer, property_address] if x]
    info_str = " · ".join(info_parts) if info_parts else ""

    thumb_items = ""
    for idx, (rel, name) in enumerate(rel_paths):
        thumb_items += f"""
        <div class="thumb" id="t{idx}">
          <div class="wm-wrap">
            <img src="{rel}" alt="{name}" loading="lazy" onclick="zoom('{rel}','{name}')">
            <div class="wm">{watermark_text}</div>
          </div>
          <div class="caption">
            <label class="chk-wrap">
              <input type="checkbox" onchange="updateCount()" id="c{idx}">
              <span>{name}</span>
            </label>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  :root{{--bg:#0d1117;--bg2:#161b22;--bg3:#21262d;--border:#30363d;--text:#e6edf3;--text2:#8b949e;--teal:#1ed4a0;--danger:#f85149;}}
  *{{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}}
  body{{background:var(--bg);color:var(--text);min-height:100vh;}}
  header{{background:var(--bg2);border-bottom:1px solid var(--border);padding:18px 32px;display:flex;align-items:center;gap:20px;}}
  .logo{{font-size:20px;font-weight:800;color:var(--teal);letter-spacing:-0.5px;}}
  .header-info{{flex:1;}}
  h1{{font-size:17px;font-weight:700;}}
  .sub{{font-size:12px;color:var(--text2);margin-top:2px;}}
  .badge{{background:var(--bg3);border:1px solid var(--border);border-radius:20px;padding:4px 14px;font-size:12px;color:var(--text2);}}
  #count-badge{{color:var(--teal);font-weight:700;}}
  .toolbar{{padding:14px 32px;display:flex;gap:10px;align-items:center;background:var(--bg2);border-bottom:1px solid var(--border);}}
  .btn{{background:var(--teal);color:#03261c;border:none;border-radius:10px;padding:8px 18px;font-size:13px;font-weight:700;cursor:pointer;}}
  .btn:hover{{background:#2de0b6;}}
  .btn-ghost{{background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:10px;padding:7px 16px;font-size:13px;font-weight:600;cursor:pointer;}}
  .btn-ghost:hover{{background:#2d333b;}}
  #sel-count{{font-size:13px;color:var(--text2);}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;padding:24px 32px;}}
  .thumb{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;transition:border-color .15s;}}
  .thumb.selected{{border-color:var(--teal);box-shadow:0 0 0 2px rgba(30,212,160,.25);}}
  .wm-wrap{{position:relative;overflow:hidden;}}
  .wm-wrap img{{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;cursor:zoom-in;transition:opacity .15s;}}
  .wm-wrap img:hover{{opacity:.92;}}
  .wm{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;
    font-size:14px;font-weight:800;color:rgba(255,255,255,.18);letter-spacing:1px;
    transform:rotate(-30deg);text-align:center;line-height:1.8;user-select:none;}}
  .caption{{padding:8px 12px;}}
  .chk-wrap{{display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;color:var(--text2);}}
  .chk-wrap input{{accent-color:var(--teal);width:16px;height:16px;cursor:pointer;}}
  .chk-wrap span{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px;}}
  /* Modal */
  #modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:100;align-items:center;justify-content:center;}}
  #modal.open{{display:flex;}}
  #modal img{{max-width:92vw;max-height:88vh;border-radius:8px;box-shadow:0 8px 40px rgba(0,0,0,.6);}}
  #modal-name{{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);color:#ccc;font-size:13px;background:rgba(0,0,0,.6);padding:6px 16px;border-radius:20px;}}
  #modal-close{{position:fixed;top:20px;right:28px;color:#ccc;font-size:32px;cursor:pointer;line-height:1;}}
  @media print{{header,#modal,.toolbar{{display:none!important;}} body{{background:#fff;color:#000;}} .wm{{color:rgba(0,0,0,.08);}} .thumb{{border:1px solid #ddd;}} }}
</style>
</head>
<body>
<header>
  <div class="header-info">
    <h1 class="logo">AGENTE FOTOS</h1>
    <h1>{title}</h1>
    {f'<div class="sub">{info_str}</div>' if info_str else ''}
  </div>
  <div class="badge">{n} foto(s)</div>
  <div class="badge" id="count-badge">0 aprovadas</div>
</header>
<div class="toolbar">
  <button class="btn" onclick="selectAll()">Selecionar todas</button>
  <button class="btn-ghost" onclick="clearAll()">Limpar seleção</button>
  <button class="btn-ghost" onclick="printApproved()">Imprimir aprovadas</button>
  <button class="btn-ghost" onclick="copyList()">Copiar lista</button>
  <span id="sel-count"></span>
</div>
<div class="grid" id="grid">{thumb_items}
</div>
<div id="modal" onclick="closeModal()">
  <img id="modal-img" src="" alt="">
  <div id="modal-name"></div>
  <div id="modal-close">✕</div>
</div>
<script>
function updateCount(){{
  const checked = document.querySelectorAll('input[type=checkbox]:checked');
  const n = checked.length;
  document.getElementById('count-badge').textContent = n + ' aprovada'+(n===1?'':'s');
  document.querySelectorAll('.thumb').forEach((t,i)=>{{
    t.classList.toggle('selected', document.getElementById('c'+i)?.checked||false);
  }});
}}
function selectAll(){{document.querySelectorAll('input[type=checkbox]').forEach(c=>c.checked=true);updateCount();}}
function clearAll(){{document.querySelectorAll('input[type=checkbox]').forEach(c=>c.checked=false);updateCount();}}
function getApproved(){{
  const names=[];
  document.querySelectorAll('input[type=checkbox]:checked').forEach(c=>{{
    names.push(c.nextElementSibling?.textContent||c.id);
  }});
  return names;
}}
function printApproved(){{
  const names=getApproved();
  if(!names.length){{alert('Nenhuma foto selecionada.');return;}}
  window.print();
}}
function copyList(){{
  const names=getApproved();
  if(!names.length){{alert('Nenhuma foto selecionada.');return;}}
  navigator.clipboard.writeText(names.join('\\n')).then(()=>alert('Lista copiada: '+names.length+' foto(s)'));
}}
function zoom(src,name){{
  document.getElementById('modal-img').src=src;
  document.getElementById('modal-name').textContent=name;
  document.getElementById('modal').classList.add('open');
}}
function closeModal(){{document.getElementById('modal').classList.remove('open');}}
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeModal();}});
</script>
</body>
</html>"""

    Path(output_html).write_text(html, encoding="utf-8")
    return output_html
