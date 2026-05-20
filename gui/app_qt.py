"""
GUI PySide6 — v26: fluxo automatizado estilo Lightroom, sem controles manuais na tela principal.

Objetivo desta versão:
- manter o motor Python atual intacto;
- trocar a experiência principal para um fluxo de automação;
- preview antes/depois funcional ao selecionar pasta/imagem;
- filmstrip/lista de fotos;
- painel direito simples com Preset, Intensidade, Cor, Bracketing/HDR, Upscale e Exportação;
- controles avançados recolhidos por padrão.
"""

from __future__ import annotations

import os
import sys
import json
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QSystemTrayIcon,
    QWidget,
)
from PySide6.QtCore import QByteArray, QPoint, QRect, QSize, Qt, QObject, Signal, QTimer, QUrl
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QImageReader,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QTextCursor,
)
from PySide6.QtSvg import QSvgRenderer

from core.pipeline import ProcessingPipeline
from core.style_trainer import StyleTrainer
from core.styled_enhancer import StyledEnhancer
from core.classifier_trainer import ClassifierTrainer
from core.raw_support import RAW_EXTENSIONS, RawSupportError, is_raw_file, read_raw_preview_rgb, convert_raw_to_jpeg
from core.hdr_trainer import HdrBracketTrainer, find_bracket_images
from core.bracketing import BracketingProcessor


# ──────────────────────────────────────────────────────────────────────────────
# Design tokens
# ──────────────────────────────────────────────────────────────────────────────
T = {
    "bg0": "#07111D",
    "bg1": "#0B1524",
    "bg2": "#101B2C",
    "bg3": "#142235",
    "bg4": "#182A42",
    "border": "#22324A",
    "borderSoft": "#1A2940",
    "text1": "#E6EDF5",
    "text2": "#B7C2D2",
    "text3": "#7E8DA3",
    "text4": "#5A6678",
    "teal": "#1FD1A8",
    "teal2": "#14B894",
    "tealDark": "#06352C",
    "green": "#22C58A",
    "purple": "#A78BFA",
    "danger": "#EF4D5C",
}

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".cr3", ".cr2", ".nef", ".arw", ".dng", ".raf", ".rw2", ".orf")

_SETTINGS_PATH = Path.home() / ".agente_fotos_settings.json"
_PRESETS_PATH  = Path.home() / ".agente_fotos_presets.json"
_HISTORY_PATH  = Path.home() / ".agente_fotos_history.json"
_NOTES_PATH    = Path.home() / ".agente_fotos_notes.json"
_HISTORY_MAX   = 50


# ──────────────────────────────────────────────────────────────────────────────
# Icons via SVG inline
# ──────────────────────────────────────────────────────────────────────────────
def _svg_icon(svg: str, size: int = 18, color: str | None = None) -> QIcon:
    if color:
        svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
        svg = svg.replace('fill="currentColor"', f'fill="{color}"')
    data = QByteArray(svg.encode("utf-8"))
    renderer = QSvgRenderer(data)
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    renderer.render(painter)
    painter.end()
    return QIcon(px)


class Icons:
    @staticmethod
    def home(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M3 10.5 12 3l9 7.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 9.8V20h5v-6h4v6h5V9.8" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def grid(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.7"/><rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.7"/><rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.7"/><path d="M14 17.5h7M17.5 14v7" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>', color=c)

    @staticmethod
    def folder(c=T["text2"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def settings(c=T["text3"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.7"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.8 1.2V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1A1.7 1.7 0 0 0 4.6 9 1.7 1.7 0 0 0 4.3 7.2l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" stroke="currentColor" stroke-width="1.5"/></svg>', color=c)

    @staticmethod
    def star(c=T["text3"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="m12 2 3 6.9 7.5.7-5.7 5L18.5 22 12 18.3 5.5 22l1.7-7.4L1.5 9.6 9 8.9 12 2z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def eye(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.7"/></svg>', color=c)

    @staticmethod
    def activity(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def upscale(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.7"/></svg>', color=c)

    @staticmethod
    def palette(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M12 3a9 9 0 1 0 0 18c1 0 1.5-.5 1.5-1.3 0-.9-.7-1-.7-1.7 0-.7.6-1 1.5-1H16a5 5 0 0 0 5-5 8 8 0 0 0-9-9z" stroke="currentColor" stroke-width="1.7"/></svg>', color=c)

    @staticmethod
    def play(c="#03261C"):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M8 5v14l11-7L8 5z" fill="currentColor"/></svg>', color=c)

    @staticmethod
    def import_icon(c=T["text1"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M12 3v12M7 8l5-5 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 15v4h14v-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def close(c=T["text2"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>', color=c)

    @staticmethod
    def min(c=T["text2"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M5 12h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>', color=c)

    @staticmethod
    def max(c=T["text2"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><rect x="6" y="6" width="12" height="12" rx="1.5" stroke="currentColor" stroke-width="1.7"/></svg>', color=c)

    @staticmethod
    def tune(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><circle cx="15" cy="6" r="2" stroke="currentColor" stroke-width="1.7"/><circle cx="9" cy="12" r="2" stroke="currentColor" stroke-width="1.7"/><circle cx="17" cy="18" r="2" stroke="currentColor" stroke-width="1.7"/></svg>', color=c)

    @staticmethod
    def bookmark(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M5 3h14a1 1 0 0 1 1 1v17l-8-4-8 4V4a1 1 0 0 1 1-1z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def pdf(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M14 3v6h6" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M8 13h1.5a1.5 1.5 0 0 1 0 3H8v-5h1.5M13 11v5M13 14h2M16 11v5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def plus(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>', color=c)

    @staticmethod
    def refresh(c=T["text2"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M3 12a9 9 0 0 1 15.5-6.3M21 5v4h-4M21 12a9 9 0 0 1-15.5 6.3M3 19v-4h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def bolt(c=T["teal"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def chevron_down(c=T["text2"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def chevron_up(c=T["text2"]):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M6 15l6-6 6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', color=c)


# ──────────────────────────────────────────────────────────────────────────────
# QSS helpers
# ──────────────────────────────────────────────────────────────────────────────
def button_qss(bg, color, border="none", hover=None, radius=12, weight=600, height=38):
    hover = hover or bg
    return f"""
    QPushButton {{
        background: {bg}; color: {color}; border: {border}; border-radius: {radius}px;
        font-size: 13px; font-weight: {weight}; min-height: {height}px; padding: 0 14px;
    }}
    QPushButton:hover {{ background: {hover}; }}
    QPushButton:pressed {{ background: {T['teal2']}; }}
    QPushButton:disabled {{ background: {T['bg3']}; color: {T['text4']}; }}
    """

BTN_PRIMARY = button_qss(T["teal"], "#03261C", hover="#2DE0B6", radius=13, weight=800, height=50)
BTN_SECONDARY = button_qss(T["bg3"], T["text1"], f"1px solid {T['border']}", hover=T["bg4"], radius=13, height=50)
BTN_GHOST = button_qss(T["bg3"], T["text2"], f"1px solid {T['borderSoft']}", hover=T["bg4"], radius=10, height=34)
BTN_FLAT = button_qss("transparent", T["text3"], "none", hover=T["bg2"], radius=10, height=36)

GLOBAL_QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; }}
QMainWindow {{ background: {T['bg0']}; color: {T['text1']}; }}
QWidget {{ color: {T['text1']}; }}
QLabel {{ color: {T['text1']}; background: transparent; border: none; }}
QFrame {{ background: transparent; }}
QLineEdit {{
    background: {T['bg0']}; border: 1px solid {T['border']}; border-radius: 10px;
    padding: 8px 12px; color: {T['text2']}; font-family: 'Consolas', monospace; font-size: 12.5px;
}}
QLineEdit:focus {{ border-color: {T['teal']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {T['bg3']}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {T['bg4']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: {T['bg3']}; border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; width: 0; }}
QTextEdit {{
    background: {T['bg2']}; border: 1px solid {T['borderSoft']}; border-radius: 12px;
    color: {T['text2']}; font-family: 'Consolas', monospace; font-size: 12px; padding: 10px;
}}
QProgressBar {{ background: {T['bg3']}; border: none; border-radius: 5px; min-height: 10px; max-height: 10px; }}
QProgressBar::chunk {{ background: {T['teal']}; border-radius: 5px; }}
"""


def seg_qss(active: bool) -> str:
    if active:
        return button_qss(T["teal"], "#03261C", hover="#2DE0B6", radius=9, weight=700, height=34)
    return button_qss(T["bg0"], T["text2"], f"1px solid {T['borderSoft']}", hover=T["bg2"], radius=9, weight=500, height=34)


# ──────────────────────────────────────────────────────────────────────────────
# Signal bridge
# ──────────────────────────────────────────────────────────────────────────────
class ProgressBridge(QObject):
    progress = Signal(str, float)


class TrainBridge(QObject):
    done = Signal(object)
    error = Signal(str)
    status = Signal(str)


class PreviewBridge(QObject):
    preview_ready = Signal(str, str)  # (original_path, enhanced_temp_path)


class QualityBridge(QObject):
    issue = Signal(str, str)  # (image_path, issue_description)


class PixmapBridge(QObject):
    loaded = Signal(str, object)  # (path, QPixmap)


# ──────────────────────────────────────────────────────────────────────────────
# Reusable widgets
# ──────────────────────────────────────────────────────────────────────────────
class Card(QFrame):
    def __init__(self, parent=None, padding=(16, 14, 16, 14), shadow=True):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(T["bg1"]))
        self.setPalette(pal)
        self.setStyleSheet(f"#Card {{ border: 1px solid {T['borderSoft']}; border-radius: 14px; background: {T['bg1']}; }} #Card QLabel {{ background: transparent; }}")
        if shadow:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(24)
            effect.setOffset(0, 8)
            effect.setColor(QColor(0, 0, 0, 48))
            self.setGraphicsEffect(effect)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(*padding)
        self.lay.setSpacing(10)

    def add(self, widget, stretch=0):
        self.lay.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout, stretch=0):
        self.lay.addLayout(layout, stretch)
        return layout


class Toggle(QPushButton):
    toggled_signal = Signal(bool)

    def __init__(self, on=False, parent=None):
        super().__init__(parent)
        self._on = bool(on)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._flip)
        self._refresh()

    def _flip(self):
        self._on = not self._on
        self._refresh()
        self.toggled_signal.emit(self._on)

    def set_state(self, state: bool, emit=False):
        self._on = bool(state)
        self._refresh()
        if emit:
            self.toggled_signal.emit(self._on)

    def isChecked(self):
        return self._on

    def _refresh(self):
        bg = T["teal"] if self._on else T["bg3"]
        self.setStyleSheet(f"QPushButton {{ background:{bg}; border:none; border-radius:12px; }}")

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(22 if self._on else 2, 2, 20, 20)
        p.end()


class SegGroup(QWidget):
    changed = Signal(str)

    def __init__(self, options, current=None, min_button_width=78, equal=True, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self._value = current or options[0]
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        for option in options:
            btn = QPushButton(option)
            btn.setCursor(Qt.PointingHandCursor)
            natural = btn.fontMetrics().horizontalAdvance(option) + 34
            btn.setMinimumWidth(max(min_button_width, natural))
            btn.setFixedHeight(36)
            btn.setSizePolicy(QSizePolicy.Expanding if equal else QSizePolicy.Minimum, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _, v=option: self.select(v))
            lay.addWidget(btn, 1 if equal else 0)
            self._buttons[option] = btn
        self.select(self._value, emit=False)

    def select(self, value, emit=True):
        self._value = value
        for option, btn in self._buttons.items():
            btn.setStyleSheet(seg_qss(option == value))
        if emit:
            self.changed.emit(value)

    def value(self):
        return self._value


class TitleBar(QFrame):
    def __init__(self, parent_window: QMainWindow):
        super().__init__(parent_window)
        self._window = parent_window
        self._drag_pos = None
        self.setFixedHeight(44)
        self.setObjectName("TitleBar")
        self.setStyleSheet(f"#TitleBar {{ background:{T['bg0']}; border-bottom:1px solid {T['borderSoft']}; }}")
        h = QHBoxLayout(self)
        h.setContentsMargins(18, 0, 10, 0)
        h.setSpacing(10)

        icon = QLabel()
        icon.setPixmap(Icons.home(T["teal"]).pixmap(24, 24))
        icon.setFixedSize(28, 28)
        h.addWidget(icon)

        title = QLabel("Agente de Fotos Imobiliárias")
        title.setStyleSheet(f"font-size:16px;font-weight:800;color:{T['text1']};")
        h.addWidget(title)
        h.addStretch()

        for icon_fn, cb in [
            (Icons.min, self._window.showMinimized),
            (Icons.max, self._toggle_max),
            (Icons.close, self._window.close),
        ]:
            b = QPushButton(icon_fn(), "")
            b.setFixedSize(34, 30)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(BTN_FLAT)
            b.clicked.connect(cb)
            h.addWidget(b)

    def _toggle_max(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton and not self._window.isMaximized():
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle_max()


class CompareView(QWidget):
    """Preview antes/depois com divisor arrastável."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._before = None
        self._after = None
        self._split = 0.5
        self._dragging = False
        self.setMinimumHeight(420)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.SizeHorCursor)
        self._generate_placeholder()

    def _generate_placeholder(self):
        w, h = 1200, 760
        self._before = self._placeholder_pixmap(w, h, "ANTES", QColor("#1B2038"), QColor("#132B47"))
        self._after = self._placeholder_pixmap(w, h, "DEPOIS", QColor("#16375B"), QColor("#1A2038"))

    def _placeholder_pixmap(self, w, h, label, c1, c2):
        px = QPixmap(w, h)
        p = QPainter(px)
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        p.fillRect(0, 0, w, h, grad)
        p.setPen(QColor(230, 237, 245, 92))
        p.setFont(QFont("Segoe UI", 24, QFont.Bold))
        p.drawText(QRect(0, h // 2 - 60, w, 60), Qt.AlignCenter, f"[ {label} ]")
        p.setFont(QFont("Segoe UI", 17))
        p.drawText(QRect(0, h // 2, w, 80), Qt.AlignCenter, "Selecione uma pasta ou clique em uma miniatura")
        p.end()
        return px

    def set_images_from_pixmaps(self, before: QPixmap, after: QPixmap):
        if before and not before.isNull() and after and not after.isNull():
            self._before = before
            self._after = after
            self._split = 0.5
            self.update()

    def paintEvent(self, event):
        if not self._before or not self._after:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        split_x = int(w * self._split)

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 14, 14)
        p.setClipPath(path)

        before = self._before.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        bx = max(0, (before.width() - w) // 2)
        by = max(0, (before.height() - h) // 2)
        p.drawPixmap(0, 0, before, bx, by, w, h)

        p.save()
        p.setClipRect(split_x, 0, w - split_x, h)
        after = self._after.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        ax = max(0, (after.width() - w) // 2)
        ay = max(0, (after.height() - h) // 2)
        p.drawPixmap(0, 0, after, ax, ay, w, h)
        p.restore()
        p.setClipPath(path)

        # subtle vignette
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(0, 0, 0, 60))
        grad.setColorAt(0.3, QColor(0, 0, 0, 0))
        grad.setColorAt(1, QColor(0, 0, 0, 70))
        p.fillRect(0, 0, w, h, grad)

        # corner markers
        p.setPen(QPen(QColor(255, 255, 255, 130), 1.5))
        m, sz = 12, 16
        for x, y, dx, dy in [
            (m, m, sz, 0), (m, m, 0, sz),
            (w - m, m, -sz, 0), (w - m, m, 0, sz),
            (m, h - m, sz, 0), (m, h - m, 0, -sz),
            (w - m, h - m, -sz, 0), (w - m, h - m, 0, -sz),
        ]:
            p.drawLine(x, y, x + dx, y + dy)

        # divider + handle
        p.setPen(QPen(QColor(255, 255, 255, 210), 2))
        p.drawLine(split_x, 0, split_x, h)
        cy = h // 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(31, 209, 168, 56))
        p.drawEllipse(QPoint(split_x, cy), 26, 26)
        p.setBrush(QColor(T["teal"]))
        p.drawEllipse(QPoint(split_x, cy), 20, 20)
        p.setPen(QPen(QColor("#03261C"), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(split_x - 7, cy, split_x - 2, cy - 5)
        p.drawLine(split_x - 7, cy, split_x - 2, cy + 5)
        p.drawLine(split_x + 7, cy, split_x + 2, cy - 5)
        p.drawLine(split_x + 7, cy, split_x + 2, cy + 5)

        self._draw_pill(p, "Antes", 16, 16, False)
        self._draw_pill(p, "Depois", w - 92, 16, True)
        p.end()

    def _draw_pill(self, p: QPainter, text: str, x: int, y: int, after: bool):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(11, 18, 32, 190))
        p.drawRoundedRect(x, y, 76, 28, 14, 14)
        p.setBrush(QColor(T["teal"] if after else T["text3"]))
        p.drawEllipse(QPoint(x + (58 if after else 12), y + 14), 3, 3)
        p.setPen(QColor(T["text1"]))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(x + (10 if after else 22), y + 19, text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._update_split(event.position().x())

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._update_split(event.position().x())

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def _update_split(self, x):
        if self.width() > 0:
            self._split = max(0.06, min(0.94, x / self.width()))
            self.update()


class ThumbCard(QFrame):
    clicked = Signal(str)

    def __init__(self, image_path: str, pixmap: QPixmap | None, selected=False, parent=None):
        super().__init__(parent)
        self.path = image_path
        self._selected = selected
        self._warn: str = ""
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(148, 112)
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignCenter)
        self._img.setFixedHeight(72)
        if pixmap and not pixmap.isNull():
            self._img.setPixmap(pixmap.scaled(140, 72, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        self._name = QLabel(os.path.basename(image_path))
        self._name.setAlignment(Qt.AlignCenter)
        self._name.setStyleSheet(f"font-size:10.5px;color:{T['text2']};")
        self._name.setToolTip(image_path)
        self._warn_lbl = QLabel()
        self._warn_lbl.setAlignment(Qt.AlignCenter)
        self._warn_lbl.setStyleSheet("font-size:9px;color:#F59E0B;background:transparent;")
        self._warn_lbl.setFixedHeight(13)
        self._warn_lbl.hide()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        lay.addWidget(self._img)
        lay.addWidget(self._name)
        lay.addWidget(self._warn_lbl)
        self._refresh_style()

    def set_pixmap(self, pixmap: QPixmap):
        if pixmap and not pixmap.isNull():
            self._img.setPixmap(pixmap.scaled(140, 72, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def set_selected(self, selected: bool):
        self._selected = selected
        self._refresh_style()

    def set_warning(self, text: str):
        self._warn = text
        if text:
            self._warn_lbl.setText(f"⚠ {text}")
            self._warn_lbl.show()
            self.setToolTip(f"⚠ {text}")
        else:
            self._warn_lbl.hide()
            self.setToolTip("")
        self._refresh_style()

    def _refresh_style(self):
        if self._selected:
            border, bg = T["teal"], T["bg3"]
        elif self._warn:
            border, bg = "#F59E0B", T["bg2"]
        else:
            border, bg = T["borderSoft"], T["bg2"]
        self.setStyleSheet(f"QFrame {{ background:{bg}; border:1px solid {border}; border-radius:10px; }} QLabel {{ border:none; background:transparent; }}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.path)


class QueueItem(QFrame):
    clicked = Signal(str)

    def __init__(self, image_path: str, pixmap: QPixmap | None, selected=False, parent=None):
        super().__init__(parent)
        self.path = image_path
        self._selected = selected
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(64)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)
        self._thumb = QLabel()
        self._thumb.setFixedSize(54, 40)
        self._thumb.setAlignment(Qt.AlignCenter)
        if pixmap and not pixmap.isNull():
            self._thumb.setPixmap(pixmap.scaled(54, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        lay.addWidget(self._thumb)
        col = QVBoxLayout()
        name = QLabel(os.path.basename(image_path))
        name.setStyleSheet(f"font-size:12px;font-weight:700;color:{T['text1']};")
        status = QLabel("● Pronto para processar")
        status.setStyleSheet(f"font-size:11px;color:{T['teal']};")
        col.addWidget(name)
        col.addWidget(status)
        lay.addLayout(col, 1)
        self._refresh_style()

    def set_pixmap(self, pixmap: QPixmap):
        if pixmap and not pixmap.isNull():
            self._thumb.setPixmap(pixmap.scaled(54, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def set_selected(self, selected: bool):
        self._selected = selected
        self._refresh_style()

    def _refresh_style(self):
        border = T["teal"] if self._selected else T["borderSoft"]
        bg = T["bg3"] if self._selected else T["bg2"]
        self.setStyleSheet(f"QFrame {{ background:{bg}; border:1px solid {border}; border-radius:10px; }} QLabel {{ border:none; background:transparent; }}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.path)


# ──────────────────────────────────────────────────────────────────────────────
# Image preview helpers
# ──────────────────────────────────────────────────────────────────────────────
def enhanced_preview(source: QPixmap, max_size=900) -> QPixmap | None:
    if source is None or source.isNull():
        return None
    scaled = source.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    try:
        import numpy as np
        img = scaled.toImage().convertToFormat(QImage.Format_ARGB32)
        w, h = img.width(), img.height()
        ptr = img.bits()
        ptr.setsize(h * w * 4)
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 4)).copy()
        b = arr[:, :, 0].astype(np.float32)
        g = arr[:, :, 1].astype(np.float32)
        r = arr[:, :, 2].astype(np.float32)
        # Premium real-estate temporary preview: brighten, protect highlights a bit, enhance saturation.
        r = 128 + (r * 1.12 - 128) * 1.08
        g = 128 + (g * 1.12 - 128) * 1.08
        b = 128 + (b * 1.12 - 128) * 1.08
        gray = 0.299 * r + 0.587 * g + 0.114 * b
        r = gray + (r - gray) * 1.07
        g = gray + (g - gray) * 1.07
        b = gray + (b - gray) * 1.07
        arr[:, :, 0] = np.clip(b, 0, 255).astype(np.uint8)
        arr[:, :, 1] = np.clip(g, 0, 255).astype(np.uint8)
        arr[:, :, 2] = np.clip(r, 0, 255).astype(np.uint8)
        result = QImage(arr.data, w, h, w * 4, QImage.Format_ARGB32).copy()
        return QPixmap.fromImage(result)
    except Exception:
        # Safe fallback: return same image if numpy is not available.
        return scaled


# ──────────────────────────────────────────────────────────────────────────────
# Main app
# ──────────────────────────────────────────────────────────────────────────────
class PhotoAgentApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agente de Fotos Imobiliárias")
        self.resize(1480, 930)
        self.setMinimumSize(1180, 760)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setStyleSheet(GLOBAL_QSS)

        self.pipeline = None
        self._bridge = ProgressBridge()
        self._bridge.progress.connect(self._update_ui)
        self._train_bridge = TrainBridge()
        self._train_bridge.done.connect(self._on_train_done)
        self._train_bridge.error.connect(self._on_train_error)
        self._train_bridge.status.connect(self._set_train_status)

        self._image_paths: list[str] = []
        self._selected_image: str | None = None
        self._thumb_cards: list[ThumbCard] = []
        self._queue_items: list[QueueItem] = []
        # HDR preview: mapa base_path → [todas as paths do grupo]
        self._bracket_groups: dict[str, list[str]] = {}
        self._hdr_preview_loading = False

        # Automation defaults
        self._automation_preset = "Luxury Real Estate"
        self._intensity = "normal"
        self._color_mode = "luxury"
        self._bracketing_enabled = False
        self._bracketing_group_size = "3"
        self._bracketing_fusion_preset = "lightroom_like"
        self._bracketing_apply_auto_enhance = False
        self._upscale_enabled = False
        self._upscale_factor = "2x"
        self._subfolder_recursive = False
        self._preview_available = False

        # Item 1 — Rename & Watermark
        self._rename_enabled = False
        self._rename_prefix = "IMOVEL"
        self._rename_code = ""
        self._watermark_enabled = False
        self._watermark_mode = "text"
        self._watermark_text = ""
        self._watermark_logo_path = ""
        self._watermark_position = "bottom-right"
        self._watermark_opacity = 0.4

        # Item 3 — Gallery & EXIF
        self._gallery_title = "Galeria de Fotos"
        self._gallery_subtitle = ""
        self._photographer = ""
        self._copyright_text = ""

        # Item 2 — Classifier labeling
        self._clf_label = "interior"
        self.classifier_trainer = ClassifierTrainer()

        # Nível 5 — Export profiles & upscale preset
        self._export_profiles: set[str] = {"alta_qualidade", "instagram", "whatsapp"}
        self._upscale_preset = "natural_pro"

        # Nível 4 — Settings tab
        self._duplicates_enabled = True
        self._duplicates_threshold = 10
        self._contact_sheet_enabled = False
        self._before_after_enabled = False
        self._classifier_profile_path = ""

        # Nível 8.3 — threads de processamento paralelo (0 = auto)
        self._max_workers: int = 0

        # Nível 6.1 — multi-folder queue
        self._folder_queue: list[str] = []
        self._batch_folders: list[str] = []
        self._current_batch_idx: int = 0
        self._is_batch_processing: bool = False

        # Nível 6.3 — preset manager
        self._presets: dict[str, dict] = {}
        self._load_presets_from_disk()

        # Nível 7.1 — histórico
        self._history: list[dict] = []
        self._load_history_from_disk()

        # Nível 7.3 — comparação pós-processamento
        self._compare_mode: bool = False
        self._results_map: dict[str, str] = {}  # processed_path → original_path
        self._current_run_files: list[str] = []   # arquivos do processamento atual
        self._current_run_map: dict[str, str] = {}  # enhanced → original (atual)
        self._run_start_time: float = 0.0  # epoch do início do último run

        # Nível 6.4 — real-time preview
        self._preview_bridge = PreviewBridge()
        self._preview_bridge.preview_ready.connect(self._on_preview_ready)
        self._preview_loading: bool = False
        self._quality_bridge = QualityBridge()
        self._quality_bridge.issue.connect(self._on_quality_issue)
        self._pixmap_bridge = PixmapBridge()
        self._pixmap_bridge.loaded.connect(self._on_pixmap_loaded)
        self._image_classifications: dict[str, str] = {}
        self._filmstrip_filter: str | None = None
        self._sample_paths: list | None = None
        self._photo_notes: dict[str, str] = self._load_notes()

        # Style training state
        self.train_pairs: list[dict[str, str]] = []
        self.hdr_train_groups: list[dict[str, object]] = []

        self.setAcceptDrops(True)
        self._build_ui()
        self._update_summary()
        self._load_settings()
        self._setup_tray()

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if event.modifiers() == Qt.NoModifier:
            if key == Qt.Key_Space:
                if hasattr(self, "_btn_preview") and self._btn_preview.isEnabled():
                    self._btn_preview.click()
                    return
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                if hasattr(self, "_btn_proc") and self._btn_proc.isEnabled():
                    self._btn_proc.click()
                    return
        super().keyPressEvent(event)

    def _save_log(self):
        text = self._log.toPlainText()
        if not text.strip():
            return
        default = str(Path.home() / f"agente_fotos_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        path, _ = QFileDialog.getSaveFileName(self, "Salvar log", default, "Texto (*.txt)")
        if path:
            try:
                Path(path).write_text(text, encoding="utf-8")
            except OSError as e:
                QMessageBox.critical(self, "Erro ao salvar", str(e))

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_windows_dark_titlebar()

    def _apply_windows_dark_titlebar(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            value = ctypes.c_int(1)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    # ── System tray (7.4) ─────────────────────────────────────────
    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = None
            return
        px = QPixmap(32, 32)
        px.fill(QColor(T["teal"]))
        p = QPainter(px)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#03261C"))
        p.drawEllipse(8, 8, 16, 16)
        p.end()
        self._tray = QSystemTrayIcon(QIcon(px), self)
        self._tray.setToolTip("Agente de Fotos Imobiliárias")
        self._tray.show()

    def _notify_done(self, processed: int, errors: int):
        if not getattr(self, "_tray", None):
            return
        icon = QSystemTrayIcon.MessageIcon.Warning if errors else QSystemTrayIcon.MessageIcon.Information
        msg = f"{processed} foto(s) processada(s)"
        if errors:
            msg += f" · {errors} erro(s)"
        self._tray.showMessage("Agente de Fotos — Concluído", msg, icon, 5000)

    # ── Drag & drop (7.2) ─────────────────────────────────────────
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            dirs = [u.toLocalFile() for u in event.mimeData().urls()
                    if os.path.isdir(u.toLocalFile())]
            if dirs:
                event.acceptProposedAction()
                n = len(dirs)
                self._sb_st.setText(f"Solte para adicionar {n} pasta{'s' if n > 1 else ''} à fila")
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._sb_st.setText("Pronto")

    def dropEvent(self, event):
        dirs = [u.toLocalFile() for u in event.mimeData().urls()
                if os.path.isdir(u.toLocalFile())]
        if not dirs:
            event.ignore()
            return
        event.acceptProposedAction()
        queue_was_empty = len(self._folder_queue) == 0
        added = 0
        for d in dirs:
            if d not in self._folder_queue:
                self._folder_queue.append(d)
                added += 1
        self._refresh_folder_list_ui()
        if queue_was_empty and self._folder_queue:
            first = self._folder_queue[0]
            self._input_dir.setText(first)
            self._load_images_from_folder(first, show_feedback=True)
        total = len(self._folder_queue)
        self._sb_st.setText(
            f"{added} pasta{'s' if added > 1 else ''} adicionada{'s' if added > 1 else ''}  ·  {total} na fila"
        )

    # ── UI construction ───────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        central.setAutoFillBackground(True)
        pal = central.palette()
        pal.setColor(QPalette.Window, QColor(T["bg0"]))
        central.setPalette(pal)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(TitleBar(self))
        root.addWidget(self._mk_navbar())
        root.addWidget(self._mk_content_stack(), 1)
        root.addWidget(self._mk_bottom_bar())

    def _mk_navbar(self):
        f = QFrame()
        f.setObjectName("NavBar")
        f.setFixedHeight(58)
        f.setStyleSheet(f"#NavBar {{ background:{T['bg0']}; border-bottom:1px solid {T['borderSoft']}; }}")
        h = QHBoxLayout(f)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(10)

        self._nav_buttons = []
        tabs = [
            ("Processar", Icons.grid(T["teal"]), 0),
            ("Configurações", Icons.settings(T["text3"]), 1),
            ("Treinar estilo", Icons.star(T["text3"]), 2),
            ("Histórico", Icons.activity(T["text3"]), 3),
        ]
        for label, icon, idx in tabs:
            b = QPushButton(icon, f" {label}")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, i=idx: self._switch_tab(i))
            h.addWidget(b)
            self._nav_buttons.append(b)
        h.addStretch()
        h.addWidget(self._mk_summary_chips())
        self._refresh_nav(0)
        return f

    def _nav_qss(self, active: bool) -> str:
        if active:
            return f"QPushButton {{ color:{T['teal']}; border:none; border-bottom:2px solid {T['teal']}; background:transparent; font-size:14px; font-weight:700; min-height:54px; padding:0 14px; }}"
        return f"QPushButton {{ color:{T['text3']}; border:none; background:transparent; font-size:14px; font-weight:500; min-height:54px; padding:0 14px; }} QPushButton:hover {{ color:{T['text2']}; }}"

    def _refresh_nav(self, active_idx: int):
        for idx, b in enumerate(getattr(self, "_nav_buttons", [])):
            b.setStyleSheet(self._nav_qss(idx == active_idx))

    def _switch_tab(self, idx: int):
        if hasattr(self, "_stack"):
            self._stack.setCurrentIndex(idx)
        self._refresh_nav(idx)

    def _mk_summary_chips(self):
        f = QFrame()
        f.setObjectName("Summary")
        f.setStyleSheet(f"#Summary {{ background:{T['bg2']}; border:1px solid {T['borderSoft']}; border-radius:14px; }}")
        lay = QHBoxLayout(f)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(0)
        self._sum = {}
        specs = [
            ("intensity", "Intensidade", "Normal", Icons.activity()),
            ("color", "Cor", "Luxury", Icons.palette()),
            ("upscale", "Upscale", "2x", Icons.upscale()),
            ("preview", "Preview", "Off", Icons.eye()),
        ]
        for idx, (key, label, value, icon) in enumerate(specs):
            if idx:
                sep = QFrame()
                sep.setFixedSize(1, 30)
                sep.setStyleSheet(f"background:{T['borderSoft']};")
                lay.addWidget(sep)
            wrap = QWidget()
            wrap.setMinimumWidth(96)
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(10, 0, 10, 0)
            wl.setSpacing(8)
            ic = QLabel()
            ic.setPixmap(icon.pixmap(16, 16))
            ic.setFixedSize(16, 16)
            wl.addWidget(ic)
            col = QVBoxLayout()
            col.setSpacing(0)
            lab = QLabel(label)
            lab.setStyleSheet(f"font-size:10px;color:{T['text3']};")
            val = QLabel(value)
            val.setStyleSheet(f"font-size:13px;font-weight:800;color:{T['text1']};")
            col.addWidget(lab)
            col.addWidget(val)
            self._sum[key] = val
            wl.addLayout(col)
            lay.addWidget(wrap)
        return f

    def _mk_content_stack(self):
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{T['bg0']}; border:none;")
        self._stack.addWidget(self._mk_body())
        self._stack.addWidget(self._mk_settings_placeholder())
        self._stack.addWidget(self._mk_train_body())
        self._stack.addWidget(self._mk_history_tab())
        return self._stack

    def _mk_settings_placeholder(self):
        body = QWidget()
        body.setStyleSheet(f"background:{T['bg0']};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        root = QHBoxLayout(inner)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # ── Coluna esquerda ──────────────────────────────────────
        left = QWidget()
        left.setStyleSheet("background: transparent;")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(14)
        left.setMaximumWidth(460)

        # Card: Duplicatas
        dup_card = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(dup_card, "Detecção de duplicatas", "Remove fotos redundantes antes do processamento.", Icons.grid(T["teal"]))
        dup_row = QHBoxLayout()
        dup_lbl = QLabel("Ativar detecção")
        dup_lbl.setStyleSheet(f"font-size:13px;color:{T['text1']};font-weight:500;")
        dup_row.addWidget(dup_lbl, 1)
        self._tg_duplicates = Toggle(self._duplicates_enabled)
        self._tg_duplicates.toggled_signal.connect(self._on_duplicates_toggle)
        dup_row.addWidget(self._tg_duplicates)
        dup_card.add_layout(dup_row)

        dup_card.add(self._section_label("Sensibilidade (0 = exata · 20 = permissiva)"))
        thr_row = QHBoxLayout()
        self._dup_slider = QSlider(Qt.Horizontal)
        self._dup_slider.setRange(0, 20)
        self._dup_slider.setValue(self._duplicates_threshold)
        self._dup_slider.valueChanged.connect(self._on_dup_threshold)
        thr_row.addWidget(self._dup_slider, 1)
        self._dup_thr_lbl = QLabel(str(self._duplicates_threshold))
        self._dup_thr_lbl.setStyleSheet(f"font-size:12px;color:{T['text2']};min-width:24px;")
        thr_row.addWidget(self._dup_thr_lbl)
        dup_card.add_layout(thr_row)
        left_lay.addWidget(dup_card)

        # Card: Saídas opcionais
        out_card = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(out_card, "Saídas opcionais", "Controle o que o pipeline gera além das fotos processadas.", Icons.import_icon(T["text2"]))

        cs_row = QHBoxLayout()
        cs_col = QVBoxLayout(); cs_col.setSpacing(2)
        cs_title = QLabel("Folha de contato")
        cs_title.setStyleSheet(f"font-size:13px;color:{T['text1']};font-weight:500;")
        cs_sub = QLabel("Imagem com grade de miniaturas de todas as fotos")
        cs_sub.setStyleSheet(f"font-size:11px;color:{T['text3']};")
        cs_col.addWidget(cs_title); cs_col.addWidget(cs_sub)
        cs_row.addLayout(cs_col, 1)
        self._tg_contact = Toggle(self._contact_sheet_enabled)
        self._tg_contact.toggled_signal.connect(lambda v: setattr(self, "_contact_sheet_enabled", bool(v)))
        cs_row.addWidget(self._tg_contact)
        out_card.add_layout(cs_row)

        ba_row = QHBoxLayout()
        ba_row.setContentsMargins(0, 6, 0, 0)
        ba_col = QVBoxLayout(); ba_col.setSpacing(2)
        ba_title = QLabel("Comparações antes/depois")
        ba_title.setStyleSheet(f"font-size:13px;color:{T['text1']};font-weight:500;")
        ba_sub = QLabel("Pares lado a lado de cada foto original e processada")
        ba_sub.setStyleSheet(f"font-size:11px;color:{T['text3']};")
        ba_col.addWidget(ba_title); ba_col.addWidget(ba_sub)
        ba_row.addLayout(ba_col, 1)
        self._tg_before_after = Toggle(self._before_after_enabled)
        self._tg_before_after.toggled_signal.connect(lambda v: setattr(self, "_before_after_enabled", bool(v)))
        ba_row.addWidget(self._tg_before_after)
        out_card.add_layout(ba_row)
        left_lay.addWidget(out_card)

        left_lay.addStretch()
        root.addWidget(left)

        # ── Coluna direita ──────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background: transparent;")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(14)
        right.setMaximumWidth(460)

        # Card: Perfil do classificador
        clf_cfg_card = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(clf_cfg_card, "Perfil do classificador", "Use um perfil treinado para ajustar a separação Interior / Exterior / Detalhes.", Icons.tune(T["purple"]))
        clf_row = QHBoxLayout()
        self._clf_profile_edit = QLineEdit(self._classifier_profile_path)
        self._clf_profile_edit.setPlaceholderText("classifier_profile.json (opcional)")
        self._clf_profile_edit.setMinimumHeight(36)
        self._clf_profile_edit.textChanged.connect(lambda v: setattr(self, "_classifier_profile_path", v))
        clf_row.addWidget(self._clf_profile_edit, 1)
        clf_browse_btn = QPushButton("...")
        clf_browse_btn.setFixedWidth(42)
        clf_browse_btn.setStyleSheet(BTN_GHOST)
        clf_browse_btn.setCursor(Qt.PointingHandCursor)
        clf_browse_btn.clicked.connect(self._browse_clf_profile)
        clf_row.addWidget(clf_browse_btn)
        clf_cfg_card.add_layout(clf_row)
        clf_clear_cfg = QPushButton("Remover perfil")
        clf_clear_cfg.setStyleSheet(BTN_GHOST)
        clf_clear_cfg.setCursor(Qt.PointingHandCursor)
        clf_clear_cfg.clicked.connect(lambda: (
            self._clf_profile_edit.clear(),
            setattr(self, "_classifier_profile_path", ""),
        ))
        clf_cfg_card.add(clf_clear_cfg)
        hint = QLabel("Treine um perfil na aba \"Treinar estilo\" → seção \"Treinar classificador\".")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size:11px;color:{T['text3']};")
        clf_cfg_card.add(hint)
        right_lay.addWidget(clf_cfg_card)

        # Card: Perfis de exportação
        exp_card = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(exp_card, "Perfis de exportação", "Escolha quais versões serão geradas para cada foto.", Icons.import_icon(T["teal"]))
        profiles_info = [
            ("alta_qualidade", "Alta Qualidade", "Resolução máxima — JPG 95%"),
            ("instagram",      "Instagram",      "1080×1080 px — JPG 85%"),
            ("whatsapp",       "WhatsApp",       "1280×960 px — JPG 75%"),
        ]
        self._tg_export: dict[str, Toggle] = {}
        for key, label, desc_text in profiles_info:
            row = QHBoxLayout()
            row.setContentsMargins(0, 2, 0, 2)
            col = QVBoxLayout(); col.setSpacing(1)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size:12px;color:{T['text1']};font-weight:500;")
            sub = QLabel(desc_text)
            sub.setStyleSheet(f"font-size:10.5px;color:{T['text3']};")
            col.addWidget(lbl); col.addWidget(sub)
            row.addLayout(col, 1)
            tg = Toggle(True)
            tg.toggled_signal.connect(lambda v, k=key: self._on_export_profile_toggle(k, v))
            self._tg_export[key] = tg
            row.addWidget(tg)
            exp_card.add_layout(row)
        right_lay.addWidget(exp_card)

        # Desempenho — Nível 8.3
        perf_card = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(perf_card, "Desempenho", "Threads paralelas para processamento de imagens.", Icons.activity(T["teal"]))
        row_perf = QHBoxLayout()
        row_perf.setContentsMargins(0, 4, 0, 0)
        lbl_perf = QLabel("Threads paralelas")
        lbl_perf.setStyleSheet(f"font-size:12px;color:{T['text1']};font-weight:500;")
        row_perf.addWidget(lbl_perf, 1)
        self._seg_max_workers = SegGroup(["Auto", "2", "4", "8"], "Auto", min_button_width=56, equal=True)
        self._seg_max_workers.changed.connect(self._on_max_workers_change)
        row_perf.addWidget(self._seg_max_workers)
        perf_card.add_layout(row_perf)
        right_lay.addWidget(perf_card)

        right_lay.addStretch()
        root.addWidget(right)

        scroll.setWidget(inner)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return body

    def _mk_body(self):
        body = QWidget()
        body.setStyleSheet(f"background:{T['bg0']};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner = QWidget()
        inner.setStyleSheet(f"background:{T['bg0']};")
        main = QVBoxLayout(inner)
        main.setContentsMargins(20, 14, 20, 14)
        main.setSpacing(10)

        # Bloco 1: Pastas (Entrada · Saída) + Estilo
        main.addWidget(self._mk_paths_block())

        # Bloco 2: Settings strip (HDR · Grupo · Acabamento · Mais opções)
        main.addWidget(self._mk_settings_strip())

        # Cria o dialog de mais opções (panels avançados ficam aqui)
        # Precisa ser construído DEPOIS do strip para que self._tg_bracket etc. existam
        self._build_advanced_dialog()

        # Bloco 3: Fotos (count + ações + filmstrip)
        main.addWidget(self._mk_photos_block())

        # Bloco 4: Preview (área grande)
        main.addWidget(self._mk_preview_card(), 1)

        # Bloco 5: Log (recolhível)
        main.addWidget(self._mk_log_card())

        # Bloco 6: Resultados (escondido inicialmente)
        self._results_card = self._mk_results_card()
        main.addWidget(self._results_card)

        scroll.setWidget(inner)

        wrap = QWidget()
        wrap_lay = QVBoxLayout(wrap)
        wrap_lay.setContentsMargins(0, 0, 0, 0)
        wrap_lay.setSpacing(0)
        wrap_lay.addWidget(scroll)
        return wrap

    # ── Novo layout vertical ──────────────────────────────────────
    def _mk_paths_block(self):
        card = Card(padding=(14, 12, 14, 12), shadow=False)
        card.lay.setSpacing(8)

        # Linha 1: Entrada | Saída (lado a lado)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._mk_compact_path("Entrada", "Pasta com as fotos originais", "_input_dir", True), 1)
        row.addWidget(self._mk_compact_path("Saída", "Pasta onde tudo será salvo", "_output_dir", False), 1)
        card.add_layout(row)

        # Linha 2: Perfil treinado (linha cheia)
        style_row = QHBoxLayout()
        style_row.setSpacing(8)
        ic = QLabel(); ic.setPixmap(Icons.star(T["purple"]).pixmap(14, 14)); ic.setFixedSize(14, 14)
        style_row.addWidget(ic)
        style_lbl = QLabel("Perfil")
        style_lbl.setStyleSheet(f"font-size:12px;color:{T['text3']};font-weight:700;min-width:46px;")
        style_lbl.setToolTip("Perfil .json treinado na aba \"Treinar estilo\" (opcional)")
        style_row.addWidget(style_lbl)
        self._style_path = QLineEdit()
        self._style_path.setPlaceholderText("Perfil .json treinado (opcional)")
        self._style_path.setMinimumHeight(30)
        self._style_path.setStyleSheet(
            f"QLineEdit {{ background:{T['bg0']}; border:1px solid {T['border']};"
            f" border-radius:8px; color:{T['text2']}; font-size:12px; padding:0 10px; }}"
        )
        style_row.addWidget(self._style_path, 1)
        sel = QPushButton("Selecionar"); sel.setFixedHeight(30)
        sel.setStyleSheet(BTN_GHOST); sel.setCursor(Qt.PointingHandCursor)
        sel.clicked.connect(self._browse_style)
        style_row.addWidget(sel)
        clr = QPushButton("Limpar"); clr.setFixedHeight(30)
        clr.setStyleSheet(BTN_GHOST); clr.setCursor(Qt.PointingHandCursor)
        clr.clicked.connect(self._style_path.clear)
        style_row.addWidget(clr)
        card.add_layout(style_row)
        return card

    def _mk_compact_path(self, label_text: str, placeholder: str, attr: str, is_input: bool):
        wrap = QFrame()
        wrap.setStyleSheet("background:transparent;")
        col = QVBoxLayout(wrap)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        # Label
        head = QHBoxLayout(); head.setSpacing(6); head.setContentsMargins(0, 0, 0, 0)
        ic = QLabel(); ic.setPixmap(Icons.folder(T["text3"]).pixmap(14, 14)); ic.setFixedSize(14, 14)
        head.addWidget(ic)
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"font-size:12px;color:{T['text3']};font-weight:700;")
        head.addWidget(lbl)
        head.addStretch()
        col.addLayout(head)

        # Input + button
        line_row = QHBoxLayout(); line_row.setSpacing(6); line_row.setContentsMargins(0, 0, 0, 0)
        line = QLineEdit()
        line.setPlaceholderText(placeholder)
        line.setMinimumHeight(30)
        line.setStyleSheet(
            f"QLineEdit {{ background:{T['bg0']}; border:1px solid {T['border']};"
            f" border-radius:8px; color:{T['text2']}; font-size:12px; padding:0 10px; }}"
        )
        setattr(self, attr, line)
        line_row.addWidget(line, 1)
        btn = QPushButton("...")
        btn.setFixedSize(34, 30)
        btn.setStyleSheet(BTN_GHOST)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _, w=line, inp=is_input: self._browse_dir(w, inp))
        line_row.addWidget(btn)
        col.addLayout(line_row)
        if is_input:
            line.textChanged.connect(self._on_input_dir_changed)
        return wrap

    def _mk_settings_strip(self):
        card = Card(padding=(12, 10, 12, 10), shadow=False)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.setContentsMargins(0, 0, 0, 0)

        # HDR toggle
        hdr_box = QHBoxLayout(); hdr_box.setSpacing(8)
        hdr_lbl = QLabel("HDR")
        hdr_lbl.setStyleSheet(f"font-size:13px;font-weight:700;color:{T['text1']};")
        hdr_tip = (
            "Quando ligado, executa o fluxo Lightroom automatizado:\n"
            "stacking por horário → photo merge → exposure → contraste →\n"
            "aberração cromática → distorção de lente → highlights → shadows →\n"
            "vibrance → geometria."
        )
        hdr_lbl.setToolTip(hdr_tip)
        hdr_box.addWidget(hdr_lbl)
        self._tg_bracket = Toggle(False)
        self._tg_bracket.setToolTip(hdr_tip)
        self._tg_bracket.toggled_signal.connect(self._on_bracketing)
        hdr_box.addWidget(self._tg_bracket)
        row.addLayout(hdr_box)

        # Separator
        sep1 = QFrame(); sep1.setFixedSize(1, 28); sep1.setStyleSheet(f"background:{T['borderSoft']};")
        row.addWidget(sep1)

        # Grupo
        grp_box = QHBoxLayout(); grp_box.setSpacing(8)
        grp_lbl = QLabel("Grupo")
        grp_lbl.setStyleSheet(f"font-size:13px;color:{T['text3']};")
        grp_box.addWidget(grp_lbl)
        self._seg_bracket_group = SegGroup(["Auto", "3 fotos", "5 fotos"], "3 fotos", min_button_width=68, equal=True)
        self._seg_bracket_group.changed.connect(self._on_bracket_group)
        grp_box.addWidget(self._seg_bracket_group)
        row.addLayout(grp_box)

        # Separator
        sep2 = QFrame(); sep2.setFixedSize(1, 28); sep2.setStyleSheet(f"background:{T['borderSoft']};")
        row.addWidget(sep2)

        # Acabamento toggle
        fin_box = QHBoxLayout(); fin_box.setSpacing(8)
        fin_lbl = QLabel("Acabamento")
        fin_lbl.setStyleSheet(f"font-size:13px;font-weight:700;color:{T['text1']};")
        fin_box.addWidget(fin_lbl)
        self._tg_hdr_finish = Toggle(False)
        self._tg_hdr_finish.toggled_signal.connect(self._on_hdr_finish)
        fin_box.addWidget(self._tg_hdr_finish)
        row.addLayout(fin_box)

        # Separator
        sep3 = QFrame(); sep3.setFixedSize(1, 28); sep3.setStyleSheet(f"background:{T['borderSoft']};")
        row.addWidget(sep3)

        # Preset
        ps_box = QHBoxLayout(); ps_box.setSpacing(8)
        ps_lbl = QLabel("Estilo")
        ps_lbl.setStyleSheet(f"font-size:13px;color:{T['text3']};")
        ps_box.addWidget(ps_lbl)
        self._seg_preset = SegGroup(["Natural", "Luxury", "Strong"], "Luxury", min_button_width=72, equal=True)
        self._seg_preset.changed.connect(self._on_preset)
        ps_box.addWidget(self._seg_preset)
        row.addLayout(ps_box)

        row.addStretch(1)

        # Botão Mais opções
        more = QPushButton(Icons.settings(T["text2"]), " Mais opções")
        more.setFixedHeight(32)
        more.setStyleSheet(BTN_GHOST)
        more.setCursor(Qt.PointingHandCursor)
        more.clicked.connect(self._show_more_options)
        row.addWidget(more)

        card.add_layout(row)
        return card

    def _mk_photos_block(self):
        card = Card(padding=(12, 10, 12, 10), shadow=False)
        card.lay.setSpacing(8)

        # Header com count + ações
        head = QHBoxLayout(); head.setSpacing(10); head.setContentsMargins(0, 0, 0, 0)
        ic = QLabel(); ic.setPixmap(Icons.grid(T["teal"]).pixmap(16, 16)); ic.setFixedSize(16, 16)
        head.addWidget(ic)
        self._photos_count_lbl = QLabel("Nenhuma foto carregada")
        self._photos_count_lbl.setStyleSheet(f"font-size:13px;color:{T['text1']};font-weight:700;")
        head.addWidget(self._photos_count_lbl)
        self._selected_label = QLabel("")
        self._selected_label.setStyleSheet(f"font-size:11px;color:{T['text3']};")
        head.addWidget(self._selected_label)
        # Mantidos para compatibilidade (uso interno)
        self._queue_badge = QLabel("0")
        self._queue_badge.setVisible(False)
        head.addStretch()

        # Ações
        sample_btn = QPushButton(Icons.bolt(T["teal"]), " Amostra")
        sample_btn.setFixedHeight(30)
        sample_btn.setStyleSheet(BTN_GHOST)
        sample_btn.setCursor(Qt.PointingHandCursor)
        sample_btn.setToolTip("Carrega os primeiros N grupos de bracketing para teste rápido")
        sample_btn.clicked.connect(self._show_sample_dialog)
        head.addWidget(sample_btn)

        import_btn = QPushButton(Icons.import_icon(T["text2"]), " Importar")
        import_btn.setFixedHeight(30)
        import_btn.setStyleSheet(BTN_GHOST)
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.setToolTip("Selecionar pasta de entrada")
        import_btn.clicked.connect(lambda: self._browse_dir(self._input_dir, True))
        head.addWidget(import_btn)

        reload_btn = QPushButton(Icons.refresh(T["text2"]), " Recarregar")
        reload_btn.setFixedHeight(30)
        reload_btn.setStyleSheet(BTN_GHOST)
        reload_btn.setCursor(Qt.PointingHandCursor)
        reload_btn.setToolTip("Recarregar a pasta de entrada atual")
        reload_btn.clicked.connect(self._reload_input_folder)
        head.addWidget(reload_btn)
        card.add_layout(head)

        # Filtros (escondidos até processar)
        self._filter_chips_widget = QWidget()
        self._filter_chips_widget.setVisible(False)
        self._filter_chips_layout = QHBoxLayout(self._filter_chips_widget)
        self._filter_chips_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_chips_layout.setSpacing(6)
        card.add(self._filter_chips_widget)

        # Filmstrip horizontal
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(124)
        scroll.setStyleSheet("background:transparent;")
        self._filmstrip_widget = QWidget()
        self._filmstrip_widget.setStyleSheet("background:transparent;")
        self._filmstrip_layout = QHBoxLayout(self._filmstrip_widget)
        self._filmstrip_layout.setContentsMargins(0, 0, 0, 0)
        self._filmstrip_layout.setSpacing(8)
        self._filmstrip_layout.addStretch()
        scroll.setWidget(self._filmstrip_widget)
        card.add(scroll)

        # Fila de pastas em lote (escondida; só aparece quando usuário arrasta múltiplas pastas)
        self._folder_list_widget = QWidget()
        self._folder_list_widget.setStyleSheet("background:transparent;")
        self._folder_list_widget.setVisible(False)
        self._folder_list_layout = QVBoxLayout(self._folder_list_widget)
        self._folder_list_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_list_layout.setSpacing(4)
        card.add(self._folder_list_widget)

        # Queue list interno (escondido — mantido para compatibilidade com _populate_queue)
        self._queue_area = QScrollArea()
        self._queue_area.setVisible(False)
        self._queue_area.setMaximumHeight(0)
        _q_inner = QWidget()
        self._queue_layout = QVBoxLayout(_q_inner)
        self._queue_layout.setContentsMargins(0, 0, 0, 0)
        self._queue_layout.addStretch()
        self._queue_area.setWidget(_q_inner)
        card.add(self._queue_area)

        return card

    def _reload_input_folder(self):
        path = self._input_dir.text().strip()
        if path and os.path.isdir(path):
            self._load_images_from_folder(path, show_feedback=True)

    def _update_photos_count(self):
        n = len(getattr(self, "_image_paths", []))
        sample_tag = ""
        if getattr(self, "_sample_paths", None):
            sample_tag = " · amostra"
        if n == 0:
            self._photos_count_lbl.setText("Nenhuma foto carregada")
        else:
            # tenta estimar grupos
            grp = 3
            if getattr(self, "_bracketing_group_size", "auto") in ("3", "5"):
                grp = int(self._bracketing_group_size)
            groups = n // grp
            if getattr(self, "_bracketing_enabled", False) and groups:
                self._photos_count_lbl.setText(f"{n} fotos  ·  ~{groups} grupos HDR{sample_tag}")
            else:
                self._photos_count_lbl.setText(f"{n} fotos{sample_tag}")

    def _build_advanced_dialog(self):
        """Cria o dialog de Mais opções com todos os panels avançados.
        Chamado após criar widgets do strip (HDR, grupo, acabamento, preset)."""
        self._more_dialog = QDialog(self)
        self._more_dialog.setWindowTitle("Mais opções")
        self._more_dialog.setMinimumSize(560, 620)
        self._more_dialog.setStyleSheet(f"QDialog {{ background:{T['bg1']}; }}")

        dlg_lay = QVBoxLayout(self._more_dialog)
        dlg_lay.setContentsMargins(0, 0, 0, 0)
        dlg_lay.setSpacing(0)

        # Tab bar
        tab_bar = QFrame()
        tab_bar.setStyleSheet(f"QFrame {{ background:{T['bg2']}; border-bottom:1px solid {T['borderSoft']}; }}")
        tab_h = QHBoxLayout(tab_bar)
        tab_h.setContentsMargins(12, 8, 12, 8)
        tab_h.setSpacing(4)
        self._adv_tab_btns: list = []
        for i, label in enumerate(["Automação", "Saída", "Avançado"]):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(seg_qss(i == 0))
            btn.clicked.connect(lambda _, idx=i: self._switch_adv_tab(idx))
            self._adv_tab_btns.append(btn)
            tab_h.addWidget(btn)
        tab_h.addStretch()
        dlg_lay.addWidget(tab_bar)

        # Stack
        self._adv_stack = QStackedWidget()
        self._adv_stack.setStyleSheet(f"background:{T['bg1']};")

        for panels in [
            [self._mk_preset_panel(), self._mk_auto_extras_panel()],
            [self._mk_export_panel(), self._mk_rename_watermark_panel()],
            [self._mk_bracket_extras_panel(), self._mk_upscale_panel(), self._mk_advanced_panel()],
        ]:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setStyleSheet(f"background:{T['bg1']};")
            page_w = QWidget(); page_w.setStyleSheet(f"background:{T['bg1']};")
            page_v = QVBoxLayout(page_w)
            page_v.setContentsMargins(16, 14, 16, 14)
            page_v.setSpacing(12)
            for p in panels:
                page_v.addWidget(p)
            page_v.addStretch(1)
            scroll.setWidget(page_w)
            self._adv_stack.addWidget(scroll)
        dlg_lay.addWidget(self._adv_stack, 1)

        # Footer
        footer = QFrame()
        footer.setStyleSheet(f"QFrame {{ background:{T['bg2']}; border-top:1px solid {T['borderSoft']}; }}")
        fh = QHBoxLayout(footer); fh.setContentsMargins(14, 10, 14, 10)
        fh.addStretch()
        close_btn = QPushButton("Fechar")
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(BTN_PRIMARY)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self._more_dialog.accept)
        fh.addWidget(close_btn)
        dlg_lay.addWidget(footer)

    def _switch_adv_tab(self, idx: int):
        self._adv_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._adv_tab_btns):
            btn.setStyleSheet(seg_qss(i == idx))

    def _show_more_options(self):
        self._more_dialog.exec()

    def _mk_auto_extras_panel(self):
        """Versão reduzida do Modo Automático sem o Preset (que está no strip)."""
        card = Card(padding=(16, 16, 16, 16), shadow=False)
        card.lay.setSpacing(12)
        self._card_header(card, "Modo Automático — detalhes", "Ajuste fino da intensidade e cor.", Icons.tune())
        card.add(self._section_label("Intensidade"))
        self._seg_intensity = SegGroup(["Suave", "Normal", "Forte"], "Normal", min_button_width=82, equal=True)
        self._seg_intensity.changed.connect(self._on_intensity)
        card.add(self._seg_intensity)
        card.add(self._section_label("Modo de cor"))
        self._seg_color = SegGroup(["Natural", "Vibrant", "Luxury"], "Luxury", min_button_width=86, equal=True)
        self._seg_color.changed.connect(self._on_color)
        card.add(self._seg_color)
        return card

    def _mk_bracket_extras_panel(self):
        """Versão reduzida do Bracketing sem HDR/Grupo/Acabamento (estão no strip)."""
        card = Card(padding=(16, 16, 16, 16), shadow=False)
        card.lay.setSpacing(12)
        self._card_header(card, "HDR — fusão", "Escolha o estilo de fusão das exposições.", Icons.activity())
        card.add(self._section_label("Preset de fusão"))
        self._seg_bracket_preset = SegGroup(
            ["Lightroom", "Natural", "Janela", "Interior", "Imob. Claro"],
            "Lightroom",
            min_button_width=72,
            equal=True,
        )
        self._seg_bracket_preset.changed.connect(self._on_bracket_preset)
        card.add(self._seg_bracket_preset)

        # Lista de passos automatizados (espelha o fluxo do Lightroom)
        steps_label = QLabel(
            "<b>Lightroom automatiza, na ordem:</b><br>"
            "stacking por horário · photo merge HDR · exposure · contraste · "
            "aberração cromática · distorção de lente · highlights · shadows · "
            "vibrance · geometria"
        )
        steps_label.setWordWrap(True)
        steps_label.setStyleSheet(f"font-size:11px;color:{T['text3']};line-height:1.5;")
        card.add(steps_label)

        hint = QLabel("Os toggles HDR, Grupo e Acabamento ficam na barra principal.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size:11px;color:{T['text4']};")
        card.add(hint)
        return card

    def _mk_log_card(self):
        card = Card(padding=(10, 10, 10, 10), shadow=False)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(Icons.activity(T["teal"]).pixmap(16, 16))
        ic.setFixedSize(16, 16)
        header_row.addWidget(ic)
        title = QLabel("Log de processamento")
        title.setStyleSheet(f"font-size:13px;font-weight:700;color:{T['text2']};")
        header_row.addWidget(title, 1)
        self._log_save_btn = QPushButton("Salvar")
        self._log_save_btn.setFixedHeight(26)
        self._log_save_btn.setStyleSheet(BTN_GHOST)
        self._log_save_btn.setCursor(Qt.PointingHandCursor)
        self._log_save_btn.clicked.connect(self._save_log)
        header_row.addWidget(self._log_save_btn)
        self._log_clear_btn = QPushButton("Limpar")
        self._log_clear_btn.setFixedHeight(26)
        self._log_clear_btn.setStyleSheet(BTN_GHOST)
        self._log_clear_btn.setCursor(Qt.PointingHandCursor)
        self._log_clear_btn.clicked.connect(lambda: self._log.clear())
        header_row.addWidget(self._log_clear_btn)
        self._log_toggle_btn = QPushButton(Icons.chevron_down(T["text2"]), "")
        self._log_toggle_btn.setFixedSize(28, 26)
        self._log_toggle_btn.setStyleSheet(BTN_GHOST)
        self._log_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._log_toggle_btn.setToolTip("Mostrar/ocultar log")
        self._log_toggle_btn.clicked.connect(self._toggle_log)
        header_row.addWidget(self._log_toggle_btn)
        card.add_layout(header_row)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setAcceptRichText(True)
        self._log.setMinimumHeight(110)
        self._log.setMaximumHeight(200)
        self._log.setPlaceholderText("O log de processamento aparecerá aqui...")
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background:{T['bg0']}; border:1px solid {T['borderSoft']}; border-radius:10px;
                color:{T['text2']}; font-family:'Consolas',monospace; font-size:11.5px; padding:8px;
            }}
        """)
        # Começa recolhido — abre automaticamente ao iniciar processamento
        self._log.setVisible(False)
        self._log_clear_btn.setVisible(False)
        card.add(self._log)
        return card

    def _toggle_log(self):
        visible = self._log.isVisible()
        self._log.setVisible(not visible)
        self._log_clear_btn.setVisible(not visible)
        self._log_toggle_btn.setIcon(
            Icons.chevron_down(T["text2"]) if visible else Icons.chevron_up(T["text2"])
        )

    def _mk_results_card(self) -> QWidget:
        card = Card(padding=(12, 12, 12, 12), shadow=False)
        card.setVisible(False)

        # Header row
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(Icons.activity(T["teal"]).pixmap(16, 16))
        ic.setFixedSize(16, 16)
        h.addWidget(ic)
        title = QLabel("Resultado do processamento")
        title.setStyleSheet(f"font-size:13px;font-weight:700;color:{T['text1']};")
        h.addWidget(title, 1)
        self._res_report_btn = QPushButton("Ver relatório")
        self._res_report_btn.setStyleSheet(BTN_GHOST)
        self._res_report_btn.setFixedHeight(28)
        self._res_report_btn.setCursor(Qt.PointingHandCursor)
        self._res_report_btn.clicked.connect(self._open_report)
        h.addWidget(self._res_report_btn)
        self._res_pdf_btn = QPushButton(Icons.pdf(T["text1"]), " PDF")
        self._res_pdf_btn.setStyleSheet(BTN_GHOST)
        self._res_pdf_btn.setFixedHeight(28)
        self._res_pdf_btn.setCursor(Qt.PointingHandCursor)
        self._res_pdf_btn.clicked.connect(self._export_pdf)
        h.addWidget(self._res_pdf_btn)
        self._res_compare_btn = QPushButton(Icons.eye(T["text1"]), " Comparar")
        self._res_compare_btn.setStyleSheet(BTN_GHOST)
        self._res_compare_btn.setFixedHeight(28)
        self._res_compare_btn.setCursor(Qt.PointingHandCursor)
        self._res_compare_btn.clicked.connect(self._enter_compare_mode)
        h.addWidget(self._res_compare_btn)
        self._res_slideshow_btn = QPushButton(Icons.play(T["text1"]), " Slideshow")
        self._res_slideshow_btn.setStyleSheet(BTN_GHOST)
        self._res_slideshow_btn.setFixedHeight(28)
        self._res_slideshow_btn.setCursor(Qt.PointingHandCursor)
        self._res_slideshow_btn.clicked.connect(self._show_slideshow_output)
        h.addWidget(self._res_slideshow_btn)
        self._res_deliver_btn = QPushButton(Icons.import_icon(T["teal"]), " Entregar")
        self._res_deliver_btn.setStyleSheet(button_qss(T["teal"], "#03261C", hover="#2DE0B6", radius=10, weight=700, height=28))
        self._res_deliver_btn.setFixedHeight(28)
        self._res_deliver_btn.setCursor(Qt.PointingHandCursor)
        self._res_deliver_btn.clicked.connect(self._show_delivery_dialog)
        h.addWidget(self._res_deliver_btn)
        card.add_layout(h)

        # Stat chips row
        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 4, 0, 0)
        chips_row.setSpacing(8)
        self._res_lbl_processed = self._mk_stat_chip("Processadas", "—")
        self._res_lbl_errors    = self._mk_stat_chip("Erros", "—")
        self._res_lbl_time      = self._mk_stat_chip("Tempo", "—")
        chips_row.addWidget(self._res_lbl_processed)
        chips_row.addWidget(self._res_lbl_errors)
        chips_row.addWidget(self._res_lbl_time)
        chips_row.addStretch()
        card.add_layout(chips_row)

        # Class breakdown label
        self._res_classes_lbl = QLabel()
        self._res_classes_lbl.setStyleSheet(f"font-size:12px;color:{T['text3']};margin-top:4px;")
        self._res_classes_lbl.setWordWrap(True)
        card.add(self._res_classes_lbl)

        self._res_report_path = ""
        return card

    def _mk_stat_chip(self, label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:{T['bg3']};border:1px solid {T['borderSoft']};"
            f"border-radius:8px;padding:6px 12px;}}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size:10px;color:{T['text4']};font-weight:600;letter-spacing:0.5px;")
        lbl.setAlignment(Qt.AlignCenter)
        val = QLabel(value)
        val.setStyleSheet(f"font-size:16px;font-weight:800;color:{T['text1']};")
        val.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)
        lay.addWidget(val)
        frame._value_label = val
        return frame

    def _mk_preview_card(self):
        card = Card(padding=(16, 14, 16, 16))
        row = QHBoxLayout()
        col = QVBoxLayout()
        title = QLabel("Prévia")
        title.setStyleSheet(f"font-size:17px;font-weight:800;color:{T['text1']};")
        subtitle = QLabel("Compare o resultado automático antes de processar todo o lote.")
        subtitle.setStyleSheet(f"font-size:12px;color:{T['text3']};")
        col.addWidget(title)
        col.addWidget(subtitle)
        row.addLayout(col, 1)
        slideshow_btn = QPushButton("Slideshow")
        slideshow_btn.setIcon(Icons.play(T["text2"]))
        slideshow_btn.setStyleSheet(BTN_GHOST)
        slideshow_btn.setCursor(Qt.PointingHandCursor)
        slideshow_btn.clicked.connect(lambda: self._show_slideshow(self._image_paths))
        row.addWidget(slideshow_btn)
        fullscreen = QPushButton("Tela cheia")
        fullscreen.setIcon(Icons.eye(T["text2"]))
        fullscreen.setStyleSheet(BTN_GHOST)
        fullscreen.setCursor(Qt.PointingHandCursor)
        fullscreen.clicked.connect(self._show_fullscreen_preview)
        row.addWidget(fullscreen)
        card.add_layout(row)
        self._compare = CompareView()
        card.add(self._compare, 1)
        # 10.4 — campo de notas por foto
        note_row = QHBoxLayout()
        note_row.setContentsMargins(0, 6, 0, 0)
        note_row.setSpacing(8)
        note_lbl = QLabel("Nota:")
        note_lbl.setStyleSheet(f"font-size:12px;color:{T['text3']};min-width:36px;")
        note_row.addWidget(note_lbl)
        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("Adicione uma anotação para esta foto…")
        self._note_edit.setFixedHeight(30)
        self._note_edit.setStyleSheet(
            f"QLineEdit{{background:{T['bg0']};border:1px solid {T['border']};"
            f"border-radius:8px;padding:0 10px;color:{T['text2']};font-size:12px;}}"
        )
        self._note_edit.editingFinished.connect(self._save_current_note)
        note_row.addWidget(self._note_edit, 1)
        card.add_layout(note_row)
        return card

    def _mk_preset_panel(self):
        card = Card(padding=(14, 12, 14, 12), shadow=False)
        self._card_header(card, "Presets", "Salve e carregue configurações completas.", Icons.bookmark())
        combo_row = QHBoxLayout()
        combo_row.setSpacing(8)
        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumHeight(34)
        self._preset_combo.setStyleSheet(
            f"QComboBox {{ background:{T['bg3']}; border:1px solid {T['border']}; border-radius:10px;"
            f" color:{T['text1']}; font-size:13px; padding:4px 10px; }}"
            f"QComboBox::drop-down {{ border:none; width:24px; }}"
            f"QComboBox QAbstractItemView {{ background:{T['bg2']}; color:{T['text1']}; border:1px solid {T['border']}; selection-background-color:{T['bg4']}; }}"
        )
        self._refresh_preset_combo()
        combo_row.addWidget(self._preset_combo, 1)
        load_btn = QPushButton("Carregar")
        load_btn.setFixedHeight(34)
        load_btn.setStyleSheet(BTN_GHOST)
        load_btn.setCursor(Qt.PointingHandCursor)
        load_btn.clicked.connect(self._load_selected_preset)
        combo_row.addWidget(load_btn)
        card.add_layout(combo_row)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        save_btn = QPushButton(Icons.bookmark(T["text1"]), " Salvar atual")
        save_btn.setStyleSheet(BTN_GHOST)
        save_btn.setFixedHeight(34)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save_current_preset)
        btn_row.addWidget(save_btn, 1)
        del_btn = QPushButton("Excluir")
        del_btn.setFixedHeight(34)
        del_btn.setStyleSheet(button_qss(T["bg3"], T["danger"], f"1px solid {T['borderSoft']}", hover=T["bg4"], radius=10, height=34))
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(self._delete_selected_preset)
        btn_row.addWidget(del_btn)
        card.add_layout(btn_row)
        return card

    def _mk_upscale_panel(self):
        card = Card(padding=(16, 16, 16, 16), shadow=False)
        card.setMinimumHeight(170)
        card.lay.setSpacing(12)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        ic = QLabel(); ic.setPixmap(Icons.upscale().pixmap(18, 18)); ic.setFixedSize(28, 28); ic.setAlignment(Qt.AlignCenter); ic.setStyleSheet(f"background:{T['bg3']};border-radius:9px;"); header.addWidget(ic)
        title = QLabel("Upscale")
        title.setStyleSheet(f"font-size:14px;font-weight:800;color:{T['text1']};")
        header.addWidget(title)
        header.addStretch()
        self._tg_upscale = Toggle(False)
        self._tg_upscale.toggled_signal.connect(self._on_upscale)
        header.addWidget(self._tg_upscale)
        card.add_layout(header)
        desc = QLabel("Automático por padrão. Use 4x só para arquivos pequenos.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size:11.5px;color:{T['text3']};")
        card.add(desc)
        card.add(self._section_label("Fator"))
        self._seg_factor = SegGroup(["Off", "2x", "4x"], "2x", min_button_width=82, equal=True)
        self._seg_factor.changed.connect(self._on_factor)
        card.add(self._seg_factor)
        card.add(self._section_label("Preset de qualidade"))
        self._seg_upscale_preset = SegGroup(
            ["Natural Pro", "Forte", "Luxury"], "Natural Pro",
            min_button_width=82, equal=True,
        )
        self._seg_upscale_preset.changed.connect(self._on_upscale_preset)
        card.add(self._seg_upscale_preset)
        return card

    def _mk_export_panel(self):
        card = Card(padding=(16, 16, 16, 16), shadow=False)
        card.lay.setSpacing(10)
        self._card_header(card, "Exportação & Galeria", "Saída otimizada para entrega ao cliente.", Icons.import_icon(T["text2"]))

        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 4)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        for row, (k, v) in enumerate([("Formato", "JPG"), ("Qualidade", "95%"), ("Perfil de cor", "sRGB")]):
            lab = QLabel(k); lab.setStyleSheet(f"font-size:12px;color:{T['text3']};")
            val = QLabel(v); val.setStyleSheet(f"font-size:12px;font-weight:700;color:{T['text1']};")
            grid.addWidget(lab, row, 0)
            grid.addWidget(val, row, 1, alignment=Qt.AlignRight)
        card.add_layout(grid)

        card.add(self._section_label("Galeria HTML"))
        self._gallery_title_edit = QLineEdit(self._gallery_title)
        self._gallery_title_edit.setPlaceholderText("Título da galeria")
        self._gallery_title_edit.textChanged.connect(lambda v: setattr(self, "_gallery_title", v))
        card.add(self._gallery_title_edit)
        self._gallery_subtitle_edit = QLineEdit(self._gallery_subtitle)
        self._gallery_subtitle_edit.setPlaceholderText("Subtítulo (ex: endereço do imóvel)")
        self._gallery_subtitle_edit.textChanged.connect(lambda v: setattr(self, "_gallery_subtitle", v))
        card.add(self._gallery_subtitle_edit)

        card.add(self._section_label("Metadados EXIF"))
        self._photographer_edit = QLineEdit(self._photographer)
        self._photographer_edit.setPlaceholderText("Nome do fotógrafo")
        self._photographer_edit.textChanged.connect(lambda v: setattr(self, "_photographer", v))
        card.add(self._photographer_edit)
        self._copyright_edit = QLineEdit(self._copyright_text)
        self._copyright_edit.setPlaceholderText("Copyright (ex: © Studio 2025)")
        self._copyright_edit.textChanged.connect(lambda v: setattr(self, "_copyright_text", v))
        card.add(self._copyright_edit)

        return card

    def _mk_rename_watermark_panel(self):
        card = Card(padding=(16, 14, 16, 14), shadow=False)
        card.lay.setSpacing(10)

        # ── Renomeação ─────────────────────────────────────────────
        ren_row = QHBoxLayout()
        ren_row.setContentsMargins(0, 0, 0, 0)
        ren_row.setSpacing(8)
        ren_title = QLabel("Renomear arquivos")
        ren_title.setStyleSheet(f"font-size:13px;font-weight:700;color:{T['text1']};")
        ren_row.addWidget(ren_title, 1)
        self._tg_rename = Toggle(False)
        self._tg_rename.toggled_signal.connect(self._on_rename_toggle)
        ren_row.addWidget(self._tg_rename)
        card.add_layout(ren_row)

        self._rename_body = QFrame()
        self._rename_body.setVisible(False)
        rb = QVBoxLayout(self._rename_body)
        rb.setContentsMargins(0, 2, 0, 0)
        rb.setSpacing(6)
        self._rename_prefix_edit = QLineEdit(self._rename_prefix)
        self._rename_prefix_edit.setPlaceholderText("Prefixo (ex: APTO)")
        self._rename_prefix_edit.textChanged.connect(self._on_rename_prefix_changed)
        rb.addWidget(self._rename_prefix_edit)
        self._rename_code_edit = QLineEdit(self._rename_code)
        self._rename_code_edit.setPlaceholderText("Código do imóvel (opcional)")
        self._rename_code_edit.textChanged.connect(self._on_rename_code_changed)
        rb.addWidget(self._rename_code_edit)
        # Preview do rename (8.2)
        self._rename_preview_lbl = QLabel()
        self._rename_preview_lbl.setStyleSheet(
            f"font-size:10.5px;color:{T['teal']};font-family:Consolas,monospace;"
            f"background:{T['bg0']};border:1px solid {T['borderSoft']};border-radius:6px;padding:4px 8px;"
        )
        self._rename_preview_lbl.setWordWrap(True)
        rb.addWidget(self._rename_preview_lbl)
        self._update_rename_preview()
        card.add(self._rename_body)

        # ── Marca d'água ───────────────────────────────────────────
        wm_row = QHBoxLayout()
        wm_row.setContentsMargins(0, 4, 0, 0)
        wm_row.setSpacing(8)
        wm_title = QLabel("Marca d'água")
        wm_title.setStyleSheet(f"font-size:13px;font-weight:700;color:{T['text1']};")
        wm_row.addWidget(wm_title, 1)
        self._tg_watermark = Toggle(False)
        self._tg_watermark.toggled_signal.connect(self._on_watermark_toggle)
        wm_row.addWidget(self._tg_watermark)
        card.add_layout(wm_row)

        self._watermark_body = QFrame()
        self._watermark_body.setVisible(False)
        wb = QVBoxLayout(self._watermark_body)
        wb.setContentsMargins(0, 2, 0, 0)
        wb.setSpacing(6)

        # Seletor Texto / Logo (8.1)
        self._seg_wm_mode = SegGroup(["Texto", "Logo"], "Texto", min_button_width=80, equal=True)
        self._seg_wm_mode.changed.connect(self._on_wm_mode)
        wb.addWidget(self._seg_wm_mode)

        # Painel Texto
        self._wm_text_panel = QFrame()
        self._wm_text_panel.setStyleSheet("background:transparent;")
        tp = QVBoxLayout(self._wm_text_panel)
        tp.setContentsMargins(0, 0, 0, 0)
        tp.setSpacing(6)
        self._wm_text_edit = QLineEdit(self._watermark_text)
        self._wm_text_edit.setPlaceholderText("Texto (ex: © Foto Studio)")
        self._wm_text_edit.textChanged.connect(lambda v: setattr(self, "_watermark_text", v))
        tp.addWidget(self._wm_text_edit)
        wb.addWidget(self._wm_text_panel)

        # Painel Logo (8.1)
        self._wm_logo_panel = QFrame()
        self._wm_logo_panel.setStyleSheet("background:transparent;")
        self._wm_logo_panel.setVisible(False)
        lp = QHBoxLayout(self._wm_logo_panel)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.setSpacing(6)
        self._wm_logo_edit = QLineEdit(self._watermark_logo_path)
        self._wm_logo_edit.setPlaceholderText("Caminho do logo (.png)")
        self._wm_logo_edit.setMinimumHeight(34)
        self._wm_logo_edit.textChanged.connect(lambda v: setattr(self, "_watermark_logo_path", v))
        lp.addWidget(self._wm_logo_edit, 1)
        logo_browse = QPushButton("...")
        logo_browse.setFixedWidth(38)
        logo_browse.setFixedHeight(34)
        logo_browse.setStyleSheet(BTN_GHOST)
        logo_browse.setCursor(Qt.PointingHandCursor)
        logo_browse.clicked.connect(self._browse_wm_logo)
        lp.addWidget(logo_browse)
        wb.addWidget(self._wm_logo_panel)

        self._seg_wm_pos = SegGroup(
            ["Inf. Dir.", "Inf. Esq.", "Centro"],
            "Inf. Dir.",
            min_button_width=72,
            equal=True,
        )
        self._seg_wm_pos.changed.connect(self._on_wm_position)
        wb.addWidget(self._seg_wm_pos)
        op_row = QHBoxLayout()
        op_lbl = QLabel("Opacidade:")
        op_lbl.setStyleSheet(f"font-size:12px;color:{T['text3']};")
        op_row.addWidget(op_lbl)
        self._wm_opacity_slider = QSlider(Qt.Horizontal)
        self._wm_opacity_slider.setRange(10, 90)
        self._wm_opacity_slider.setValue(int(self._watermark_opacity * 100))
        op_row.addWidget(self._wm_opacity_slider, 1)
        self._wm_opacity_lbl = QLabel(f"{int(self._watermark_opacity * 100)}%")
        self._wm_opacity_lbl.setStyleSheet(f"font-size:12px;color:{T['text2']};min-width:32px;")
        self._wm_opacity_slider.valueChanged.connect(self._on_wm_opacity)
        op_row.addWidget(self._wm_opacity_lbl)
        wb.addLayout(op_row)
        card.add(self._watermark_body)

        return card

    def _mk_advanced_panel(self):
        card = Card(padding=(16, 16, 16, 16), shadow=False)
        card.setMinimumHeight(82)
        card.lay.setSpacing(10)
        self._btn_adv = QPushButton("Ajustes avançados  ▼")
        self._btn_adv.setStyleSheet(BTN_GHOST)
        self._btn_adv.setCursor(Qt.PointingHandCursor)
        self._btn_adv.clicked.connect(self._toggle_advanced)
        card.add(self._btn_adv)
        self._advanced_body = QFrame()
        self._advanced_body.setStyleSheet(f"QFrame {{ background:{T['bg1']}; border:1px solid {T['borderSoft']}; border-radius:12px; }}")
        self._advanced_body.setVisible(False)
        b = QVBoxLayout(self._advanced_body)
        b.setContentsMargins(14, 12, 14, 12)
        b.setSpacing(8)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        txt_col = QVBoxLayout()
        txt_col.setSpacing(2)
        lbl = QLabel("Processar subpastas")
        lbl.setStyleSheet(f"font-size:13px;color:{T['text1']};font-weight:500;")
        sub = QLabel("Inclui imagens de todas as subpastas da entrada")
        sub.setStyleSheet(f"font-size:11px;color:{T['text3']};")
        txt_col.addWidget(lbl)
        txt_col.addWidget(sub)
        self._tg_subfolder = Toggle(False)
        self._tg_subfolder.toggled_signal.connect(self._on_subfolder_toggle)
        row.addLayout(txt_col)
        row.addStretch()
        row.addWidget(self._tg_subfolder)
        b.addLayout(row)

        card.add(self._advanced_body)
        return card

    # ── Train tab ────────────────────────────────────────────────
    def _mk_train_body(self):
        body = QWidget()
        body.setStyleSheet(f"background:{T['bg0']};")
        root = QVBoxLayout(body)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(10)

        # ── Tab bar ──────────────────────────────────────────────
        tab_bar = QFrame()
        tab_bar.setStyleSheet(
            f"QFrame {{ background:{T['bg2']}; border:1px solid {T['borderSoft']}; border-radius:12px; }}"
        )
        tab_h = QHBoxLayout(tab_bar)
        tab_h.setContentsMargins(4, 4, 4, 4)
        tab_h.setSpacing(4)
        self._train_tab_btns: list = []
        for i, label in enumerate(["Estilo", "HDR", "Classificador"]):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(seg_qss(i == 0))
            btn.clicked.connect(lambda _, idx=i: self._switch_train_tab(idx))
            self._train_tab_btns.append(btn)
            tab_h.addWidget(btn)
        root.addWidget(tab_bar)

        self._train_stack = QStackedWidget()
        self._train_stack.setStyleSheet("background:transparent;")

        # ── Página 0: Estilo ─────────────────────────────────────
        p0 = QWidget(); p0.setStyleSheet("background:transparent;")
        p0_lay = QHBoxLayout(p0)
        p0_lay.setContentsMargins(0, 0, 0, 0)
        p0_lay.setSpacing(16)

        left0_scroll = QScrollArea()
        left0_scroll.setWidgetResizable(True)
        left0_scroll.setFrameShape(QFrame.NoFrame)
        left0_scroll.setStyleSheet("background:transparent;")
        left0_scroll.setFixedWidth(430)
        left0_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left0_w = QWidget(); left0_w.setStyleSheet("background:transparent;")
        left0_v = QVBoxLayout(left0_w)
        left0_v.setContentsMargins(0, 0, 0, 0)
        left0_v.setSpacing(14)

        card_single = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(card_single, "Adicionar par de exemplo", "Use uma foto original e a versão final editada como referência.", Icons.star(T["purple"]))
        self._train_before = QLineEdit(); self._train_before.setPlaceholderText("Foto ANTES / original")
        card_single.add_layout(self._path_picker_row(self._train_before, lambda: self._browse_train_file(self._train_before, "Foto ANTES")))
        self._train_after = QLineEdit(); self._train_after.setPlaceholderText("Foto DEPOIS / editada")
        card_single.add_layout(self._path_picker_row(self._train_after, lambda: self._browse_train_file(self._train_after, "Foto DEPOIS")))
        add_btn = QPushButton("+  Adicionar par")
        add_btn.setStyleSheet(BTN_SECONDARY); add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_train_pair)
        card_single.add(add_btn)
        left0_v.addWidget(card_single)

        card_batch = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(card_batch, "Carregar pares por pasta", "Duas pastas com fotos de mesmo nome: originais e editadas.", Icons.folder(T["teal"]))
        self._train_batch_before = QLineEdit(); self._train_batch_before.setPlaceholderText("Pasta ANTES")
        card_batch.add_layout(self._path_picker_row(self._train_batch_before, lambda: self._browse_train_folder(self._train_batch_before)))
        self._train_batch_after = QLineEdit(); self._train_batch_after.setPlaceholderText("Pasta DEPOIS")
        card_batch.add_layout(self._path_picker_row(self._train_batch_after, lambda: self._browse_train_folder(self._train_batch_after)))
        load_btn = QPushButton("Carregar pares da pasta")
        load_btn.setStyleSheet(BTN_SECONDARY); load_btn.setCursor(Qt.PointingHandCursor)
        load_btn.clicked.connect(self._load_train_batch_pairs)
        card_batch.add(load_btn)
        left0_v.addWidget(card_batch)
        left0_v.addStretch(1)
        left0_scroll.setWidget(left0_w)
        p0_lay.addWidget(left0_scroll)

        right0 = QWidget(); right0.setStyleSheet("background:transparent;")
        right0_v = QVBoxLayout(right0)
        right0_v.setContentsMargins(0, 0, 0, 0)
        right0_v.setSpacing(14)

        pairs_card = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(pairs_card, "Pares adicionados", "Usados para aprender o estilo.", Icons.grid(T["teal"]))
        self._train_pairs_box = QTextEdit()
        self._train_pairs_box.setReadOnly(True)
        self._train_pairs_box.setMinimumHeight(200)
        self._train_pairs_box.setPlaceholderText("Nenhum par adicionado ainda.")
        pairs_card.add(self._train_pairs_box, 1)
        right0_v.addWidget(pairs_card, 1)

        action_card = Card(padding=(16, 14, 16, 14), shadow=False)
        self._card_header(action_card, "Treinar perfil de estilo", "Gera um .json com o estilo aprendido.", Icons.tune(T["teal"]))
        self._train_status = QLabel("0 par(es) carregados.")
        self._train_status.setWordWrap(True)
        self._train_status.setStyleSheet(f"font-size:12px;color:{T['text2']};background:transparent;border:none;")
        action_card.add(self._train_status)
        style_row = QHBoxLayout(); style_row.setSpacing(8)
        self._btn_train_style = QPushButton(Icons.play(), " Treinar perfil")
        self._btn_train_style.setStyleSheet(BTN_PRIMARY); self._btn_train_style.setCursor(Qt.PointingHandCursor)
        self._btn_train_style.clicked.connect(self._train_style_profile)
        style_row.addWidget(self._btn_train_style, 1)
        clear_style = QPushButton("Limpar")
        clear_style.setStyleSheet(BTN_GHOST); clear_style.setCursor(Qt.PointingHandCursor)
        clear_style.clicked.connect(self._clear_train_pairs)
        style_row.addWidget(clear_style)
        action_card.add_layout(style_row)
        right0_v.addWidget(action_card)
        p0_lay.addWidget(right0, 1)
        self._train_stack.addWidget(p0)

        # ── Página 1: HDR ────────────────────────────────────────
        p1 = QWidget(); p1.setStyleSheet("background:transparent;")
        p1_lay = QHBoxLayout(p1)
        p1_lay.setContentsMargins(0, 0, 0, 0)
        p1_lay.setSpacing(16)

        hdr_input = Card(padding=(16, 16, 16, 16), shadow=False)
        hdr_input.setFixedWidth(430)
        self._card_header(hdr_input, "Treino Bracketing / HDR", "Pasta com 3 bracketadas + foto final editada.", Icons.activity(T["teal"]))
        self._hdr_train_folder = QLineEdit(); self._hdr_train_folder.setPlaceholderText("Pasta com 3 fotos do bracket")
        hdr_input.add_layout(self._path_picker_row(self._hdr_train_folder, lambda: self._browse_train_folder(self._hdr_train_folder)))
        self._hdr_train_reference = QLineEdit(); self._hdr_train_reference.setPlaceholderText("Foto final editada / referência")
        hdr_input.add_layout(self._path_picker_row(self._hdr_train_reference, lambda: self._browse_train_file(self._hdr_train_reference, "Foto final de referência")))
        add_hdr = QPushButton("+  Adicionar grupo HDR")
        add_hdr.setStyleSheet(BTN_SECONDARY); add_hdr.setCursor(Qt.PointingHandCursor)
        add_hdr.clicked.connect(self._add_hdr_train_group)
        hdr_input.add(add_hdr)
        sep2 = QFrame(); sep2.setFixedHeight(1); sep2.setStyleSheet(f"background:{T['borderSoft']};")
        hdr_input.add(sep2)
        auto_lbl = QLabel("Importação automática — pasta de cômodos")
        auto_lbl.setStyleSheet(f"font-size:11.5px;color:{T['text3']};margin-top:2px;")
        hdr_input.add(auto_lbl)
        auto_desc = QLabel("Estrutura esperada: cada subcarpeta com brutos/ + referencia.jpg")
        auto_desc.setStyleSheet(f"font-size:10.5px;color:{T['text4']};")
        auto_desc.setWordWrap(True)
        hdr_input.add(auto_desc)
        auto_btn = QPushButton(Icons.folder(T["teal"]), "  Importar todos os grupos da pasta")
        auto_btn.setStyleSheet(BTN_PRIMARY); auto_btn.setFixedHeight(38); auto_btn.setCursor(Qt.PointingHandCursor)
        auto_btn.clicked.connect(self._auto_import_hdr_groups)
        hdr_input.add(auto_btn)
        p1_lay.addWidget(hdr_input)

        right1 = QWidget(); right1.setStyleSheet("background:transparent;")
        right1_v = QVBoxLayout(right1)
        right1_v.setContentsMargins(0, 0, 0, 0)
        right1_v.setSpacing(14)

        hdr_list_card = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(hdr_list_card, "Grupos HDR adicionados", "Cada linha: 3/5 bracketadas → 1 referência.", Icons.activity(T["teal"]))
        self._hdr_groups_box = QTextEdit()
        self._hdr_groups_box.setReadOnly(True)
        self._hdr_groups_box.setMinimumHeight(200)
        self._hdr_groups_box.setPlaceholderText("Nenhum grupo HDR adicionado ainda.")
        hdr_list_card.add(self._hdr_groups_box, 1)
        right1_v.addWidget(hdr_list_card, 1)

        hdr_action = Card(padding=(16, 14, 16, 14), shadow=False)
        self._btn_train_hdr = QPushButton(Icons.activity(T["text1"]), " Treinar HDR")
        self._btn_train_hdr.setStyleSheet(BTN_PRIMARY); self._btn_train_hdr.setCursor(Qt.PointingHandCursor)
        self._btn_train_hdr.clicked.connect(self._train_hdr_profile)
        hdr_action.add(self._btn_train_hdr)
        right1_v.addWidget(hdr_action)
        p1_lay.addWidget(right1, 1)
        self._train_stack.addWidget(p1)

        # ── Página 2: Classificador ──────────────────────────────
        p2 = QWidget(); p2.setStyleSheet("background:transparent;")
        p2_lay = QHBoxLayout(p2)
        p2_lay.setContentsMargins(0, 0, 0, 0)
        p2_lay.setSpacing(16)

        clf_card = Card(padding=(16, 16, 16, 16), shadow=False)
        clf_card.setFixedWidth(430)
        self._card_header(clf_card, "Treinar classificador", "Rotule fotos e ajuste como o agente separa Interior / Exterior / Detalhes.", Icons.tune(T["purple"]))
        clf_info = QLabel("Selecione uma foto, escolha a classe correta e adicione como exemplo.")
        clf_info.setWordWrap(True)
        clf_info.setStyleSheet(f"font-size:11.5px;color:{T['text3']};")
        clf_card.add(clf_info)
        clf_file_row = QHBoxLayout()
        self._clf_photo_edit = QLineEdit()
        self._clf_photo_edit.setPlaceholderText("Foto para rotular...")
        self._clf_photo_edit.setMinimumHeight(36)
        clf_file_row.addWidget(self._clf_photo_edit, 1)
        clf_browse = QPushButton("...")
        clf_browse.setFixedWidth(42); clf_browse.setStyleSheet(BTN_GHOST); clf_browse.setCursor(Qt.PointingHandCursor)
        clf_browse.clicked.connect(self._browse_clf_photo)
        clf_file_row.addWidget(clf_browse)
        clf_card.add_layout(clf_file_row)
        clf_card.add(self._section_label("Classe"))
        self._seg_clf_label = SegGroup(
            ["Interior", "Exterior", "Detalhes", "Revisar"],
            "Interior", min_button_width=68, equal=True,
        )
        self._seg_clf_label.changed.connect(self._on_clf_label)
        clf_card.add(self._seg_clf_label)
        clf_add_btn = QPushButton("+  Adicionar exemplo")
        clf_add_btn.setStyleSheet(BTN_SECONDARY); clf_add_btn.setCursor(Qt.PointingHandCursor)
        clf_add_btn.clicked.connect(self._add_clf_example)
        clf_card.add(clf_add_btn)
        self._clf_status = QLabel("0 exemplo(s) adicionados.")
        self._clf_status.setStyleSheet(f"font-size:12px;color:{T['text2']};")
        clf_card.add(self._clf_status)
        clf_train_row = QHBoxLayout()
        self._btn_train_clf = QPushButton(Icons.play(), " Treinar classificador")
        self._btn_train_clf.setStyleSheet(BTN_PRIMARY); self._btn_train_clf.setCursor(Qt.PointingHandCursor)
        self._btn_train_clf.clicked.connect(self._train_classifier)
        clf_train_row.addWidget(self._btn_train_clf, 1)
        clf_clear_btn = QPushButton("Limpar")
        clf_clear_btn.setStyleSheet(BTN_GHOST); clf_clear_btn.setCursor(Qt.PointingHandCursor)
        clf_clear_btn.clicked.connect(self._clear_clf_examples)
        clf_train_row.addWidget(clf_clear_btn)
        clf_card.add_layout(clf_train_row)
        p2_lay.addWidget(clf_card)

        right2 = QWidget(); right2.setStyleSheet("background:transparent;")
        right2_v = QVBoxLayout(right2)
        right2_v.setContentsMargins(0, 0, 0, 0)
        right2_v.setSpacing(14)
        how_card = Card(padding=(16, 16, 16, 16), shadow=False)
        self._card_header(how_card, "Como usar", "Fluxo recomendado para treinar cada perfil.", Icons.eye(T["teal"]))
        how_text = QLabel(
            "Fluxo normal:\n1. Adicione pares ANTES/DEPOIS.\n2. Clique em Treinar perfil.\n\n"
            "Fluxo HDR:\n1. Adicione grupos de 3 bracketadas + referência.\n2. Clique em Treinar HDR.\n"
            "3. Use o JSON em Estilo (opcional) com Bracketing ativo.\n\n"
            "Classificador:\n1. Rotule fotos com a classe correta.\n2. Clique em Treinar classificador."
        )
        how_text.setWordWrap(True)
        how_text.setStyleSheet(f"font-size:12px;color:{T['text3']};background:transparent;border:none;")
        how_card.add(how_text)
        right2_v.addWidget(how_card)
        right2_v.addStretch(1)
        p2_lay.addWidget(right2, 1)
        self._train_stack.addWidget(p2)

        root.addWidget(self._train_stack, 1)
        return body

    def _switch_train_tab(self, idx: int):
        self._train_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._train_tab_btns):
            btn.setStyleSheet(seg_qss(i == idx))

    def _path_picker_row(self, line_edit: QLineEdit, callback):
        row = QHBoxLayout()
        row.setSpacing(8)
        line_edit.setMinimumHeight(38)
        row.addWidget(line_edit, 1)
        btn = QPushButton("...")
        btn.setFixedWidth(42)
        btn.setStyleSheet(BTN_GHOST)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(callback)
        row.addWidget(btn)
        return row

    def _browse_train_file(self, line_edit: QLineEdit, title: str):
        path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            "",
            "Imagens (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.cr3 *.cr2 *.nef *.arw *.dng *.raf *.rw2 *.orf)",
        )
        if path:
            line_edit.setText(path)

    def _browse_train_folder(self, line_edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if path:
            line_edit.setText(path)

    def _add_train_pair(self):
        before = self._train_before.text().strip()
        after = self._train_after.text().strip()
        if not before or not os.path.exists(before):
            QMessageBox.critical(self, "Erro", "Selecione uma foto ANTES válida.")
            return
        if not after or not os.path.exists(after):
            QMessageBox.critical(self, "Erro", "Selecione uma foto DEPOIS válida.")
            return
        self.train_pairs.append({"before": before, "after": after})
        self._train_before.clear()
        self._train_after.clear()
        self._refresh_train_pairs_list()

    def _load_train_batch_pairs(self):
        before_dir = self._train_batch_before.text().strip()
        after_dir = self._train_batch_after.text().strip()
        if not before_dir or not os.path.isdir(before_dir):
            QMessageBox.critical(self, "Erro", "Pasta ANTES inválida.")
            return
        if not after_dir or not os.path.isdir(after_dir):
            QMessageBox.critical(self, "Erro", "Pasta DEPOIS inválida.")
            return
        exts = tuple(IMAGE_EXTS)
        before_files = {os.path.splitext(f)[0]: f for f in os.listdir(before_dir) if f.lower().endswith(exts)}
        after_files = {os.path.splitext(f)[0]: f for f in os.listdir(after_dir) if f.lower().endswith(exts)}
        matched = sorted(set(before_files) & set(after_files))
        if not matched:
            QMessageBox.warning(self, "Nenhum par", "Nenhum arquivo com mesmo nome nas duas pastas.")
            return
        for stem in matched:
            self.train_pairs.append({
                "before": os.path.join(before_dir, before_files[stem]),
                "after": os.path.join(after_dir, after_files[stem]),
            })
        self._refresh_train_pairs_list()
        self._set_train_status(f"+{len(matched)} par(es). Total: {len(self.train_pairs)}")

    def _add_hdr_train_group(self):
        folder = self._hdr_train_folder.text().strip()
        reference = self._hdr_train_reference.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.critical(self, "Erro", "Selecione uma pasta válida com as fotos bracketadas.")
            return
        if not reference or not os.path.exists(reference):
            QMessageBox.critical(self, "Erro", "Selecione uma foto final editada de referência.")
            return
        bracket_paths = find_bracket_images(folder, max_count=5)
        if len(bracket_paths) < 3:
            QMessageBox.critical(self, "Erro", "A pasta do bracket precisa ter pelo menos 3 imagens.")
            return
        self.hdr_train_groups.append({
            "folder": folder,
            "bracket_paths": bracket_paths,
            "reference": reference,
        })
        self._hdr_train_folder.clear()
        self._hdr_train_reference.clear()
        self._refresh_hdr_groups_list()
        self._set_train_status(f"+1 grupo HDR. Total HDR: {len(self.hdr_train_groups)}")

    def _auto_import_hdr_groups(self):
        """
        Escaneia uma pasta raiz buscando subpastas no formato:
          <comodo>/brutos/  +  <comodo>/referencia.jpg
        e importa todos os grupos de uma vez.
        """
        root = QFileDialog.getExistingDirectory(self, "Selecionar pasta raiz dos cômodos")
        if not root:
            return

        IMAGE_EXTS_RAW = {".cr3", ".cr2", ".nef", ".arw", ".dng", ".raf", ".rw2", ".orf",
                          ".jpg", ".jpeg", ".png"}
        added = 0
        skipped: list[str] = []

        for entry in sorted(os.scandir(root), key=lambda e: e.name):
            if not entry.is_dir():
                continue
            comodo = entry.name
            brutos_dir = os.path.join(entry.path, "brutos")

            # Tenta referencia.jpg na pasta do cômodo
            ref_candidates = [
                os.path.join(entry.path, "referencia.jpg"),
                os.path.join(entry.path, "referencia.jpeg"),
                os.path.join(entry.path, "reference.jpg"),
            ]
            reference = next((p for p in ref_candidates if os.path.isfile(p)), None)

            if not os.path.isdir(brutos_dir):
                skipped.append(f"{comodo}: sem pasta brutos/")
                continue
            if not reference:
                skipped.append(f"{comodo}: sem referencia.jpg")
                continue

            bracket_paths = find_bracket_images(brutos_dir, max_count=6)
            if len(bracket_paths) < 2:
                skipped.append(f"{comodo}: menos de 2 imagens em brutos/")
                continue

            self.hdr_train_groups.append({
                "folder": brutos_dir,
                "bracket_paths": bracket_paths,
                "reference": reference,
            })
            added += 1

        self._refresh_hdr_groups_list()
        self._set_train_status(f"+{added} grupo(s) HDR importados. Total: {len(self.hdr_train_groups)}")

        msg = f"{added} grupo(s) importado(s) com sucesso."
        if skipped:
            msg += f"\n\nIgnorados ({len(skipped)}):\n" + "\n".join(skipped[:10])
            if len(skipped) > 10:
                msg += f"\n… e mais {len(skipped) - 10}"
        QMessageBox.information(self, "Importação concluída", msg)

    def _refresh_hdr_groups_list(self):
        if not hasattr(self, "_hdr_groups_box"):
            return
        lines = []
        for idx, group in enumerate(self.hdr_train_groups, 1):
            bracket_names = ", ".join(os.path.basename(p) for p in group["bracket_paths"])
            ref = os.path.basename(str(group["reference"]))
            lines.append(f"{idx:02d}. [{bracket_names}]  →  {ref}")
        self._hdr_groups_box.setPlainText("\n".join(lines))
        if self.hdr_train_groups:
            self._set_train_status(f"{len(self.hdr_train_groups)} grupo(s) HDR carregado(s).")

    def _clear_train_pairs(self):
        self.train_pairs.clear()
        self.hdr_train_groups.clear()
        self._refresh_train_pairs_list()
        self._refresh_hdr_groups_list()
        self._set_train_status("Listas limpas.")

    def _refresh_train_pairs_list(self):
        if not hasattr(self, "_train_pairs_box"):
            return
        lines = []
        for idx, pair in enumerate(self.train_pairs, 1):
            lines.append(f"{idx:02d}. {os.path.basename(pair['before'])}  →  {os.path.basename(pair['after'])}")
        self._train_pairs_box.setPlainText("\n".join(lines))
        self._set_train_status(f"{len(self.train_pairs)} par(es) carregados.")

    def _prepare_train_image(self, path: str, temp_dir: str) -> str:
        if is_raw_file(path):
            return convert_raw_to_jpeg(path, temp_dir, suffix="_TRAIN", quality=96)
        return path

    def _train_style_profile(self):
        if not self.train_pairs:
            QMessageBox.critical(self, "Erro", "Adicione pelo menos um par de fotos antes de treinar.")
            return
        self._btn_train_style.setEnabled(False)
        self._set_train_status("Treinando perfil...")

        pairs = list(self.train_pairs)
        temp_dir = os.path.join(os.getcwd(), "_train_tmp_raw")

        def worker():
            try:
                trainer = StyleTrainer()
                os.makedirs(temp_dir, exist_ok=True)
                for pair in pairs:
                    before = self._prepare_train_image(pair["before"], temp_dir)
                    after = self._prepare_train_image(pair["after"], temp_dir)
                    trainer.add_pair(before, after)
                trainer.learn()
                self._train_bridge.done.emit(trainer)
            except Exception as exc:
                self._train_bridge.error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _train_hdr_profile(self):
        if not self.hdr_train_groups:
            QMessageBox.critical(self, "Erro", "Adicione pelo menos um grupo HDR antes de treinar.")
            return
        self._btn_train_hdr.setEnabled(False)
        self._btn_train_style.setEnabled(False)
        self._set_train_status("Treinando perfil HDR...")

        groups = list(self.hdr_train_groups)

        def worker():
            try:
                trainer = HdrBracketTrainer()
                for group in groups:
                    trainer.add_group(
                        list(group["bracket_paths"]),
                        str(group["reference"]),
                        name=os.path.basename(str(group["folder"])),
                    )
                profile = trainer.train(lambda msg: self._train_bridge.status.emit(msg))
                self._train_bridge.done.emit(("hdr", trainer, profile))
            except Exception as exc:
                self._train_bridge.error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_train_done(self, trainer):
        self._btn_train_style.setEnabled(True)
        if hasattr(self, "_btn_train_hdr"):
            self._btn_train_hdr.setEnabled(True)

        if isinstance(trainer, tuple) and trainer and trainer[0] == "hdr":
            _, hdr_trainer, profile = trainer
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar perfil HDR treinado",
                "perfil_hdr_imobiliario.json",
                "JSON (*.json)",
            )
            if path:
                hdr_trainer.save_profile(path)
                if hasattr(self, "_style_path"):
                    self._style_path.setText(path)
                self._set_train_status(f"Perfil HDR salvo com {len(self.hdr_train_groups)} grupo(s): {os.path.basename(path)}")
                self._switch_tab(0)
            else:
                self._set_train_status("Treinamento HDR concluído, mas o perfil não foi salvo.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar perfil de estilo",
            "meu_estilo.json",
            "JSON (*.json)",
        )
        if path:
            trainer.save_profile(path)
            if hasattr(self, "_style_path"):
                self._style_path.setText(path)
            self._set_train_status(f"Perfil salvo com {len(self.train_pairs)} par(es): {os.path.basename(path)}")
            self._switch_tab(0)
        else:
            self._set_train_status("Treinamento concluído, mas o perfil não foi salvo.")

    def _on_train_error(self, message: str):
        self._btn_train_style.setEnabled(True)
        if hasattr(self, "_btn_train_hdr"):
            self._btn_train_hdr.setEnabled(True)
        self._set_train_status("Erro no treinamento.")
        QMessageBox.critical(self, "Erro ao treinar", message)

    def _set_train_status(self, text: str):
        if hasattr(self, "_train_status"):
            self._train_status.setText(text)

    # ── Classifier labeling handlers ─────────────────────────────

    def _browse_clf_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar foto para rotular", "",
            "Imagens (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp)",
        )
        if path:
            self._clf_photo_edit.setText(path)

    def _on_clf_label(self, value: str):
        mapping = {"Interior": "interior", "Exterior": "exterior",
                   "Detalhes": "detalhes", "Revisar": "revisar"}
        self._clf_label = mapping.get(value, "interior")

    def _add_clf_example(self):
        path = self._clf_photo_edit.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.critical(self, "Erro", "Selecione uma foto válida para rotular.")
            return
        try:
            ok = self.classifier_trainer.add_example(path, self._clf_label)
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        if not ok:
            QMessageBox.warning(self, "Aviso", "Não foi possível ler a imagem selecionada.")
            return
        self._clf_photo_edit.clear()
        counts = self.classifier_trainer.count()
        total = sum(counts.values())
        detail = " | ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        self._clf_status.setText(f"{total} exemplo(s) — {detail}")

    def _clear_clf_examples(self):
        self.classifier_trainer.clear()
        self._clf_status.setText("0 exemplo(s) adicionados.")

    def _train_classifier(self):
        counts = self.classifier_trainer.count()
        if sum(counts.values()) < 2:
            QMessageBox.critical(self, "Erro", "Adicione pelo menos 2 exemplos rotulados antes de treinar.")
            return
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar perfil do classificador", "classifier_profile.json",
            "JSON (*.json)"
        )
        if not out_path:
            return
        try:
            profile = self.classifier_trainer.train()
            self.classifier_trainer.save(profile, out_path)
            QMessageBox.information(
                self, "Treinamento concluído",
                f"Perfil salvo em:\n{out_path}\n\n"
                f"Exemplos: {profile['n_examples']} | Classes: {profile['class_counts']}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao treinar classificador", str(exc))

    # ── Histórico (7.1) ──────────────────────────────────────────
    def _mk_history_tab(self):
        body = QWidget()
        body.setStyleSheet(f"background:{T['bg0']};")
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Histórico de processamentos")
        title.setStyleSheet(f"font-size:18px;font-weight:800;color:{T['text1']};")
        header.addWidget(title, 1)
        clear_btn = QPushButton("Limpar histórico")
        clear_btn.setStyleSheet(BTN_GHOST)
        clear_btn.setFixedHeight(34)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_history)
        header.addWidget(clear_btn)
        root.addLayout(header)

        # 9.3 — estatísticas acumuladas
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self._stat_lbl_sessions = self._mk_hist_stat_chip("Sessões", "0", stats_row)
        self._stat_lbl_photos   = self._mk_hist_stat_chip("Fotos processadas", "0", stats_row)
        self._stat_lbl_preset   = self._mk_hist_stat_chip("Preset mais usado", "—", stats_row)
        stats_row.addStretch()
        root.addLayout(stats_row)

        # 9.4 — busca
        self._history_search_edit = QLineEdit()
        self._history_search_edit.setPlaceholderText("Buscar por pasta ou data…")
        self._history_search_edit.setFixedHeight(34)
        self._history_search_edit.setStyleSheet(
            f"QLineEdit{{background:{T['bg2']};border:1px solid {T['border']};"
            f"border-radius:10px;padding:0 12px;color:{T['text2']};font-size:12px;}}"
        )
        self._history_search_edit.textChanged.connect(self._refresh_history_ui)
        root.addWidget(self._history_search_edit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._history_list_widget = QWidget()
        self._history_list_widget.setStyleSheet("background: transparent;")
        self._history_list_layout = QVBoxLayout(self._history_list_widget)
        self._history_list_layout.setContentsMargins(0, 0, 0, 0)
        self._history_list_layout.setSpacing(10)
        self._history_list_layout.addStretch()
        scroll.setWidget(self._history_list_widget)
        root.addWidget(scroll, 1)
        self._refresh_history_ui()
        return body

    def _load_history_from_disk(self):
        try:
            self._history = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._history = []

    def _save_history_to_disk(self):
        try:
            _HISTORY_PATH.write_text(
                json.dumps(self._history[-_HISTORY_MAX:], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _add_history_entry(self, stats: dict):
        if not stats:
            return
        folders = self._batch_folders or [self._input_dir.text().strip()]
        entry = {
            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "folders": folders,
            "output": self._output_dir.text().strip(),
            "processed": stats.get("processed", stats.get("total", 0)),
            "errors": stats.get("errors", 0),
            "duration_sec": stats.get("duration_sec", 0),
            "by_class": stats.get("by_class", {}),
            "preset": self._automation_preset,
        }
        self._history.append(entry)
        self._save_history_to_disk()
        self._refresh_history_ui()

    def _clear_history(self):
        from PySide6.QtWidgets import QMessageBox as _MB
        if _MB.question(self, "Limpar histórico", "Apagar todo o histórico?",
                        _MB.Yes | _MB.No) != _MB.Yes:
            return
        self._history.clear()
        self._save_history_to_disk()
        self._refresh_history_ui()

    def _mk_hist_stat_chip(self, label: str, value: str, layout: QHBoxLayout) -> QLabel:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:{T['bg2']};border:1px solid {T['borderSoft']};"
            f"border-radius:10px;}} QLabel{{border:none;background:transparent;}}"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(14, 6, 14, 6)
        fl.setSpacing(1)
        ll = QLabel(label)
        ll.setStyleSheet(f"font-size:10px;color:{T['text4']};")
        vl = QLabel(value)
        vl.setStyleSheet(f"font-size:16px;font-weight:800;color:{T['teal']};")
        fl.addWidget(ll)
        fl.addWidget(vl)
        layout.addWidget(frame)
        return vl

    def _refresh_history_ui(self):
        if not hasattr(self, "_history_list_layout"):
            return

        # 9.3 — update accumulated stats
        if hasattr(self, "_stat_lbl_sessions"):
            total_photos = sum(e.get("processed", 0) for e in self._history)
            preset_counts: dict[str, int] = {}
            for e in self._history:
                p = e.get("preset", "")
                if p:
                    preset_counts[p] = preset_counts.get(p, 0) + 1
            top_preset = max(preset_counts, key=preset_counts.get) if preset_counts else "—"
            self._stat_lbl_sessions.setText(str(len(self._history)))
            self._stat_lbl_photos.setText(str(total_photos))
            self._stat_lbl_preset.setText(top_preset)

        # 9.4 — apply search filter
        query = ""
        if hasattr(self, "_history_search_edit"):
            query = self._history_search_edit.text().strip().lower()
        filtered = [
            e for e in self._history
            if not query
            or query in e.get("date", "").lower()
            or any(query in f.lower() for f in e.get("folders", []))
            or query in e.get("preset", "").lower()
        ]

        while self._history_list_layout.count():
            item = self._history_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not filtered:
            msg = "Nenhum resultado para a busca." if query else "Nenhum processamento registrado ainda."
            empty = QLabel(msg)
            empty.setStyleSheet(f"font-size:13px;color:{T['text4']};")
            empty.setAlignment(Qt.AlignCenter)
            self._history_list_layout.addWidget(empty)
            self._history_list_layout.addStretch()
            return

        for entry in reversed(filtered):
            card = Card(padding=(14, 12, 14, 12), shadow=False)
            top = QHBoxLayout()
            date_lbl = QLabel(entry.get("date", ""))
            date_lbl.setStyleSheet(f"font-size:12px;color:{T['text3']};font-family:Consolas,monospace;")
            top.addWidget(date_lbl)
            top.addStretch()
            preset_lbl = QLabel(entry.get("preset", ""))
            preset_lbl.setStyleSheet(
                f"background:{T['bg3']};color:{T['teal']};border-radius:8px;"
                f"font-size:11px;font-weight:700;padding:2px 8px;"
            )
            top.addWidget(preset_lbl)
            card.add_layout(top)

            folders = entry.get("folders", [])
            for f in folders[:3]:
                flbl = QLabel(f"📁  {os.path.basename(f) or f}")
                flbl.setStyleSheet(f"font-size:12px;color:{T['text1']};font-weight:600;")
                flbl.setToolTip(f)
                card.add(flbl)
            if len(folders) > 3:
                card.add(QLabel(f"  + {len(folders) - 3} pasta(s)"))

            chips = QHBoxLayout()
            chips.setSpacing(8)
            processed = entry.get("processed", 0)
            errors = entry.get("errors", 0)
            dur = entry.get("duration_sec", 0)
            mins, secs = divmod(int(dur), 60)
            time_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
            for label, value, color in [
                ("Processadas", str(processed), T["teal"]),
                ("Erros", str(errors), T["danger"] if errors else T["text3"]),
                ("Tempo", time_str, T["text2"]),
            ]:
                chip = QFrame()
                chip.setStyleSheet(
                    f"QFrame{{background:{T['bg3']};border:1px solid {T['borderSoft']};"
                    f"border-radius:8px;}} QLabel{{border:none;background:transparent;}}"
                )
                cl = QVBoxLayout(chip)
                cl.setContentsMargins(10, 5, 10, 5)
                cl.setSpacing(1)
                ll = QLabel(label)
                ll.setStyleSheet(f"font-size:10px;color:{T['text4']};")
                vl = QLabel(value)
                vl.setStyleSheet(f"font-size:14px;font-weight:800;color:{color};")
                cl.addWidget(ll)
                cl.addWidget(vl)
                chips.addWidget(chip)
            chips.addStretch()
            out_path = entry.get("output", "")
            if out_path and os.path.isdir(out_path):
                open_btn = QPushButton(Icons.folder(T["text3"]), " Abrir saída")
                open_btn.setFixedHeight(30)
                open_btn.setStyleSheet(BTN_GHOST)
                open_btn.setCursor(Qt.PointingHandCursor)
                open_btn.clicked.connect(lambda _, p=out_path: os.startfile(p))
                chips.addWidget(open_btn)
            card.add_layout(chips)
            self._history_list_layout.addWidget(card)

        self._history_list_layout.addStretch()

    # ── Comparação pós-processamento (7.3) ───────────────────────
    def _enter_compare_mode(self):
        import time as _time
        from utils.config import SUPPORTED_EXTENSIONS
        out = self._output_dir.text().strip()
        originals_dir = os.path.join(out, "01_ORIGINAIS")

        # 1ª opção: lista exata vinda do STATS do pipeline
        if self._current_run_files:
            processed = sorted(self._current_run_files)
            self._results_map = dict(self._current_run_map)
        else:
            # 2ª opção: varre 03_MELHORADAS filtrando só arquivos gerados neste run
            enhanced_dir = os.path.join(out, "03_MELHORADAS")
            run_start = self._run_start_time
            if run_start > 0 and os.path.isdir(enhanced_dir):
                processed = sorted([
                    os.path.join(enhanced_dir, f)
                    for f in os.listdir(enhanced_dir)
                    if os.path.splitext(f.lower())[1] in SUPPORTED_EXTENSIONS
                    and os.path.getmtime(os.path.join(enhanced_dir, f)) >= run_start - 2
                ])
            else:
                processed = []
            self._results_map = {}

        if not processed:
            QMessageBox.information(
                self, "Comparar",
                "Processe as imagens primeiro.\n"
                "O modo comparação mostra apenas o resultado do processamento atual."
            )
            return

        # Completa o mapa com originais pelo nome para arquivos sem par
        from utils.config import SUPPORTED_EXTENSIONS
        for p in processed:
            if p not in self._results_map:
                name = os.path.basename(p)
                orig = os.path.join(originals_dir, name)
                if not os.path.isfile(orig) and name.lower().endswith("_hdr.jpg"):
                    # Para arquivo HDR busca o original base pelo nome sem _HDR
                    stem = name[:-8]  # remove "_HDR.jpg"
                    for ext in (".jpg", ".jpeg", ".cr3", ".cr2", ".nef", ".arw", ".dng"):
                        candidate = os.path.join(originals_dir, stem + ext)
                        if os.path.isfile(candidate):
                            orig = candidate
                            break
                self._results_map[p] = orig if os.path.isfile(orig) else p

        self._compare_mode = True
        self._image_paths = processed
        self._populate_filmstrip(processed)
        self._populate_queue(processed)
        self._queue_badge.setText(str(len(processed)))
        self._sb_st.setText(f"Modo comparação — {len(processed)} foto(s) processada(s)")
        self._sb_ct.setText("Clique em uma foto para comparar original vs processada")
        if processed:
            self._select_image(processed[0])
        if hasattr(self, "_res_compare_btn"):
            self._res_compare_btn.setText("Sair da comparação")
            self._res_compare_btn.clicked.disconnect()
            self._res_compare_btn.clicked.connect(self._exit_compare_mode)

    def _exit_compare_mode(self):
        self._compare_mode = False
        self._results_map = {}
        inp = self._input_dir.text().strip()
        if inp and os.path.isdir(inp):
            self._load_images_from_folder(inp)
        self._sb_st.setText("Pronto")
        self._sb_ct.setText(f"{len(self._image_paths)} fotos na fila")
        if hasattr(self, "_res_compare_btn"):
            self._res_compare_btn.setText(f"{Icons.eye(T['text1'])}  Comparar")
            self._res_compare_btn.clicked.disconnect()
            self._res_compare_btn.clicked.connect(self._enter_compare_mode)
        # Reconecta ícone corretamente
        if hasattr(self, "_res_compare_btn"):
            self._res_compare_btn.setIcon(Icons.eye(T["text1"]))
            self._res_compare_btn.setText(" Comparar")

    # ── Preset Manager (6.3) ─────────────────────────────────────
    def _load_presets_from_disk(self):
        try:
            self._presets = json.loads(_PRESETS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._presets = {}

    def _save_presets_to_disk(self):
        try:
            _PRESETS_PATH.write_text(json.dumps(self._presets, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _refresh_preset_combo(self):
        if not hasattr(self, "_preset_combo"):
            return
        self._preset_combo.clear()
        if not self._presets:
            self._preset_combo.addItem("— Nenhum preset salvo —")
        else:
            for name in sorted(self._presets.keys()):
                self._preset_combo.addItem(name)

    def _collect_preset_state(self) -> dict:
        return {
            "automation_preset":             self._automation_preset,
            "intensity":                     self._intensity,
            "color_mode":                    self._color_mode,
            "upscale_enabled":               self._upscale_enabled,
            "upscale_factor":                self._upscale_factor,
            "upscale_preset":                self._upscale_preset,
            "bracketing_enabled":            self._bracketing_enabled,
            "bracketing_group_size":         self._bracketing_group_size,
            "bracketing_fusion_preset":      self._bracketing_fusion_preset,
            "bracketing_apply_auto_enhance": self._bracketing_apply_auto_enhance,
            "rename_enabled":                self._rename_enabled,
            "rename_prefix":                 self._rename_prefix,
            "rename_code":                   self._rename_code,
            "watermark_enabled":             self._watermark_enabled,
            "watermark_text":                self._watermark_text,
            "watermark_position":            self._watermark_position,
            "watermark_opacity":             self._watermark_opacity,
            "export_profiles":               sorted(self._export_profiles),
            "duplicates_enabled":            self._duplicates_enabled,
            "duplicates_threshold":          self._duplicates_threshold,
            "contact_sheet_enabled":         self._contact_sheet_enabled,
            "before_after_enabled":          self._before_after_enabled,
            "gallery_title":                 self._gallery_title,
            "gallery_subtitle":              self._gallery_subtitle,
            "photographer":                  self._photographer,
            "copyright_text":                self._copyright_text,
            "subfolder_recursive":           self._subfolder_recursive,
            # widget visual state
            "seg_preset":         getattr(self, "_seg_preset", None) and self._seg_preset.value(),
            "seg_intensity":      getattr(self, "_seg_intensity", None) and self._seg_intensity.value(),
            "seg_color":          getattr(self, "_seg_color", None) and self._seg_color.value(),
            "seg_bracket_group":  getattr(self, "_seg_bracket_group", None) and self._seg_bracket_group.value(),
            "seg_bracket_preset": getattr(self, "_seg_bracket_preset", None) and self._seg_bracket_preset.value(),
            "seg_factor":         getattr(self, "_seg_factor", None) and self._seg_factor.value(),
            "seg_upscale_preset": getattr(self, "_seg_upscale_preset", None) and self._seg_upscale_preset.value(),
            "tg_bracket":         getattr(self, "_tg_bracket", None) and self._tg_bracket.isChecked(),
            "tg_hdr_finish":      getattr(self, "_tg_hdr_finish", None) and self._tg_hdr_finish.isChecked(),
            "tg_upscale":         getattr(self, "_tg_upscale", None) and self._tg_upscale.isChecked(),
            "tg_subfolder":       getattr(self, "_tg_subfolder", None) and self._tg_subfolder.isChecked(),
        }

    def _apply_preset_state(self, state: dict):
        # Internal state
        for attr in ("automation_preset", "intensity", "color_mode", "upscale_factor",
                     "upscale_preset", "bracketing_group_size", "bracketing_fusion_preset",
                     "rename_prefix", "rename_code", "watermark_text", "watermark_position",
                     "gallery_title", "gallery_subtitle", "photographer", "copyright_text"):
            if attr in state:
                setattr(self, f"_{attr}", state[attr])
        for bool_attr in ("upscale_enabled", "bracketing_enabled", "bracketing_apply_auto_enhance",
                          "rename_enabled", "watermark_enabled", "duplicates_enabled",
                          "contact_sheet_enabled", "before_after_enabled", "subfolder_recursive"):
            if bool_attr in state:
                setattr(self, f"_{bool_attr}", bool(state[bool_attr]))
        if "watermark_opacity" in state:
            self._watermark_opacity = float(state["watermark_opacity"])
        if "duplicates_threshold" in state:
            self._duplicates_threshold = int(state["duplicates_threshold"])
        if "export_profiles" in state:
            self._export_profiles = set(state["export_profiles"])
        # Widget visuals
        for seg_attr, key in [
            ("_seg_preset", "seg_preset"), ("_seg_intensity", "seg_intensity"),
            ("_seg_color", "seg_color"), ("_seg_bracket_group", "seg_bracket_group"),
            ("_seg_bracket_preset", "seg_bracket_preset"), ("_seg_factor", "seg_factor"),
            ("_seg_upscale_preset", "seg_upscale_preset"),
        ]:
            if state.get(key) and hasattr(self, seg_attr):
                getattr(self, seg_attr).select(state[key], emit=False)
        for tg_attr, key in [
            ("_tg_bracket", "tg_bracket"), ("_tg_hdr_finish", "tg_hdr_finish"),
            ("_tg_upscale", "tg_upscale"), ("_tg_subfolder", "tg_subfolder"),
        ]:
            if key in state and hasattr(self, tg_attr):
                getattr(self, tg_attr).set_state(bool(state[key]))
        if hasattr(self, "_tg_rename"):
            self._tg_rename.set_state(self._rename_enabled)
            self._rename_body.setVisible(self._rename_enabled)
            self._rename_prefix_edit.setText(self._rename_prefix)
            self._rename_code_edit.setText(self._rename_code)
        if hasattr(self, "_tg_watermark"):
            self._tg_watermark.set_state(self._watermark_enabled)
            self._watermark_body.setVisible(self._watermark_enabled)
            self._wm_text_edit.setText(self._watermark_text)
            self._wm_opacity_slider.setValue(int(self._watermark_opacity * 100))
            if hasattr(self, "_seg_wm_mode"):
                mode_label = "Logo" if self._watermark_mode == "image" else "Texto"
                self._seg_wm_mode.select(mode_label, emit=False)
                self._wm_text_panel.setVisible(self._watermark_mode == "text")
                self._wm_logo_panel.setVisible(self._watermark_mode == "image")
            if hasattr(self, "_wm_logo_edit"):
                self._wm_logo_edit.setText(self._watermark_logo_path)
        if hasattr(self, "_tg_export"):
            for key, tg in self._tg_export.items():
                tg.set_state(key in self._export_profiles)
        if hasattr(self, "_tg_duplicates"):
            self._tg_duplicates.set_state(self._duplicates_enabled)
            self._dup_slider.setValue(self._duplicates_threshold)
        if hasattr(self, "_tg_contact"):
            self._tg_contact.set_state(self._contact_sheet_enabled)
        if hasattr(self, "_tg_before_after"):
            self._tg_before_after.set_state(self._before_after_enabled)
        if hasattr(self, "_gallery_title_edit"):
            self._gallery_title_edit.setText(self._gallery_title)
            self._gallery_subtitle_edit.setText(self._gallery_subtitle)
            self._photographer_edit.setText(self._photographer)
            self._copyright_edit.setText(self._copyright_text)
        self._update_summary()

    def _save_current_preset(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Salvar preset", "Nome do preset:")
        if not ok or not name.strip():
            return
        name = name.strip()
        self._presets[name] = self._collect_preset_state()
        self._save_presets_to_disk()
        self._refresh_preset_combo()
        idx = self._preset_combo.findText(name)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)

    def _load_selected_preset(self):
        name = self._preset_combo.currentText()
        if name not in self._presets:
            return
        self._apply_preset_state(self._presets[name])

    def _delete_selected_preset(self):
        name = self._preset_combo.currentText()
        if name not in self._presets:
            return
        reply = QMessageBox.question(
            self, "Excluir preset", f'Excluir o preset "{name}"?',
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            del self._presets[name]
            self._save_presets_to_disk()
            self._refresh_preset_combo()

    # ── Multi-folder queue (6.1) ──────────────────────────────────
    def _add_folder_clicked(self):
        path = QFileDialog.getExistingDirectory(self, "Adicionar pasta à fila")
        if not path:
            return
        if path in self._folder_queue:
            return
        self._folder_queue.append(path)
        self._refresh_folder_list_ui()
        # Carrega imagens da primeira pasta adicionada para o preview
        if len(self._folder_queue) == 1:
            self._input_dir.setText(path)
            self._load_images_from_folder(path, show_feedback=True)

    def _remove_folder_from_queue(self, idx: int):
        if 0 <= idx < len(self._folder_queue):
            self._folder_queue.pop(idx)
            self._refresh_folder_list_ui()

    def _refresh_folder_list_ui(self):
        if not hasattr(self, "_folder_list_layout"):
            return
        # Limpa widgets antigos
        while self._folder_list_layout.count():
            item = self._folder_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, folder_path in enumerate(self._folder_queue):
            row = QFrame()
            row.setStyleSheet(
                f"QFrame {{ background:{T['bg3']}; border:1px solid {T['borderSoft']};"
                f" border-radius:8px; }} QLabel {{ border:none; background:transparent; }}"
            )
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(8, 5, 8, 5)
            row_lay.setSpacing(6)
            ic = QLabel()
            ic.setPixmap(Icons.folder(T["teal"]).pixmap(14, 14))
            ic.setFixedSize(14, 14)
            row_lay.addWidget(ic)
            name = os.path.basename(folder_path) or folder_path
            lbl = QLabel(name)
            lbl.setStyleSheet(f"font-size:11.5px;color:{T['text1']};font-weight:600;")
            lbl.setToolTip(folder_path)
            row_lay.addWidget(lbl, 1)
            badge = QLabel(f"{len(self._find_images(folder_path))}")
            badge.setStyleSheet(f"font-size:11px;color:{T['text3']};")
            row_lay.addWidget(badge)
            rm_btn = QPushButton("×")
            rm_btn.setFixedSize(20, 20)
            rm_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{T['text4']};border:none;font-size:14px;font-weight:700;}} QPushButton:hover{{color:{T['danger']};}}")
            rm_btn.setCursor(Qt.PointingHandCursor)
            rm_btn.clicked.connect(lambda _, i=idx: self._remove_folder_from_queue(i))
            row_lay.addWidget(rm_btn)
            self._folder_list_layout.addWidget(row)

    # ── PDF Export (6.2) ─────────────────────────────────────────
    def _export_pdf(self):
        out = self._output_dir.text().strip()
        if not out or not os.path.isdir(out):
            QMessageBox.warning(self, "PDF", "Defina uma pasta de saída válida primeiro.")
            return
        from utils.config import SUPPORTED_EXTENSIONS
        search_dirs = [
            os.path.join(out, "03_MELHORADAS"),
            out,
        ]
        image_files = []
        for d in search_dirs:
            if os.path.isdir(d):
                image_files = sorted([
                    os.path.join(d, f) for f in os.listdir(d)
                    if os.path.splitext(f.lower())[1] in SUPPORTED_EXTENSIONS
                ])
                if image_files:
                    break
        if not image_files:
            QMessageBox.warning(self, "PDF", "Nenhuma imagem encontrada na pasta de saída.")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar PDF", os.path.join(out, "fotos_imovel.pdf"), "PDF (*.pdf)"
        )
        if not save_path:
            return
        try:
            from core.pdf_exporter import export_contact_sheet_pdf
            export_contact_sheet_pdf(image_files, save_path, title=self._gallery_title or "Fotos do Imóvel")
            QMessageBox.information(
                self, "PDF exportado",
                f"{len(image_files)} fotos exportadas para PDF:\n{save_path}"
            )
            try:
                os.startfile(save_path)
            except Exception:
                pass
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao gerar PDF", str(exc))

    # ── Real-time preview (6.4) ───────────────────────────────────
    def _run_real_preview(self, path: str):
        tmp_src = None
        tmp_out = None
        try:
            # Converte RAW para JPEG temporário se necessário
            if is_raw_file(path):
                tmp_dir = tempfile.mkdtemp()
                tmp_src = convert_raw_to_jpeg(path, tmp_dir, suffix="_PREV", quality=95)
                src = tmp_src
            else:
                src = path

            style_path = self._style_path.text().strip() or None
            intensity = self._intensity
            color_mode = self._color_mode

            if style_path and os.path.isfile(style_path):
                enhancer = StyledEnhancer.from_file(style_path, intensity=intensity, color_mode=color_mode)
            else:
                enhancer = StyledEnhancer({}, intensity=intensity, color_mode=color_mode)

            fd, tmp_out = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            enhancer.enhance(src, tmp_out, category="interior")
            self._preview_bridge.preview_ready.emit(path, tmp_out)
        except Exception:
            if tmp_out and os.path.exists(tmp_out):
                try:
                    os.unlink(tmp_out)
                except Exception:
                    pass
            self._preview_bridge.preview_ready.emit(path, "")
        finally:
            if tmp_src and os.path.exists(tmp_src):
                try:
                    os.unlink(tmp_src)
                except Exception:
                    pass

    def _run_hdr_preview(self, base_path: str, group_paths: list[str]):
        """Funde o grupo de brackets e emite o resultado como preview HDR."""
        raw_tmp_dir = None
        fd, tmp_out = tempfile.mkstemp(suffix="_hdr_preview.jpg")
        os.close(fd)
        try:
            proc = BracketingProcessor(
                group_size=len(group_paths),
                fusion_preset=self._bracketing_fusion_preset,
                auto_chromatic_aberration=True,
                auto_lens_correction=True,
                auto_geometry_correction=True,
                skip_lightroom_finish=False,
            )
            # Converte RAW se necessário
            ready_paths = []
            needs_raw_conversion = any(is_raw_file(p) for p in group_paths)
            if needs_raw_conversion:
                raw_tmp_dir = tempfile.mkdtemp()
                for p in group_paths:
                    if is_raw_file(p):
                        jp = convert_raw_to_jpeg(p, raw_tmp_dir, suffix="_PREV", quality=95)
                        ready_paths.append(jp)
                    else:
                        ready_paths.append(p)
            else:
                ready_paths = list(group_paths)
            proc.fuse_group(ready_paths, tmp_out)
            self._preview_bridge.preview_ready.emit(base_path, tmp_out)
        except Exception as exc:
            if os.path.exists(tmp_out):
                try:
                    os.unlink(tmp_out)
                except Exception:
                    pass
            self._preview_bridge.preview_ready.emit(base_path, "")
            import traceback
            print(f"[HDR preview] erro: {exc}\n{traceback.format_exc()}")
        finally:
            self._hdr_preview_loading = False
            if raw_tmp_dir and os.path.isdir(raw_tmp_dir):
                import shutil
                try:
                    shutil.rmtree(raw_tmp_dir, ignore_errors=True)
                except Exception:
                    pass

    def _show_fullscreen_preview(self):
        if self._compare._before is None:
            return
        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Prévia — Tela cheia")
        dlg.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        dlg.setStyleSheet(f"QDialog {{ background:{T['bg0']}; }}")
        dlg.resize(1400, 900)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Header
        header = QHBoxLayout()
        lbl = QLabel("Antes / Depois")
        lbl.setStyleSheet(f"font-size:16px;font-weight:800;color:{T['text1']};")
        header.addWidget(lbl, 1)
        if self._selected_image:
            name_lbl = QLabel(os.path.basename(self._selected_image))
            name_lbl.setStyleSheet(f"font-size:12px;color:{T['text3']};")
            header.addWidget(name_lbl)
        close_btn = QPushButton("Fechar")
        close_btn.setStyleSheet(BTN_GHOST)
        close_btn.setFixedHeight(34)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dlg.close)
        header.addWidget(close_btn)
        lay.addLayout(header)

        # CompareView com as mesmas imagens
        view = CompareView()
        view.set_images_from_pixmaps(self._compare._before, self._compare._after)
        lay.addWidget(view, 1)

        dlg.exec()

    def _on_preview_ready(self, original_path: str, enhanced_path: str):
        self._preview_loading = False
        self._hdr_preview_loading = False
        if original_path != self._selected_image:
            if enhanced_path and os.path.exists(enhanced_path):
                try:
                    os.unlink(enhanced_path)
                except Exception:
                    pass
            return
        before = self._load_pixmap(original_path)
        if enhanced_path and os.path.isfile(enhanced_path):
            reader = QImageReader(enhanced_path)
            reader.setAutoTransform(True)
            img = reader.read()
            after = QPixmap.fromImage(img) if not img.isNull() else before
            try:
                os.unlink(enhanced_path)
            except Exception:
                pass
        else:
            after = before
        self._compare.set_images_from_pixmaps(before, after)
        is_hdr = original_path in getattr(self, "_bracket_groups", {})
        label = "HDR fundido" if is_hdr else "Preview"
        self._sb_st.setText(f"{label}: {os.path.basename(original_path)}")

    # ── Nível 10.3 — slideshow ────────────────────────────────────
    def _show_slideshow(self, images: list[str]):
        images = [p for p in images if os.path.isfile(p)]
        if not images:
            QMessageBox.information(self, "Slideshow", "Nenhuma imagem disponível.")
            return
        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Slideshow — AGENTE FOTOS")
        dlg.setStyleSheet(f"QDialog{{background:#000;}}")
        dlg.showFullScreen()

        root = QVBoxLayout(dlg)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        img_lbl.setStyleSheet("background:#000;")
        root.addWidget(img_lbl, 1)

        bar = QHBoxLayout()
        bar.setContentsMargins(20, 8, 20, 8)
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(40, 40)
        prev_btn.setStyleSheet("QPushButton{background:#222;color:#fff;border-radius:8px;font-size:18px;} QPushButton:hover{background:#444;}")
        counter_lbl = QLabel()
        counter_lbl.setStyleSheet("color:#aaa;font-size:13px;")
        counter_lbl.setAlignment(Qt.AlignCenter)
        name_lbl = QLabel()
        name_lbl.setStyleSheet("color:#ddd;font-size:12px;")
        name_lbl.setAlignment(Qt.AlignCenter)
        next_btn = QPushButton("▶")
        next_btn.setFixedSize(40, 40)
        next_btn.setStyleSheet("QPushButton{background:#222;color:#fff;border-radius:8px;font-size:18px;} QPushButton:hover{background:#444;}")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("QPushButton{background:#333;color:#aaa;border-radius:8px;font-size:14px;} QPushButton:hover{background:#555;color:#fff;}")
        bar.addWidget(prev_btn)
        bar.addStretch()
        bar.addWidget(counter_lbl)
        bar.addWidget(name_lbl)
        bar.addStretch()
        bar.addWidget(next_btn)
        bar.addSpacing(16)
        bar.addWidget(close_btn)
        bar_w = QWidget()
        bar_w.setStyleSheet("background:#111;")
        bar_w.setFixedHeight(56)
        bar_w.setLayout(bar)
        root.addWidget(bar_w)

        state = {"idx": 0, "paused": False}

        def show_image(i):
            state["idx"] = i % len(images)
            path = images[state["idx"]]
            px = QPixmap(path)
            if not px.isNull():
                avail = img_lbl.size()
                img_lbl.setPixmap(px.scaled(avail, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            counter_lbl.setText(f"{state['idx'] + 1} / {len(images)}")
            name_lbl.setText(f"   {os.path.basename(path)}")

        timer = QTimer(dlg)
        timer.setInterval(5000)
        timer.timeout.connect(lambda: show_image(state["idx"] + 1))
        timer.start()

        prev_btn.clicked.connect(lambda: (show_image(state["idx"] - 1), timer.start()))
        next_btn.clicked.connect(lambda: (show_image(state["idx"] + 1), timer.start()))
        close_btn.clicked.connect(dlg.close)

        def key_handler(event):
            k = event.key()
            if k == Qt.Key_Escape:
                dlg.close()
            elif k in (Qt.Key_Right, Qt.Key_Space):
                show_image(state["idx"] + 1); timer.start()
            elif k == Qt.Key_Left:
                show_image(state["idx"] - 1); timer.start()
            elif k == Qt.Key_P:
                if timer.isActive(): timer.stop()
                else: timer.start()
        dlg.keyPressEvent = key_handler

        show_image(0)
        dlg.exec()

    def _show_slideshow_output(self):
        out = self._output_dir.text().strip()
        enhanced_dir = os.path.join(out, "03_MELHORADAS")
        folder = enhanced_dir if os.path.isdir(enhanced_dir) else out
        images = self._find_images(folder) if os.path.isdir(folder) else []
        self._show_slideshow(images)

    # ── Nível 10.4 — anotações por foto ──────────────────────────
    def _load_notes(self) -> dict:
        try:
            return json.loads(_NOTES_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_notes_to_disk(self):
        try:
            _NOTES_PATH.write_text(json.dumps(self._photo_notes, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _save_current_note(self):
        if not self._selected_image:
            return
        text = self._note_edit.text().strip()
        if text:
            self._photo_notes[self._selected_image] = text
        else:
            self._photo_notes.pop(self._selected_image, None)
        self._save_notes_to_disk()

    # ── Nível 10.1 — análise de qualidade ─────────────────────────
    def _analyze_quality_bg(self, paths: list[str]):
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            return
        for path in paths:
            try:
                img = Image.open(path).convert("L").resize((256, 256))
                arr = np.array(img, dtype=np.float32)
                gy = arr[1:, :] - arr[:-1, :]
                gx = arr[:, 1:] - arr[:, :-1]
                sharpness = float(gy.var() + gx.var())
                mean_val = float(arr.mean())
                issues = []
                if sharpness < 180:
                    issues.append("Borrão")
                if mean_val < 45:
                    issues.append("Subexposta")
                elif mean_val > 215:
                    issues.append("Superexposta")
                if issues:
                    self._quality_bridge.issue.emit(path, " · ".join(issues))
            except Exception:
                pass

    def _on_quality_issue(self, path: str, issue: str):
        for thumb in self._thumb_cards:
            if thumb.path == path:
                thumb.set_warning(issue)
                break

    # ── Nível 10.2 — filtro por classificação ────────────────────
    def _update_filmstrip_filter_chips(self):
        if not hasattr(self, "_filter_chips_layout"):
            return
        while self._filter_chips_layout.count():
            item = self._filter_chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        classes = sorted({v for v in self._image_classifications.values() if v})
        if not classes:
            self._filter_chips_widget.hide()
            return

        all_btn = self._mk_filter_chip("Todas", active=True)
        all_btn.clicked.connect(lambda: self._apply_filmstrip_filter(None, all_btn))
        self._filter_chips_layout.addWidget(all_btn)
        self._filter_all_btn = all_btn
        self._filter_class_btns: dict[str, QPushButton] = {}
        for cls in classes:
            btn = self._mk_filter_chip(cls, active=False)
            btn.clicked.connect(lambda _, c=cls, b=btn: self._apply_filmstrip_filter(c, b))
            self._filter_chips_layout.addWidget(btn)
            self._filter_class_btns[cls] = btn
        self._filter_chips_layout.addStretch()
        self._filter_chips_widget.show()

    def _mk_filter_chip(self, label: str, active: bool) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedHeight(26)
        btn.setCursor(Qt.PointingHandCursor)
        self._style_filter_chip(btn, active)
        return btn

    def _style_filter_chip(self, btn: QPushButton, active: bool):
        bg = T["teal"] if active else T["bg3"]
        color = "#03261C" if active else T["text2"]
        border = T["teal"] if active else T["borderSoft"]
        hover_bg = "#2DE0B6" if active else T["bg4"]
        btn.setStyleSheet(
            f"QPushButton {{background:{bg};color:{color};border:1px solid {border};"
            f"border-radius:10px;font-size:11px;font-weight:600;min-height:26px;padding:0 12px;}}"
            f"QPushButton:hover {{background:{hover_bg};}}"
        )

    def _apply_filmstrip_filter(self, cls: str | None, active_btn: QPushButton):
        self._filmstrip_filter = cls
        if hasattr(self, "_filter_all_btn"):
            self._style_filter_chip(self._filter_all_btn, cls is None)
        if hasattr(self, "_filter_class_btns"):
            for c, b in self._filter_class_btns.items():
                self._style_filter_chip(b, c == cls)
        for thumb in self._thumb_cards:
            if cls is None:
                thumb.setVisible(True)
            else:
                thumb.setVisible(self._image_classifications.get(thumb.path) == cls)

    def _mk_bottom_bar(self):
        f = QFrame()
        f.setFixedHeight(70)
        f.setObjectName("BottomBar")
        f.setStyleSheet(f"#BottomBar {{ background:{T['bg0']}; border-top:1px solid {T['borderSoft']}; }}")
        h = QHBoxLayout(f)
        h.setContentsMargins(18, 10, 18, 10)
        h.setSpacing(16)
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{T['teal']};font-size:16px;")
        h.addWidget(dot)
        self._sb_st = QLabel("Pronto")
        self._sb_st.setStyleSheet(f"font-size:14px;font-weight:700;color:{T['text1']};")
        h.addWidget(self._sb_st)
        self._sb_ct = QLabel("0 fotos na fila")
        self._sb_ct.setStyleSheet(f"font-size:13px;color:{T['text3']};")
        h.addWidget(self._sb_ct)
        sep = QFrame(); sep.setFixedSize(1, 34); sep.setStyleSheet(f"background:{T['borderSoft']};")
        h.addWidget(sep)
        h.addWidget(QLabel("Processados:"))
        self._processed = QLabel("0/0")
        self._processed.setStyleSheet(f"font-size:13px;color:{T['text2']};")
        h.addWidget(self._processed)
        self._prog = QProgressBar()
        self._prog.setRange(0, 1000)
        self._prog.setValue(0)
        self._prog.setTextVisible(False)
        self._prog.setMinimumWidth(260)
        h.addWidget(self._prog)
        self._lbl_pct = QLabel("0%")
        self._lbl_pct.setStyleSheet(f"font-size:13px;color:{T['text2']};font-family:Consolas,monospace;")
        h.addWidget(self._lbl_pct)
        h.addStretch()
        self._btn_open_out = QPushButton(Icons.folder(T["text3"]), " Abrir saída")
        self._btn_open_out.setStyleSheet(BTN_GHOST)
        self._btn_open_out.setCursor(Qt.PointingHandCursor)
        self._btn_open_out.setToolTip("Abre a pasta de saída no Explorer (defina-a primeiro)")
        self._btn_open_out.clicked.connect(self._open_output_folder)
        h.addWidget(self._btn_open_out)
        self._btn_preview = QPushButton(Icons.eye(T["text1"]), " Gerar preview")
        self._btn_preview.setStyleSheet(BTN_SECONDARY)
        self._btn_preview.setCursor(Qt.PointingHandCursor)
        self._btn_preview.clicked.connect(self._generate_preview_clicked)
        h.addWidget(self._btn_preview)
        self._btn_proc = QPushButton(Icons.play(), " Processar lote")
        self._btn_proc.setStyleSheet(BTN_PRIMARY)
        self._btn_proc.setCursor(Qt.PointingHandCursor)
        self._btn_proc.clicked.connect(self._start_processing)
        h.addWidget(self._btn_proc)
        return f

    # ── Helper UI ─────────────────────────────────────────────────
    def _card_header(self, card: Card, title: str, subtitle: str | None, icon: QIcon | None = None):
        row = QHBoxLayout()
        row.setSpacing(10)
        if icon:
            ic = QLabel()
            ic.setPixmap(icon.pixmap(18, 18))
            ic.setFixedSize(32, 32)
            ic.setAlignment(Qt.AlignCenter)
            ic.setStyleSheet(f"background:{T['bg3']};border-radius:9px;")
            row.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(f"font-size:14px;font-weight:800;color:{T['text1']};background:transparent;border:none;")
        col.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setWordWrap(True)
            s.setStyleSheet(f"font-size:11.5px;color:{T['text3']};background:transparent;border:none;")
            col.addWidget(s)
        row.addLayout(col, 1)
        card.add_layout(row)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                PhotoAgentApp._clear_layout(child_layout)

    def _section_label(self, text: str):
        lab = QLabel(text)
        lab.setStyleSheet(f"font-size:12px;font-weight:700;color:{T['text1']};background:transparent;border:none;")
        return lab

    # ── Handlers / state ──────────────────────────────────────────
    def _show_sample_dialog(self):
        if not getattr(self, "_image_paths", None):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Amostra", "Carregue uma pasta de fotos primeiro.")
            return

        total = len(self._image_paths)
        group_size = {"3 fotos": 3, "5 fotos": 5}.get(
            getattr(self, "_bracketing_group_size", "auto"), 3
        )
        max_groups = total // group_size

        dlg = QDialog(self)
        dlg.setWindowTitle("Carregar amostra")
        dlg.setFixedWidth(320)
        dlg.setStyleSheet(f"background:{T['bg1']};color:{T['text1']};")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(14)
        lay.setContentsMargins(20, 18, 20, 18)

        lay.addWidget(QLabel(
            f"<b>Pasta:</b> {total} foto(s) total<br>"
            f"<b>Tamanho do grupo:</b> {group_size} fotos<br>"
            f"<b>Máximo de grupos disponíveis:</b> {max_groups}"
        ))

        row = QHBoxLayout()
        row.addWidget(QLabel("Quantos grupos carregar?"))
        spin = QSpinBox()
        spin.setRange(1, max_groups or 1)
        spin.setValue(min(6, max_groups or 1))
        spin.setMinimumHeight(34)
        spin.setStyleSheet(
            f"QSpinBox {{ background:{T['bg3']}; border:1px solid {T['border']};"
            f" border-radius:8px; color:{T['text1']}; font-size:13px; padding:4px 8px; }}"
        )
        row.addWidget(spin)
        lay.addLayout(row)

        btns = QHBoxLayout()
        ok = QPushButton("Carregar")
        ok.setStyleSheet(BTN_PRIMARY)
        ok.setCursor(Qt.PointingHandCursor)
        ok.clicked.connect(lambda: (self._apply_sample(spin.value(), group_size), dlg.accept()))
        cancel = QPushButton("Cancelar")
        cancel.setStyleSheet(BTN_GHOST)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(dlg.reject)
        btns.addWidget(ok, 1)
        btns.addWidget(cancel)
        lay.addLayout(btns)
        dlg.exec()

    def _apply_sample(self, n_groups: int, group_size: int):
        sample = self._image_paths[: n_groups * group_size]
        self._image_paths = sample
        self._sample_paths = sample  # pipeline vai filtrar só esses arquivos
        self._queue_badge.setText(str(len(sample)))
        self._sb_ct.setText(f"{len(sample)} fotos na fila  (amostra)")
        self._processed.setText(f"0/{len(sample)}")
        self._populate_queue(sample)
        self._populate_filmstrip(sample)
        if hasattr(self, "_update_photos_count"):
            self._update_photos_count()
        if sample:
            self._select_image(sample[0])
        self._sb_st.setText(f"Amostra: {n_groups} grupo(s) × {group_size} = {len(sample)} foto(s)")

    def _browse_dir(self, line_edit: QLineEdit, is_input=False):
        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if path:
            line_edit.setText(path)
            if is_input:
                self._load_images_from_folder(path, show_feedback=True)

    def _browse_style(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar perfil de estilo", "", "JSON (*.json)")
        if path:
            error = self._validate_style_profile(path)
            if error:
                QMessageBox.warning(
                    self,
                    "Perfil inválido",
                    f"O arquivo não parece ser um perfil de estilo válido:\n\n{error}\n\n"
                    "Verifique se é um perfil gerado pelo Treinar Estilo ou Treinar HDR.",
                )
            self._style_path.setText(path)

    def _validate_style_profile(self, path: str) -> str | None:
        """Valida estrutura do JSON do perfil. Retorna mensagem de erro ou None se ok."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            return f"JSON malformado: {exc}"
        except OSError as exc:
            return f"Não foi possível ler o arquivo: {exc}"
        if not isinstance(data, dict):
            return "O arquivo não contém um objeto JSON válido."
        profile_type = data.get("type", "")
        if profile_type == "hdr_bracketing_profile":
            if "corrections" not in data:
                return "Perfil HDR sem campo 'corrections'."
            return None
        # Perfil de estilo normal: gerado por StyleTrainer
        known = {"corrections", "stats", "version", "color_mode", "intensity"}
        if not known & set(data.keys()):
            return (
                f"Nenhum campo reconhecido encontrado. "
                f"Chaves presentes: {', '.join(list(data.keys())[:6])}"
            )
        return None

    def _on_input_dir_changed(self, path):
        # Debounce não é necessário aqui; só carrega se o caminho existir.
        if os.path.isdir(path):
            self._load_images_from_folder(path, show_feedback=False)

    def _on_preset(self, value):
        # Display labels are shortened to avoid clipping in the automation sidebar.
        preset_map = {
            "Natural": "Natural Pro",
            "Luxury": "Luxury Real Estate",
            "Strong": "Strong Enhance",
        }
        self._automation_preset = preset_map.get(value, value)
        if value in ("Natural", "Natural Pro"):
            self._seg_intensity.select("Normal")
            self._seg_color.select("Natural")
        elif value in ("Luxury", "Luxury Real Estate"):
            self._seg_intensity.select("Normal")
            self._seg_color.select("Luxury")
        else:
            self._seg_intensity.select("Forte")
            self._seg_color.select("Vibrant")
        self._update_summary()

    def _on_intensity(self, value):
        self._intensity = value.lower()
        self._update_summary()

    def _on_color(self, value):
        self._color_mode = value.lower()
        self._update_summary()

    def _on_bracketing(self, state):
        self._bracketing_enabled = bool(state)
        if hasattr(self, "_update_photos_count"):
            self._update_photos_count()
        # Reagrupa o filmstrip quando HDR é ligado/desligado
        folder = self._input_dir.text().strip() if hasattr(self, "_input_dir") else ""
        if folder and os.path.isdir(folder) and getattr(self, "_image_paths", None):
            self._load_images_from_folder(folder)

    def _ensure_bracketing_on(self):
        """Ao escolher 3/5 fotos ou um preset HDR, o usuário espera que o HDR esteja ativo."""
        self._bracketing_enabled = True
        if hasattr(self, "_tg_bracket") and not self._tg_bracket.isChecked():
            self._tg_bracket.set_state(True)

    def _on_bracket_group(self, value):
        self._bracketing_group_size = {"Auto": "auto", "3 fotos": "3", "5 fotos": "5"}.get(value, "auto")
        if self._bracketing_group_size in {"3", "5"}:
            self._ensure_bracketing_on()
        if hasattr(self, "_update_photos_count"):
            self._update_photos_count()

    def _on_bracket_preset(self, value):
        self._bracketing_fusion_preset = {
            "Natural": "natural",
            "Janela": "janela_preservada",
            "Interior": "interior_claro",
            "Luxury": "luxury_suave",
            "LR-like": "lightroom_like",
            "Lightroom": "lightroom_like",
            "Imob. Claro": "imobiliario_claro",
            "Imobiliário Claro": "imobiliario_claro",
        }.get(value, "imobiliario_claro")
        if self._bracketing_fusion_preset in {"lightroom_like", "imobiliario_claro"}:
            self._ensure_bracketing_on()

    def _on_hdr_finish(self, state):
        # False = HDR puro; True = HDR + Modo Automático/Enhance.
        self._bracketing_apply_auto_enhance = bool(state)

    def _on_upscale(self, state):
        self._upscale_enabled = bool(state)
        self._update_summary()

    def _on_factor(self, value):
        if value == "Off":
            self._upscale_enabled = False
            self._tg_upscale.set_state(False)
            self._upscale_factor = "2x"
        else:
            self._upscale_enabled = True
            self._tg_upscale.set_state(True)
            self._upscale_factor = value
        self._update_summary()

    def _on_subfolder_toggle(self, state: bool):
        self._subfolder_recursive = bool(state)

    def _on_duplicates_toggle(self, state: bool):
        self._duplicates_enabled = bool(state)

    def _on_dup_threshold(self, value: int):
        self._duplicates_threshold = value
        if hasattr(self, "_dup_thr_lbl"):
            self._dup_thr_lbl.setText(str(value))

    def _browse_clf_profile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar perfil do classificador", "",
            "JSON (*.json)"
        )
        if path:
            self._clf_profile_edit.setText(path)
            self._classifier_profile_path = path

    def _on_upscale_preset(self, value: str):
        mapping = {"Natural Pro": "natural_pro", "Forte": "strong_pro", "Luxury": "luxury"}
        self._upscale_preset = mapping.get(value, "natural_pro")

    def _on_export_profile_toggle(self, key: str, state: bool):
        if state:
            self._export_profiles.add(key)
        else:
            self._export_profiles.discard(key)

    def _on_max_workers_change(self, v: str):
        self._max_workers = 0 if v == "Auto" else int(v)

    def _on_rename_toggle(self, state: bool):
        self._rename_enabled = bool(state)
        self._rename_body.setVisible(state)

    def _on_rename_prefix_changed(self, v: str):
        self._rename_prefix = v
        self._update_rename_preview()

    def _on_rename_code_changed(self, v: str):
        self._rename_code = v
        self._update_rename_preview()

    def _update_rename_preview(self):
        if not hasattr(self, "_rename_preview_lbl"):
            return
        from datetime import datetime as _dt
        prefix = self._rename_prefix or "IMOVEL"
        code = self._rename_code or _dt.now().strftime("%Y%m%d")
        examples = [
            f"{prefix}_{code}_interior_01.jpg",
            f"{prefix}_{code}_exterior_01.jpg",
            f"{prefix}_{code}_detalhes_01.jpg",
        ]
        self._rename_preview_lbl.setText("Ex:  " + "  ·  ".join(examples[:2]))

    def _on_watermark_toggle(self, state: bool):
        self._watermark_enabled = bool(state)
        self._watermark_body.setVisible(state)

    def _on_wm_mode(self, value: str):
        self._watermark_mode = "image" if value == "Logo" else "text"
        if hasattr(self, "_wm_text_panel"):
            self._wm_text_panel.setVisible(self._watermark_mode == "text")
        if hasattr(self, "_wm_logo_panel"):
            self._wm_logo_panel.setVisible(self._watermark_mode == "image")

    def _browse_wm_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar logo",  "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path and hasattr(self, "_wm_logo_edit"):
            self._wm_logo_edit.setText(path)
            self._watermark_logo_path = path

    def _on_wm_position(self, value: str):
        mapping = {"Inf. Dir.": "bottom-right", "Inf. Esq.": "bottom-left", "Centro": "center"}
        self._watermark_position = mapping.get(value, "bottom-right")

    def _on_wm_opacity(self, value: int):
        self._watermark_opacity = value / 100
        self._wm_opacity_lbl.setText(f"{value}%")

    def _toggle_advanced(self):
        show = not self._advanced_body.isVisible()
        self._advanced_body.setVisible(show)
        self._btn_adv.setText("Ajustes avançados  ▲" if show else "Ajustes avançados  ▼")

    def _update_summary(self):
        if not hasattr(self, "_sum"):
            return
        self._sum["intensity"].setText(self._intensity.capitalize())
        self._sum["color"].setText(self._color_mode.capitalize())
        self._sum["upscale"].setText(self._upscale_factor if self._upscale_enabled else "Off")
        self._sum["preview"].setText("Ativo" if self._preview_available else "Off")

    # ── Image list / preview ──────────────────────────────────────
    def _find_images(self, folder: str) -> list[str]:
        if not folder or not os.path.isdir(folder):
            return []
        images = []
        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if os.path.isfile(path) and name.lower().endswith(IMAGE_EXTS):
                    images.append(path)
        except OSError:
            return []
        if not images:
            for root, dirs, files in os.walk(folder):
                depth = root.count(os.sep) - folder.count(os.sep)
                if depth > 1:
                    dirs[:] = []
                    continue
                for name in files:
                    path = os.path.join(root, name)
                    if name.lower().endswith(IMAGE_EXTS):
                        images.append(path)
                    if len(images) >= 300:
                        break
                if len(images) >= 300:
                    break
        images.sort(key=lambda p: (os.path.dirname(p), os.path.basename(p).lower()))
        return images

    def _raw_error_pixmap(self, filename: str, message: str) -> QPixmap:
        px = QPixmap(900, 620)
        px.fill(QColor(T["bg2"]))
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor(T["text1"]))
        p.setFont(QFont("Segoe UI", 24, QFont.Bold))
        p.drawText(QRect(0, 210, 900, 50), Qt.AlignCenter, "RAW/CR3 não carregado")
        p.setPen(QColor(T["text3"]))
        p.setFont(QFont("Segoe UI", 15))
        p.drawText(QRect(90, 270, 720, 90), Qt.AlignCenter | Qt.TextWordWrap, filename)
        p.setFont(QFont("Segoe UI", 12))
        p.drawText(QRect(90, 350, 720, 110), Qt.AlignCenter | Qt.TextWordWrap, message)
        p.end()
        return px

    def _load_pixmap(self, path: str) -> QPixmap:
        # RAW/CR3 não é lido pelo Qt/Pillow diretamente; usa rawpy para gerar RGB.
        if is_raw_file(path):
            try:
                rgb = read_raw_preview_rgb(path)
                h, w, ch = rgb.shape
                image = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
                return QPixmap.fromImage(image)
            except RawSupportError as exc:
                msg = str(exc)
                if hasattr(self, "_sb_st"):
                    self._sb_st.setText("Erro RAW/CR3")
                return self._raw_error_pixmap(os.path.basename(path), msg)
            except Exception as exc:
                msg = f"Erro inesperado ao carregar RAW/CR3: {exc}"
                if hasattr(self, "_sb_st"):
                    self._sb_st.setText("Erro RAW/CR3")
                return self._raw_error_pixmap(os.path.basename(path), msg)

        reader = QImageReader(path)
        reader.setAutoTransform(True)
        image = reader.read()
        if not image.isNull():
            return QPixmap.fromImage(image)
        return QPixmap(path)

    def _load_images_from_folder(self, folder: str, show_feedback=False):
        images = self._find_images(folder)
        self._image_paths = images
        self._sample_paths = None

        # Detecta grupos HDR se bracketing ativo
        self._bracket_groups = {}
        hdr_on = self._bracketing_enabled or self._bracketing_group_size in {"3", "5"}
        display_images = images  # o que o filmstrip vai mostrar

        if hdr_on and images:
            try:
                proc = BracketingProcessor(group_size=self._bracketing_group_size)
                candidates = [proc._read_candidate(p) for p in images]
                raw_groups = proc.detect_groups(candidates)
                # Monta mapa: path_base → [todos os paths do grupo]
                for grp in raw_groups:
                    if len(grp) > 1:
                        # base = exposição 0EV (meio do grupo ordenado)
                        ordered = proc._order_exposures(grp)
                        base = proc._select_base_exposure(ordered)
                        self._bracket_groups[base.path] = [c.path for c in ordered]
                # Filmstrip mostra apenas as fotos base (1 por grupo)
                base_paths = list(self._bracket_groups.keys())
                singles = [p for p in images if p not in {p2 for g in self._bracket_groups.values() for p2 in g}]
                display_images = base_paths + singles
            except Exception:
                pass  # fallback: mostra todas as imagens normalmente

        self._queue_badge.setText(str(len(images)))
        n_groups = len(self._bracket_groups)
        if n_groups:
            self._sb_ct.setText(f"{n_groups} grupos HDR · {len(images)} fotos")
        else:
            self._sb_ct.setText(f"{len(images)} fotos na fila")
        self._processed.setText(f"0/{len(images)}")
        self._populate_queue(display_images)
        self._populate_filmstrip(display_images)
        if hasattr(self, "_update_photos_count"):
            self._update_photos_count()
        if display_images:
            self._select_image(display_images[0])
            self._sb_st.setText("Pronto")
        else:
            self._selected_image = None
            self._selected_label.setText("Nenhuma imagem encontrada")
            self._preview_available = False
            self._update_summary()
            if show_feedback:
                self._sb_st.setText("Nenhuma imagem encontrada")

    def _placeholder_pixmap(self) -> QPixmap:
        px = QPixmap(140, 72)
        px.fill(QColor(T["bg3"]))
        return px

    def _populate_queue(self, images: list[str]):
        self._clear_layout(self._queue_layout)
        self._queue_items = []
        placeholder = self._placeholder_pixmap()
        for path in images[:40]:
            item = QueueItem(path, placeholder, selected=(path == self._selected_image))
            item.clicked.connect(self._select_image)
            self._queue_layout.addWidget(item)
            self._queue_items.append(item)
        self._queue_layout.addStretch()
        threading.Thread(
            target=self._load_pixmaps_bg,
            args=(list(images[:40]), "queue"),
            daemon=True,
        ).start()

    def _populate_filmstrip(self, images: list[str]):
        self._clear_layout(self._filmstrip_layout)
        self._thumb_cards = []
        self._filmstrip_filter = None
        placeholder = self._placeholder_pixmap()
        for path in images[:60]:
            thumb = ThumbCard(path, placeholder, selected=(path == self._selected_image))
            thumb.clicked.connect(self._select_image)
            self._filmstrip_layout.addWidget(thumb)
            self._thumb_cards.append(thumb)
        self._filmstrip_layout.addStretch()
        if images:
            threading.Thread(
                target=self._load_pixmaps_bg,
                args=(list(images[:60]), "filmstrip"),
                daemon=True,
            ).start()
            threading.Thread(
                target=self._analyze_quality_bg,
                args=(list(images[:60]),),
                daemon=True,
            ).start()

    def _load_pixmaps_bg(self, paths: list[str], target: str):
        for path in paths:
            try:
                px = self._load_pixmap(path)
                self._pixmap_bridge.loaded.emit(path + "\x00" + target, px)
            except Exception:
                pass

    def _on_pixmap_loaded(self, key: str, pixmap):
        path, target = key.split("\x00", 1)
        if target == "filmstrip":
            for card in getattr(self, "_thumb_cards", []):
                if card.path == path:
                    card.set_pixmap(pixmap)
                    break
        elif target == "queue":
            for item in getattr(self, "_queue_items", []):
                if item.path == path:
                    item.set_pixmap(pixmap)
                    break

    def _select_image(self, path: str):
        if not path or not os.path.isfile(path):
            return

        # Modo comparação pós-processamento (7.3)
        if self._compare_mode and path in self._results_map:
            orig = self._results_map[path]
            before = self._load_pixmap(orig) if os.path.isfile(orig) else self._load_pixmap(path)
            after = self._load_pixmap(path)
            self._compare.set_images_from_pixmaps(before, after)
            self._selected_image = path
            self._selected_label.setText(os.path.basename(path))
            for item in self._queue_items:
                item.set_selected(item.path == path)
            for thumb in self._thumb_cards:
                thumb.set_selected(thumb.path == path)
            self._sb_st.setText(f"Comparando: {os.path.basename(path)}")
            return

        before = self._load_pixmap(path)
        if before.isNull():
            self._sb_st.setText("Erro ao carregar preview")
            return
        # Mostra preview rápido imediatamente
        after = enhanced_preview(before) or before
        self._compare.set_images_from_pixmaps(before, after)
        self._selected_image = path
        self._selected_label.setText(os.path.basename(path))
        self._preview_available = True
        for item in self._queue_items:
            item.set_selected(item.path == path)
        for thumb in self._thumb_cards:
            thumb.set_selected(thumb.path == path)
        self._sb_st.setText(f"Preview: {os.path.basename(path)}")
        # 10.4 — carrega nota da foto selecionada
        if hasattr(self, "_note_edit"):
            self._note_edit.blockSignals(True)
            self._note_edit.setText(self._photo_notes.get(path, ""))
            self._note_edit.blockSignals(False)
        self._update_summary()
        # Lança preview em background — HDR se for grupo, StyledEnhancer se for foto individual
        group_paths = self._bracket_groups.get(path)
        if group_paths:
            if not self._hdr_preview_loading:
                self._hdr_preview_loading = True
                self._sb_st.setText(f"Gerando HDR preview ({len(group_paths)} fotos)…")
                threading.Thread(
                    target=self._run_hdr_preview,
                    args=(path, group_paths),
                    daemon=True,
                ).start()
        elif not self._preview_loading:
            self._preview_loading = True
            threading.Thread(
                target=self._run_real_preview,
                args=(path,),
                daemon=True,
            ).start()

    def _generate_preview_clicked(self):
        if self._selected_image and os.path.isfile(self._selected_image):
            self._select_image(self._selected_image)
            return
        folder = self._input_dir.text().strip()
        if folder:
            self._load_images_from_folder(folder, show_feedback=True)
        else:
            QMessageBox.information(self, "Preview", "Selecione uma pasta de entrada primeiro.")

    # ── Processing ────────────────────────────────────────────────
    def _collect_options(self):
        return {
            "automation_preset": self._automation_preset,
            "intensity": self._intensity,
            "color_mode": self._color_mode,
            "preview_mode": False,
            "upscale_enabled": self._upscale_enabled,
            "upscale_factor": float(self._upscale_factor.replace("x", "")) if self._upscale_enabled else 1.0,
            "upscale_preset": self._upscale_preset,
            "export_profiles": sorted(self._export_profiles) if self._export_profiles else None,
            # Se o usuário selecionou 3/5 fotos, força o fluxo HDR mesmo que o toggle não tenha sido clicado.
            "bracketing_enabled": bool(
                self._bracketing_enabled
                or self._bracketing_group_size in {"3", "5"}
            ),
            "bracketing_group_size": self._bracketing_group_size,
            "bracketing_fusion_preset": self._bracketing_fusion_preset,
            "bracketing_auto_chromatic_aberration": True,
            "bracketing_auto_lens_correction": True,
            "bracketing_auto_geometry_correction": True,
            "bracketing_apply_auto_enhance": self._bracketing_apply_auto_enhance,
            "duplicates_enabled": self._duplicates_enabled,
            "duplicates_threshold": self._duplicates_threshold,
            "rename_enabled": self._rename_enabled,
            "rename_prefix": self._rename_prefix,
            "rename_code": self._rename_code,
            "watermark_enabled": self._watermark_enabled,
            "watermark_config": {
                "mode": self._watermark_mode,
                "text": self._watermark_text,
                "image_path": self._watermark_logo_path,
                "position": self._watermark_position,
                "opacity": self._watermark_opacity,
            } if self._watermark_enabled else None,
            "contact_sheet": self._contact_sheet_enabled,
            "before_after": self._before_after_enabled,
            "gallery": False,
            "gallery_title": self._gallery_title or "Galeria de Fotos",
            "gallery_subtitle": self._gallery_subtitle,
            "exif_preserve": True,
            "photographer": self._photographer,
            "copyright": self._copyright_text,
            "subfolder_recursive": self._subfolder_recursive,
            "classifier_profile_path": self._classifier_profile_path or None,
            "max_workers": self._max_workers,
            "allowed_files": self._sample_paths or None,
        }

    def _start_processing(self):
        out = self._output_dir.text().strip()
        if not out:
            QMessageBox.critical(self, "Erro", "Selecione uma pasta de saída.")
            return

        # Determine folders: use queue if populated, else single input dir
        if self._folder_queue:
            folders = list(self._folder_queue)
        else:
            inp = self._input_dir.text().strip()
            if not inp or not os.path.isdir(inp):
                QMessageBox.critical(self, "Erro", "Selecione uma pasta de entrada válida.")
                return
            folders = [inp]

        os.makedirs(out, exist_ok=True)
        self._log_clear()
        # Expande o log automaticamente ao iniciar o processamento
        if hasattr(self, "_log") and not self._log.isVisible():
            self._toggle_log()
        self._results_card.setVisible(False)
        self._current_run_files = []
        self._current_run_map = {}
        import time as _time
        self._run_start_time = _time.time()
        self._prog.setValue(0)
        self._lbl_pct.setText("0%")
        self._processed.setText(f"0/{len(self._image_paths)}")
        self._btn_proc.setEnabled(False)
        self._btn_preview.setEnabled(False)

        self._batch_folders = folders
        self._current_batch_idx = 0
        self._is_batch_processing = len(folders) > 1
        self._start_pipeline_at(0)

    def _start_pipeline_at(self, idx: int):
        inp = self._batch_folders[idx]
        out = self._output_dir.text().strip()
        opts = self._collect_options()
        style_path = self._style_path.text().strip() or None
        total = len(self._batch_folders)
        if total > 1:
            folder_name = os.path.basename(inp) or inp
            self._sb_st.setText(f"Processando [{idx + 1}/{total}]: {folder_name}")
            self._log_append("", f"── Pasta {idx + 1}/{total}: {folder_name} ──", 0.0)

        def cb(msg, pct):
            self._bridge.progress.emit(msg, pct)

        self.pipeline = ProcessingPipeline(inp, out, cb, style_profile_path=style_path, options=opts)
        self.pipeline.start()

    def _log_clear(self):
        if hasattr(self, "_log"):
            self._log.clear()

    def _log_append(self, timestamp: str, msg: str, pct: float):
        is_error = (
            msg.startswith("ERRO")
            or "Erro" in msg
            or "Nenhuma imagem processável" in msg
            or "RAW/CR3 ignorado" in msg
        )
        is_warn = "Cancelado" in msg or "ignorado" in msg.lower()
        if is_error:
            color = T["danger"]
        elif pct >= 1.0:
            color = T["teal"]
        elif is_warn:
            color = T["purple"]
        else:
            color = T["text2"]
        msg_safe = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = (
            f'<span style="color:{T["text4"]};font-family:Consolas,monospace">{timestamp}</span>'
            f'<span style="color:{color};font-family:Consolas,monospace"> {msg_safe}</span>'
        )
        sb = self._log.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._log.setTextCursor(cursor)
        self._log.insertHtml(html + "<br>")
        if at_bottom:
            sb.setValue(sb.maximum())

    def _update_ui(self, msg, pct):
        self._prog.setValue(int(pct * 1000))
        self._lbl_pct.setText(f"{int(pct * 100)}%")
        msg_txt = str(msg)

        # Machine-readable stats message — show results panel, skip log
        if msg_txt.startswith("STATS:"):
            # Se há mais pastas na fila, inicia a próxima
            if self._is_batch_processing and self._current_batch_idx < len(self._batch_folders) - 1:
                self._current_batch_idx += 1
                self._start_pipeline_at(self._current_batch_idx)
                return
            # Último batch (ou único) — finaliza
            self._is_batch_processing = False
            self._sb_st.setText("Processamento concluído")
            processed, errors, stats = 0, 0, {}
            try:
                stats = json.loads(msg_txt[6:])
                self._show_results_panel(stats)
                processed = stats.get("processed", stats.get("total", 0))
                errors = stats.get("errors", 0)
                # Armazena arquivos e mapa do run atual para comparação
                self._current_run_files = stats.get("enhanced_files", [])
                self._current_run_map = {p["after"]: p["before"] for p in stats.get("ba_pairs", []) if p.get("after")}
                # 10.2 — armazena classificação por imagem e atualiza chips de filtro
                per_image = stats.get("per_image", [])
                if per_image:
                    self._image_classifications = {item["orig"]: item["cls"] for item in per_image if item.get("orig")}
                    self._update_filmstrip_filter_chips()
            except Exception:
                pass
            self._notify_done(processed, errors)
            self._add_history_entry(stats)
            self._btn_proc.setEnabled(True)
            self._btn_preview.setEnabled(True)
            out = self._output_dir.text().strip()
            if out and os.path.isdir(out):
                self._btn_open_out.setVisible(True)
            return

        if msg_txt.startswith("ERRO") or "Nenhuma imagem processável" in msg_txt or "RAW/CR3 ignorado" in msg_txt:
            self._sb_st.setText("Erro no processamento")
        else:
            self._sb_st.setText("Processando" if pct < 1.0 else "Processamento concluído")
        if "]" in msg:
            left = msg.split("]", 1)[0].replace("[", "")
            if "/" in left:
                self._processed.setText(left)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_append(timestamp, msg_txt, pct)
        if pct >= 1.0:
            self._btn_proc.setEnabled(True)
            self._btn_preview.setEnabled(True)
            out = self._output_dir.text().strip()
            if out and os.path.isdir(out):
                self._btn_open_out.setVisible(True)

    def _open_output_folder(self):
        out = self._output_dir.text().strip()
        if not out or not os.path.isdir(out):
            QMessageBox.information(self, "Saída", "Defina uma pasta de saída primeiro.")
            return
        try:
            if sys.platform == "win32":
                os.startfile(out)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{out}"')
            else:
                os.system(f'xdg-open "{out}"')
        except Exception as exc:
            QMessageBox.warning(self, "Saída", f"Não foi possível abrir a pasta:\n{exc}")

    def _show_results_panel(self, stats: dict):
        processed = stats.get("processed", stats.get("total", 0))
        total     = stats.get("total", processed)
        errors    = stats.get("errors", 0)
        duration  = stats.get("duration_sec", 0)
        by_class  = stats.get("by_class", {})
        self._res_report_path = stats.get("report_path", "")

        self._res_lbl_processed._value_label.setText(f"{processed}/{total}")
        self._res_lbl_errors._value_label.setText(str(errors))
        mins, secs = divmod(duration, 60)
        self._res_lbl_time._value_label.setText(f"{mins}m {secs:02d}s" if mins else f"{secs}s")

        if by_class:
            parts = [f"{cls}: {n}" for cls, n in sorted(by_class.items())]
            self._res_classes_lbl.setText("Classificação — " + " · ".join(parts))
        else:
            self._res_classes_lbl.setText("")

        error_color = T["danger"] if errors else T["teal"]
        self._res_lbl_errors._value_label.setStyleSheet(
            f"font-size:16px;font-weight:800;color:{error_color};"
        )
        self._res_report_btn.setVisible(bool(self._res_report_path and os.path.isfile(self._res_report_path)))
        self._results_card.setVisible(True)

    def _open_report(self):
        path = getattr(self, "_res_report_path", "")
        if not path or not os.path.isfile(path):
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception as exc:
            QMessageBox.warning(self, "Relatório", f"Não foi possível abrir o relatório:\n{exc}")

    # ── Direção A — Entrega ao cliente ───────────────────────────

    def _show_delivery_dialog(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        out = self._output_dir.text().strip()
        enhanced_dir = os.path.join(out, "03_MELHORADAS")
        source = enhanced_dir if os.path.isdir(enhanced_dir) else out
        if not os.path.isdir(source):
            QMessageBox.warning(self, "Entregar", "Pasta de saída não encontrada.\nProcesse o lote primeiro.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Preparar entrega ao cliente")
        dlg.setMinimumWidth(460)
        dlg.setStyleSheet(f"QDialog{{background:{T['bg1']};}} QLabel{{color:{T['text1']};}} QLineEdit{{background:{T['bg0']};border:1px solid {T['border']};border-radius:8px;padding:6px 10px;color:{T['text2']};font-size:12px;}}")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(14)
        lay.setContentsMargins(24, 20, 24, 20)

        title_lbl = QLabel("Entrega ao cliente")
        title_lbl.setStyleSheet(f"font-size:16px;font-weight:800;color:{T['text1']};")
        lay.addWidget(title_lbl)

        # Campos de informação
        form = QGridLayout()
        form.setSpacing(8)
        form.setColumnMinimumWidth(0, 110)

        def field(label, placeholder, row):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size:12px;color:{T['text3']};")
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            form.addWidget(lbl, row, 0)
            form.addWidget(edit, row, 1)
            return edit

        self._dlv_client   = field("Cliente",    "Nome do cliente ou imobiliária", 0)
        self._dlv_address  = field("Endereço",   "Rua, número, cidade", 1)
        self._dlv_wm_text  = field("Nota prova", "PROVA — NÃO UTILIZAR SEM APROVAÇÃO", 2)
        self._dlv_wm_text.setText("PROVA — NÃO UTILIZAR SEM APROVAÇÃO")
        lay.addLayout(form)

        # Conta imagens e tamanho estimado
        images = self._find_images(source)
        total_mb = sum(os.path.getsize(p) for p in images if os.path.isfile(p)) / 1_048_576
        info = QLabel(f"{len(images)} foto(s)  ·  {total_mb:.1f} MB na pasta {os.path.basename(source)}")
        info.setStyleSheet(f"font-size:11.5px;color:{T['text3']};")
        lay.addWidget(info)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{T['border']};")
        lay.addWidget(sep)

        # Botões de ação
        zip_btn = QPushButton(Icons.import_icon(T["teal"]), "  Exportar ZIP")
        zip_btn.setStyleSheet(BTN_PRIMARY)
        zip_btn.setFixedHeight(42)
        zip_btn.setCursor(Qt.PointingHandCursor)
        zip_btn.clicked.connect(lambda: self._run_delivery(dlg, source, "zip"))
        lay.addWidget(zip_btn)

        gallery_btn = QPushButton(Icons.eye(T["text1"]), "  Gerar galeria de prova")
        gallery_btn.setStyleSheet(BTN_SECONDARY)
        gallery_btn.setFixedHeight(42)
        gallery_btn.setCursor(Qt.PointingHandCursor)
        gallery_btn.clicked.connect(lambda: self._run_delivery(dlg, source, "gallery"))
        lay.addWidget(gallery_btn)

        both_btn = QPushButton("  ZIP + Galeria de prova")
        both_btn.setStyleSheet(BTN_SECONDARY)
        both_btn.setFixedHeight(42)
        both_btn.setCursor(Qt.PointingHandCursor)
        both_btn.clicked.connect(lambda: self._run_delivery(dlg, source, "both"))
        lay.addWidget(both_btn)

        close = QPushButton("Fechar")
        close.setStyleSheet(BTN_GHOST)
        close.setFixedHeight(34)
        close.clicked.connect(dlg.close)
        lay.addWidget(close)

        dlg.exec()

    def _run_delivery(self, dlg, source: str, mode: str):
        client  = self._dlv_client.text().strip()
        address = self._dlv_address.text().strip()
        wm_text = self._dlv_wm_text.text().strip() or "PROVA — NÃO UTILIZAR SEM APROVAÇÃO"
        title   = client or "Galeria de Prova"
        out_dir = self._output_dir.text().strip()
        photographer = getattr(self, "_photographer", "")

        errors: list[str] = []
        opened: list[str] = []

        if mode in ("zip", "both"):
            try:
                from core.delivery import create_delivery_zip
                zip_path = os.path.join(out_dir, f"entrega_{client or 'fotos'}.zip".replace(" ", "_"))
                # Progresso simples na status bar
                self._sb_st.setText("Gerando ZIP…")
                QApplication.processEvents()
                create_delivery_zip(source, zip_path)
                opened.append(zip_path)
                self._sb_st.setText(f"ZIP: {os.path.basename(zip_path)}")
            except Exception as e:
                errors.append(f"ZIP: {e}")

        if mode in ("gallery", "both"):
            try:
                from core.delivery import create_proof_gallery
                images = self._find_images(source)
                html_path = os.path.join(out_dir, "galeria_prova.html")
                self._sb_st.setText("Gerando galeria…")
                QApplication.processEvents()
                create_proof_gallery(
                    images, html_path,
                    title=title,
                    photographer=photographer,
                    property_address=address,
                    watermark_text=wm_text,
                )
                opened.append(html_path)
                self._sb_st.setText("Galeria gerada")
            except Exception as e:
                errors.append(f"Galeria: {e}")

        if errors:
            QMessageBox.critical(dlg, "Erro na entrega", "\n".join(errors))
            return

        dlg.close()
        # Abre os arquivos gerados
        for path in opened:
            try:
                if sys.platform == "win32":
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    os.system(f'xdg-open "{path}"')
            except Exception:
                pass
        msg = "\n".join(os.path.basename(p) for p in opened)
        QMessageBox.information(self, "Entrega concluída", f"Arquivo(s) gerado(s):\n{msg}")

    # ── Persistência de configurações ────────────────────────────

    def _save_settings(self):
        """Salva estado atual dos controles em disco."""
        try:
            settings = {
                "style_path": self._style_path.text(),
                # estado interno (fonte da verdade)
                "automation_preset":            self._automation_preset,
                "intensity":                    self._intensity,
                "color_mode":                   self._color_mode,
                "upscale_enabled":              self._upscale_enabled,
                "upscale_factor":               self._upscale_factor,
                "bracketing_enabled":           self._bracketing_enabled,
                "bracketing_group_size":        self._bracketing_group_size,
                "bracketing_fusion_preset":     self._bracketing_fusion_preset,
                "bracketing_apply_auto_enhance":self._bracketing_apply_auto_enhance,
                # estado visual dos widgets (para restaurar a aparência)
                "seg_preset":         self._seg_preset.value(),
                "seg_intensity":      self._seg_intensity.value(),
                "seg_color":          self._seg_color.value(),
                "seg_bracket_group":  self._seg_bracket_group.value(),
                "seg_bracket_preset": self._seg_bracket_preset.value(),
                "seg_factor":         self._seg_factor.value(),
                "tg_bracket":         self._tg_bracket.isChecked(),
                "tg_hdr_finish":      self._tg_hdr_finish.isChecked(),
                "tg_upscale":         self._tg_upscale.isChecked(),
                "tg_subfolder":       self._tg_subfolder.isChecked(),
                "subfolder_recursive": self._subfolder_recursive,
                # Item 1 — Rename & Watermark
                "rename_enabled":     self._rename_enabled,
                "rename_prefix":      self._rename_prefix,
                "rename_code":        self._rename_code,
                "watermark_enabled":   self._watermark_enabled,
                "watermark_mode":      self._watermark_mode,
                "watermark_text":      self._watermark_text,
                "watermark_logo_path": self._watermark_logo_path,
                "watermark_position":  self._watermark_position,
                "watermark_opacity":   self._watermark_opacity,
                # Nível 5 — Export profiles & upscale preset
                "export_profiles":    sorted(self._export_profiles),
                "upscale_preset":     self._upscale_preset,
                "seg_upscale_preset": self._seg_upscale_preset.value(),
                # Nível 4 — Settings tab
                "duplicates_enabled":    self._duplicates_enabled,
                "duplicates_threshold":  self._duplicates_threshold,
                "contact_sheet_enabled": self._contact_sheet_enabled,
                "before_after_enabled":  self._before_after_enabled,
                "classifier_profile_path": self._classifier_profile_path,
                # Item 3 — Gallery & EXIF
                "gallery_title":      self._gallery_title,
                "gallery_subtitle":   self._gallery_subtitle,
                "photographer":       self._photographer,
                "copyright_text":     self._copyright_text,
                # Nível 8.3 — parallel workers
                "max_workers":        self._max_workers,
            }
            _SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _load_settings(self):
        """Restaura controles da última sessão."""
        try:
            settings = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        # Caminhos (input/output não restaurados — usuário escolhe a cada sessão)
        if v := settings.get("style_path"):
            if os.path.isfile(v):
                self._style_path.setText(v)

        # Estado interno (restaura antes dos widgets para evitar cascata de handlers)
        if v := settings.get("automation_preset"):
            self._automation_preset = v
        if v := settings.get("intensity"):
            self._intensity = v
        if v := settings.get("color_mode"):
            self._color_mode = v
        if "upscale_enabled" in settings:
            self._upscale_enabled = bool(settings["upscale_enabled"])
        if v := settings.get("upscale_factor"):
            self._upscale_factor = v
        if "bracketing_enabled" in settings:
            self._bracketing_enabled = bool(settings["bracketing_enabled"])
        if v := settings.get("bracketing_group_size"):
            self._bracketing_group_size = v
        if v := settings.get("bracketing_fusion_preset"):
            self._bracketing_fusion_preset = v
        if "bracketing_apply_auto_enhance" in settings:
            self._bracketing_apply_auto_enhance = bool(settings["bracketing_apply_auto_enhance"])

        # Estado visual dos widgets (sem emitir sinal para não sobreescrever o estado interno)
        if v := settings.get("seg_preset"):
            self._seg_preset.select(v, emit=False)
        if v := settings.get("seg_intensity"):
            self._seg_intensity.select(v, emit=False)
        if v := settings.get("seg_color"):
            self._seg_color.select(v, emit=False)
        if v := settings.get("seg_bracket_group"):
            self._seg_bracket_group.select(v, emit=False)
        if v := settings.get("seg_bracket_preset"):
            self._seg_bracket_preset.select(v, emit=False)
        if v := settings.get("seg_factor"):
            self._seg_factor.select(v, emit=False)
        if "tg_bracket" in settings:
            self._tg_bracket.set_state(bool(settings["tg_bracket"]))
        if "tg_hdr_finish" in settings:
            self._tg_hdr_finish.set_state(bool(settings["tg_hdr_finish"]))
        if "tg_upscale" in settings:
            self._tg_upscale.set_state(bool(settings["tg_upscale"]))
        if "subfolder_recursive" in settings:
            self._subfolder_recursive = bool(settings["subfolder_recursive"])
        if "tg_subfolder" in settings:
            self._tg_subfolder.set_state(bool(settings["tg_subfolder"]))

        # Item 1 — Rename & Watermark (internal state first)
        if "rename_enabled" in settings:
            self._rename_enabled = bool(settings["rename_enabled"])
        if v := settings.get("rename_prefix"):
            self._rename_prefix = v
        if "rename_code" in settings:
            self._rename_code = settings["rename_code"]
        if "watermark_enabled" in settings:
            self._watermark_enabled = bool(settings["watermark_enabled"])
        if v := settings.get("watermark_mode"):
            self._watermark_mode = v
        if v := settings.get("watermark_text"):
            self._watermark_text = v
        if "watermark_logo_path" in settings:
            self._watermark_logo_path = settings["watermark_logo_path"] or ""
        if v := settings.get("watermark_position"):
            self._watermark_position = v
        if "watermark_opacity" in settings:
            self._watermark_opacity = float(settings["watermark_opacity"])

        # Item 1 — widget visuals
        if hasattr(self, "_tg_rename"):
            self._tg_rename.set_state(self._rename_enabled)
            self._rename_body.setVisible(self._rename_enabled)
            self._rename_prefix_edit.setText(self._rename_prefix)
            self._rename_code_edit.setText(self._rename_code)
            self._update_rename_preview()
        if hasattr(self, "_tg_watermark"):
            self._tg_watermark.set_state(self._watermark_enabled)
            self._watermark_body.setVisible(self._watermark_enabled)
            self._wm_text_edit.setText(self._watermark_text)
            self._wm_opacity_slider.setValue(int(self._watermark_opacity * 100))
            if hasattr(self, "_seg_wm_mode"):
                mode_label = "Logo" if self._watermark_mode == "image" else "Texto"
                self._seg_wm_mode.select(mode_label, emit=False)
                self._wm_text_panel.setVisible(self._watermark_mode == "text")
                self._wm_logo_panel.setVisible(self._watermark_mode == "image")
            if hasattr(self, "_wm_logo_edit"):
                self._wm_logo_edit.setText(self._watermark_logo_path)

        # Item 3 — Gallery & EXIF
        if v := settings.get("gallery_title"):
            self._gallery_title = v
        if "gallery_subtitle" in settings:
            self._gallery_subtitle = settings["gallery_subtitle"]
        if "photographer" in settings:
            self._photographer = settings["photographer"]
        if "copyright_text" in settings:
            self._copyright_text = settings["copyright_text"]
        # Nível 5 — restore
        if v := settings.get("export_profiles"):
            self._export_profiles = set(v)
        if v := settings.get("upscale_preset"):
            self._upscale_preset = v
        if v := settings.get("seg_upscale_preset"):
            if hasattr(self, "_seg_upscale_preset"):
                self._seg_upscale_preset.select(v, emit=False)
        if hasattr(self, "_tg_export"):
            for key, tg in self._tg_export.items():
                tg.set_state(key in self._export_profiles)

        if hasattr(self, "_gallery_title_edit"):
            self._gallery_title_edit.setText(self._gallery_title)
            self._gallery_subtitle_edit.setText(self._gallery_subtitle)
            self._photographer_edit.setText(self._photographer)
            self._copyright_edit.setText(self._copyright_text)

        # Nível 4 — Settings tab (internal state first)
        if "duplicates_enabled" in settings:
            self._duplicates_enabled = bool(settings["duplicates_enabled"])
        if "duplicates_threshold" in settings:
            self._duplicates_threshold = int(settings["duplicates_threshold"])
        if "contact_sheet_enabled" in settings:
            self._contact_sheet_enabled = bool(settings["contact_sheet_enabled"])
        if "before_after_enabled" in settings:
            self._before_after_enabled = bool(settings["before_after_enabled"])
        if "classifier_profile_path" in settings:
            self._classifier_profile_path = settings["classifier_profile_path"] or ""
        # Nível 4 — widget visuals
        if hasattr(self, "_tg_duplicates"):
            self._tg_duplicates.set_state(self._duplicates_enabled)
            self._dup_slider.setValue(self._duplicates_threshold)
        if hasattr(self, "_tg_contact"):
            self._tg_contact.set_state(self._contact_sheet_enabled)
        if hasattr(self, "_tg_before_after"):
            self._tg_before_after.set_state(self._before_after_enabled)
        if hasattr(self, "_clf_profile_edit") and self._classifier_profile_path:
            self._clf_profile_edit.setText(self._classifier_profile_path)

        # Nível 8.3 — parallel workers
        if "max_workers" in settings:
            self._max_workers = int(settings["max_workers"])
        if hasattr(self, "_seg_max_workers") and self._max_workers != 0:
            label = str(self._max_workers)
            if label in ("2", "4", "8"):
                self._seg_max_workers.select(label, emit=False)

        self._update_summary()

    def mainloop(self):
        self.show()
        QApplication.instance().exec()
