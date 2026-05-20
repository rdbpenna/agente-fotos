"""
Módulo de aprendizado de estilo por exemplos.

Analisa pares de fotos (ANTES → DEPOIS) e extrai os parâmetros
de edição que transformam uma na outra. Salva como um "perfil de estilo"
que pode ser aplicado automaticamente a novas fotos.

O que ele aprende:
  • Delta de brilho (exposição)
  • Delta de contraste
  • Delta de saturação
  • Deslocamento de temperatura de cor (quente/frio)
  • Nível de nitidez
  • Curva de tons (sombras, meios-tons, altas-luzes)

Uso:
  trainer = StyleTrainer()
  trainer.add_pair("foto_antes.jpg", "foto_depois.jpg")
  trainer.add_pair("foto2_antes.jpg", "foto2_depois.jpg")
  trainer.learn()
  trainer.save_profile("meu_estilo.json")
"""

import os
import json
import cv2
import numpy as np
from datetime import datetime


class StyleTrainer:
    """Aprende parâmetros de edição a partir de pares antes/depois."""

    def __init__(self):
        self.pairs: list[dict] = []          # pares de caminhos
        self.analyses: list[dict] = []       # análises individuais
        self.profile: dict | None = None     # perfil final aprendido

    def add_pair(self, before_path: str, after_path: str, category: str = "geral"):
        """
        Adiciona um par de imagens para treinamento.

        Args:
            before_path: foto original (antes da edição).
            after_path:  foto editada (como você quer que fique).
            category:    categoria opcional (interior, exterior, detalhes).
        """
        if not os.path.exists(before_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {before_path}")
        if not os.path.exists(after_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {after_path}")

        self.pairs.append({
            "before": before_path,
            "after": after_path,
            "category": category,
        })

    def learn(self) -> dict:
        """
        Analisa todos os pares e gera o perfil de estilo.

        Returns:
            Dicionário com os parâmetros aprendidos.
        """
        if not self.pairs:
            raise ValueError("Adicione pelo menos um par de imagens antes de treinar.")

        self.analyses = []

        for pair in self.pairs:
            analysis = self._analyze_pair(pair["before"], pair["after"])
            analysis["category"] = pair["category"]
            self.analyses.append(analysis)

        # Calcula médias ponderadas dos parâmetros
        self.profile = self._compute_average_profile()
        return self.profile

    def save_profile(self, output_path: str):
        """Salva o perfil aprendido em arquivo JSON."""
        if self.profile is None:
            raise ValueError("Execute learn() antes de salvar.")

        data = {
            "nome": "Perfil personalizado",
            "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "total_pares_analisados": len(self.pairs),
            "parametros": self.profile,
            "detalhes_por_par": [
                {
                    "antes": p["before"],
                    "depois": p["after"],
                    "categoria": p["category"],
                    "analise": a,
                }
                for p, a in zip(self.pairs, self.analyses)
            ],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_profile(profile_path: str) -> dict:
        """Carrega um perfil de estilo salvo."""
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["parametros"]

    # ── Análise de pares ─────────────────────────────────────────

    def _analyze_pair(self, before_path: str, after_path: str) -> dict:
        """
        Compara antes/depois e extrai os deltas de cada parâmetro.
        """
        before = cv2.imread(before_path)
        after = cv2.imread(after_path)

        if before is None or after is None:
            return self._empty_analysis()

        # Redimensiona 'after' para mesmo tamanho do 'before' se necessário
        if before.shape[:2] != after.shape[:2]:
            after = cv2.resize(after, (before.shape[1], before.shape[0]))

        return {
            "brilho": self._analyze_brightness(before, after),
            "contraste": self._analyze_contrast(before, after),
            "saturacao": self._analyze_saturation(before, after),
            "temperatura": self._analyze_temperature(before, after),
            "nitidez": self._analyze_sharpness(before, after),
            "curva_tons": self._analyze_tone_curve(before, after),
        }

    def _analyze_brightness(self, before, after) -> dict:
        """Mede a mudança de brilho entre antes e depois."""
        gray_b = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY).astype(float)
        gray_a = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY).astype(float)

        mean_before = gray_b.mean()
        mean_after = gray_a.mean()

        # Fator multiplicativo e aditivo
        if mean_before > 0:
            factor = mean_after / mean_before
        else:
            factor = 1.0

        offset = mean_after - mean_before

        return {
            "media_antes": round(mean_before, 2),
            "media_depois": round(mean_after, 2),
            "fator": round(factor, 4),
            "offset": round(offset, 2),
        }

    def _analyze_contrast(self, before, after) -> dict:
        """Mede a mudança de contraste (desvio padrão do brilho)."""
        gray_b = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY).astype(float)
        gray_a = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY).astype(float)

        std_before = gray_b.std()
        std_after = gray_a.std()

        if std_before > 0:
            factor = std_after / std_before
        else:
            factor = 1.0

        return {
            "desvio_antes": round(std_before, 2),
            "desvio_depois": round(std_after, 2),
            "fator": round(factor, 4),
        }

    def _analyze_saturation(self, before, after) -> dict:
        """Mede a mudança de saturação no espaço HSV."""
        hsv_b = cv2.cvtColor(before, cv2.COLOR_BGR2HSV).astype(float)
        hsv_a = cv2.cvtColor(after, cv2.COLOR_BGR2HSV).astype(float)

        sat_before = hsv_b[:, :, 1].mean()
        sat_after = hsv_a[:, :, 1].mean()

        if sat_before > 0:
            factor = sat_after / sat_before
        else:
            factor = 1.0

        return {
            "media_antes": round(sat_before, 2),
            "media_depois": round(sat_after, 2),
            "fator": round(factor, 4),
        }

    def _analyze_temperature(self, before, after) -> dict:
        """
        Mede o deslocamento de temperatura de cor.
        Compara a proporção entre canais azul e vermelho.
        Valor positivo = mais quente, negativo = mais frio.
        """
        # Médias dos canais BGR
        b_before, g_before, r_before = [before[:, :, i].mean() for i in range(3)]
        b_after, g_after, r_after = [after[:, :, i].mean() for i in range(3)]

        # Razão vermelho/azul indica temperatura
        if b_before > 0:
            temp_before = r_before / b_before
        else:
            temp_before = 1.0

        if b_after > 0:
            temp_after = r_after / b_after
        else:
            temp_after = 1.0

        shift = temp_after - temp_before

        # Calcula offsets por canal para aplicação direta
        r_offset = r_after - r_before
        g_offset = g_after - g_before
        b_offset = b_after - b_before

        return {
            "razao_rb_antes": round(temp_before, 4),
            "razao_rb_depois": round(temp_after, 4),
            "shift": round(shift, 4),
            "canal_r_offset": round(r_offset, 2),
            "canal_g_offset": round(g_offset, 2),
            "canal_b_offset": round(b_offset, 2),
        }

    def _analyze_sharpness(self, before, after) -> dict:
        """
        Mede a diferença de nitidez usando variância do Laplaciano.
        Quanto maior a variância, mais nítida a imagem.
        """
        gray_b = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY)
        gray_a = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)

        lap_before = cv2.Laplacian(gray_b, cv2.CV_64F).var()
        lap_after = cv2.Laplacian(gray_a, cv2.CV_64F).var()

        if lap_before > 0:
            factor = lap_after / lap_before
        else:
            factor = 1.0

        return {
            "laplaciano_antes": round(lap_before, 2),
            "laplaciano_depois": round(lap_after, 2),
            "fator": round(factor, 4),
        }

    def _analyze_tone_curve(self, before, after) -> dict:
        """
        Analisa como sombras, meios-tons e altas-luzes foram alterados.
        Divide o histograma em 3 regiões e mede o deslocamento em cada uma.
        """
        gray_b = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY).astype(float)
        gray_a = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY).astype(float)

        # Sombras: pixels 0-85, meios-tons: 85-170, altas-luzes: 170-255
        regions = {
            "sombras": (0, 85),
            "meios_tons": (85, 170),
            "altas_luzes": (170, 256),
        }

        curve = {}
        for name, (low, high) in regions.items():
            mask = (gray_b >= low) & (gray_b < high)
            if mask.sum() > 0:
                mean_b = gray_b[mask].mean()
                mean_a = gray_a[mask].mean()
                curve[name] = {
                    "offset": round(mean_a - mean_b, 2),
                    "fator": round(mean_a / mean_b, 4) if mean_b > 0 else 1.0,
                }
            else:
                curve[name] = {"offset": 0.0, "fator": 1.0}

        return curve

    # ── Cálculo do perfil médio ──────────────────────────────────

    def _compute_average_profile(self) -> dict:
        """Calcula a média dos parâmetros de todos os pares analisados."""
        n = len(self.analyses)
        if n == 0:
            return {}

        profile = {
            "brilho_fator": round(sum(a["brilho"]["fator"] for a in self.analyses) / n, 4),
            "brilho_offset": round(sum(a["brilho"]["offset"] for a in self.analyses) / n, 2),
            "contraste_fator": round(sum(a["contraste"]["fator"] for a in self.analyses) / n, 4),
            "saturacao_fator": round(sum(a["saturacao"]["fator"] for a in self.analyses) / n, 4),
            "temperatura_shift": round(sum(a["temperatura"]["shift"] for a in self.analyses) / n, 4),
            "canal_r_offset": round(sum(a["temperatura"]["canal_r_offset"] for a in self.analyses) / n, 2),
            "canal_g_offset": round(sum(a["temperatura"]["canal_g_offset"] for a in self.analyses) / n, 2),
            "canal_b_offset": round(sum(a["temperatura"]["canal_b_offset"] for a in self.analyses) / n, 2),
            "nitidez_fator": round(sum(a["nitidez"]["fator"] for a in self.analyses) / n, 4),
            "sombras_offset": round(sum(a["curva_tons"]["sombras"]["offset"] for a in self.analyses) / n, 2),
            "sombras_fator": round(sum(a["curva_tons"]["sombras"]["fator"] for a in self.analyses) / n, 4),
            "meios_tons_offset": round(sum(a["curva_tons"]["meios_tons"]["offset"] for a in self.analyses) / n, 2),
            "meios_tons_fator": round(sum(a["curva_tons"]["meios_tons"]["fator"] for a in self.analyses) / n, 4),
            "altas_luzes_offset": round(sum(a["curva_tons"]["altas_luzes"]["offset"] for a in self.analyses) / n, 2),
            "altas_luzes_fator": round(sum(a["curva_tons"]["altas_luzes"]["fator"] for a in self.analyses) / n, 4),
        }

        return profile

    @staticmethod
    def _empty_analysis() -> dict:
        return {
            "brilho": {"media_antes": 0, "media_depois": 0, "fator": 1.0, "offset": 0},
            "contraste": {"desvio_antes": 0, "desvio_depois": 0, "fator": 1.0},
            "saturacao": {"media_antes": 0, "media_depois": 0, "fator": 1.0},
            "temperatura": {"razao_rb_antes": 1, "razao_rb_depois": 1, "shift": 0,
                           "canal_r_offset": 0, "canal_g_offset": 0, "canal_b_offset": 0},
            "nitidez": {"laplaciano_antes": 0, "laplaciano_depois": 0, "fator": 1.0},
            "curva_tons": {
                "sombras": {"offset": 0, "fator": 1.0},
                "meios_tons": {"offset": 0, "fator": 1.0},
                "altas_luzes": {"offset": 0, "fator": 1.0},
            },
        }
