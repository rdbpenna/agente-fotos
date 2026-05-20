"""
Módulo de exportação em múltiplos perfis.

Perfis disponíveis:
  • alta_qualidade — resolução máxima, JPEG 95%
  • instagram      — 1080×1080, JPEG 85%
  • whatsapp       — 1280×960, JPEG 75%
"""

import os
import cv2
from utils.config import EXPORT_PROFILES


class ImageExporter:
    """Exporta imagens melhoradas em diferentes perfis de qualidade/tamanho."""

    def export(self, image_path: str, output_dir: str, base_name: str,
               profiles: list[str] | None = None) -> list[str]:
        """
        Exporta uma imagem nos perfis selecionados.

        Args:
            image_path: caminho da imagem melhorada.
            output_dir: diretório raiz de exportação.
            base_name:  nome base do arquivo (sem extensão).
            profiles:   lista de nomes de perfis a gerar (None = todos).

        Returns:
            Lista de caminhos dos arquivos exportados.
        """
        img = cv2.imread(image_path)
        if img is None:
            return []

        exported = []

        for profile_name, profile in EXPORT_PROFILES.items():
            if profiles is not None and profile_name not in profiles:
                continue
            # Cria subpasta do perfil
            profile_dir = os.path.join(output_dir, profile_name)
            os.makedirs(profile_dir, exist_ok=True)

            # Redimensiona mantendo proporção
            resized = self._resize_fit(
                img,
                profile["max_width"],
                profile["max_height"],
            )

            # Monta nome do arquivo
            out_name = f"{base_name}{profile['suffix']}.jpg"
            out_path = os.path.join(profile_dir, out_name)

            # Salva com qualidade configurada
            cv2.imwrite(out_path, resized, [cv2.IMWRITE_JPEG_QUALITY, profile["quality"]])
            exported.append(out_path)

        return exported

    @staticmethod
    def _resize_fit(img, max_w: int, max_h: int):
        """
        Redimensiona a imagem para caber em max_w × max_h
        mantendo a proporção original. Nunca amplia.
        """
        h, w = img.shape[:2]

        # Não amplia imagens menores
        if w <= max_w and h <= max_h:
            return img

        scale = min(max_w / w, max_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
