"""
GUI PySide6 — v22: correções de layout, espaçamento, backgrounds.
Mesma estrutura e handlers da v21, com todos os problemas visuais corrigidos.
"""

import os
import sys
import json
import threading
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QScrollArea,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox,
    QGraphicsDropShadowEffect, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QPainter

from core.pipeline import ProcessingPipeline

# ── Tokens ────────────────────────────────────────────────────────
T = {
    "bg0": "#0B1220", "bg1": "#0E1626", "bg2": "#101B2C", "bg3": "#142235",
    "bgElev": "#16243A", "border": "#1D2C44", "borderSoft": "#182338",
    "text1": "#E6EDF5", "text2": "#B7C2D2", "text3": "#7E8DA3", "text4": "#5A6678",
    "teal": "#1FD1A8", "teal2": "#14B894", "green": "#22C58A",
}

# ── QSS ───────────────────────────────────────────────────────────
GLOBAL_QSS = f"""
* {{ font-family: 'Segoe UI', sans-serif; }}
QMainWindow {{ background: {T['bg0']}; }}
QWidget {{ background: transparent; color: {T['text1']}; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{
    background: {T['bg0']}; width: 8px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {T['bg3']}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {T['bgElev']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; height: 0; }}
QLineEdit {{
    background: {T['bg0']};
    border: 1px solid {T['border']};
    border-radius: 10px;
    padding: 8px 12px;
    color: {T['text2']};
    font-family: 'Consolas', monospace;
    font-size: 13px;
    min-height: 22px;
}}
QLineEdit:hover {{ border-color: {T['bgElev']}; }}
QLineEdit:focus {{ border-color: {T['teal']}; }}
QProgressBar {{
    background: {T['bg3']}; border: none; border-radius: 4px;
    max-height: 8px; min-height: 8px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {T['teal2']},stop:1 {T['teal']});
    border-radius: 4px;
}}
QTextEdit {{
    background: {T['bg2']};
    border: 1px solid {T['borderSoft']};
    border-radius: 10px;
    color: {T['text2']};
    font-family: 'Consolas', monospace;
    font-size: 12px;
    padding: 10px;
}}
"""


def _btn_qss(bg, color, border="none", hover_bg=None, hover_border=None,
             font_size="13px", font_weight="500", min_h="38px", radius="12px"):
    hbg = hover_bg or bg
    hbr = hover_border or border
    return f"""
    QPushButton {{
        background: {bg}; color: {color}; font-size: {font_size};
        font-weight: {font_weight}; border: {border}; border-radius: {radius};
        padding: 0 16px; min-height: {min_h};
    }}
    QPushButton:hover {{ background: {hbg}; border: {hbr}; }}
    QPushButton:pressed {{ background: {T['teal2']}; }}
    QPushButton:disabled {{ background: {T['bg3']}; color: {T['text4']}; }}
    """


BTN_PRIMARY = _btn_qss(T['teal'], "#03261C", hover_bg="#2DE0B6",
                         font_size="14px", font_weight="700", min_h="48px")
BTN_SECONDARY = _btn_qss(T['bg3'], T['text1'],
                           border=f"1px solid {T['border']}",
                           hover_bg=T['bgElev'],
                           hover_border=f"1px solid {T['bgElev']}",
                           font_size="14px", min_h="48px")
BTN_GHOST = _btn_qss(T['bg3'], T['text2'],
                       border=f"1px solid {T['borderSoft']}",
                       hover_bg=T['bgElev'],
                       hover_border=f"1px solid {T['border']}")


def seg_qss(active=False):
    if active:
        return _btn_qss(T['teal'], "#03261C", font_weight="600",
                         hover_bg="#2DE0B6", min_h="34px", radius="8px")
    return _btn_qss(T['bg2'], T['text2'],
                     border=f"1px solid {T['borderSoft']}",
                     hover_bg=T['bg3'], min_h="34px", radius="8px")


# ── Signal bridge ─────────────────────────────────────────────────
class ProgressBridge(QObject):
    progress = Signal(str, float)


# ── Reusable widgets ──────────────────────────────────────────────

class Card(QFrame):
    """Card com fundo, borda, sombra."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            Card {{
                background: {T['bg1']};
                border: 1px solid {T['borderSoft']};
                border-radius: 14px;
            }}
        """)
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(24); sh.setOffset(0, 6)
        sh.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(sh)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 16, 18, 16)
        self.lay.setSpacing(0)

    def w(self, widget, stretch=0):
        self.lay.addWidget(widget, stretch); return widget

    def l(self, layout):
        self.lay.addLayout(layout)

    def sp(self, px):
        self.lay.addSpacing(px)


class SubCard(QFrame):
    """Subcard dentro de Card (bg2)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            SubCard {{
                background: {T['bg2']};
                border: 1px solid {T['borderSoft']};
                border-radius: 12px;
            }}
        """)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(14, 12, 14, 12)
        self.lay.setSpacing(6)


class SegGroup(QWidget):
    """Grupo de botões segmentados."""
    changed = Signal(str)

    def __init__(self, options, current="", parent=None):
        super().__init__(parent)
        self._btns = {}
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        for opt in options:
            btn = QPushButton(opt)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumWidth(70)
            btn.clicked.connect(lambda _, v=opt: self.select(v))
            h.addWidget(btn)
            self._btns[opt] = btn
        self.select(current or options[0])

    def select(self, v):
        self._val = v
        for k, btn in self._btns.items():
            btn.setStyleSheet(seg_qss(k == v))
        self.changed.emit(v)

    def value(self):
        return self._val


class Toggle(QPushButton):
    """Switch on/off."""
    toggled_signal = Signal(bool)

    def __init__(self, on=False, parent=None):
        super().__init__(parent)
        self._on = on
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._flip)
        self._refresh()

    def _flip(self):
        self._on = not self._on
        self._refresh()
        self.toggled_signal.emit(self._on)

    def _refresh(self):
        bg = T['teal'] if self._on else T['bg3']
        self.setStyleSheet(f"""
            QPushButton {{ background: {bg}; border: none; border-radius: 12px; }}
        """)

    def isChecked(self):
        return self._on

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        x = 22 if self._on else 2
        p.drawEllipse(x, 2, 20, 20)
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

        self.pipeline = None
        self._bridge = ProgressBridge()
        self._bridge.progress.connect(self._update_ui)

        self._intensity = "normal"
        self._color_mode = "natural"
        self._preview_mode = False
        self._upscale_enabled = False
        self._upscale_factor = "2x"

        self._build_ui()

    # ── Root layout ───────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background: {T['bg0']};")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Fixed header
        root.addWidget(self._make_titlebar())
        root.addWidget(self._make_topbar())

        # Scrollable body — fills remaining space
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"QScrollArea {{ background: {T['bg0']}; }}")

        body = QWidget()
        body.setStyleSheet(f"background: {T['bg0']};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(20, 16, 20, 20)
        body_lay.setSpacing(0)

        # Two-column grid
        cols = QHBoxLayout()
        cols.setSpacing(20)

        # Left
        left = QWidget()
        left.setMinimumWidth(480)
        left.setMaximumWidth(500)
        left.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(14)
        ll.addWidget(self._make_pastas_card())
        ll.addWidget(self._make_edition_card())
        ll.addWidget(self._make_upscale_card())
        ll.addWidget(self._make_actions())
        ll.addStretch()
        cols.addWidget(left)

        # Right
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(14)
        rl.addWidget(self._make_preview_card(), 1)
        rl.addWidget(self._make_bottom_row())
        cols.addWidget(right, 1)

        body_lay.addLayout(cols, 1)
        self._scroll.setWidget(body)
        root.addWidget(self._scroll, 1)

        # Fixed footer
        root.addWidget(self._make_statusbar())

    # ── Title bar ─────────────────────────────────────────────────

    def _make_titlebar(self):
        f = QFrame()
        f.setFixedHeight(52)
        f.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(255,255,255,0.012), stop:1 {T['bg1']});
                border-bottom: 1px solid {T['borderSoft']};
            }}
        """)
        h = QHBoxLayout(f)
        h.setContentsMargins(20, 0, 20, 0)
        brand = QLabel("Agente de Fotos Imobiliárias")
        brand.setStyleSheet(f"font-weight: 700; font-size: 17px; color: {T['text1']};")
        h.addWidget(brand)
        h.addStretch()
        return f

    # ── Top bar ───────────────────────────────────────────────────

    def _make_topbar(self):
        f = QFrame()
        f.setFixedHeight(52)
        f.setStyleSheet(f"QFrame {{ background: {T['bg0']}; border-bottom: 1px solid {T['borderSoft']}; }}")
        h = QHBoxLayout(f)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(4)

        for label, active in [("Processar", True), ("Configurações", False), ("Treinar estilo", False)]:
            btn = QPushButton(label)
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{ color: {T['teal']}; font-weight: 600; font-size: 14px;
                        border: none; border-bottom: 2px solid {T['teal']};
                        padding: 12px 16px; background: transparent; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{ color: {T['text3']}; font-weight: 500; font-size: 14px;
                        border: none; padding: 12px 16px; background: transparent; }}
                    QPushButton:hover {{ color: {T['text2']}; }}
                """)
            h.addWidget(btn)

        h.addStretch()

        # Summary chips
        summary = QFrame()
        summary.setStyleSheet(f"""
            QFrame {{ background: {T['bg2']}; border: 1px solid {T['borderSoft']};
                      border-radius: 12px; }}
        """)
        sh = QHBoxLayout(summary)
        sh.setContentsMargins(6, 6, 6, 6)
        sh.setSpacing(0)

        self._sum = {}
        items = [("intensity", "Intensidade", "Normal"), ("color", "Cor", "Natural"),
                 ("upscale", "Upscale", "2x"), ("preview", "Preview", "Off")]
        for i, (key, lbl_text, val_text) in enumerate(items):
            if i > 0:
                sep = QFrame()
                sep.setFixedSize(1, 28)
                sep.setStyleSheet(f"background: {T['borderSoft']};")
                sh.addWidget(sep)
            wrap = QWidget()
            wrap.setMinimumWidth(80)
            wl = QVBoxLayout(wrap)
            wl.setContentsMargins(12, 2, 12, 2)
            wl.setSpacing(1)
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(f"font-size: 10px; color: {T['text3']}; letter-spacing: 0.5px;")
            lbl.setAlignment(Qt.AlignCenter)
            wl.addWidget(lbl)
            vlbl = QLabel(val_text)
            vlbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {T['text1']};")
            vlbl.setAlignment(Qt.AlignCenter)
            wl.addWidget(vlbl)
            self._sum[key] = vlbl
            sh.addWidget(wrap)

        h.addWidget(summary)
        return f

    # ── Card: Pastas ──────────────────────────────────────────────

    def _make_pastas_card(self):
        card = Card()
        self._card_hdr(card, "Pastas")

        for label, desc, attr in [
            ("Entrada", "Pasta com as fotos originais.", "_input_dir"),
            ("Saída", "Pasta onde o agente salvará tudo.", "_output_dir"),
        ]:
            sc = SubCard()
            t = QLabel(label)
            t.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {T['text1']};")
            sc.lay.addWidget(t)
            d = QLabel(desc)
            d.setStyleSheet(f"font-size: 11.5px; color: {T['text3']};")
            sc.lay.addWidget(d)
            sc.lay.addSpacing(4)
            row = QHBoxLayout()
            row.setSpacing(8)
            le = QLineEdit()
            le.setPlaceholderText("C:\\Fotos\\...")
            setattr(self, attr, le)
            row.addWidget(le, 1)
            b = QPushButton("Procurar")
            b.setStyleSheet(BTN_GHOST)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, w=le: self._browse_dir(w))
            row.addWidget(b)
            sc.lay.addLayout(row)
            card.w(sc)
            card.sp(8)

        # Style
        sc = SubCard()
        t = QLabel("Estilo (opcional)")
        t.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {T['text1']};")
        sc.lay.addWidget(t)
        d = QLabel("Use um perfil .json treinado com o seu estilo.")
        d.setStyleSheet(f"font-size: 11.5px; color: {T['text3']};")
        sc.lay.addWidget(d)
        sc.lay.addSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(8)
        self._style_path = QLineEdit()
        row.addWidget(self._style_path, 1)
        bc = QPushButton("Limpar")
        bc.setStyleSheet(BTN_GHOST)
        bc.setCursor(Qt.PointingHandCursor)
        bc.clicked.connect(lambda: self._style_path.clear())
        row.addWidget(bc)
        bs = QPushButton("Selecionar")
        bs.setStyleSheet(BTN_GHOST)
        bs.setCursor(Qt.PointingHandCursor)
        bs.clicked.connect(self._browse_style)
        row.addWidget(bs)
        sc.lay.addLayout(row)
        card.w(sc)

        return card

    # ── Card: Edição ──────────────────────────────────────────────

    def _make_edition_card(self):
        card = Card()
        self._card_hdr(card, "Edição",
                       "Controle a intensidade e teste o resultado antes do lote completo.")

        row = QHBoxLayout()
        row.setSpacing(20)

        # Intensity
        lv = QVBoxLayout(); lv.setSpacing(4)
        li = QLabel("Intensidade")
        li.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {T['text1']};")
        lv.addWidget(li)
        self._seg_int = SegGroup(["Suave", "Normal", "Forte"], "Normal")
        self._seg_int.changed.connect(self._on_intensity)
        lv.addWidget(self._seg_int)
        ri = QLabel("Recomendado: Normal")
        ri.setStyleSheet(f"font-size: 11px; color: {T['text4']};")
        lv.addWidget(ri)
        row.addLayout(lv, 1)

        # Color mode
        rv = QVBoxLayout(); rv.setSpacing(4)
        lc = QLabel("Modo de Cor")
        lc.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {T['text1']};")
        rv.addWidget(lc)
        self._seg_color = SegGroup(["Natural", "Vibrant", "Luxury"], "Natural")
        self._seg_color.changed.connect(self._on_color_mode)
        rv.addWidget(self._seg_color)
        rc = QLabel("Recomendado: Luxury")
        rc.setStyleSheet(f"font-size: 11px; color: {T['text4']};")
        rv.addWidget(rc)
        row.addLayout(rv, 1)

        card.l(row)
        card.sp(14)

        # Preview toggle
        prow = QHBoxLayout()
        prow.setSpacing(10)
        pl = QLabel("Teste rápido (preview)")
        pl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {T['text1']};")
        prow.addWidget(pl)
        pd = QLabel("Processa miniaturas para visualização rápida.")
        pd.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        prow.addWidget(pd, 1)
        self._tg_preview = Toggle(False)
        self._tg_preview.toggled_signal.connect(self._on_preview)
        prow.addWidget(self._tg_preview)
        card.l(prow)

        return card

    # ── Card: Upscale ─────────────────────────────────────────────

    def _make_upscale_card(self):
        card = Card()
        self._card_hdr(card, "Upscale",
                       "Aumente a resolução das fotos antes das exportações finais.")

        row = QHBoxLayout()
        row.setSpacing(12)
        self._tg_upscale = Toggle(False)
        self._tg_upscale.toggled_signal.connect(self._on_upscale)
        row.addWidget(self._tg_upscale)
        ul = QLabel("Ativar upscale nas fotos")
        ul.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {T['text1']};")
        row.addWidget(ul)
        row.addStretch()
        fl = QLabel("Fator:")
        fl.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        row.addWidget(fl)
        self._seg_factor = SegGroup(["2x", "3x", "4x"], "2x")
        self._seg_factor.changed.connect(self._on_factor)
        row.addWidget(self._seg_factor)
        card.l(row)
        card.sp(6)
        rec = QLabel("Recomendado: 2x. Use 3x ou 4x só quando precisar de arquivos maiores.")
        rec.setStyleSheet(f"font-size: 11.5px; color: {T['text4']};")
        card.w(rec)

        return card

    # ── Actions ───────────────────────────────────────────────────

    def _make_actions(self):
        f = QWidget()
        h = QHBoxLayout(f)
        h.setContentsMargins(0, 4, 0, 0)
        h.setSpacing(12)

        self._btn_process = QPushButton("Processar fotos")
        self._btn_process.setStyleSheet(BTN_PRIMARY)
        self._btn_process.setCursor(Qt.PointingHandCursor)
        self._btn_process.clicked.connect(self._start_processing)
        h.addWidget(self._btn_process, 3)

        self._btn_open = QPushButton("Abrir saída")
        self._btn_open.setStyleSheet(BTN_SECONDARY)
        self._btn_open.setCursor(Qt.PointingHandCursor)
        self._btn_open.clicked.connect(self._open_output_folder)
        h.addWidget(self._btn_open, 2)

        return f

    # ── Preview ───────────────────────────────────────────────────

    def _make_preview_card(self):
        card = Card()

        hdr = QHBoxLayout()
        lh = QVBoxLayout()
        t = QLabel("Prévia")
        t.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {T['text1']};")
        lh.addWidget(t)
        s = QLabel("Compare o resultado antes de processar todas as fotos.")
        s.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        lh.addWidget(s)
        hdr.addLayout(lh, 1)
        bf = QPushButton("Tela cheia")
        bf.setStyleSheet(BTN_GHOST)
        bf.setCursor(Qt.PointingHandCursor)
        hdr.addWidget(bf)
        card.l(hdr)
        card.sp(12)

        pf = QFrame()
        pf.setMinimumHeight(300)
        pf.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pf.setStyleSheet(f"""
            QFrame {{
                background: #000000;
                border-radius: 12px;
                border: 1px solid {T['borderSoft']};
            }}
        """)
        pl = QVBoxLayout(pf)
        plbl = QLabel("Selecione uma pasta e clique em Preview para ver a prévia")
        plbl.setAlignment(Qt.AlignCenter)
        plbl.setStyleSheet(f"color: {T['text4']}; font-size: 13px;")
        pl.addWidget(plbl)
        card.w(pf, 1)

        return card

    # ── Bottom row (status + log) ─────────────────────────────────

    def _make_bottom_row(self):
        f = QWidget()
        f.setMaximumHeight(240)
        h = QHBoxLayout(f)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)

        # Status
        sc = Card()
        self._card_hdr(sc, "Status do processamento",
                       "Acompanhe o andamento em tempo real.")
        sr = QHBoxLayout()
        slv = QVBoxLayout()
        slv.addWidget(self._lbl("Arquivo atual", T['text3'], "12px"))
        self._lbl_file = QLabel("—")
        self._lbl_file.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {T['text1']};"
            f"font-family: Consolas, monospace;"
        )
        slv.addWidget(self._lbl_file)
        sr.addLayout(slv, 1)
        srv = QVBoxLayout()
        srv.setAlignment(Qt.AlignRight)
        srv.addWidget(self._lbl("Progresso", T['text3'], "12px", Qt.AlignRight))
        self._lbl_pct = QLabel("0%")
        self._lbl_pct.setAlignment(Qt.AlignRight)
        self._lbl_pct.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {T['text1']};"
            f"font-family: Consolas, monospace;"
        )
        srv.addWidget(self._lbl_pct)
        sr.addLayout(srv)
        sc.l(sr)
        sc.sp(8)
        self._prog = QProgressBar()
        self._prog.setRange(0, 1000)
        self._prog.setValue(0)
        self._prog.setTextVisible(False)
        sc.w(self._prog)
        sc.sp(8)
        self._lbl_foot = QLabel("Pronto para processar.")
        self._lbl_foot.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        self._lbl_foot.setWordWrap(True)
        sc.w(self._lbl_foot)
        h.addWidget(sc, 1)

        # Log
        lc = Card()
        self._card_hdr(lc, "Log de atividades",
                       "Mensagens do processamento, erros e eventos.")
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        lc.w(self._log, 1)
        h.addWidget(lc, 1)

        return f

    # ── Status bar ────────────────────────────────────────────────

    def _make_statusbar(self):
        f = QFrame()
        f.setFixedHeight(36)
        f.setStyleSheet(f"""
            QFrame {{ background: {T['bg1']}; border-top: 1px solid {T['borderSoft']}; }}
        """)
        h = QHBoxLayout(f)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(10)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {T['green']}; font-size: 9px;")
        h.addWidget(dot)
        self._sb_status = QLabel("Pronto para processar")
        self._sb_status.setStyleSheet(f"font-size: 12px; color: {T['text2']};")
        h.addWidget(self._sb_status)
        sep = QFrame(); sep.setFixedSize(1, 12)
        sep.setStyleSheet(f"background: {T['border']};")
        h.addWidget(sep)
        self._sb_count = QLabel("0 fotos na fila")
        self._sb_count.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        h.addWidget(self._sb_count)
        h.addStretch()
        tips = QLabel("Dicas e boas práticas")
        tips.setStyleSheet(f"font-size: 12px; color: {T['text3']};")
        h.addWidget(tips)
        return f

    # ── Helpers ────────────────────────────────────────────────────

    def _card_hdr(self, card, title, sub=None):
        t = QLabel(title)
        t.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {T['text1']};")
        card.w(t)
        if sub:
            s = QLabel(sub)
            s.setStyleSheet(f"font-size: 12px; color: {T['text3']}; padding-bottom: 4px;")
            s.setWordWrap(True)
            card.w(s)
        card.sp(10)

    def _lbl(self, text, color, size="13px", align=None):
        l = QLabel(text)
        l.setStyleSheet(f"font-size: {size}; color: {color};")
        if align: l.setAlignment(align)
        return l

    def _update_summary(self):
        self._sum["intensity"].setText(self._intensity.capitalize())
        self._sum["color"].setText(self._color_mode.capitalize())
        self._sum["upscale"].setText(self._upscale_factor if self._upscale_enabled else "Off")
        self._sum["preview"].setText("Ligado" if self._preview_mode else "Off")

    # ══════════════════════════════════════════════════════════════
    #  HANDLERS (preservados)
    # ══════════════════════════════════════════════════════════════

    def _browse_dir(self, le):
        p = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if p: le.setText(p)

    def _browse_style(self):
        p, _ = QFileDialog.getOpenFileName(self, "Perfil de estilo", "", "JSON (*.json)")
        if p: self._style_path.setText(p)

    def _on_intensity(self, v):
        self._intensity = v.lower()
        self._update_summary()

    def _on_color_mode(self, v):
        self._color_mode = v.lower()
        self._update_summary()

    def _on_preview(self, v):
        self._preview_mode = v
        self._update_summary()

    def _on_upscale(self, v):
        self._upscale_enabled = v
        self._update_summary()

    def _on_factor(self, v):
        self._upscale_factor = v
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
        self._log.clear()
        self._prog.setValue(0)
        self._lbl_pct.setText("0%")
        self._lbl_file.setText("—")
        self._btn_process.setEnabled(False)

        style_path = self._style_path.text().strip() or None
        opts = self._collect_options()

        def cb(msg, pct):
            self._bridge.progress.emit(msg, pct)

        self.pipeline = ProcessingPipeline(inp, out, cb,
                                            style_profile_path=style_path, options=opts)
        self.pipeline.start()

    def _update_ui(self, msg, pct):
        self._prog.setValue(int(pct * 1000))
        self._lbl_pct.setText(f"{int(pct * 100)}%")
        if "]" in msg:
            parts = msg.split("]", 1)
            if len(parts) > 1:
                self._lbl_file.setText(parts[1].strip())
                self._lbl_foot.setText(f"Processados: {parts[0].replace('[', '')} fotos")
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f'<span style="color:{T["text3"]}">{ts}</span>  {msg}')
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
        self.show()
        QApplication.instance().exec()
