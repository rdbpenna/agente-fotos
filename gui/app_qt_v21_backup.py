"""
GUI PySide6 — Fase 1: aba Processar fiel ao protótipo HTML/CSS.
Arquivo: gui/app_qt.py
Lógica de processamento importada de core.pipeline (sem alterações).
"""

import os
import sys
import json
import threading
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QScrollArea,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QSplitter,
    QGraphicsDropShadowEffect, QSizePolicy, QTabBar,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QObject
from PySide6.QtGui import QFont, QFontDatabase, QColor, QPixmap, QPainter, QIcon

from core.pipeline import ProcessingPipeline


# ── Design tokens (do mockup CSS) ────────────────────────────────
T = {
    "bg0": "#0B1220", "bg1": "#0E1626", "bg2": "#101B2C", "bg3": "#142235",
    "bgElev": "#16243A", "border": "#1D2C44", "borderSoft": "#182338",
    "text1": "#E6EDF5", "text2": "#B7C2D2", "text3": "#7E8DA3", "text4": "#5A6678",
    "teal": "#1FD1A8", "teal2": "#14B894",
    "tealSoft": "rgba(31,209,168,0.12)", "tealGlow": "rgba(31,209,168,0.25)",
    "red": "#EF4D5C", "green": "#22C58A",
    "rCard": "14px", "rSub": "12px", "rInput": "10px", "rBtn": "12px",
}


# ── QSS Global ───────────────────────────────────────────────────
GLOBAL_QSS = f"""
QMainWindow, QWidget#central {{
    background: {T['bg0']};
    color: {T['text1']};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {T['bg3']}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {T['bgElev']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QLabel {{ background: transparent; }}
QLineEdit {{
    background: {T['bg0']};
    border: 1px solid {T['border']};
    border-radius: {T['rInput']};
    padding: 0 12px;
    height: 38px;
    color: {T['text2']};
    font-family: 'Consolas', 'JetBrains Mono', monospace;
    font-size: 13px;
    selection-background-color: {T['teal']};
}}
QLineEdit:hover {{ border-color: {T['bgElev']}; }}
QLineEdit:focus {{ border-color: {T['teal']}; }}
QProgressBar {{
    background: {T['bg3']};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {T['teal2']},stop:1 {T['teal']});
    border-radius: 4px;
}}
QTextEdit {{
    background: {T['bg2']};
    border: 1px solid {T['borderSoft']};
    border-radius: {T['rSub']};
    color: {T['text2']};
    font-family: 'Consolas', 'JetBrains Mono', monospace;
    font-size: 12px;
    padding: 8px;
    selection-background-color: {T['teal']};
}}
"""


def card_qss(extra=""):
    return f"""
    QFrame#card {{
        background: {T['bg1']};
        border: 1px solid {T['borderSoft']};
        border-radius: {T['rCard']};
        {extra}
    }}"""


def btn_primary_qss():
    return f"""
    QPushButton {{
        background: {T['teal']};
        color: #03261C;
        font-weight: 700;
        font-size: 14px;
        border: none;
        border-radius: {T['rBtn']};
        padding: 0 22px;
        min-height: 48px;
    }}
    QPushButton:hover {{ background: #2DE0B6; }}
    QPushButton:pressed {{ background: {T['teal2']}; }}
    QPushButton:disabled {{ background: {T['bg3']}; color: {T['text4']}; }}
    """


def btn_secondary_qss():
    return f"""
    QPushButton {{
        background: {T['bg3']};
        color: {T['text1']};
        font-size: 14px;
        border: 1px solid {T['border']};
        border-radius: {T['rBtn']};
        padding: 0 18px;
        min-height: 48px;
    }}
    QPushButton:hover {{ background: {T['bgElev']}; border-color: {T['bgElev']}; }}
    """


def btn_ghost_qss():
    return f"""
    QPushButton {{
        background: {T['bg3']};
        color: {T['text2']};
        font-size: 13px;
        font-weight: 500;
        border: 1px solid {T['borderSoft']};
        border-radius: {T['rBtn']};
        padding: 0 14px;
        min-height: 38px;
    }}
    QPushButton:hover {{ background: {T['bgElev']}; color: {T['text1']}; border-color: {T['border']}; }}
    """


def seg_btn_qss(active=False):
    if active:
        return f"""
        QPushButton {{
            background: {T['teal']};
            color: #03261C;
            font-weight: 600;
            font-size: 13px;
            border: none;
            border-radius: 8px;
            padding: 6px 16px;
            min-height: 32px;
        }}
        QPushButton:hover {{ background: #2DE0B6; }}
        """
    return f"""
    QPushButton {{
        background: {T['bg2']};
        color: {T['text2']};
        font-size: 13px;
        border: 1px solid {T['borderSoft']};
        border-radius: 8px;
        padding: 6px 16px;
        min-height: 32px;
    }}
    QPushButton:hover {{ background: {T['bg3']}; color: {T['text1']}; }}
    """


def toggle_qss(on=False):
    bg = T['teal'] if on else T['bg3']
    return f"""
    QPushButton {{
        background: {bg};
        border: none;
        border-radius: 12px;
        min-width: 44px; max-width: 44px;
        min-height: 24px; max-height: 24px;
    }}
    """


# ── Signal bridge (thread → GUI) ─────────────────────────────────
class ProgressBridge(QObject):
    progress = Signal(str, float)


# ── Helper widgets ────────────────────────────────────────────────

class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(card_qss())
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 64))
        self.setGraphicsEffect(shadow)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 18, 18, 18)
        self._layout.setSpacing(0)

    def add(self, widget, stretch=0):
        self._layout.addWidget(widget, stretch)
        return widget

    def addLayout(self, layout):
        self._layout.addLayout(layout)

    def addSpacing(self, px):
        self._layout.addSpacing(px)


class SubCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {T['bg2']};
                border: 1px solid {T['borderSoft']};
                border-radius: {T['rSub']};
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(8)

    def add(self, widget):
        self._layout.addWidget(widget)
        return widget

    def addLayout(self, layout):
        self._layout.addLayout(layout)


class SegButtonGroup(QWidget):
    changed = Signal(str)

    def __init__(self, options, current="", parent=None):
        super().__init__(parent)
        self.buttons = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for opt in options:
            btn = QPushButton(opt)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, v=opt: self.select(v))
            layout.addWidget(btn)
            self.buttons[opt] = btn
        self.select(current or options[0])

    def select(self, value):
        self._current = value
        for v, btn in self.buttons.items():
            btn.setStyleSheet(seg_btn_qss(v == value))
        self.changed.emit(value)

    def value(self):
        return self._current


class ToggleSwitch(QPushButton):
    toggled_signal = Signal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._toggle)
        self._update()

    def _toggle(self):
        self._checked = not self._checked
        self._update()
        self.toggled_signal.emit(self._checked)

    def _update(self):
        self.setStyleSheet(toggle_qss(self._checked))
        self.setText("")

    def isChecked(self):
        return self._checked

    def setChecked(self, v):
        self._checked = v
        self._update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        thumb_x = 22 if self._checked else 2
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(thumb_x, 2, 20, 20)
        p.end()


# ═══════════════════════════════════════════════════════════════════
#  JANELA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

class PhotoAgentApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agente de Fotos Imobiliárias")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(GLOBAL_QSS)

        # State
        self.pipeline = None
        self._bridge = ProgressBridge()
        self._bridge.progress.connect(self._update_ui)

        # Values (equivalente às tk.StringVar da versão anterior)
        self._intensity = "normal"
        self._color_mode = "natural"
        self._preview_mode = False
        self._upscale_enabled = False
        self._upscale_factor = "2x"

        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_titlebar())
        root.addWidget(self._build_topbar())
        root.addWidget(self._build_body(), 1)
        root.addWidget(self._build_statusbar())

    # ── Title bar ─────────────────────────────────────────────────

    def _build_titlebar(self):
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"""
            QFrame {{ background: {T['bg1']};
                      border-bottom: 1px solid {T['borderSoft']}; }}
        """)
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 0, 20, 0)

        brand = QLabel("Agente de Fotos Imobiliárias")
        brand.setStyleSheet(f"font-weight: 700; font-size: 18px; color: {T['text1']};")
        h.addWidget(brand)
        h.addStretch()

        return bar

    # ── Top bar (tabs + summary) ──────────────────────────────────

    def _build_topbar(self):
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"QFrame {{ background: transparent; }}")
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 0, 20, 0)

        # Tabs
        for label, active in [("Processar", True), ("Configurações", False), ("Treinar estilo", False)]:
            tb = QPushButton(label)
            if active:
                tb.setStyleSheet(f"""
                    QPushButton {{
                        color: {T['teal']};
                        font-weight: 600; font-size: 14px;
                        border: none; border-bottom: 2px solid {T['teal']};
                        padding: 8px 16px;
                        background: transparent;
                    }}
                """)
            else:
                tb.setStyleSheet(f"""
                    QPushButton {{
                        color: {T['text3']}; font-weight: 500; font-size: 14px;
                        border: none; padding: 8px 16px; background: transparent;
                    }}
                    QPushButton:hover {{ color: {T['text2']}; }}
                """)
            h.addWidget(tb)

        h.addStretch()

        # Summary
        summary = QFrame()
        summary.setStyleSheet(f"""
            QFrame {{ background: {T['bg2']}; border: 1px solid {T['borderSoft']};
                      border-radius: 12px; }}
        """)
        sh = QHBoxLayout(summary)
        sh.setContentsMargins(14, 8, 14, 8)
        sh.setSpacing(0)

        self._sum_labels = {}
        for i, (key, icon_text, val) in enumerate([
            ("intensity", "Intensidade", "Normal"),
            ("color", "Cor", "Natural"),
            ("upscale", "Upscale", "2x"),
            ("preview", "Preview", "Desligado"),
        ]):
            if i > 0:
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setStyleSheet(f"background: {T['borderSoft']};")
                sh.addWidget(sep)

            item = QWidget()
            iv = QVBoxLayout(item)
            iv.setContentsMargins(12, 2, 12, 2)
            iv.setSpacing(1)
            lbl = QLabel(icon_text)
            lbl.setStyleSheet(f"font-size: 11px; color: {T['text3']};")
            lbl.setAlignment(Qt.AlignCenter)
            iv.addWidget(lbl)
            val_lbl = QLabel(val)
            val_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {T['text1']};")
            val_lbl.setAlignment(Qt.AlignCenter)
            iv.addWidget(val_lbl)
            self._sum_labels[key] = val_lbl
            sh.addWidget(item)

        h.addWidget(summary)
        return bar

    # ── Body (2 columns) ──────────────────────────────────────────

    def _build_body(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        grid = QHBoxLayout(container)
        grid.setContentsMargins(20, 16, 20, 20)
        grid.setSpacing(20)

        # Left column (460px fixed)
        left = QWidget()
        left.setFixedWidth(460)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)

        left_layout.addWidget(self._build_pastas_card())
        left_layout.addWidget(self._build_edition_card())
        left_layout.addWidget(self._build_upscale_card())
        left_layout.addWidget(self._build_action_row())
        left_layout.addStretch()

        grid.addWidget(left)

        # Right column
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)

        right_layout.addWidget(self._build_preview_card(), 1)
        right_layout.addWidget(self._build_bottom_grid())

        grid.addWidget(right, 1)

        scroll.setWidget(container)
        return scroll

    # ── Card: Pastas ──────────────────────────────────────────────

    def _build_pastas_card(self):
        card = Card()
        h = self._card_header(card, "Pastas")

        for label, sublabel, attr in [
            ("Entrada", "Pasta com as fotos originais.", "_input_dir"),
            ("Saída", "Pasta onde o agente salvará tudo.", "_output_dir"),
        ]:
            sub = SubCard()
            title = QLabel(label)
            title.setStyleSheet(f"font-size: 13.5px; font-weight: 600; color: {T['text1']};")
            desc = QLabel(sublabel)
            desc.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
            sub.add(title)
            sub.add(desc)

            row = QHBoxLayout()
            row.setSpacing(8)
            le = QLineEdit()
            le.setPlaceholderText("C:\\Fotos\\...")
            setattr(self, attr, le)
            row.addWidget(le, 1)
            browse = QPushButton("Procurar")
            browse.setStyleSheet(btn_ghost_qss())
            browse.setCursor(Qt.PointingHandCursor)
            browse.clicked.connect(lambda checked, w=le: self._browse_dir(w))
            row.addWidget(browse)
            sub.addLayout(row)
            card.add(sub)
            card.addSpacing(6)

        # Estilo (opcional)
        sub = SubCard()
        title = QLabel("Estilo (opcional)")
        title.setStyleSheet(f"font-size: 13.5px; font-weight: 600; color: {T['text1']};")
        desc = QLabel("Use um perfil .json treinado com o seu estilo.")
        desc.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        sub.add(title)
        sub.add(desc)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._style_path = QLineEdit()
        self._style_path.setPlaceholderText("")
        row.addWidget(self._style_path, 1)
        btn_clear = QPushButton("Limpar")
        btn_clear.setStyleSheet(btn_ghost_qss())
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(lambda: self._style_path.clear())
        row.addWidget(btn_clear)
        btn_sel = QPushButton("Selecionar")
        btn_sel.setStyleSheet(btn_ghost_qss())
        btn_sel.setCursor(Qt.PointingHandCursor)
        btn_sel.clicked.connect(self._browse_style)
        row.addWidget(btn_sel)
        sub.addLayout(row)
        card.add(sub)

        return card

    # ── Card: Edição ──────────────────────────────────────────────

    def _build_edition_card(self):
        card = Card()
        self._card_header(card, "Edição",
                          "Controle a intensidade e teste o resultado antes do lote completo.")

        # Intensity + Color side by side
        row = QHBoxLayout()
        row.setSpacing(24)

        # Intensity
        left = QVBoxLayout()
        left.setSpacing(4)
        lbl_i = QLabel("Intensidade")
        lbl_i.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {T['text1']};")
        left.addWidget(lbl_i)
        self._intensity_seg = SegButtonGroup(["Suave", "Normal", "Forte"], "Normal")
        self._intensity_seg.changed.connect(self._on_intensity)
        left.addWidget(self._intensity_seg)
        rec_i = QLabel("Recomendado: Normal")
        rec_i.setStyleSheet(f"font-size: 11px; color: {T['text4']};")
        left.addWidget(rec_i)
        row.addLayout(left)

        # Color
        right = QVBoxLayout()
        right.setSpacing(4)
        lbl_c = QLabel("Modo de Cor")
        lbl_c.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {T['text1']};")
        right.addWidget(lbl_c)
        self._color_seg = SegButtonGroup(["Natural", "Vibrant", "Luxury"], "Natural")
        self._color_seg.changed.connect(self._on_color_mode)
        right.addWidget(self._color_seg)
        rec_c = QLabel("Recomendado: Luxury")
        rec_c.setStyleSheet(f"font-size: 11px; color: {T['text4']};")
        right.addWidget(rec_c)
        row.addLayout(right)

        card.addLayout(row)
        card.addSpacing(14)

        # Preview toggle
        prev_row = QHBoxLayout()
        prev_row.setSpacing(10)
        lbl_p = QLabel("Teste rápido (preview)")
        lbl_p.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {T['text1']};")
        prev_row.addWidget(lbl_p)
        desc_p = QLabel("Processa miniaturas para visualização rápida dos resultados.")
        desc_p.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        prev_row.addWidget(desc_p, 1)
        self._preview_toggle = ToggleSwitch(False)
        self._preview_toggle.toggled_signal.connect(self._on_preview_toggle)
        prev_row.addWidget(self._preview_toggle)
        card.addLayout(prev_row)

        return card

    # ── Card: Upscale ─────────────────────────────────────────────

    def _build_upscale_card(self):
        card = Card()
        self._card_header(card, "Upscale",
                          "Aumente a resolução das fotos antes das exportações finais.")

        # Toggle + factor
        row = QHBoxLayout()
        row.setSpacing(12)
        self._upscale_toggle = ToggleSwitch(False)
        self._upscale_toggle.toggled_signal.connect(self._on_upscale_toggle)
        row.addWidget(self._upscale_toggle)
        lbl = QLabel("Ativar upscale nas fotos")
        lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {T['text1']};")
        row.addWidget(lbl)
        row.addStretch()
        fl = QLabel("Fator:")
        fl.setStyleSheet(f"font-size: 12.5px; color: {T['text3']};")
        row.addWidget(fl)
        self._factor_seg = SegButtonGroup(["2x", "3x", "4x"], "2x")
        self._factor_seg.changed.connect(self._on_factor)
        row.addWidget(self._factor_seg)
        card.addLayout(row)

        card.addSpacing(6)
        rec = QLabel("Recomendado: 2x. Use 3x ou 4x só quando precisar de arquivos maiores.")
        rec.setStyleSheet(f"font-size: 12px; color: {T['text4']};")
        card.add(rec)

        return card

    # ── Action row ────────────────────────────────────────────────

    def _build_action_row(self):
        frame = QWidget()
        h = QHBoxLayout(frame)
        h.setContentsMargins(0, 4, 0, 0)
        h.setSpacing(12)

        self._btn_process = QPushButton("Processar fotos")
        self._btn_process.setStyleSheet(btn_primary_qss())
        self._btn_process.setCursor(Qt.PointingHandCursor)
        self._btn_process.clicked.connect(self._start_processing)
        h.addWidget(self._btn_process, 3)

        self._btn_open = QPushButton("Abrir saída")
        self._btn_open.setStyleSheet(btn_secondary_qss())
        self._btn_open.setCursor(Qt.PointingHandCursor)
        self._btn_open.clicked.connect(self._open_output_folder)
        h.addWidget(self._btn_open, 2)

        return frame

    # ── Preview card ──────────────────────────────────────────────

    def _build_preview_card(self):
        card = Card()

        # Header
        hdr = QHBoxLayout()
        left_h = QVBoxLayout()
        t = QLabel("Prévia")
        t.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {T['text1']};")
        left_h.addWidget(t)
        s = QLabel("Compare o resultado antes de processar todas as fotos.")
        s.setStyleSheet(f"font-size: 12.5px; color: {T['text3']};")
        left_h.addWidget(s)
        hdr.addLayout(left_h, 1)
        btn_full = QPushButton("Tela cheia")
        btn_full.setStyleSheet(btn_ghost_qss())
        btn_full.setCursor(Qt.PointingHandCursor)
        hdr.addWidget(btn_full)
        card.addLayout(hdr)
        card.addSpacing(14)

        # Preview area (placeholder)
        preview_frame = QFrame()
        preview_frame.setMinimumHeight(360)
        preview_frame.setStyleSheet(f"""
            QFrame {{
                background: #000;
                border-radius: 12px;
                border: 1px solid {T['borderSoft']};
            }}
        """)
        plbl = QLabel("Selecione uma pasta e clique em Preview para ver a prévia aqui")
        plbl.setAlignment(Qt.AlignCenter)
        plbl.setStyleSheet(f"color: {T['text4']}; font-size: 14px;")
        pl = QVBoxLayout(preview_frame)
        pl.addWidget(plbl)
        card.add(preview_frame, 1)

        return card

    # ── Bottom grid (status + log) ────────────────────────────────

    def _build_bottom_grid(self):
        frame = QWidget()
        h = QHBoxLayout(frame)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)

        # Status card
        status_card = Card()
        self._card_header(status_card, "Status do processamento",
                          "Acompanhe o andamento do processo em tempo real.")

        row = QHBoxLayout()
        lv = QVBoxLayout()
        lbl_curr = QLabel("Arquivo atual")
        lbl_curr.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        lv.addWidget(lbl_curr)
        self._current_file_lbl = QLabel("—")
        self._current_file_lbl.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {T['text1']}; font-family: Consolas, monospace;")
        lv.addWidget(self._current_file_lbl)
        row.addLayout(lv, 1)

        rv = QVBoxLayout()
        rv.setAlignment(Qt.AlignRight)
        lbl_prog = QLabel("Progresso")
        lbl_prog.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        lbl_prog.setAlignment(Qt.AlignRight)
        rv.addWidget(lbl_prog)
        self._progress_pct_lbl = QLabel("0%")
        self._progress_pct_lbl.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {T['text1']}; font-family: Consolas, monospace;")
        self._progress_pct_lbl.setAlignment(Qt.AlignRight)
        rv.addWidget(self._progress_pct_lbl)
        row.addLayout(rv)
        status_card.addLayout(row)
        status_card.addSpacing(8)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        status_card.add(self._progress_bar)
        status_card.addSpacing(10)

        self._status_foot = QLabel("Pronto para processar.")
        self._status_foot.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        self._status_foot.setWordWrap(True)
        status_card.add(self._status_foot)

        h.addWidget(status_card, 1)

        # Log card
        log_card = Card()
        self._card_header(log_card, "Log de atividades",
                          "Mensagens do processamento, erros e eventos relevantes.")
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMinimumHeight(120)
        log_card.add(self._log_text, 1)

        h.addWidget(log_card, 1)

        return frame

    # ── Status bar ────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = QFrame()
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"""
            QFrame {{ background: {T['bg1']};
                      border-top: 1px solid {T['borderSoft']}; }}
        """)
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 0, 20, 0)

        # Pulse dot
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {T['green']}; font-size: 10px;")
        h.addWidget(dot)
        self._sb_status = QLabel("Pronto para processar")
        self._sb_status.setStyleSheet(f"font-size: 12.5px; color: {T['text2']};")
        h.addWidget(self._sb_status)

        sep = QFrame()
        sep.setFixedSize(1, 14)
        sep.setStyleSheet(f"background: {T['border']};")
        h.addWidget(sep)

        self._sb_count = QLabel("0 fotos na fila")
        self._sb_count.setStyleSheet(f"font-size: 12.5px; color: {T['text3']};")
        h.addWidget(self._sb_count)

        h.addStretch()

        tips = QLabel("Dicas e boas práticas")
        tips.setStyleSheet(f"font-size: 12.5px; color: {T['text3']};")
        h.addWidget(tips)

        return bar

    # ── Card header helper ────────────────────────────────────────

    def _card_header(self, card, title, subtitle=None):
        t = QLabel(title)
        t.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {T['text1']};")
        card.add(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(f"font-size: 12.5px; color: {T['text3']}; margin-bottom: 6px;")
            s.setWordWrap(True)
            card.add(s)
        card.addSpacing(10)

    # ── Summary update ────────────────────────────────────────────

    def _update_summary(self):
        self._sum_labels["intensity"].setText(self._intensity.capitalize())
        self._sum_labels["color"].setText(self._color_mode.capitalize())
        self._sum_labels["upscale"].setText(self._upscale_factor if self._upscale_enabled else "Off")
        self._sum_labels["preview"].setText("Ligado" if self._preview_mode else "Desligado")

    # ══════════════════════════════════════════════════════════════
    #  HANDLERS
    # ══════════════════════════════════════════════════════════════

    def _browse_dir(self, line_edit):
        p = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if p:
            line_edit.setText(p)

    def _browse_style(self):
        p, _ = QFileDialog.getOpenFileName(self, "Perfil de estilo", "", "JSON (*.json)")
        if p:
            self._style_path.setText(p)

    def _on_intensity(self, val):
        self._intensity = val.lower()
        self._update_summary()

    def _on_color_mode(self, val):
        self._color_mode = val.lower()
        self._update_summary()

    def _on_preview_toggle(self, val):
        self._preview_mode = val
        self._update_summary()

    def _on_upscale_toggle(self, val):
        self._upscale_enabled = val
        self._update_summary()

    def _on_factor(self, val):
        self._upscale_factor = val
        self._update_summary()

    def _collect_options(self):
        return {
            "intensity": self._intensity,
            "color_mode": self._color_mode,
            "preview_mode": self._preview_mode,
            "upscale_enabled": self._upscale_enabled,
            "upscale_factor": float(self._upscale_factor.replace("x", "")),
            "upscale_preset": "natural_pro",
            "duplicates_enabled": True,
            "duplicates_threshold": 10,
            "rename_enabled": False,
            "rename_prefix": "IMOVEL",
            "rename_code": "",
            "watermark_enabled": False,
            "watermark_config": None,
            "contact_sheet": True,
            "before_after": True,
            "gallery": True,
            "gallery_title": "Galeria de Fotos",
            "gallery_subtitle": "",
            "exif_preserve": True,
            "photographer": "",
            "copyright": "",
        }

    def _start_processing(self):
        inp = self._input_dir.text().strip()
        out = self._output_dir.text().strip()
        if not inp or not os.path.isdir(inp):
            QMessageBox.critical(self, "Erro", "Selecione uma pasta de entrada válida.")
            return
        if not out:
            QMessageBox.critical(self, "Erro", "Selecione uma pasta de saída.")
            return
        os.makedirs(out, exist_ok=True)

        self._log_text.clear()
        self._progress_bar.setValue(0)
        self._progress_pct_lbl.setText("0%")
        self._current_file_lbl.setText("—")
        self._btn_process.setEnabled(False)

        style_path = self._style_path.text().strip() or None
        options = self._collect_options()

        def progress_cb(msg, pct):
            self._bridge.progress.emit(msg, pct)

        self.pipeline = ProcessingPipeline(
            inp, out, progress_cb,
            style_profile_path=style_path,
            options=options,
        )
        self.pipeline.start()

    def _update_ui(self, message, pct):
        self._progress_bar.setValue(int(pct * 1000))
        pct_int = int(pct * 100)
        self._progress_pct_lbl.setText(f"{pct_int}%")

        # Extract filename from message like "[3/20] IMG_0123.jpg"
        if "]" in message:
            parts = message.split("]", 1)
            if len(parts) > 1:
                self._current_file_lbl.setText(parts[1].strip())
                count_part = parts[0].replace("[", "")
                self._status_foot.setText(f"Processados: {count_part} fotos")

        ts = datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f'<span style="color:{T["text3"]}">{ts}</span>  {message}')

        if pct >= 1.0:
            self._btn_process.setEnabled(True)
            self._sb_status.setText("Processamento concluído")

    def _open_output_folder(self):
        p = self._output_dir.text().strip()
        if p and os.path.isdir(p):
            os.startfile(p)
        else:
            QMessageBox.information(self, "Info", "Defina uma pasta de saída primeiro.")

    def mainloop(self):
        """Compatibilidade com main.py atual."""
        self.show()
        QApplication.instance().exec()
