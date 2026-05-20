"""
Módulo de renomeação inteligente de fotos.

Renomeia arquivos de forma organizada e profissional:
  IMOVEL_001_exterior_01.jpg
  IMOVEL_001_interior_01.jpg
  IMOVEL_001_detalhes_01.jpg

Padrão configurável:
  {prefixo}_{codigo}_{classe}_{sequencia}.{ext}
"""

import os
import re
from datetime import datetime


class SmartRenamer:
    """Renomeia fotos de imóveis de forma organizada."""

    def __init__(self, prefix: str = "IMOVEL",
                 property_code: str = "",
                 pattern: str = "{prefix}_{code}_{class}_{seq}"):
        """
        Args:
            prefix:        prefixo padrão (ex: "IMOVEL", "APTO", "CASA")
            property_code: código do imóvel (ex: "001", "AP2B")
            pattern:       padrão de nome. Variáveis disponíveis:
                           {prefix}, {code}, {class}, {seq}, {date}, {original}
        """
        self.prefix = prefix
        self.property_code = property_code or datetime.now().strftime("%Y%m%d")
        self.pattern = pattern
        self._counters: dict[str, int] = {}

    def generate_name(self, original_name: str, classification: str,
                      extension: str = ".jpg") -> str:
        """
        Gera novo nome para o arquivo baseado na classificação.

        Args:
            original_name: nome original do arquivo (sem extensão).
            classification: classe da imagem (interior, exterior, etc.).
            extension: extensão do arquivo.

        Returns:
            Novo nome completo (com extensão).
        """
        # Incrementa contador por classe
        if classification not in self._counters:
            self._counters[classification] = 0
        self._counters[classification] += 1
        seq = self._counters[classification]

        # Monta nome
        name = self.pattern.format(
            prefix=self.prefix,
            code=self.property_code,
            **{"class": classification},  # class é keyword
            seq=f"{seq:02d}",
            date=datetime.now().strftime("%Y%m%d"),
            original=self._sanitize(original_name),
        )

        # Limpa caracteres inválidos
        name = self._sanitize(name)
        return f"{name}{extension}"

    def reset(self) -> None:
        """Reinicia contadores de sequência por classe."""
        self._counters.clear()

    def generate_mapping(self, files: list[dict]) -> list[dict]:
        """
        Gera mapeamento completo de renomeação.

        Args:
            files: lista de dicts {"filename": str, "classification": str}

        Returns:
            Lista de dicts {"old_name": str, "new_name": str, "classification": str}
        """
        self._counters.clear()
        mapping = []

        for f in files:
            old_name = f["filename"]
            base, ext = os.path.splitext(old_name)
            new_name = self.generate_name(base, f["classification"], ext)
            mapping.append({
                "old_name": old_name,
                "new_name": new_name,
                "classification": f["classification"],
            })

        return mapping

    def apply_renaming(self, folder: str, mapping: list[dict]) -> list[str]:
        """
        Aplica a renomeação nos arquivos de uma pasta.

        Returns:
            Lista de logs das operações realizadas.
        """
        logs = []
        for item in mapping:
            old_path = os.path.join(folder, item["old_name"])
            new_path = os.path.join(folder, item["new_name"])

            if os.path.exists(old_path):
                # Evita conflito
                if os.path.exists(new_path):
                    base, ext = os.path.splitext(item["new_name"])
                    counter = 2
                    while os.path.exists(new_path):
                        new_path = os.path.join(folder, f"{base}_{counter}{ext}")
                        counter += 1

                os.rename(old_path, new_path)
                logs.append(f"  {item['old_name']}  →  {os.path.basename(new_path)}")
            else:
                logs.append(f"  ⚠ Não encontrado: {item['old_name']}")

        return logs

    @staticmethod
    def _sanitize(name: str) -> str:
        """Remove caracteres inválidos de nomes de arquivo."""
        # Remove caracteres proibidos no Windows
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Substitui espaços por underline
        name = name.replace(' ', '_')
        # Remove underlines duplos
        name = re.sub(r'_+', '_', name)
        return name.strip('_')
