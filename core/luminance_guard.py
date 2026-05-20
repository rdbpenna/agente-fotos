"""
Proteção de luminância para evitar fotos imobiliárias estouradas.

A ideia é clarear sombras/meios-tons sem destruir detalhes em paredes,
tetos, armários brancos e janelas. Este módulo é usado tanto pelo enhancer
padrão quanto pelo enhancer treinado por estilo.
"""

from __future__ import annotations

import cv2
import numpy as np


def luminance_stats(img: np.ndarray) -> dict[str, float]:
    """Retorna métricas simples de brilho/clipping da imagem."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return {
        "mean": float(gray.mean()),
        "p95": float(np.percentile(gray, 95)),
        "p99": float(np.percentile(gray, 99)),
        "bright_pct": float(np.mean(gray >= 230) * 100.0),
        "near_clip_pct": float(np.mean(gray >= 245) * 100.0),
        "clip_pct": float(np.mean(gray >= 252) * 100.0),
        "shadow_pct": float(np.mean(gray <= 70) * 100.0),
    }


def scene_is_already_bright(stats: dict[str, float]) -> bool:
    """Detecta cenas que não devem receber exposição global positiva."""
    return (
        stats["mean"] >= 150
        or stats["bright_pct"] >= 12.0
        or stats["near_clip_pct"] >= 2.0
        or stats["p95"] >= 235
    )


def apply_shadow_lift(img: np.ndarray, strength: float = 16.0) -> np.ndarray:
    """
    Clareia sombras e meios-tons preservando altas-luzes.
    Funciona no canal L do LAB para evitar saturar cores.
    """
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    l = lab[:, :, 0]

    # Peso alto nas sombras, médio em meios-tons e quase zero nas altas-luzes.
    # Acima de ~200 a alteração fica praticamente nula.
    weight = np.clip((205.0 - l) / 205.0, 0.0, 1.0) ** 1.7
    l = l + strength * weight

    lab[:, :, 0] = np.clip(l, 0, 255)
    return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)


def compress_highlights(img: np.ndarray, start: int = 224, ratio: float = 0.42) -> np.ndarray:
    """Comprime altas-luzes de forma suave para segurar brancos."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    l = lab[:, :, 0]
    mask = l > start
    l[mask] = start + (l[mask] - start) * ratio
    lab[:, :, 0] = np.clip(l, 0, 255)
    return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)


def blend_highlights_with_original(
    original: np.ndarray,
    edited: np.ndarray,
    threshold: int = 235,
    original_weight: float = 0.65,
) -> np.ndarray:
    """
    Nas áreas que ficaram claras demais, mistura de volta a foto original.
    Isso preserva textura de paredes/armários sem desfazer a edição toda.
    """
    if original.shape != edited.shape:
        return edited

    gray_edited = cv2.cvtColor(edited, cv2.COLOR_BGR2GRAY)
    mask = (gray_edited >= threshold).astype(np.float32)
    mask = cv2.GaussianBlur(mask, (0, 0), 5.0)
    mask = np.clip(mask[:, :, None], 0.0, 1.0)

    result = edited.astype(np.float32) * (1.0 - mask * original_weight) + original.astype(np.float32) * (mask * original_weight)
    return np.clip(result, 0, 255).astype(np.uint8)


def guard_luminance(original: np.ndarray, edited: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """
    Protege a edição final contra superexposição.

    Retorna a imagem corrigida e logs explicando as ações tomadas.
    """
    logs: list[str] = []
    if original.shape != edited.shape:
        return edited, ["Proteção de luz: ignorada (tamanho diferente)"]

    before = luminance_stats(original)
    after = luminance_stats(edited)

    logs.append(
        "Luz antes/depois: "
        f"média {before['mean']:.0f}->{after['mean']:.0f}, "
        f"quase branco {before['near_clip_pct']:.1f}%->{after['near_clip_pct']:.1f}%"
    )

    result = edited

    # Se a edição aumentou demais as áreas quase brancas, volta detalhes das altas-luzes.
    max_near_clip = max(before["near_clip_pct"] + 2.0, 3.0)
    max_clip = max(before["clip_pct"] + 0.4, 1.0)

    if after["near_clip_pct"] > max_near_clip or after["clip_pct"] > max_clip or after["p99"] >= 252:
        result = blend_highlights_with_original(original, result, threshold=232, original_weight=0.70)
        result = compress_highlights(result, start=225, ratio=0.38)
        logs.append("Proteção de luz: realces/brancos recuperados automaticamente")

    # Checagem final: se ainda estiver estourando, reduz o efeito global aos poucos.
    final_stats = luminance_stats(result)
    if final_stats["near_clip_pct"] > max_near_clip * 1.35 or final_stats["clip_pct"] > max_clip * 1.35:
        result = cv2.addWeighted(result, 0.65, original, 0.35, 0)
        result = compress_highlights(result, start=222, ratio=0.35)
        logs.append("Proteção de luz: intensidade geral reduzida por risco de estouro")

    return result, logs


def safe_global_exposure(img: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """
    Ajuste conservador de exposição.
    Só clareia globalmente quando a imagem está realmente escura e sem muitos brancos.
    """
    stats = luminance_stats(img)
    logs: list[str] = []

    if scene_is_already_bright(stats):
        logs.append(
            f"Exposição global bloqueada: foto já clara/brancos altos "
            f"(média={stats['mean']:.0f}, quase branco={stats['near_clip_pct']:.1f}%)"
        )
        # Mesmo em cenas claras, um pequeno shadow lift ajuda sem estourar.
        return apply_shadow_lift(img, strength=7.0), logs + ["Sombras abertas levemente"]

    # Foto escura: usa ganho pequeno e abre sombras. Nada agressivo.
    if stats["mean"] < 95:
        alpha = 1.08
        beta = 3
        shadow_strength = 18
    elif stats["mean"] < 125:
        alpha = 1.04
        beta = 2
        shadow_strength = 14
    else:
        alpha = 1.00
        beta = 0
        shadow_strength = 10

    result = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
    result = apply_shadow_lift(result, strength=shadow_strength)
    logs.append(
        f"Exposição conservadora: alpha={alpha:.2f}, beta={beta:+.0f}, sombras=+{shadow_strength:.0f}"
    )
    return result, logs
