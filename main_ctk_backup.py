"""
╔══════════════════════════════════════════════════════════════╗
║  AGENTE DE FOTOS IMOBILIÁRIAS - MVP                        ║
║  Automatiza organização e pré-edição de fotos de imóveis   ║
║  Autor: Assistente Claude · Licença: MIT                   ║
╚══════════════════════════════════════════════════════════════╝

Ponto de entrada principal — abre a interface gráfica (tkinter).
Execute: python main.py
"""

import sys
import os

# Garante que o diretório do projeto esteja no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import PhotoAgentApp


def main():
    app = PhotoAgentApp()
    app.mainloop()


if __name__ == "__main__":
    main()
