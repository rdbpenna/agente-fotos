"""
GUI PySide6 — v24: fix overlay, text truncation, topbar, preview auto-load, simulated "depois".
"""

import os, sys, json, threading, glob
from datetime import datetime
from io import BytesIO

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QScrollArea,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox,
    QGraphicsDropShadowEffect, QSizePolicy, QComboBox,
)
from PySide6.QtCore import Qt, Signal, QObject, QByteArray, QRect, QPoint, QSize
from PySide6.QtGui import (
    QColor, QPainter, QPixmap, QImage, QPen, QBrush, QFont,
    QIcon, QPainterPath, QLinearGradient, QPalette,
)
from PySide6.QtSvg import QSvgRenderer

from core.pipeline import ProcessingPipeline

# ── Tokens ────────────────────────────────────────────────────────
T = {
    "bg0": "#0B1220", "bg1": "#0E1626", "bg2": "#101B2C", "bg3": "#142235",
    "bgElev": "#16243A", "border": "#1D2C44", "borderSoft": "#182338",
    "text1": "#E6EDF5", "text2": "#B7C2D2", "text3": "#7E8DA3", "text4": "#5A6678",
    "teal": "#1FD1A8", "teal2": "#14B894", "green": "#22C58A",
}


# ── SVG Icons ─────────────────────────────────────────────────────
def _svg_icon(svg_str, size=18, color=None):
    """Cria QIcon a partir de SVG inline."""
    if color:
        svg_str = svg_str.replace('stroke="currentColor"', f'stroke="{color}"')
        svg_str = svg_str.replace('fill="currentColor"', f'fill="{color}"')
    data = QByteArray(svg_str.encode())
    renderer = QSvgRenderer(data)
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    renderer.render(p)
    p.end()
    return QIcon(px)


class Icons:
    @staticmethod
    def folder(c=T['text2']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def edit(c=T['text2']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def upscale(c=T['text2']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.7"/></svg>', color=c)

    @staticmethod
    def process(c=T['teal']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.7"/><rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.7"/><rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.7"/><path d="M14 17.5h7M17.5 14v7" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>', color=c)

    @staticmethod
    def settings(c=T['text3']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.7"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.8 1.2V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1A1.7 1.7 0 0 0 4.6 9 1.7 1.7 0 0 0 4.3 7.2l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" stroke="currentColor" stroke-width="1.5"/></svg>', color=c)

    @staticmethod
    def star(c=T['text3']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="m12 2 3 6.9 7.5.7-5.7 5L18.5 22 12 18.3 5.5 22l1.7-7.4L1.5 9.6 9 8.9 12 2z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def intensity(c=T['teal']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M3 17 9 11l4 4 8-8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def palette(c=T['teal']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M12 3a9 9 0 1 0 0 18c1 0 1.5-.5 1.5-1.3 0-.9-.7-1-.7-1.7 0-.7.6-1 1.5-1H16a5 5 0 0 0 5-5 8 8 0 0 0-9-9z" stroke="currentColor" stroke-width="1.7"/></svg>', color=c)

    @staticmethod
    def eye(c=T['teal']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.7"/></svg>', color=c)

    @staticmethod
    def expand(c=T['text2']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def activity(c=T['text2']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def list_icon(c=T['text2']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><line x1="8" y1="6" x2="21" y2="6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><line x1="8" y1="12" x2="21" y2="12" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><line x1="8" y1="18" x2="21" y2="18" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><line x1="3" y1="6" x2="3.01" y2="6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="3" y1="12" x2="3.01" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="3" y1="18" x2="3.01" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>', color=c)

    @staticmethod
    def open_folder(c=T['text1']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>', color=c)

    @staticmethod
    def sun(c=T['text2']):
        return _svg_icon('<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.7"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>', color=c)


# ── QSS ───────────────────────────────────────────────────────────
# FIX: Remove wildcard "QWidget { background: transparent }" that caused
# overlay/dark layer on all children. Instead, only set bg on specific classes.
GLOBAL_QSS = f"""
* {{ font-family: 'Segoe UI', sans-serif; }}
QMainWindow {{ background: {T['bg0']}; color: {T['text1']}; }}
QScrollArea {{ border: none; background: {T['bg0']}; }}
QScrollBar:vertical {{ background: {T['bg0']}; width: 8px; }}
QScrollBar::handle:vertical {{ background: {T['bg3']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {T['bgElev']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; height: 0; }}
QLineEdit {{
    background: {T['bg0']}; border: 1px solid {T['border']}; border-radius: 10px;
    padding: 8px 12px; color: {T['text2']}; font-family: 'Consolas', monospace; font-size: 13px;
}}
QLineEdit:hover {{ border-color: {T['bgElev']}; }}
QLineEdit:focus {{ border-color: {T['teal']}; }}
QProgressBar {{ background: {T['bg3']}; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {T['teal2']},stop:1 {T['teal']});
    border-radius: 4px;
}}
QTextEdit {{
    background: {T['bg2']}; border: 1px solid {T['borderSoft']}; border-radius: 10px;
    color: {T['text2']}; font-family: 'Consolas', monospace; font-size: 12px; padding: 10px;
}}
QLabel {{ color: {T['text1']}; background: transparent; }}
QPushButton {{ background: transparent; color: {T['text1']}; }}
QFrame {{ background: transparent; color: {T['text1']}; }}
QWidget {{ color: {T['text1']}; }}
"""


def _bqss(bg, color, border="none", hbg=None, hbr=None,
          fs="13px", fw="500", mh="38px", r="10px", pad="0 16px"):
    hbg = hbg or bg; hbr = hbr or border
    return f"""QPushButton {{ background:{bg};color:{color};font-size:{fs};font-weight:{fw};
        border:{border};border-radius:{r};padding:{pad};min-height:{mh}; }}
    QPushButton:hover {{ background:{hbg};border:{hbr}; }}
    QPushButton:pressed {{ background:{T['teal2']}; }}
    QPushButton:disabled {{ background:{T['bg3']};color:{T['text4']}; }}"""


BTN_PRIMARY = _bqss(T['teal'], "#03261C", hbg="#2DE0B6", fs="14px", fw="700", mh="48px", r="12px", pad="0 24px")
BTN_SECONDARY = _bqss(T['bg3'], T['text1'], border=f"1px solid {T['border']}",
                        hbg=T['bgElev'], hbr=f"1px solid {T['bgElev']}", fs="14px", mh="48px", r="12px")
BTN_GHOST = _bqss(T['bg3'], T['text2'], border=f"1px solid {T['borderSoft']}",
                    hbg=T['bgElev'], hbr=f"1px solid {T['border']}", pad="0 14px")


def seg_qss(active):
    """FIX: Use padding that allows text to breathe — no min-width forcing truncation."""
    if active:
        return _bqss(T['teal'], "#03261C", hbg="#2DE0B6", fw="600", mh="34px", r="8px", pad="6px 14px")
    return _bqss(T['bg2'], T['text2'], border=f"1px solid {T['borderSoft']}",
                  hbg=T['bg3'], mh="34px", r="8px", pad="6px 14px")


# ── Signal bridge ─────────────────────────────────────────────────
class ProgressBridge(QObject):
    progress = Signal(str, float)


# ── Compare View (preview antes/depois) ──────────────────────────

class CompareView(QWidget):
    """Widget de comparação antes/depois com divisor arrastável."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.SizeHorCursor)

        self._before = None  # QPixmap
        self._after = None   # QPixmap
        self._split = 0.5    # posição 0.0-1.0
        self._dragging = False
        self._has_images = False

        # Gera placeholder
        self._generate_placeholder()

    def set_images(self, before_path: str, after_path: str):
        """Carrega par de imagens reais."""
        b = QPixmap(before_path)
        a = QPixmap(after_path)
        if not b.isNull() and not a.isNull():
            self._before = b
            self._after = a
            self._has_images = True
            self._split = 0.5
            self.update()

    def set_before_pixmap(self, pixmap):
        """Define imagem 'antes' diretamente como QPixmap."""
        if pixmap and not pixmap.isNull():
            self._before = pixmap
            self._has_images = self._after is not None and not self._after.isNull()
            self.update()

    def set_after_pixmap(self, pixmap):
        """Define imagem 'depois' diretamente como QPixmap."""
        if pixmap and not pixmap.isNull():
            self._after = pixmap
            self._has_images = self._before is not None and not self._before.isNull()
            self.update()

    def set_images_from_pixmaps(self, before_px, after_px):
        """Define ambas as imagens a partir de QPixmaps."""
        if before_px and not before_px.isNull() and after_px and not after_px.isNull():
            self._before = before_px
            self._after = after_px
            self._has_images = True
            self._split = 0.5
            self.update()

    def _generate_placeholder(self):
        """Cria imagens placeholder (gradiente escuro com texto)."""
        w, h = 800, 500
        for attr, label, col1, col2 in [
            ("_before", "ANTES", QColor("#1a1a2e"), QColor("#16213e")),
            ("_after", "DEPOIS", QColor("#0f3460"), QColor("#1a1a2e")),
        ]:
            px = QPixmap(w, h)
            p = QPainter(px)
            grad = QLinearGradient(0, 0, w, h)
            grad.setColorAt(0, col1)
            grad.setColorAt(1, col2)
            p.fillRect(0, 0, w, h, grad)
            p.setPen(QColor(T['text4']))
            p.setFont(QFont("Segoe UI", 16))
            p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, f"[ {label} ]\nSelecione uma pasta para preview")
            p.end()
            setattr(self, attr, px)

    def paintEvent(self, ev):
        if not self._before or not self._after:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        split_x = int(w * self._split)

        # Clip arredondado
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 12, 12)
        p.setClipPath(path)

        # Antes (inteira)
        scaled_before = self._before.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        bx = (scaled_before.width() - w) // 2
        by = (scaled_before.height() - h) // 2
        p.drawPixmap(0, 0, scaled_before, bx, by, w, h)

        # Depois (clip direita)
        p.save()
        clip = QPainterPath()
        clip.addRect(split_x, 0, w - split_x, h)
        p.setClipPath(clip)
        scaled_after = self._after.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        ax = (scaled_after.width() - w) // 2
        ay = (scaled_after.height() - h) // 2
        p.drawPixmap(0, 0, scaled_after, ax, ay, w, h)
        p.restore()
        p.setClipPath(path)  # restore clip arredondado

        # Corner markers
        p.setPen(QPen(QColor(255, 255, 255, 140), 1.5))
        m, sz = 10, 14
        for x1, y1, dx, dy in [
            (m, m, sz, 0), (m, m, 0, sz),
            (w-m, m, -sz, 0), (w-m, m, 0, sz),
            (m, h-m, sz, 0), (m, h-m, 0, -sz),
            (w-m, h-m, -sz, 0), (w-m, h-m, 0, -sz),
        ]:
            p.drawLine(x1, y1, x1+dx, y1+dy)

        # Linha divisória
        p.setPen(QPen(QColor(255, 255, 255, 200), 2))
        p.drawLine(split_x, 0, split_x, h)

        # Handle circular
        cy = h // 2
        handle_r = 18
        p.setPen(Qt.NoPen)
        # Glow
        p.setBrush(QColor(31, 209, 168, 40))
        p.drawEllipse(QPoint(split_x, cy), handle_r + 4, handle_r + 4)
        # Handle
        p.setBrush(QColor(T['teal']))
        p.drawEllipse(QPoint(split_x, cy), handle_r, handle_r)
        # Setas
        p.setPen(QPen(QColor("#0B1220"), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(split_x - 6, cy, split_x - 2, cy - 4)
        p.drawLine(split_x - 6, cy, split_x - 2, cy + 4)
        p.drawLine(split_x + 6, cy, split_x + 2, cy - 4)
        p.drawLine(split_x + 6, cy, split_x + 2, cy + 4)

        # Labels "Antes" / "Depois"
        label_font = QFont("Segoe UI", 10, QFont.Bold)
        p.setFont(label_font)
        for text, lx, ly in [("Antes", 14, 14), ("Depois", w - 80, 14)]:
            # Pill background
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(11, 18, 32, 184))
            p.drawRoundedRect(lx, ly, 66, 26, 13, 13)
            # Dot
            dot_color = QColor(T['text3']) if text == "Antes" else QColor(T['teal'])
            p.setBrush(dot_color)
            dot_x = lx + 10 if text == "Antes" else lx + 50
            p.drawEllipse(QPoint(dot_x, ly + 13), 3, 3)
            # Text
            p.setPen(QColor(T['text1']))
            tx = lx + 18 if text == "Antes" else lx + 8
            p.drawText(tx, ly + 18, text)

        p.end()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._dragging = True
            self._update_split(ev.position().x())

    def mouseMoveEvent(self, ev):
        if self._dragging:
            self._update_split(ev.position().x())

    def mouseReleaseEvent(self, ev):
        self._dragging = False

    def _update_split(self, x):
        self._split = max(0.05, min(0.95, x / self.width()))
        self.update()


# ── Reusable widgets ──────────────────────────────────────────────

class Card(QFrame):
    """FIX: Use objectName selector + QPalette to avoid bg bleeding to children."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        # Use QPalette for background instead of QSS that bleeds to children
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(T['bg1']))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setStyleSheet(f"#Card {{ border:1px solid {T['borderSoft']};border-radius:14px; }}")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(24); sh.setOffset(0, 6); sh.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(sh)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 16, 18, 16)
        self.lay.setSpacing(0)
    def w(self, widget, stretch=0): self.lay.addWidget(widget, stretch); return widget
    def l(self, layout): self.lay.addLayout(layout)
    def sp(self, px): self.lay.addSpacing(px)


class SubCard(QFrame):
    """FIX: Use objectName selector to scope styling."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SubCard")
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(T['bg2']))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setStyleSheet(f"#SubCard {{ border:1px solid {T['borderSoft']};border-radius:12px; }}")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(14, 12, 14, 12)
        self.lay.setSpacing(6)


class SegGroup(QWidget):
    """FIX: Use Preferred size policy + no forced min-width so text is never truncated."""
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
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn.setMinimumWidth(0)  # let Qt calculate natural width from text
            btn.clicked.connect(lambda _, v=opt: self.select(v))
            h.addWidget(btn)
            self._btns[opt] = btn
        self.select(current or options[0])
    def select(self, v):
        self._val = v
        for k, b in self._btns.items(): b.setStyleSheet(seg_qss(k == v))
        self.changed.emit(v)
    def value(self): return self._val


class Toggle(QPushButton):
    toggled_signal = Signal(bool)
    def __init__(self, on=False, parent=None):
        super().__init__(parent)
        self._on = on; self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._flip); self._refresh()
    def _flip(self):
        self._on = not self._on; self._refresh(); self.toggled_signal.emit(self._on)
    def _refresh(self):
        bg = T['teal'] if self._on else T['bg3']
        self.setStyleSheet(f"QPushButton {{ background:{bg};border:none;border-radius:12px; }}")
    def isChecked(self): return self._on
    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen); p.setBrush(QColor("#FFF"))
        p.drawEllipse(22 if self._on else 2, 2, 20, 20); p.end()


# ── Image enhancement helper ─────────────────────────────────────

def _generate_enhanced_preview(source_pixmap):
    """Gera versão 'depois' simulada: +15% brilho, +10% contraste, +8% saturação.
    Usa QImage pixel manipulation (sem dependência de numpy/cv2)."""
    if source_pixmap is None or source_pixmap.isNull():
        return None

    img = source_pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()

    # Work on a copy
    result = img.copy()

    brightness_factor = 1.15
    contrast_factor = 1.10
    saturation_factor = 1.08

    for y in range(h):
        for x in range(w):
            c = result.pixelColor(x, y)
            r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()

            # Brightness
            r = min(255, int(r * brightness_factor))
            g = min(255, int(g * brightness_factor))
            b = min(255, int(b * brightness_factor))

            # Contrast (around mid-point 128)
            r = min(255, max(0, int(128 + (r - 128) * contrast_factor)))
            g = min(255, max(0, int(128 + (g - 128) * contrast_factor)))
            b = min(255, max(0, int(128 + (b - 128) * contrast_factor)))

            # Saturation
            gray = int(0.299 * r + 0.587 * g + 0.114 * b)
            r = min(255, max(0, int(gray + (r - gray) * saturation_factor)))
            g = min(255, max(0, int(gray + (g - gray) * saturation_factor)))
            b = min(255, max(0, int(gray + (b - gray) * saturation_factor)))

            result.setPixelColor(x, y, QColor(r, g, b, a))

    return QPixmap.fromImage(result)


def _generate_enhanced_preview_fast(source_pixmap, max_size=600):
    """Gera preview 'depois' rápida — reduz resolução antes de processar pixels.
    Muito mais rápido que processar a imagem em resolução total."""
    if source_pixmap is None or source_pixmap.isNull():
        return None

    # Scale down for speed
    scaled = source_pixmap.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    try:
        import numpy as np
        # Fast path with numpy
        img = scaled.toImage().convertToFormat(QImage.Format_ARGB32)
        w, h = img.width(), img.height()
        ptr = img.bits()
        ptr.setsize(h * w * 4)
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 4)).copy()

        # BGRA order in QImage
        b_ch, g_ch, r_ch = arr[:,:,0].astype(np.float32), arr[:,:,1].astype(np.float32), arr[:,:,2].astype(np.float32)

        # Brightness +15%
        r_ch *= 1.15; g_ch *= 1.15; b_ch *= 1.15

        # Contrast +10%
        r_ch = 128 + (r_ch - 128) * 1.10
        g_ch = 128 + (g_ch - 128) * 1.10
        b_ch = 128 + (b_ch - 128) * 1.10

        # Saturation +8%
        gray = 0.299 * r_ch + 0.587 * g_ch + 0.114 * b_ch
        r_ch = gray + (r_ch - gray) * 1.08
        g_ch = gray + (g_ch - gray) * 1.08
        b_ch = gray + (b_ch - gray) * 1.08

        arr[:,:,0] = np.clip(b_ch, 0, 255).astype(np.uint8)
        arr[:,:,1] = np.clip(g_ch, 0, 255).astype(np.uint8)
        arr[:,:,2] = np.clip(r_ch, 0, 255).astype(np.uint8)

        result = QImage(arr.data, w, h, w * 4, QImage.Format_ARGB32).copy()
        return QPixmap.fromImage(result)
    except ImportError:
        pass

    # Fallback: pixel-by-pixel on scaled (small) image
    return _generate_enhanced_preview(scaled)


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

    def _build_ui(self):
        c = QWidget()
        pal = c.palette()
        pal.setColor(QPalette.Window, QColor(T['bg0']))
        c.setPalette(pal)
        c.setAutoFillBackground(True)
        self.setCentralWidget(c)
        root = QVBoxLayout(c)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._mk_topbar())
        # Body scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body_pal = body.palette()
        body_pal.setColor(QPalette.Window, QColor(T['bg0']))
        body.setPalette(body_pal)
        body.setAutoFillBackground(True)
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 14, 20, 20)
        bl.setSpacing(0)
        cols = QHBoxLayout(); cols.setSpacing(20)
        # Left
        left = QWidget(); left.setMinimumWidth(420); left.setMaximumWidth(480)
        left.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(12)
        ll.addWidget(self._mk_pastas())
        ll.addWidget(self._mk_edition())
        ll.addWidget(self._mk_upscale())
        ll.addWidget(self._mk_actions())
        ll.addStretch()
        cols.addWidget(left)
        # Right
        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(14)
        rl.addWidget(self._mk_preview(), 1)
        rl.addWidget(self._mk_bottom())
        cols.addWidget(right, 1)
        bl.addLayout(cols, 1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        root.addWidget(self._mk_statusbar())

    # ── Top bar (unified: brand + tabs + summary) ─────────────────
    def _mk_topbar(self):
        f = QFrame(); f.setFixedHeight(56)
        f.setObjectName("TopBar")
        f.setStyleSheet(f"#TopBar {{ background:{T['bg1']};border-bottom:1px solid {T['borderSoft']}; }}")
        h = QHBoxLayout(f); h.setContentsMargins(20, 0, 16, 0); h.setSpacing(0)

        # Brand icon + title
        brand_icon = QLabel()
        brand_icon.setPixmap(Icons.process(T['teal']).pixmap(22, 22))
        brand_icon.setFixedSize(28, 28)
        h.addWidget(brand_icon)
        h.addSpacing(8)

        # Dark/light toggle placeholder (matching mockup's toggle)
        toggle_frame = QWidget()
        toggle_frame.setFixedSize(48, 28)
        tfl = QHBoxLayout(toggle_frame)
        tfl.setContentsMargins(0, 0, 0, 0)
        sun_btn = QPushButton()
        sun_btn.setIcon(Icons.sun(T['text3']))
        sun_btn.setFixedSize(28, 28)
        sun_btn.setStyleSheet(f"QPushButton {{ background:transparent;border:none; }}")
        tfl.addWidget(sun_btn)
        tg_theme = Toggle(True)
        tfl.addWidget(tg_theme)
        h.addWidget(toggle_frame)
        h.addSpacing(20)

        # Separator
        sep = QFrame(); sep.setFixedSize(1, 30)
        sep.setStyleSheet(f"background:{T['borderSoft']};")
        h.addWidget(sep)
        h.addSpacing(16)

        # Tabs
        tabs = [
            ("Processar", Icons.process(), True),
            ("Configurações", Icons.settings(), False),
            ("Treinar estilo", Icons.star(), False),
        ]
        for label, icon, active in tabs:
            btn = QPushButton(icon, f" {label}")
            if active:
                btn.setStyleSheet(f"QPushButton{{ color:{T['teal']};font-weight:600;font-size:14px;"
                    f"border:none;border-bottom:2px solid {T['teal']};padding:14px 14px 12px 14px;background:transparent; }}"
                    f"QPushButton:hover{{ color:{T['teal']}; }}")
            else:
                btn.setStyleSheet(f"QPushButton{{ color:{T['text3']};font-weight:500;font-size:14px;"
                    f"border:none;padding:14px 14px 12px 14px;background:transparent; }}"
                    f"QPushButton:hover{{ color:{T['text2']}; }}")
            h.addWidget(btn)

        h.addStretch()

        # Summary chips
        sf = QFrame()
        sf.setObjectName("SummaryFrame")
        sf.setStyleSheet(f"#SummaryFrame {{ background:{T['bg2']};border:1px solid {T['borderSoft']};border-radius:12px; }}")
        sh_lay = QHBoxLayout(sf); sh_lay.setContentsMargins(4, 4, 4, 4); sh_lay.setSpacing(0)
        self._sum = {}
        items = [
            ("intensity", "Intensidade", "Normal", Icons.intensity()),
            ("color", "Cor", "Natural", Icons.palette()),
            ("upscale", "Upscale", "Off", Icons.upscale(T['teal'])),
            ("preview", "Preview", "Off", Icons.eye()),
        ]
        for i, (key, lbl, val, icon) in enumerate(items):
            if i > 0:
                sep2 = QFrame(); sep2.setFixedSize(1, 28)
                sep2.setStyleSheet(f"background:{T['borderSoft']};")
                sh_lay.addWidget(sep2)
            wrap = QWidget()
            wrap.setMinimumWidth(80)
            wl = QHBoxLayout(wrap); wl.setContentsMargins(10, 4, 10, 4); wl.setSpacing(6)
            icon_lbl = QLabel(); icon_lbl.setPixmap(icon.pixmap(16, 16))
            icon_lbl.setFixedSize(16, 16)
            wl.addWidget(icon_lbl)
            text_col = QVBoxLayout(); text_col.setSpacing(0)
            tl = QLabel(lbl); tl.setStyleSheet(f"font-size:10px;color:{T['text3']};letter-spacing:0.5px;")
            text_col.addWidget(tl)
            vl = QLabel(val); vl.setStyleSheet(f"font-size:13px;font-weight:600;color:{T['text1']};")
            text_col.addWidget(vl)
            self._sum[key] = vl
            wl.addLayout(text_col)
            sh_lay.addWidget(wrap)
        h.addWidget(sf)
        return f

    # ── Card helpers ──────────────────────────────────────────────
    def _hdr(self, card, title, sub=None, icon=None):
        row = QHBoxLayout(); row.setSpacing(10)
        if icon:
            ic = QLabel(); ic.setPixmap(icon.pixmap(18, 18)); ic.setFixedSize(28, 28)
            ic.setAlignment(Qt.AlignCenter)
            ic.setStyleSheet(f"background:{T['bg3']};border-radius:8px;")
            row.addWidget(ic)
        t = QLabel(title); t.setStyleSheet(f"font-size:15px;font-weight:600;color:{T['text1']};")
        row.addWidget(t); row.addStretch()
        card.l(row)
        if sub:
            s = QLabel(sub); s.setStyleSheet(f"font-size:12px;color:{T['text3']};padding-bottom:4px;")
            s.setWordWrap(True); card.w(s)
        card.sp(10)

    # ── Pastas ────────────────────────────────────────────────────
    def _mk_pastas(self):
        card = Card()
        self._hdr(card, "Pastas", icon=Icons.folder(T['text2']))
        for label, desc, attr in [
            ("Entrada", "Pasta com as fotos originais.", "_input_dir"),
            ("Saída", "Pasta onde o agente salvará tudo.", "_output_dir"),
        ]:
            sc = SubCard()
            t = QLabel(label); t.setStyleSheet(f"font-size:13px;font-weight:600;color:{T['text1']};")
            sc.lay.addWidget(t)
            d = QLabel(desc); d.setStyleSheet(f"font-size:11.5px;color:{T['text3']};")
            sc.lay.addWidget(d); sc.lay.addSpacing(4)
            row = QHBoxLayout(); row.setSpacing(8)
            le = QLineEdit(); le.setPlaceholderText("C:\\Fotos\\...")
            setattr(self, attr, le); row.addWidget(le, 1)
            b = QPushButton("Procurar"); b.setStyleSheet(BTN_GHOST); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, w=le: self._browse_dir(w)); row.addWidget(b)
            sc.lay.addLayout(row); card.w(sc); card.sp(8)
        # Estilo
        sc = SubCard()
        t = QLabel("Estilo (opcional)"); t.setStyleSheet(f"font-size:13px;font-weight:600;color:{T['text1']};")
        sc.lay.addWidget(t)
        d = QLabel("Use um perfil .json treinado com o seu estilo.")
        d.setStyleSheet(f"font-size:11.5px;color:{T['text3']};"); sc.lay.addWidget(d); sc.lay.addSpacing(4)
        row = QHBoxLayout(); row.setSpacing(8)
        self._style_path = QLineEdit(); row.addWidget(self._style_path, 1)
        bc = QPushButton("Limpar"); bc.setStyleSheet(BTN_GHOST); bc.setCursor(Qt.PointingHandCursor)
        bc.clicked.connect(lambda: self._style_path.clear()); row.addWidget(bc)
        bs = QPushButton("Selecionar"); bs.setStyleSheet(BTN_GHOST); bs.setCursor(Qt.PointingHandCursor)
        bs.clicked.connect(self._browse_style); row.addWidget(bs)
        sc.lay.addLayout(row); card.w(sc)

        # Connect input dir change to preview auto-load
        self._input_dir.textChanged.connect(self._on_input_dir_changed)

        return card

    # ── Edição ────────────────────────────────────────────────────
    def _mk_edition(self):
        card = Card()
        self._hdr(card, "Edição", "Controle a intensidade e teste o resultado antes do lote completo.",
                  icon=Icons.edit(T['text2']))
        row = QHBoxLayout(); row.setSpacing(20)
        for label, opts, cur, slot, rec in [
            ("Intensidade", ["Suave", "Normal", "Forte"], "Normal", self._on_intensity, "Normal"),
            ("Modo de Cor", ["Natural", "Vibrant", "Luxury"], "Natural", self._on_color, "Luxury"),
        ]:
            col = QVBoxLayout(); col.setSpacing(4)
            l = QLabel(label); l.setStyleSheet(f"font-size:13px;font-weight:600;color:{T['text1']};")
            col.addWidget(l)
            sg = SegGroup(opts, cur); sg.changed.connect(slot); col.addWidget(sg)
            r = QLabel(f"Recomendado: {rec}"); r.setStyleSheet(f"font-size:11px;color:{T['text4']};")
            col.addWidget(r); row.addLayout(col, 1)
        card.l(row); card.sp(14)
        prow = QHBoxLayout(); prow.setSpacing(10)
        pl = QLabel("Teste rápido (preview)"); pl.setStyleSheet(f"font-size:13px;font-weight:500;color:{T['text1']};")
        prow.addWidget(pl)
        pd = QLabel("Processa miniaturas para visualização rápida.")
        pd.setStyleSheet(f"font-size:12px;color:{T['text3']};"); prow.addWidget(pd, 1)
        self._tg_preview = Toggle(False); self._tg_preview.toggled_signal.connect(self._on_preview)
        prow.addWidget(self._tg_preview); card.l(prow)
        return card

    # ── Upscale ───────────────────────────────────────────────────
    def _mk_upscale(self):
        card = Card()
        self._hdr(card, "Upscale", "Aumente a resolução das fotos antes das exportações finais.",
                  icon=Icons.upscale(T['text2']))
        row = QHBoxLayout(); row.setSpacing(12)
        self._tg_up = Toggle(False); self._tg_up.toggled_signal.connect(self._on_upscale)
        row.addWidget(self._tg_up)
        ul = QLabel("Ativar upscale nas fotos"); ul.setStyleSheet(f"font-size:13px;font-weight:500;color:{T['text1']};")
        row.addWidget(ul); row.addStretch()
        fl = QLabel("Fator:"); fl.setStyleSheet(f"font-size:12px;color:{T['text3']};"); row.addWidget(fl)
        self._seg_fac = SegGroup(["2x", "3x", "4x"], "2x")
        self._seg_fac.changed.connect(self._on_factor); row.addWidget(self._seg_fac)
        card.l(row); card.sp(6)
        rec = QLabel("Recomendado: 2x. Use 3x ou 4x só quando precisar de arquivos maiores.")
        rec.setStyleSheet(f"font-size:11.5px;color:{T['text4']};"); rec.setWordWrap(True); card.w(rec)
        return card

    # ── Actions ───────────────────────────────────────────────────
    def _mk_actions(self):
        f = QWidget(); h = QHBoxLayout(f); h.setContentsMargins(0, 6, 0, 0); h.setSpacing(12)
        self._btn_proc = QPushButton(Icons.process("#03261C"), " Processar fotos")
        self._btn_proc.setStyleSheet(BTN_PRIMARY); self._btn_proc.setCursor(Qt.PointingHandCursor)
        self._btn_proc.clicked.connect(self._start_processing); h.addWidget(self._btn_proc, 3)
        self._btn_open = QPushButton(Icons.open_folder(), " Abrir saída")
        self._btn_open.setStyleSheet(BTN_SECONDARY); self._btn_open.setCursor(Qt.PointingHandCursor)
        self._btn_open.clicked.connect(self._open_output_folder); h.addWidget(self._btn_open, 2)
        return f

    # ── Preview ───────────────────────────────────────────────────
    def _mk_preview(self):
        card = Card()
        hdr = QHBoxLayout()
        lh = QVBoxLayout()
        t = QLabel("Prévia"); t.setStyleSheet(f"font-size:16px;font-weight:600;color:{T['text1']};")
        lh.addWidget(t)
        s = QLabel("Compare o resultado antes de processar todas as fotos.")
        s.setStyleSheet(f"font-size:12px;color:{T['text3']};"); lh.addWidget(s)
        hdr.addLayout(lh, 1)
        bf = QPushButton(Icons.expand(), " Tela cheia"); bf.setStyleSheet(BTN_GHOST)
        bf.setCursor(Qt.PointingHandCursor); hdr.addWidget(bf)
        card.l(hdr); card.sp(12)
        self._compare = CompareView()
        card.w(self._compare, 1)
        return card

    # ── Bottom (status + log) ─────────────────────────────────────
    def _mk_bottom(self):
        f = QWidget(); f.setMinimumHeight(170); f.setMaximumHeight(220)
        h = QHBoxLayout(f); h.setContentsMargins(0,6,0,0); h.setSpacing(14)
        # Status
        sc = Card()
        self._hdr(sc, "Status do processamento", "Acompanhe o andamento do processo em tempo real.",
                  icon=Icons.activity())
        sr = QHBoxLayout()
        slv = QVBoxLayout()
        slv.addWidget(self._lbl("Arquivo atual", T['text3'], "12px"))
        self._lbl_file = QLabel("—")
        self._lbl_file.setStyleSheet(f"font-size:14px;font-weight:600;color:{T['text1']};font-family:Consolas,monospace;")
        slv.addWidget(self._lbl_file); sr.addLayout(slv, 1)
        srv = QVBoxLayout(); srv.setAlignment(Qt.AlignRight)
        srv.addWidget(self._lbl("Progresso", T['text3'], "12px", Qt.AlignRight))
        self._lbl_pct = QLabel("0%"); self._lbl_pct.setAlignment(Qt.AlignRight)
        self._lbl_pct.setStyleSheet(f"font-size:14px;font-weight:600;color:{T['text1']};font-family:Consolas,monospace;")
        srv.addWidget(self._lbl_pct); sr.addLayout(srv)
        sc.l(sr); sc.sp(8)
        self._prog = QProgressBar(); self._prog.setRange(0,1000); self._prog.setValue(0); self._prog.setTextVisible(False)
        sc.w(self._prog); sc.sp(8)
        self._lbl_foot = QLabel("Pronto para processar.")
        self._lbl_foot.setStyleSheet(f"font-size:12px;color:{T['text3']};"); self._lbl_foot.setWordWrap(True)
        sc.w(self._lbl_foot); h.addWidget(sc, 1)
        # Log
        lc = Card()
        self._hdr(lc, "Log de atividades", "Mensagens do processamento, erros e eventos relevantes.",
                  icon=Icons.list_icon())
        self._log = QTextEdit(); self._log.setReadOnly(True)
        lc.w(self._log, 1); h.addWidget(lc, 1)
        return f

    # ── Status bar ────────────────────────────────────────────────
    def _mk_statusbar(self):
        f = QFrame(); f.setFixedHeight(36)
        f.setObjectName("StatusBar")
        f.setStyleSheet(f"#StatusBar {{ background:{T['bg1']};border-top:1px solid {T['borderSoft']}; }}")
        h = QHBoxLayout(f); h.setContentsMargins(20,0,20,0); h.setSpacing(10)
        dot = QLabel("●"); dot.setStyleSheet(f"color:{T['green']};font-size:9px;"); h.addWidget(dot)
        self._sb_st = QLabel("Pronto para processar")
        self._sb_st.setStyleSheet(f"font-size:12px;color:{T['text2']};"); h.addWidget(self._sb_st)
        sep = QFrame(); sep.setFixedSize(1,12); sep.setStyleSheet(f"background:{T['border']};"); h.addWidget(sep)
        self._sb_ct = QLabel("0 fotos na fila"); self._sb_ct.setStyleSheet(f"font-size:12px;color:{T['text3']};")
        h.addWidget(self._sb_ct); h.addStretch()
        tips = QLabel("Dicas e boas práticas"); tips.setStyleSheet(f"font-size:12px;color:{T['text3']};")
        h.addWidget(tips); return f

    # ── Helpers ────────────────────────────────────────────────────
    def _lbl(self, text, color, size="13px", align=None):
        l = QLabel(text); l.setStyleSheet(f"font-size:{size};color:{color};")
        if align: l.setAlignment(align)
        return l

    def _update_summary(self):
        self._sum["intensity"].setText(self._intensity.capitalize())
        self._sum["color"].setText(self._color_mode.capitalize())
        self._sum["upscale"].setText(self._upscale_factor if self._upscale_enabled else "Off")
        self._sum["preview"].setText("Ligado" if self._preview_mode else "Off")

    # ══════════════════════════════════════════════════════════════
    #  HANDLERS
    # ══════════════════════════════════════════════════════════════
    def _browse_dir(self, le):
        p = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if p: le.setText(p)

    def _browse_style(self):
        p, _ = QFileDialog.getOpenFileName(self, "Perfil de estilo", "", "JSON (*.json)")
        if p: self._style_path.setText(p)

    def _on_intensity(self, v): self._intensity = v.lower(); self._update_summary()
    def _on_color(self, v): self._color_mode = v.lower(); self._update_summary()
    def _on_preview(self, v): self._preview_mode = v; self._update_summary()
    def _on_upscale(self, v): self._upscale_enabled = v; self._update_summary()
    def _on_factor(self, v): self._upscale_factor = v; self._update_summary()

    def _on_input_dir_changed(self, path):
        """Auto-load first image from input folder into preview."""
        if not path or not os.path.isdir(path):
            return
        # Find first image
        exts = ('*.jpg', '*.jpeg', '*.png', '*.webp', '*.bmp', '*.tiff', '*.tif')
        images = []
        for ext in exts:
            images.extend(glob.glob(os.path.join(path, ext)))
            images.extend(glob.glob(os.path.join(path, ext.upper())))
        if not images:
            return
        images.sort()
        first_image = images[0]

        # Load as "antes"
        before_px = QPixmap(first_image)
        if before_px.isNull():
            return

        # Generate simulated "depois" (enhanced)
        after_px = _generate_enhanced_preview_fast(before_px)
        if after_px and not after_px.isNull():
            self._compare.set_images_from_pixmaps(before_px, after_px)
        else:
            self._compare.set_before_pixmap(before_px)

        # Update status bar with count
        count = len(images)
        self._sb_ct.setText(f"{count} fotos na fila")

    def _collect_options(self):
        return {
            "intensity": self._intensity, "color_mode": self._color_mode,
            "preview_mode": self._preview_mode,
            "upscale_enabled": self._upscale_enabled,
            "upscale_factor": float(self._upscale_factor.replace("x", "")),
            "upscale_preset": "natural_pro",
            "duplicates_enabled": True, "duplicates_threshold": 10,
            "rename_enabled": False, "rename_prefix": "IMOVEL", "rename_code": "",
            "watermark_enabled": False, "watermark_config": None,
            "contact_sheet": True, "before_after": True, "gallery": True,
            "gallery_title": "Galeria de Fotos", "gallery_subtitle": "",
            "exif_preserve": True, "photographer": "", "copyright": "",
        }

    def _start_processing(self):
        inp = self._input_dir.text().strip()
        out = self._output_dir.text().strip()
        if not inp or not os.path.isdir(inp):
            QMessageBox.critical(self, "Erro", "Selecione uma pasta de entrada válida."); return
        if not out:
            QMessageBox.critical(self, "Erro", "Selecione uma pasta de saída."); return
        os.makedirs(out, exist_ok=True)
        self._log.clear(); self._prog.setValue(0)
        self._lbl_pct.setText("0%"); self._lbl_file.setText("—")
        self._btn_proc.setEnabled(False)
        style_path = self._style_path.text().strip() or None
        opts = self._collect_options()
        def cb(msg, pct): self._bridge.progress.emit(msg, pct)
        self.pipeline = ProcessingPipeline(inp, out, cb, style_profile_path=style_path, options=opts)
        self.pipeline.start()

    def _update_ui(self, msg, pct):
        self._prog.setValue(int(pct * 1000))
        self._lbl_pct.setText(f"{int(pct*100)}%")
        if "]" in msg:
            parts = msg.split("]", 1)
            if len(parts) > 1:
                self._lbl_file.setText(parts[1].strip())
                self._lbl_foot.setText(f"Processados: {parts[0].replace('[','')} fotos")
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f'<span style="color:{T["text3"]}">{ts}</span>  {msg}')
        if pct >= 1.0:
            self._btn_proc.setEnabled(True)
            self._sb_st.setText("Processamento concluído")

    def _open_output_folder(self):
        p = self._output_dir.text().strip()
        if p and os.path.isdir(p): os.startfile(p)
        else: QMessageBox.information(self, "Info", "Defina uma pasta de saída primeiro.")

    def mainloop(self):
        self.show(); QApplication.instance().exec()
