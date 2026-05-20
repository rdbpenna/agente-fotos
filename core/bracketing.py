"""
Bracketing / HDR imobiliário.

Fluxo esperado:
- Detecta grupos de 3 ou 5 fotos da pasta de entrada.
- Quando houver RAW/CR3, usa o RAW original na fusão, não apenas o JPEG temporário.
- Gera 1 arquivo *_HDR.jpg por grupo.
- Preset "imobiliario_claro" tenta chegar no estilo comercial enviado como referência:
  interior claro, sombras abertas, highlights moderados e contraste recolocado.
"""

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Any

import cv2
import numpy as np
from PIL import Image, ExifTags

from core.raw_support import is_raw_file, read_raw_rgb


@dataclass(slots=True)
class BracketCandidate:
    path: str
    filename: str
    width: int
    height: int
    timestamp: datetime | None
    exposure_bias: float | None
    brightness: float


@dataclass(slots=True)
class BracketItem:
    filename: str
    source_path: str
    base_source: str
    source_paths: list[str]
    is_bracket: bool
    log: list[str]


@dataclass(slots=True)
class HdrPreset:
    exposure: float = 1.0
    contrast: float = 1.0
    highlights: float = 0.0
    shadows: float = 0.0
    whites: float = 0.0
    blacks: float = 0.0
    vibrance: float = 1.0
    clarity: float = 0.0
    lens_strength: float = 0.0
    geometry: bool = False
    chromatic: bool = True


PRESETS: dict[str, HdrPreset] = {
    "natural": HdrPreset(exposure=1.01, contrast=1.04, highlights=0.14, shadows=0.14, vibrance=1.02, clarity=0.04, chromatic=True),
    "janela_preservada": HdrPreset(exposure=1.00, contrast=1.05, highlights=0.38, shadows=0.16, whites=0.005, blacks=-0.03, vibrance=1.02, clarity=0.04, chromatic=True),
    "interior_claro": HdrPreset(exposure=1.06, contrast=1.06, highlights=0.20, shadows=0.22, whites=0.02, blacks=-0.05, vibrance=1.03, clarity=0.06, chromatic=True),
    "luxury_suave": HdrPreset(exposure=1.03, contrast=1.08, highlights=0.20, shadows=0.22, whites=0.01, blacks=-0.06, vibrance=1.05, clarity=0.08, lens_strength=0.006, geometry=True, chromatic=True),
    "lightroom_like": HdrPreset(exposure=1.02, contrast=1.12, highlights=0.30, shadows=0.10, whites=0.01, blacks=-0.10, vibrance=1.06, clarity=0.08, lens_strength=0.006, geometry=True, chromatic=True),
    "imobiliario_claro": HdrPreset(exposure=1.06, contrast=1.05, highlights=0.20, shadows=0.14, whites=0.00, blacks=-0.03, vibrance=1.10, clarity=0.09, lens_strength=0.006, geometry=True, chromatic=True),
}


class BracketingProcessor:
    def __init__(
        self,
        group_size: str | int = "auto",
        fusion_preset: str = "imobiliario_claro",
        max_time_gap_seconds: float = 10.0,
        auto_chromatic_aberration: bool = True,
        auto_lens_correction: bool = True,
        auto_geometry_correction: bool = True,
        profile_path: str | None = None,
        skip_lightroom_finish: bool = False,
    ):
        self.group_size = self._normalize_group_size(group_size)
        self.fusion_preset = self._normalize_preset(fusion_preset)
        self.max_time_gap_seconds = float(max_time_gap_seconds)
        self.auto_chromatic_aberration = bool(auto_chromatic_aberration)
        self.auto_lens_correction = bool(auto_lens_correction)
        self.auto_geometry_correction = bool(auto_geometry_correction)
        self.trained_profile = self._load_trained_profile(profile_path)
        self.skip_lightroom_finish = bool(skip_lightroom_finish)
        if self.trained_profile:
            self.fusion_preset = self._normalize_preset(self.trained_profile.get("base_preset", self.fusion_preset))

    def build_items(
        self,
        image_paths: list[str],
        fused_dir: str,
        original_path_map: dict[str, str] | None = None,
    ) -> list[BracketItem]:
        """Retorna itens finais. Grupos viram um único *_HDR.jpg."""
        os.makedirs(fused_dir, exist_ok=True)
        original_path_map = original_path_map or {}
        candidates = [self._read_candidate(p) for p in image_paths]
        groups = self.detect_groups(candidates)

        items: list[BracketItem] = []
        for group in groups:
            if len(group) == 1:
                c = group[0]
                real_source = original_path_map.get(c.path, c.path)
                items.append(BracketItem(
                    filename=c.filename,
                    source_path=c.path,
                    base_source=real_source,
                    source_paths=[real_source],
                    is_bracket=False,
                    log=[],
                ))
                continue

            ordered_group = self._order_exposures(group)
            base = self._select_base_exposure(ordered_group)
            output_name = self._make_output_name(ordered_group, base)
            fused_path = os.path.join(fused_dir, output_name)
            # fusion usa os JEPGs do cache (já com diferenças de exposição preservadas)
            fusion_inputs = [c.path for c in ordered_group]
            # source_paths rastreia os originais (CR3 ou JPEG se não houver RAW)
            source_paths_originals = [original_path_map.get(c.path, c.path) for c in ordered_group]
            base_source = original_path_map.get(base.path, base.path)

            log = self.fuse_group(fusion_inputs, fused_path)
            evs = ["?" if c.exposure_bias is None else f"{c.exposure_bias:+.1f}EV" for c in ordered_group]
            log.insert(0, f"Bracketing: exposições ordenadas ({', '.join(evs)})")
            log.insert(1, f"Bracketing: grupo fusionado: {', '.join(os.path.basename(p) for p in fusion_inputs)}")
            items.append(BracketItem(
                filename=output_name,
                source_path=fused_path,
                base_source=base_source,
                source_paths=source_paths_originals,
                is_bracket=True,
                log=log,
            ))
        return items

    def detect_groups(self, candidates: list[BracketCandidate]) -> list[list[BracketCandidate]]:
        ordered = sorted(candidates, key=self._sort_key)
        groups: list[list[BracketCandidate]] = []

        if isinstance(self.group_size, int):
            size = self.group_size
            i = 0
            while i < len(ordered):
                chunk = ordered[i : i + size]
                if len(chunk) == size and self._is_sequential_manual_group(chunk):
                    groups.append(chunk)
                    i += size
                else:
                    groups.append([ordered[i]])
                    i += 1
            return groups

        i = 0
        while i < len(ordered):
            matched: list[BracketCandidate] | None = None
            for size in (5, 3):
                chunk = ordered[i : i + size]
                if len(chunk) == size and self._is_valid_group(chunk, strict=False):
                    matched = chunk
                    break
            if matched:
                groups.append(matched)
                i += len(matched)
            else:
                groups.append([ordered[i]])
                i += 1
        return groups

    def fuse_group(self, image_paths: list[str], output_path: str) -> list[str]:
        log: list[str] = []
        path_img: list[tuple[str, np.ndarray]] = []
        target_size: tuple[int, int] | None = None

        # Lê cada arquivo uma única vez (RAW em half_size para velocidade)
        for path in image_paths:
            img = self._read_bgr_for_fusion(path)
            if img is None:
                log.append(f"Bracketing: erro ao ler {os.path.basename(path)}")
                continue
            if target_size is None:
                target_size = (img.shape[1], img.shape[0])
            elif (img.shape[1], img.shape[0]) != target_size:
                img = cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)
            path_img.append((path, img))

        if not path_img:
            raise ValueError("Bracketing: nenhuma imagem válida para fusão")
        if len(path_img) == 1:
            cv2.imwrite(output_path, path_img[0][1], [cv2.IMWRITE_JPEG_QUALITY, 98])
            log.append("Bracketing: apenas 1 imagem válida; fusão ignorada")
            return log

        # Ordena por brilho médio (escuro → médio → claro)
        path_img.sort(key=lambda pi: float(np.mean(cv2.cvtColor(pi[1], cv2.COLOR_BGR2GRAY))))
        images = [img for _, img in path_img]
        log.append("Bracketing: exposições ordenadas por brilho")

        # Alinhamento MTB antes de qualquer escala (funciona melhor nos originais)
        aligned = list(images)
        try:
            aligner = cv2.createAlignMTB()
            aligner.process(images, aligned)
            log.append("Bracketing: alinhamento MTB aplicado")
        except Exception:
            aligned = [img.copy() for img in images]

        base_img = aligned[len(aligned) // 2].copy()
        log.append(f"Bracketing: usando {len(aligned)} exposições reais do bracket")

        # Salva dark original ANTES da escala — usado para computar máscara de janela.
        # No shot -2EV não escalado, interior (~10-40/255) e janelas (~80-182/255)
        # ficam bem separados. Após escala proporcional, as paredes claras sobem e
        # confundem o threshold com janelas.
        dark_unscaled = aligned[0].copy()

        # Escala proporcional: todos os shots pelo mesmo fator baseado no shot médio.
        mid_img = aligned[len(aligned) // 2]
        mid_mean = float(np.mean(cv2.cvtColor(mid_img, cv2.COLOR_BGR2GRAY)))
        if mid_mean > 1.0:
            prop_scale = 135.0 / mid_mean
            scaled = []
            for img in aligned:
                scaled.append(np.clip(img.astype(np.float32) * prop_scale, 0, 255).astype(np.uint8))
            aligned = scaled
            log.append(f"Bracketing: escala proporcional ×{prop_scale:.2f} aplicada (mid→135)")

        # Fusão por máscara de luminosidade para grupos de 3 (padrão real estate):
        # base = shot claro (+2EV), janelas recuperadas do shot escuro (-2EV).
        if len(aligned) == 3:
            fused = self._luminosity_blend_hdr(*aligned, dark_unscaled=dark_unscaled)
            fused = self._real_estate_hdr_finish(fused, aligned, base_img)
            log.append("Bracketing: fusão por máscara de luminosidade aplicada")
        else:
            # Fallback MergeMertens para grupos de 5 ou tamanho inesperado
            n = len(aligned)
            t_dark, t_bright = 60, 190
            targets = [int(t_dark + (t_bright - t_dark) * i / (n - 1)) for i in range(n)]
            valid_images = []
            for img, tgt in zip(aligned, targets):
                mv = float(np.mean(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)))
                if mv < 2:
                    continue
                scale = float(np.clip(tgt / mv, 0.1, 10.0))
                valid_images.append(np.clip(img.astype(np.float32) * scale, 0, 255).astype(np.uint8))
            if not valid_images:
                raise ValueError("Bracketing: todos os shots são inválidos após normalização")
            try:
                merge = cv2.createMergeMertens(contrast_weight=1.0, saturation_weight=1.0, exposure_weight=1.0)
                fused_float = merge.process(valid_images)
                fused = np.clip(fused_float * 255.0, 0, 255).astype("uint8")
                log.append("Bracketing: fusão MergeMertens aplicada")
            except Exception as exc:
                fused = self._fallback_weighted_fusion(valid_images)
                log.append(f"Bracketing: MergeMertens falhou; fusão ponderada ({exc})")
            fused = self._real_estate_hdr_finish(fused, valid_images, base_img)

        if not self.skip_lightroom_finish:
            fused, post_log = self._apply_lightroom_pipeline(fused)
            log.extend(post_log)
        else:
            log.append("HDR pós-merge: lightroom pipeline ignorado (StyledEnhancer aplicará depois)")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, fused, [cv2.IMWRITE_JPEG_QUALITY, 98])
        log.append(f"Bracketing: fusão final salva em {os.path.basename(output_path)}")
        return log

    def _is_sequential_manual_group(self, group: list[BracketCandidate]) -> bool:
        if len(group) not in (3, 5):
            return False
        first = group[0]
        if first.width and first.height:
            for c in group[1:]:
                if c.width and c.height and (c.width, c.height) != (first.width, first.height):
                    return False
        if self._timestamps_available(group):
            stamps = [c.timestamp for c in group if c.timestamp]
            span = (max(stamps) - min(stamps)).total_seconds()
            if span > max(self.max_time_gap_seconds * 3, 30.0):
                return False
        return True

    def _is_valid_group(self, group: list[BracketCandidate], strict: bool = False) -> bool:
        if len(group) not in (3, 5):
            return False
        first = group[0]
        same_resolution = all((c.width, c.height) == (first.width, first.height) for c in group)
        if not same_resolution:
            return False
        if self._timestamps_available(group):
            stamps = [c.timestamp for c in group if c.timestamp]
            span = (max(stamps) - min(stamps)).total_seconds()
            if span > self.max_time_gap_seconds:
                return False
        brightness_range = max(c.brightness for c in group) - min(c.brightness for c in group)
        if brightness_range >= (9 if strict else 14):
            return True
        exposure_values = [c.exposure_bias for c in group if c.exposure_bias is not None]
        if len(exposure_values) >= 2 and (max(exposure_values) - min(exposure_values)) >= 0.55:
            return True
        return strict

    @staticmethod
    def _timestamps_available(group: list[BracketCandidate]) -> bool:
        return all(c.timestamp is not None for c in group)

    @staticmethod
    def _sort_key(c: BracketCandidate):
        return (c.timestamp or datetime.min, _natural_sort_key(c.filename))

    @staticmethod
    def _normalize_group_size(value: str | int) -> str | int:
        if isinstance(value, int) and value in (3, 5):
            return value
        text = str(value or "auto").strip().lower()
        if text in {"3", "3 fotos", "3x"}:
            return 3
        if text in {"5", "5 fotos", "5x"}:
            return 5
        return "auto"

    @staticmethod
    def _normalize_preset(value: str) -> str:
        text = str(value or "imobiliario_claro").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "natural": "natural",
            "janela": "janela_preservada",
            "janela_preservada": "janela_preservada",
            "interior": "interior_claro",
            "interior_claro": "interior_claro",
            "luxury": "luxury_suave",
            "luxury_suave": "luxury_suave",
            "lightroom": "lightroom_like",
            "lightroom_like": "lightroom_like",
            "lr": "lightroom_like",
            "lr_like": "lightroom_like",
            "imobiliario": "imobiliario_claro",
            "imobiliario_claro": "imobiliario_claro",
            "imob_claro": "imobiliario_claro",
            "real_estate_bright": "imobiliario_claro",
            "bright": "imobiliario_claro",
        }
        return aliases.get(text, "imobiliario_claro")

    @staticmethod
    def _select_base_exposure(group: list[BracketCandidate]) -> BracketCandidate:
        with_bias = [c for c in group if c.exposure_bias is not None]
        if with_bias:
            return min(with_bias, key=lambda c: abs(c.exposure_bias or 0.0))
        ordered = sorted(group, key=lambda c: c.brightness)
        return ordered[len(ordered) // 2]

    @staticmethod
    def _order_exposures(group: list[BracketCandidate]) -> list[BracketCandidate]:
        if any(c.exposure_bias is not None for c in group):
            return sorted(group, key=lambda c: c.exposure_bias if c.exposure_bias is not None else c.brightness)
        return sorted(group, key=lambda c: c.brightness)

    @staticmethod
    def _make_output_name(group: list[BracketCandidate], base: BracketCandidate) -> str:
        base_name = os.path.splitext(base.filename)[0]
        base_name = re.sub(r"(_CR3_exp|_RAW_exp|_CR3|_RAW)$", "", base_name, flags=re.IGNORECASE)
        return f"{base_name}_HDR.jpg"

    def _read_candidate(self, path: str) -> BracketCandidate:
        filename = os.path.basename(path)
        width = height = 0
        timestamp = None
        exposure_bias = None
        brightness = 0.0
        try:
            with Image.open(path) as im:
                width, height = im.size
                exif = im.getexif()
                timestamp = _read_exif_datetime(exif)
                exposure_bias = _read_exif_exposure_bias(exif)
        except Exception:
            pass
        try:
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                if max(img.shape[:2]) > 700:
                    scale = 700.0 / max(img.shape[:2])
                    img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                brightness = float(np.mean(img))
                if width == 0 or height == 0:
                    height, width = img.shape[:2]
        except Exception:
            pass
        return BracketCandidate(path, filename, width, height, timestamp, exposure_bias, brightness)

    @staticmethod
    def _read_bgr_for_fusion(path: str) -> np.ndarray | None:
        try:
            if is_raw_file(path):
                # no_auto_bright=True preserva diferenças de exposição entre shots do bracket
                # half_size=True: 4x mais rápido, qualidade suficiente para fusão HDR
                rgb = read_raw_rgb(path, half_size=True, no_auto_bright=True)
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            return cv2.imread(path, cv2.IMREAD_COLOR)
        except Exception:
            return None

    def _real_estate_hdr_finish(self, fused: np.ndarray, aligned: list[np.ndarray], base_img: np.ndarray) -> np.ndarray:
        """
        Pós-processamento da fusão Mertens para o look "real estate":
        1) Levels stretch baseado em percentis (recupera pretos verdadeiros e brancos verdadeiros
           sem clipar — Mertens tende a deixar o histograma comprimido).
        2) Curva gamma suave para subir mid-tones até o alvo de interior (~120 de mean) sem
           queimar as luzes altas (janelas) — usa gamma menor que 1.
        3) CLAHE leve apenas para microcontraste local; clipLimit baixo para evitar look chapado.
        """
        lab = cv2.cvtColor(fused, cv2.COLOR_BGR2LAB).astype(np.float32)
        l = lab[:, :, 0] / 255.0

        # 1) Levels stretch com headroom de 10%: mapeia [p0.5, p99.5] → [0, 0.90].
        # O teto de 0.90 (não 1.0) preserva espaço para que exposure/whites/gamma
        # subsequentes não clipem as janelas — pixels de janela ficam em ~230/255
        # em vez de 255. Sem headroom, p99.7→1.0 + exposure 1.05 = janelas queimadas.
        p_low = float(np.percentile(l, 0.5))
        p_high = float(np.percentile(l, 99.5))
        if p_high - p_low > 0.20:
            l = np.clip((l - p_low) / (p_high - p_low) * 0.90, 0.0, 1.0)

        # 2) Gamma para abrir mid-tones (gamma < 1 clareia sem ferrar luzes).
        # Adaptativo: se mean já está alto, gamma fica mais próximo de 1.
        cur_mean = float(np.mean(l))
        target = 0.56  # alvo mais alto compatível com base no shot claro (+2EV)
        if cur_mean > 0.01:
            # gamma = log(target) / log(cur_mean), mas limitado para evitar exagero
            gamma = float(np.clip(np.log(max(target, 1e-3)) / np.log(max(cur_mean, 1e-3)), 0.70, 1.10))
            l = np.power(l, gamma)

        # 3) CLAHE leve para microcontraste — clipLimit baixo para não introduzir halos.
        l8 = np.clip(l * 255.0, 0, 255).astype(np.uint8)
        clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l8).astype(np.float32) / 255.0
        # Blend para suavizar — CLAHE puro pode chapar
        l = np.clip(l * 0.70 + l_clahe * 0.30, 0.0, 1.0)

        lab[:, :, 0] = np.clip(l * 255.0, 0, 255)
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

    @staticmethod
    def _luminosity_blend_hdr(dark: np.ndarray, mid: np.ndarray, bright: np.ndarray, *, dark_unscaled: np.ndarray | None = None) -> np.ndarray:
        """
        Fusão HDR real-estate: shot claro (+2EV) como base (interior bem iluminado),
        janelas recuperadas do shot escuro (-2EV).

        dark_unscaled: shot -2EV ANTES da escala proporcional. Usar para a máscara
        de janelas é crítico — depois da escala ×3.4 as paredes claras sobem para o
        mesmo range que as janelas, corrompendo o threshold. No -2EV original,
        interior ≈ 0.08-0.16 e janelas ≈ 0.31-0.71, ficam bem separados.
        """
        d = dark.astype(np.float32) / 255.0
        b = bright.astype(np.float32) / 255.0

        # Máscara a partir do dark NÃO escalado — thresholds confiáveis
        dark_for_mask = dark_unscaled if dark_unscaled is not None else dark
        d_gray_mask = cv2.cvtColor(dark_for_mask, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

        # d_gray escalado: usado para calcular dark_scale (valor real dos pixels na blend)
        d_gray = cv2.cvtColor(dark, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

        # Limiares a partir do dark não escalado: interior vs janela bem separados
        d_interior_p75 = float(np.percentile(d_gray_mask, 75))
        win_lo = float(np.clip(d_interior_p75 * 1.6, 0.28, 0.55))
        win_hi = float(np.clip(d_interior_p75 * 2.8, 0.45, 0.80))
        window_mask = _smoothstep(d_gray_mask, win_lo, win_hi)[:, :, None]

        # dark_scale baseado nos pixels de janela do dark ESCALADO → resultado ~55%
        d_win_pixels = d_gray[d_gray_mask > win_lo]
        d_win_mean = float(np.mean(d_win_pixels)) if len(d_win_pixels) > 200 else float(np.mean(d_gray))
        dark_scale = float(np.clip(0.55 / max(d_win_mean, 0.01), 0.3, 2.5))
        d_scaled = np.clip(d * dark_scale, 0, 1)

        # Blend em LAB: luminância gradual (detalhe suave), cor dura (sem franja).
        # Misturar cores quentes (interior) com frias (exterior) na transição causa
        # franja azul/roxa — separar os canais elimina isso.
        lab_b = cv2.cvtColor(np.clip(b * 255, 0, 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
        lab_d = cv2.cvtColor(np.clip(d_scaled * 255, 0, 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)

        # window_mask tem shape (H,W,1) — reduz para (H,W) para os canais LAB
        wm = window_mask[:, :, 0]

        # L: transição gradual (preserva detalhe na borda)
        l_blend = lab_b[:, :, 0] * (1 - wm) + lab_d[:, :, 0] * wm

        # A, B: transição dura com pequeno blur — cor não mistura, sem franja
        hard = (wm > 0.5).astype(np.float32)
        hard = cv2.GaussianBlur(hard, (7, 7), 2.0)
        a_blend = lab_b[:, :, 1] * (1 - hard) + lab_d[:, :, 1] * hard
        b_blend = lab_b[:, :, 2] * (1 - hard) + lab_d[:, :, 2] * hard

        result_lab = np.stack([l_blend, a_blend, b_blend], axis=2)
        return cv2.cvtColor(np.clip(result_lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)

    @staticmethod
    def _fallback_weighted_fusion(images: list[np.ndarray]) -> np.ndarray:
        arr = np.stack([img.astype(np.float32) for img in images], axis=0)
        gray = np.stack([cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) for img in images], axis=0)
        weights = 1.0 - np.abs(gray - 128.0) / 128.0
        weights = np.clip(weights, 0.05, 1.0)[..., None]
        fused = (arr * weights).sum(axis=0) / np.maximum(weights.sum(axis=0), 1e-6)
        return np.clip(fused, 0, 255).astype(np.uint8)

    def _apply_lightroom_pipeline(self, img: np.ndarray) -> tuple[np.ndarray, list[str]]:
        preset = PRESETS.get(self.fusion_preset, PRESETS["imobiliario_claro"])
        log: list[str] = []
        out = self._white_balance_gray_world(img.copy())
        log.append("HDR pós-merge: white balance automático aplicado")
        # Warm sutil após WB — _real_estate_hdr_finish já fez o blend; manter força baixa
        out = self._warm_interiors(out, 0.018 if self.fusion_preset != "janela_preservada" else 0.010)
        log.append("HDR pós-merge: balanço quente/neutro aplicado")
        out = self._exposure_contrast(out, preset.exposure, preset.contrast, preset.whites, preset.blacks)
        log.append("HDR pós-merge: exposure/contrast/whites/blacks ajustados")
        out = self._highlights_shadows(out, preset.highlights, preset.shadows)
        log.append("HDR pós-merge: highlights e shadows ajustados")
        # _recover_levels_and_dehaze omitido: _real_estate_hdr_finish já aplicou CLAHE
        if self.auto_chromatic_aberration and preset.chromatic and max(out.shape[:2]) <= 3200:
            out = self._reduce_chromatic_aberration(out)
            log.append("HDR pós-merge: aberração cromática reduzida")
        if self.auto_lens_correction and preset.lens_strength > 0 and max(out.shape[:2]) <= 3200:
            out = self._correct_lens_distortion(out, preset.lens_strength)
            log.append("HDR pós-merge: distorção de lente corrigida suavemente")
        out = self._vibrance(out, preset.vibrance)
        out = self._clarity(out, min(preset.clarity, 0.08))
        log.append("HDR pós-merge: vibrance e clareza aplicados")
        if self.trained_profile:
            out = self._apply_trained_profile(out, self.trained_profile)
            log.append("HDR pós-merge: perfil HDR treinado aplicado")
        log.append(f"HDR pós-merge: preset usado = {self.fusion_preset}")
        return out, log

    @staticmethod
    def _load_trained_profile(profile_path: str | None) -> dict | None:
        """Carrega apenas perfis HDR treinados; ignora perfis de estilo normal."""
        if not profile_path or not os.path.exists(profile_path):
            return None
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("type") == "hdr_bracketing_profile":
                return data
        except Exception:
            return None
        return None

    @staticmethod
    def _apply_trained_profile(img: np.ndarray, profile: dict) -> np.ndarray:
        corr = profile.get("corrections") or {}
        out = img.copy()

        # Corrige luminosidade/contraste no L* para aproximar do padrão do fotógrafo.
        lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB).astype(np.float32)
        l = lab[:, :, 0] / 255.0
        mean = float(np.mean(l))
        std = float(np.std(l))
        l = (l - mean) * float(corr.get("l_std_ratio", 1.0)) + mean + float(corr.get("l_mean_delta", 0.0))
        l = np.clip(l, 0, 1)
        lab[:, :, 0] = l * 255.0

        # Ajuste de warmth/tint aprendido.
        lab[:, :, 1] = np.clip(lab[:, :, 1] + float(corr.get("a_delta", 0.0)) * 128.0, 0, 255)
        lab[:, :, 2] = np.clip(lab[:, :, 2] + float(corr.get("b_delta", 0.0)) * 128.0, 0, 255)
        out = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

        # Saturação/vibrance aprendido, com limites seguros.
        sat_ratio = float(np.clip(corr.get("sat_ratio", 1.0), 0.75, 1.35))
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat_ratio, 0, 255)
        out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        return out

    @staticmethod
    def _white_balance_gray_world(img: np.ndarray) -> np.ndarray:
        arr = img.astype(np.float32)
        means = arr.reshape(-1, 3).mean(axis=0)
        target = float(np.mean(means))
        scales = target / np.maximum(means, 1.0)
        scales = np.clip(scales, 0.88, 1.14)
        arr *= scales.reshape(1, 1, 3)
        return np.clip(arr, 0, 255).astype(np.uint8)

    @staticmethod
    def _warm_interiors(img: np.ndarray, strength: float = 0.03) -> np.ndarray:
        strength = float(np.clip(strength, 0.0, 0.08))
        if strength <= 0:
            return img
        arr = img.astype(np.float32) / 255.0
        arr[:, :, 0] *= (1.0 - strength * 0.55)
        arr[:, :, 2] *= (1.0 + strength)
        arr[:, :, 1] *= (1.0 + strength * 0.18)
        return np.clip(arr * 255.0, 0, 255).astype(np.uint8)

    @staticmethod
    def _recover_levels_and_dehaze(img: np.ndarray, light: bool = False) -> np.ndarray:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l = lab[:, :, 0] / 255.0
        p_low = 0.4 if light else 0.8
        p_high = 99.8 if light else 99.6
        low = float(np.percentile(l, p_low))
        high = float(np.percentile(l, p_high))
        if high - low > 0.08:
            l = np.clip((l - low) / (high - low), 0, 1)
        black = 0.020 if light else 0.035
        l = np.clip((l - black) / max(1.0 - black, 1e-6), 0, 1)
        l8 = np.clip(l * 255.0, 0, 255).astype(np.uint8)
        clahe = cv2.createCLAHE(clipLimit=1.10 if light else 1.25, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l8).astype(np.float32) / 255.0
        blend = 0.12 if light else 0.22
        l = np.clip(l * (1.0 - blend) + l_clahe * blend, 0, 1)
        lab[:, :, 0] = np.clip(l * 255.0, 0, 255)
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

    @staticmethod
    def _exposure_contrast(img: np.ndarray, exposure: float, contrast: float, whites: float, blacks: float) -> np.ndarray:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l = lab[:, :, 0] / 255.0
        l = np.clip(l * exposure, 0, 1)
        # Contrast pivot na média atual (não em 0.5 fixo): evita escurecer/esticar de modo
        # arbitrário quando a imagem já está num ponto de exposição diferente. Isso impede
        # que o contraste "engula" a faixa dinâmica recém-recuperada pelo levels stretch.
        pivot = float(np.clip(np.mean(l), 0.30, 0.60))
        l = np.clip((l - pivot) * contrast + pivot, 0, 1)
        if whites:
            # Empurra brancos para cima (positivo) — extende o topo, recupera "punch" real.
            high = _smoothstep(l, 0.70, 1.00)
            l = np.clip(l + whites * high * (1.0 - l) * 1.6, 0, 1)
        if blacks:
            # blacks negativo cava sombras (recupera pretos verdadeiros).
            low = 1.0 - _smoothstep(l, 0.00, 0.30)
            l = np.clip(l + blacks * low * l * 1.4, 0, 1)
        lab[:, :, 0] = np.clip(l * 255.0, 0, 255)
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

    @staticmethod
    def _highlights_shadows(img: np.ndarray, highlights: float, shadows: float) -> np.ndarray:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l = lab[:, :, 0] / 255.0
        # Máscaras mais centradas: shadows só atua bem em baixo, highlights só no alto.
        # Importante: highlight_mask vai a 0 perto de 1.0 para NÃO puxar o branco para baixo
        # (era a causa principal do look "lavado"/sem brancos verdadeiros).
        shadow_mask = 1.0 - _smoothstep(l, 0.10, 0.45)
        # Highlight mask em forma de "sino" entre 0.62 e 0.95 — vai pro chão de novo perto de 1.0,
        # preservando o branco verdadeiro nas janelas.
        rise = _smoothstep(l, 0.62, 0.82)
        fall = 1.0 - _smoothstep(l, 0.88, 0.98)
        highlight_mask = np.clip(rise * fall, 0.0, 1.0)
        if shadows > 0:
            l = l + shadows * (1.0 - l) * shadow_mask
        if highlights > 0:
            # Coef reduzido de 0.58 para 0.30: pull mais suave.
            # Usa (1 - l) também para evitar mexer demais no que já está perto do topo.
            l = l - highlights * highlight_mask * 0.30 * (1.0 - l) * 1.4
        lab[:, :, 0] = np.clip(l * 255.0, 0, 255)
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

    @staticmethod
    def _vibrance(img: np.ndarray, factor: float) -> np.ndarray:
        if abs(factor - 1.0) < 0.01:
            return img
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        s = hsv[:, :, 1]
        boost = 1.0 + (factor - 1.0) * (1.0 - s / 255.0)
        hsv[:, :, 1] = np.clip(s * boost, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    @staticmethod
    def _clarity(img: np.ndarray, strength: float) -> np.ndarray:
        strength = float(np.clip(strength, 0, 0.25))
        if strength <= 0:
            return img
        blur = cv2.GaussianBlur(img, (0, 0), sigmaX=2.2)
        return cv2.addWeighted(img, 1.0 + strength, blur, -strength, 0)

    @staticmethod
    def _reduce_chromatic_aberration(img: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        l, a, b = cv2.split(lab)
        gray = l.astype(np.uint8)
        edges = cv2.Canny(gray, 60, 150)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1).astype(bool)
        chroma = np.sqrt((a - 128.0) ** 2 + (b - 128.0) ** 2)
        fringe = edges & (chroma > 16)
        if np.any(fringe):
            a_blur = cv2.medianBlur(a.astype(np.uint8), 3).astype(np.float32)
            b_blur = cv2.medianBlur(b.astype(np.uint8), 3).astype(np.float32)
            a[fringe] = 0.65 * a[fringe] + 0.35 * a_blur[fringe]
            b[fringe] = 0.65 * b[fringe] + 0.35 * b_blur[fringe]
        return cv2.cvtColor(cv2.merge([l, a, b]).astype(np.uint8), cv2.COLOR_LAB2BGR)

    @staticmethod
    def _correct_lens_distortion(img: np.ndarray, strength: float) -> np.ndarray:
        h, w = img.shape[:2]
        if w < 400 or h < 300:
            return img
        k = float(np.clip(strength, 0.0, 0.03))
        if k <= 0:
            return img
        camera = np.array([[w * 0.90, 0, w / 2], [0, w * 0.90, h / 2], [0, 0, 1]], dtype=np.float32)
        dist = np.array([-k, k * 0.25, 0, 0, 0], dtype=np.float32)
        new_camera, _ = cv2.getOptimalNewCameraMatrix(camera, dist, (w, h), 0.0, (w, h))
        return cv2.undistort(img, camera, dist, None, new_camera)


def _smoothstep(x: np.ndarray, edge0: float, edge1: float) -> np.ndarray:
    t = np.clip((x - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _natural_sort_key(text: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def _read_exif_datetime(exif) -> datetime | None:
    if not exif:
        return None
    tag_names = {v: k for k, v in ExifTags.TAGS.items()}
    for tag_name in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        tag = tag_names.get(tag_name)
        value = exif.get(tag) if tag else None
        if value:
            try:
                return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
            except ValueError:
                continue
    return None


def _read_exif_exposure_bias(exif) -> float | None:
    if not exif:
        return None
    tag_names = {v: k for k, v in ExifTags.TAGS.items()}
    tag = tag_names.get("ExposureBiasValue")
    if tag is None:
        return None
    value: Any = exif.get(tag)
    if value is None:
        return None
    try:
        if isinstance(value, tuple) and len(value) == 2 and value[1] != 0:
            return float(Fraction(value[0], value[1]))
        return float(value)
    except Exception:
        return None
