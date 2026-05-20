"""
Ponto de entrada — PySide6 (com fallback para CustomTkinter).
Execute: python main.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        from gui.app_qt import PhotoAgentApp
        window = PhotoAgentApp()
        window.show()
        sys.exit(app.exec())
    except ImportError:
        print("PySide6 não encontrado, usando CustomTkinter...")
        from gui.app import PhotoAgentApp
        app = PhotoAgentApp()
        app.mainloop()

if __name__ == "__main__":
    main()
