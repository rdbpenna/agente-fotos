"""
Gerador de relatório de processamento.

Cria um arquivo .txt com resumo completo de tudo que foi feito:
  • Total de imagens processadas
  • Classificação de cada imagem
  • Melhorias aplicadas
  • Arquivos exportados
  • Erros encontrados
"""

import os
from datetime import datetime


class ReportGenerator:
    """Gera relatório textual do processamento de fotos."""

    def __init__(self):
        self.entries: list[dict] = []
        self.errors: list[str] = []
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

    def start(self):
        """Marca início do processamento."""
        self.start_time = datetime.now()
        self.entries = []
        self.errors = []

    def add_entry(self, filename: str, classification: str,
                  enhancements: list[str], exports: list[str]):
        """Registra o processamento de uma imagem."""
        self.entries.append({
            "filename": filename,
            "classification": classification,
            "enhancements": enhancements,
            "exports": exports,
        })

    def add_error(self, message: str):
        """Registra um erro."""
        self.errors.append(message)

    def finish(self):
        """Marca fim do processamento."""
        self.end_time = datetime.now()

    def save(self, output_path: str):
        """Salva o relatório em arquivo .txt."""
        self.finish()

        lines = []
        lines.append("=" * 65)
        lines.append("  RELATÓRIO DE PROCESSAMENTO — AGENTE FOTOS IMOBILIÁRIAS")
        lines.append("=" * 65)
        lines.append("")
        lines.append(f"  Data/Hora início : {self.start_time:%d/%m/%Y %H:%M:%S}")
        lines.append(f"  Data/Hora fim    : {self.end_time:%d/%m/%Y %H:%M:%S}")

        duration = self.end_time - self.start_time
        lines.append(f"  Duração total    : {duration}")
        lines.append(f"  Total de imagens : {len(self.entries)}")

        # Contagem por classe
        class_count: dict[str, int] = {}
        for entry in self.entries:
            c = entry["classification"]
            class_count[c] = class_count.get(c, 0) + 1

        lines.append("")
        lines.append("  CLASSIFICAÇÃO RESUMO:")
        for cls, count in sorted(class_count.items()):
            lines.append(f"    {cls:<15} {count:>4} imagens")

        # Detalhes por imagem
        lines.append("")
        lines.append("-" * 65)
        lines.append("  DETALHES POR IMAGEM")
        lines.append("-" * 65)

        for i, entry in enumerate(self.entries, 1):
            lines.append("")
            lines.append(f"  [{i:03d}] {entry['filename']}")
            lines.append(f"        Classe: {entry['classification']}")
            lines.append(f"        Melhorias aplicadas:")
            for enh in entry["enhancements"]:
                lines.append(f"          • {enh}")
            lines.append(f"        Exportações:")
            for exp in entry["exports"]:
                lines.append(f"          → {os.path.basename(exp)}")

        # Erros
        if self.errors:
            lines.append("")
            lines.append("-" * 65)
            lines.append("  ERROS ENCONTRADOS")
            lines.append("-" * 65)
            for err in self.errors:
                lines.append(f"  ⚠ {err}")

        lines.append("")
        lines.append("=" * 65)
        lines.append("  Fim do relatório")
        lines.append("=" * 65)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
