"""
Suporte a arquivos RAW (.CR3/.CR2/.NEF/.ARW/.DNG).

Usa rawpy/LibRaw quando disponível para gerar uma versão RGB/JPEG temporária
que pode ser usada pelo preview e pelo pipeline OpenCV/Pillow existente.

Atenção: .CR3 depende do suporte do LibRaw/rawpy para a câmera específica.
Quando não for possível revelar o RAW, o módulo tenta extrair o JPEG embutido
para preview. Para processamento final, o RAW precisa ser convertido para RGB/JPEG.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional

RAW_EXTENSIONS = {".cr3", ".cr2", ".nef", ".arw", ".dng", ".raf", ".rw2", ".orf"}


class RawSupportError(RuntimeError):
    pass


def is_raw_file(path: str | os.PathLike) -> bool:
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def rawpy_available() -> bool:
    try:
        import rawpy  # noqa: F401
        return True
    except Exception:
        return False


def _require_rawpy():
    try:
        import rawpy  # type: ignore
        return rawpy
    except Exception as exc:
        raise RawSupportError(
            "Arquivos RAW/CR3 precisam da dependência rawpy. "
            "Instale com: python -m pip install rawpy"
        ) from exc


def _postprocess(path: str, *, half_size: bool = False, no_auto_bright: bool = False):
    """Tenta revelar o RAW via LibRaw/rawpy e retorna numpy RGB uint8."""
    rawpy = _require_rawpy()
    try:
        with rawpy.imread(path) as raw:
            return raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=no_auto_bright,
                output_bps=8,
                half_size=half_size,
                bright=1.0,
            )
    except Exception as exc:
        raise RawSupportError(
            f"Não foi possível revelar o RAW/CR3: {os.path.basename(path)}. "
            "Verifique se o rawpy/LibRaw suporta essa câmera."
        ) from exc


def _extract_embedded_thumb(path: str):
    """Tenta extrair JPEG/bitmap embutido do RAW para preview rápido."""
    rawpy = _require_rawpy()
    try:
        with rawpy.imread(path) as raw:
            thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                from PIL import Image
                img = Image.open(io.BytesIO(thumb.data)).convert("RGB")
                import numpy as np
                return np.asarray(img, dtype=np.uint8)
            if thumb.format == rawpy.ThumbFormat.BITMAP:
                return thumb.data
    except Exception as exc:
        raise RawSupportError(
            f"Não foi possível extrair preview embutido do RAW/CR3: {os.path.basename(path)}"
        ) from exc
    raise RawSupportError(f"RAW/CR3 sem preview embutido legível: {os.path.basename(path)}")


def read_raw_rgb(path: str, *, half_size: bool = False, no_auto_bright: bool = False):
    """Lê RAW e retorna numpy array RGB uint8 para processamento final."""
    return _postprocess(path, half_size=half_size, no_auto_bright=no_auto_bright)


def read_raw_preview_rgb(path: str):
    """
    Lê RAW para preview/miniatura.
    Primeiro tenta revelar em half_size. Se falhar, tenta JPEG embutido.
    """
    try:
        return _postprocess(path, half_size=True)
    except RawSupportError:
        return _extract_embedded_thumb(path)


def darktable_available() -> bool:
    """Retorna True se o darktable-cli estiver instalado e acessível."""
    try:
        from core.raw_engine import RawEngine
        RawEngine()
        return True
    except Exception:
        return False


def convert_raw_to_jpeg(
    input_path: str,
    output_dir: str,
    *,
    suffix: str = "_RAW",
    quality: int = 96,
    preserve_exposure: bool = False,
) -> str:
    """
    Converte RAW para JPEG processável.

    preserve_exposure=True: desativa o auto-brightness do rawpy para manter
    as diferenças de exposição entre bracketing (-2EV / 0EV / +2EV).
    Use True quando o JPEG for entrada para fusão HDR.
    Use False (padrão) para conversão de exibição/preview.
    """
    from PIL import Image

    os.makedirs(output_dir, exist_ok=True)
    base = Path(input_path).stem
    # Sufixo diferente por modo para evitar cache cruzado
    cache_suffix = f"{suffix}_exp" if preserve_exposure else suffix
    out = os.path.join(output_dir, f"{base}{cache_suffix}.jpg")

    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(input_path):
        return out

    # Quando preserve_exposure=True ignora Darktable (ele normaliza exposição)
    if not preserve_exposure:
        try:
            from core.raw_engine import RawEngine
            engine = RawEngine()
            engine.reveal_to_jpg(input_path, out, overwrite=True)
            return out
        except Exception:
            pass  # Darktable não disponível ou falhou — usa rawpy

    # rawpy / LibRaw
    rgb = read_raw_rgb(input_path, half_size=False, no_auto_bright=preserve_exposure)
    Image.fromarray(rgb).save(out, "JPEG", quality=quality, optimize=True)
    return out
