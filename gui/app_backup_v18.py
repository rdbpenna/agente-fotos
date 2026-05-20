"""
Interface gráfica do Agente de Fotos Imobiliárias.

Versão com:
- design mais clean
- modo claro / modo escuro
- correção do scroll nas abas com rolagem
- mesmas funcionalidades principais do projeto
"""

import os
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageDraw, ImageFont, ImageTk

from core.pipeline import ProcessingPipeline
from core.style_trainer import StyleTrainer


class PhotoAgentApp(tk.Tk):
    """Janela principal da aplicação."""

    THEMES = {
        "light": {
            "BG": "#EEF2F6",
            "CARD": "#FFFFFF",
            "CARD_ALT": "#F8FAFC",
            "BORDER": "#D9E2EC",
            "TEXT": "#1F2937",
            "MUTED": "#6B7280",
            "ACCENT": "#2E6B5D",
            "ACCENT_HOVER": "#24584C",
            "ACCENT_SOFT": "#E7F3EF",
            "TAB_BG": "#E6EBF1",
            "TAB_ACTIVE": "#EDF2F7",
            "ENTRY_BG": "#FBFCFE",
            "DARK_PANEL": "#101827",
            "DARK_PANEL_TEXT": "#E5EDF5",
            "DARK_PANEL_BORDER": "#253146",
            "SELECT_BG": "#1E3A5F",
            "PROGRESS_TROUGH": "#E5EAF0",
        },
        "dark": {
            "BG": "#0F172A",
            "CARD": "#111827",
            "CARD_ALT": "#172033",
            "BORDER": "#243041",
            "TEXT": "#E5E7EB",
            "MUTED": "#94A3B8",
            "ACCENT": "#22A37A",
            "ACCENT_HOVER": "#1B8A67",
            "ACCENT_SOFT": "#123A31",
            "TAB_BG": "#162033",
            "TAB_ACTIVE": "#1D2940",
            "ENTRY_BG": "#0B1220",
            "DARK_PANEL": "#0B1220",
            "DARK_PANEL_TEXT": "#D8E1EA",
            "DARK_PANEL_BORDER": "#22314A",
            "SELECT_BG": "#234C77",
            "PROGRESS_TROUGH": "#1B2A3C",
        },
    }

    def __init__(self):
        super().__init__()

        self.title("Agente de Fotos Imobiliárias")
        self.geometry("980x760")
        self.minsize(860, 620)

        self.theme_mode = "light"
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.option_add("*Font", "{Segoe UI} 10")

        # Variáveis gerais
        self._active_scroll_canvas = None
        self._scroll_canvases: list[tk.Canvas] = []
        self._theme_light_btn = None
        self._theme_dark_btn = None
        self.log_frame = None
        self.log_text = None
        self.pairs_frame = None
        self.pairs_listbox = None

        # ── Variáveis: Processar ──
        self.input_dir = tk.StringVar(value="")
        self.output_dir = tk.StringVar(value="")
        self.style_profile_path = tk.StringVar(value="")
        self.opt_intensity = tk.StringVar(value="normal")
        self.opt_color_mode = tk.StringVar(value="natural")
        self.opt_preview_mode = tk.BooleanVar(value=False)
        self.opt_upscale_enabled = tk.BooleanVar(value=False)
        self.opt_upscale_factor = tk.StringVar(value="2x")
        self.opt_upscale_preset = tk.StringVar(value="natural_pro")
        self.config_profile_name = tk.StringVar(value="")
        self.config_profile_combo = None
        self.pipeline: ProcessingPipeline | None = None

        # ── Variáveis: Configurações ──
        self.opt_duplicates = tk.BooleanVar(value=True)
        self.opt_rename = tk.BooleanVar(value=False)
        self.opt_rename_prefix = tk.StringVar(value="IMOVEL")
        self.opt_rename_code = tk.StringVar(value="")
        self.opt_watermark = tk.BooleanVar(value=False)
        self.opt_wm_mode = tk.StringVar(value="text")
        self.opt_wm_text = tk.StringVar(value="© Minha Empresa")
        self.opt_wm_image = tk.StringVar(value="")
        self.opt_wm_position = tk.StringVar(value="bottom-right")
        self.opt_wm_opacity = tk.DoubleVar(value=0.4)
        self.opt_wm_opacity_percent = tk.StringVar(value="40%")
        self._wm_preview_photo = None
        self.wm_preview_label = None
        self.opt_contact_sheet = tk.BooleanVar(value=True)
        self.opt_before_after = tk.BooleanVar(value=True)
        self.opt_gallery = tk.BooleanVar(value=True)
        self.opt_gallery_title = tk.StringVar(value="Galeria de Fotos")
        self.opt_gallery_subtitle = tk.StringVar(value="")
        self.opt_exif = tk.BooleanVar(value=True)
        self.opt_photographer = tk.StringVar(value="")
        self.opt_copyright = tk.StringVar(value="")

        # ── Variáveis: Treinar ──
        self.train_pairs: list[dict] = []

        self._bind_global_mousewheel()
        self.opt_wm_opacity.trace_add("write", lambda *_: self._on_watermark_preview_change())
        self.opt_wm_text.trace_add("write", lambda *_: self._on_watermark_preview_change())
        self.opt_wm_image.trace_add("write", lambda *_: self._on_watermark_preview_change())
        self.opt_wm_mode.trace_add("write", lambda *_: self._on_watermark_preview_change())
        self.opt_wm_position.trace_add("write", lambda *_: self._on_watermark_preview_change())
        self._apply_theme(self.theme_mode)
        self._build_ui()
        self._apply_theme(self.theme_mode)

    # ══════════════════════════════════════════════════════════════
    #  TEMA / ESTILO
    # ══════════════════════════════════════════════════════════════

    def _set_palette(self, mode: str):
        pal = self.THEMES[mode]
        self.BG = pal["BG"]
        self.CARD = pal["CARD"]
        self.CARD_ALT = pal["CARD_ALT"]
        self.BORDER = pal["BORDER"]
        self.TEXT = pal["TEXT"]
        self.MUTED = pal["MUTED"]
        self.ACCENT = pal["ACCENT"]
        self.ACCENT_HOVER = pal["ACCENT_HOVER"]
        self.ACCENT_SOFT = pal["ACCENT_SOFT"]
        self.TAB_BG = pal["TAB_BG"]
        self.TAB_ACTIVE = pal["TAB_ACTIVE"]
        self.ENTRY_BG = pal["ENTRY_BG"]
        self.DARK_PANEL = pal["DARK_PANEL"]
        self.DARK_PANEL_TEXT = pal["DARK_PANEL_TEXT"]
        self.DARK_PANEL_BORDER = pal["DARK_PANEL_BORDER"]
        self.SELECT_BG = pal["SELECT_BG"]
        self.PROGRESS_TROUGH = pal["PROGRESS_TROUGH"]

    def _apply_theme(self, mode: str | None = None):
        if mode is not None:
            self.theme_mode = mode
        self._set_palette(self.theme_mode)

        self.configure(bg=self.BG)

        s = self.style
        s.configure("App.TFrame", background=self.BG)
        s.configure("Card.TFrame", background=self.CARD)
        s.configure("Inner.TFrame", background=self.CARD)
        s.configure("Soft.TFrame", background=self.CARD_ALT)

        s.configure("Title.TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 19, "bold"))
        s.configure("Hero.TLabel", background=self.BG, foreground=self.MUTED, font=("Segoe UI", 10))
        s.configure("Section.TLabel", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 11, "bold"))
        s.configure("CardText.TLabel", background=self.CARD, foreground=self.MUTED, font=("Segoe UI", 9))
        s.configure("TLabel", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 10))
        s.configure("Muted.TLabel", background=self.CARD, foreground=self.MUTED, font=("Segoe UI", 9))

        s.configure("TButton", font=("Segoe UI", 10), padding=(10, 7), background=self.CARD, foreground=self.TEXT,
                    borderwidth=1, relief="flat")
        s.map("TButton", background=[("active", self.CARD_ALT)], foreground=[("active", self.TEXT)])

        s.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 10), background=self.ACCENT,
                    foreground="#FFFFFF", borderwidth=0, relief="flat")
        s.map("Accent.TButton", background=[("active", self.ACCENT_HOVER), ("disabled", "#90A8A1")],
              foreground=[("disabled", "#F2F5F4")])

        s.configure("ThemeOn.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 6), background=self.ACCENT,
                    foreground="#FFFFFF", borderwidth=0, relief="flat")
        s.map("ThemeOn.TButton", background=[("active", self.ACCENT_HOVER)])
        s.configure("ThemeOff.TButton", font=("Segoe UI", 9), padding=(12, 6), background=self.CARD_ALT,
                    foreground=self.TEXT, borderwidth=1, relief="flat")
        s.map("ThemeOff.TButton", background=[("active", self.CARD)], foreground=[("active", self.TEXT)])

        s.configure("Hover.TButton", font=("Segoe UI", 10), padding=(10, 7), background=self.CARD_ALT,
                    foreground=self.TEXT, borderwidth=1, relief="flat")
        s.configure("AccentHover.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 10), background=self.ACCENT_HOVER,
                    foreground="#FFFFFF", borderwidth=0, relief="flat")
        s.configure("SmallHover.TButton", font=("Segoe UI", 9), padding=(8, 5), background=self.CARD_ALT,
                    foreground=self.TEXT, borderwidth=1, relief="flat")

        s.configure("Small.TButton", font=("Segoe UI", 9), padding=(8, 5))

        s.configure("TLabelframe", background=self.CARD, bordercolor=self.BORDER, borderwidth=1,
                    relief="solid", padding=12)
        s.configure("TLabelframe.Label", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 10, "bold"))

        s.configure("TCheckbutton", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 10))
        s.map("TCheckbutton", background=[("active", self.CARD)])
        s.configure("TRadiobutton", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 10))
        s.map("TRadiobutton", background=[("active", self.CARD)])

        s.configure("TEntry", fieldbackground=self.ENTRY_BG, foreground=self.TEXT, bordercolor=self.BORDER,
                    lightcolor=self.BORDER, darkcolor=self.BORDER, padding=8)
        s.configure("TCombobox", fieldbackground=self.ENTRY_BG, background=self.ENTRY_BG, foreground=self.TEXT,
                    bordercolor=self.BORDER, lightcolor=self.BORDER, darkcolor=self.BORDER, padding=6, arrowsize=14)
        s.map("TCombobox", fieldbackground=[("readonly", self.ENTRY_BG)], foreground=[("readonly", self.TEXT)])

        s.configure("Horizontal.TProgressbar", troughcolor=self.PROGRESS_TROUGH, background=self.ACCENT,
                    bordercolor=self.PROGRESS_TROUGH, lightcolor=self.ACCENT, darkcolor=self.ACCENT, thickness=12)
        s.configure("TScale", background=self.CARD, troughcolor=self.PROGRESS_TROUGH)

        s.configure("App.TNotebook", background=self.BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure("App.TNotebook.Tab", background=self.TAB_BG, foreground=self.TEXT, padding=(18, 10),
                    font=("Segoe UI", 10, "bold"), borderwidth=0)
        s.map("App.TNotebook.Tab",
              background=[("selected", self.CARD), ("active", self.TAB_ACTIVE)],
              foreground=[("selected", self.ACCENT), ("active", self.TEXT)])

        for canvas in self._scroll_canvases:
            canvas.configure(bg=self.BG)

        self._refresh_theme_buttons()
        self._refresh_custom_panels()
        self.update_idletasks()

    def _refresh_theme_buttons(self):
        if self._theme_light_btn is not None:
            light_style = "ThemeOn.TButton" if self.theme_mode == "light" else "ThemeOff.TButton"
            self._theme_light_btn.configure(style=light_style)
        if self._theme_dark_btn is not None:
            dark_style = "ThemeOn.TButton" if self.theme_mode == "dark" else "ThemeOff.TButton"
            self._theme_dark_btn.configure(style=dark_style)

    def _refresh_custom_panels(self):
        if self.log_frame is not None:
            self.log_frame.configure(bg=self.DARK_PANEL, highlightbackground=self.DARK_PANEL_BORDER)
        if self.log_text is not None:
            self.log_text.configure(bg=self.DARK_PANEL, fg=self.DARK_PANEL_TEXT, insertbackground=self.DARK_PANEL_TEXT)
        if self.pairs_frame is not None:
            self.pairs_frame.configure(bg=self.DARK_PANEL, highlightbackground=self.DARK_PANEL_BORDER)
        if self.pairs_listbox is not None:
            self.pairs_listbox.configure(bg=self.DARK_PANEL, fg=self.DARK_PANEL_TEXT,
                                         selectbackground=self.SELECT_BG, selectforeground="#FFFFFF")
        if self.wm_preview_label is not None:
            self.wm_preview_label.configure(bg=self.CARD, highlightbackground=self.BORDER)
            self._update_watermark_preview()

    # ══════════════════════════════════════════════════════════════
    #  SCROLL
    # ══════════════════════════════════════════════════════════════

    def _bind_global_mousewheel(self):
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_mousewheel_linux, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel_linux, add="+")

    def _on_mousewheel(self, event):
        if self._active_scroll_canvas is not None:
            self._active_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        if self._active_scroll_canvas is None:
            return
        if event.num == 4:
            self._active_scroll_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._active_scroll_canvas.yview_scroll(1, "units")

    def _set_active_scroll_canvas(self, canvas):
        self._active_scroll_canvas = canvas

    # ══════════════════════════════════════════════════════════════
    #  HELPERS VISUAIS
    # ══════════════════════════════════════════════════════════════

    def _enable_hover(self, button, base_style="TButton", hover_style=None):
        """Adiciona um hover visual simples aos botões."""
        if hover_style is None:
            hover_style = base_style

        def _on_enter(_event):
            try:
                button.configure(style=hover_style, cursor="hand2")
            except Exception:
                pass

        def _on_leave(_event):
            try:
                button.configure(style=base_style, cursor="")
            except Exception:
                pass

        button.bind("<Enter>", _on_enter, add="+")
        button.bind("<Leave>", _on_leave, add="+")

    def _create_header(self, parent):
        header = ttk.Frame(parent, style="App.TFrame")
        header.pack(fill=tk.X, padx=14, pady=(14, 8))

        left = ttk.Frame(header, style="App.TFrame")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(left, text="🏠  Agente de Fotos Imobiliárias", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            left,
            text="Processamento automático com um visual mais limpo, organizado e profissional.",
            style="Hero.TLabel",
        ).pack(anchor=tk.W, pady=(4, 0))

        right = ttk.Frame(header, style="App.TFrame")
        right.pack(side=tk.RIGHT, pady=(2, 0))

        self._theme_light_btn = ttk.Button(right, text="Modo claro", command=lambda: self._apply_theme("light"))
        self._theme_light_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self._theme_dark_btn = ttk.Button(right, text="Modo escuro", command=lambda: self._apply_theme("dark"))
        self._theme_dark_btn.pack(side=tk.RIGHT)

        self._enable_hover(self._theme_light_btn, "ThemeOff.TButton", "Hover.TButton")
        self._enable_hover(self._theme_dark_btn, "ThemeOff.TButton", "Hover.TButton")
        self._refresh_theme_buttons()

    def _create_scrolled_page(self, parent):
        wrapper = ttk.Frame(parent, style="App.TFrame")
        wrapper.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(wrapper, bg=self.BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(wrapper, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas, style="App.TFrame", padding=2)

        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(window_id, width=event.width)

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        for widget in (canvas, inner, wrapper):
            widget.bind("<Enter>", lambda _e, c=canvas: self._set_active_scroll_canvas(c), add="+")

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scroll_canvases.append(canvas)
        return inner

    def _card(self, parent, title: str, subtitle: str | None = None):
        card = ttk.LabelFrame(parent, text=title, padding=12)
        card.pack(fill=tk.X, pady=(0, 10))
        if subtitle:
            ttk.Label(card, text=subtitle, style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 8))
        return card

    # ══════════════════════════════════════════════════════════════
    #  CONSTRUÇÃO DA INTERFACE
    # ══════════════════════════════════════════════════════════════

    def _build_ui(self):
        self._create_header(self)

        notebook = ttk.Notebook(self, style="App.TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))

        self.tab_process = ttk.Frame(notebook, style="App.TFrame", padding=14)
        self.tab_settings = ttk.Frame(notebook, style="App.TFrame", padding=14)
        self.tab_train = ttk.Frame(notebook, style="App.TFrame", padding=14)

        notebook.add(self.tab_process, text="Processar")
        notebook.add(self.tab_settings, text="Configurações")
        notebook.add(self.tab_train, text="Treinar estilo")

        self._build_process_tab()
        self._build_settings_tab()
        self._build_train_tab()

    # ──────────────────────────────────────────────────────────────
    #  ABA 1: PROCESSAR
    # ──────────────────────────────────────────────────────────────

    def _build_process_tab(self):
        inner = self._create_scrolled_page(self.tab_process)

        ttk.Label(inner, text="Processamento", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 2))
        ttk.Label(inner, text="Selecione as pastas, ajuste a intensidade e processe as fotos com segurança.",
                  style="Hero.TLabel").pack(anchor=tk.W, pady=(0, 12))

        card_files = self._card(inner, "Pastas", "Defina de onde as fotos serão lidas e onde os resultados serão salvos.")

        f1 = ttk.Frame(card_files, style="Card.TFrame")
        f1.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(f1, text="Entrada", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(f1, text="Pasta com as fotos originais.", style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 4))
        r1 = ttk.Frame(f1, style="Card.TFrame")
        r1.pack(fill=tk.X)
        ttk.Entry(r1, textvariable=self.input_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        btn = ttk.Button(r1, text="Procurar", command=self._browse_input)
        btn.pack(side=tk.RIGHT)
        self._enable_hover(btn, "TButton", "Hover.TButton")

        f2 = ttk.Frame(card_files, style="Card.TFrame")
        f2.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(f2, text="Saída", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(f2, text="Pasta onde o agente salvará tudo o que gerar.", style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 4))
        r2 = ttk.Frame(f2, style="Card.TFrame")
        r2.pack(fill=tk.X)
        ttk.Entry(r2, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        btn = ttk.Button(r2, text="Procurar", command=self._browse_output)
        btn.pack(side=tk.RIGHT)
        self._enable_hover(btn, "TButton", "Hover.TButton")

        f3 = ttk.Frame(card_files, style="Card.TFrame")
        f3.pack(fill=tk.X)
        ttk.Label(f3, text="Perfil de estilo", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(f3, text="Opcional: use um perfil .json treinado com o seu estilo.", style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 4))
        r3 = ttk.Frame(f3, style="Card.TFrame")
        r3.pack(fill=tk.X)
        ttk.Entry(r3, textvariable=self.style_profile_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        btn = ttk.Button(r3, text="Selecionar .json", command=self._browse_style)
        btn.pack(side=tk.RIGHT, padx=(0, 6))
        self._enable_hover(btn, "TButton", "Hover.TButton")
        btn_clear = ttk.Button(r3, text="Limpar", style="Small.TButton", command=lambda: self.style_profile_path.set(""))
        btn_clear.pack(side=tk.RIGHT)
        self._enable_hover(btn_clear, "Small.TButton", "SmallHover.TButton")

        card_edit = self._card(inner, "Edição", "Controle a intensidade e teste o resultado antes do lote completo.")
        row_edit = ttk.Frame(card_edit, style="Card.TFrame")
        row_edit.pack(fill=tk.X)

        left = ttk.Frame(row_edit, style="Card.TFrame")
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(left, text="Intensidade", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(left, text="Suave = mais seguro | Normal = padrão | Forte = mais presença", style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 6))
        ttk.Combobox(left, textvariable=self.opt_intensity, width=14,
                     values=["suave", "normal", "forte"], state="readonly").pack(anchor=tk.W)

        mid = ttk.Frame(row_edit, style="Card.TFrame")
        mid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 0))
        ttk.Label(mid, text="Modo de Cor", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(mid, text="Natural = fiel | Vibrant = vivo | Luxury = sofisticado", style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 6))
        ttk.Combobox(mid, textvariable=self.opt_color_mode, width=14,
                     values=["natural", "vibrant", "luxury"], state="readonly").pack(anchor=tk.W)

        right = ttk.Frame(row_edit, style="Card.TFrame")
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        ttk.Label(right, text="Teste rápido", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Checkbutton(right, text="Modo preview (processar só 1 foto)",
                        variable=self.opt_preview_mode).pack(anchor=tk.W, pady=(6, 0))

        ttk.Label(card_edit, text="Dica: comece no modo preview e use intensidade normal na maioria dos casos.",
                  style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 0))

        card_upscale = self._card(inner, "Upscale", "Aumente a resolução das fotos melhoradas antes das exportações finais.")
        row_up = ttk.Frame(card_upscale, style="Card.TFrame")
        row_up.pack(fill=tk.X)
        ttk.Checkbutton(row_up, text="Ativar upscale nas fotos", variable=self.opt_upscale_enabled).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(row_up, text="Fator:").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Combobox(row_up, textvariable=self.opt_upscale_factor, width=8,
                     values=["1.5x", "2x", "3x", "4x"], state="readonly").pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(row_up, text="Preset:").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Combobox(row_up, textvariable=self.opt_upscale_preset, width=16,
                     values=["natural_pro", "strong_pro", "luxury"], state="readonly").pack(side=tk.LEFT)
        ttk.Label(card_upscale, text="Natural Pro = seguro | Strong Pro = presença | Luxury = premium limpo",
                  style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 0))

        card_extra = self._card(inner, "Extras", "Escolha quais materiais complementares devem ser gerados no processamento.")
        row1 = ttk.Frame(card_extra, style="Card.TFrame")
        row1.pack(fill=tk.X, pady=(0, 6))
        ttk.Checkbutton(row1, text="Comparações antes/depois", variable=self.opt_before_after).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(row1, text="Folha de contato", variable=self.opt_contact_sheet).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(row1, text="Galeria HTML", variable=self.opt_gallery).pack(side=tk.LEFT)

        row2 = ttk.Frame(card_extra, style="Card.TFrame")
        row2.pack(fill=tk.X)
        ttk.Checkbutton(row2, text="Detectar duplicatas", variable=self.opt_duplicates).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(row2, text="Preservar EXIF", variable=self.opt_exif).pack(side=tk.LEFT)

        card_actions = self._card(inner, "Ações", "Inicie o processamento ou abra rapidamente a pasta de saída.")
        actions = ttk.Frame(card_actions, style="Card.TFrame")
        actions.pack(fill=tk.X)
        self.btn_process = ttk.Button(actions, text="Processar fotos", style="Accent.TButton", command=self._start_processing)
        self.btn_process.pack(side=tk.LEFT)
        self._enable_hover(self.btn_process, "Accent.TButton", "AccentHover.TButton")
        self.btn_cancel = ttk.Button(actions, text="Cancelar", command=self._cancel_processing, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=(8, 0))
        self._enable_hover(self.btn_cancel, "TButton", "Hover.TButton")
        btn_open = ttk.Button(actions, text="Abrir saída", command=self._open_output_folder)
        btn_open.pack(side=tk.RIGHT)
        self._enable_hover(btn_open, "TButton", "Hover.TButton")

        card_progress = self._card(inner, "Status", "Acompanhe o andamento do processo em tempo real.")
        self.progress_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(card_progress, variable=self.progress_var, maximum=1.0, mode="determinate").pack(fill=tk.X, pady=(2, 8))
        self.status_label = ttk.Label(card_progress, text="Pronto.", style="Section.TLabel")
        self.status_label.pack(anchor=tk.W)

        card_log = self._card(inner, "Log", "Mensagens do processamento, erros e eventos relevantes.")
        self.log_frame = tk.Frame(card_log, bg=self.DARK_PANEL, bd=0, highlightthickness=1, highlightbackground=self.DARK_PANEL_BORDER)
        self.log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(self.log_frame, height=11, font=("Consolas", 9), bg=self.DARK_PANEL,
                                fg=self.DARK_PANEL_TEXT, insertbackground=self.DARK_PANEL_TEXT, relief="flat",
                                bd=0, wrap=tk.WORD, state=tk.DISABLED, padx=10, pady=10)
        sb = ttk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # ──────────────────────────────────────────────────────────────
    #  ABA 2: CONFIGURAÇÕES
    # ──────────────────────────────────────────────────────────────

    def _build_settings_tab(self):
        inner = self._create_scrolled_page(self.tab_settings)

        ttk.Label(inner, text="Configurações", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 2))
        ttk.Label(inner, text="Ajuste detalhes opcionais do fluxo, exportação e metadados.",
                  style="Hero.TLabel").pack(anchor=tk.W, pady=(0, 12))

        pf = self._card(inner, "Perfis de configuração", "Salve e carregue configurações prontas para clientes ou tipos de imóvel.")
        pr1 = ttk.Frame(pf, style="Card.TFrame")
        pr1.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(pr1, text="Perfil", width=10).pack(side=tk.LEFT)
        self.config_profile_combo = ttk.Combobox(
            pr1,
            textvariable=self.config_profile_name,
            values=self._load_config_profile_names(),
            state="readonly",
            width=32,
        )
        self.config_profile_combo.pack(side=tk.LEFT, padx=(0, 8))
        btn_load_profile = ttk.Button(pr1, text="Carregar", command=self._load_selected_config_profile)
        btn_load_profile.pack(side=tk.LEFT, padx=(0, 6))
        self._enable_hover(btn_load_profile, "TButton", "Hover.TButton")
        btn_delete_profile = ttk.Button(pr1, text="Excluir", command=self._delete_selected_config_profile)
        btn_delete_profile.pack(side=tk.LEFT)
        self._enable_hover(btn_delete_profile, "TButton", "Hover.TButton")

        pr2 = ttk.Frame(pf, style="Card.TFrame")
        pr2.pack(fill=tk.X)
        btn_save_profile = ttk.Button(pr2, text="Salvar configuração atual como perfil", style="Accent.TButton", command=self._save_current_config_profile)
        btn_save_profile.pack(side=tk.LEFT)
        self._enable_hover(btn_save_profile, "Accent.TButton", "AccentHover.TButton")
        ttk.Label(pr2, text="Ex: Remax padrão, Imóvel luxo, Sem marca d'água", style="Muted.TLabel").pack(side=tk.LEFT, padx=(12, 0))

        rf = self._card(inner, "Renomeação inteligente", "Crie nomes organizados e consistentes para os arquivos exportados.")
        ttk.Checkbutton(rf, text="Renomear arquivos automaticamente", variable=self.opt_rename).pack(anchor=tk.W, pady=(0, 8))
        rr = ttk.Frame(rf, style="Card.TFrame")
        rr.pack(fill=tk.X)
        ttk.Label(rr, text="Prefixo").pack(side=tk.LEFT)
        ttk.Entry(rr, textvariable=self.opt_rename_prefix, width=14).pack(side=tk.LEFT, padx=(6, 18))
        ttk.Label(rr, text="Código do imóvel").pack(side=tk.LEFT)
        ttk.Entry(rr, textvariable=self.opt_rename_code, width=16).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(rf, text="Exemplo: IMOVEL_001_interior_01.jpg", style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 0))

        wf = self._card(inner, "Marca d'água", "Opcional: aplique um texto ou logo nas imagens finais.")
        ttk.Checkbutton(wf, text="Adicionar marca d'água nas fotos", variable=self.opt_watermark).pack(anchor=tk.W, pady=(0, 8))

        wr1 = ttk.Frame(wf, style="Card.TFrame")
        wr1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(wr1, text="Modo").pack(side=tk.LEFT)
        ttk.Radiobutton(wr1, text="Texto", variable=self.opt_wm_mode, value="text").pack(side=tk.LEFT, padx=(8, 10))
        ttk.Radiobutton(wr1, text="Logo (imagem)", variable=self.opt_wm_mode, value="image").pack(side=tk.LEFT)

        wr2 = ttk.Frame(wf, style="Card.TFrame")
        wr2.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(wr2, text="Texto", width=9).pack(side=tk.LEFT)
        ttk.Entry(wr2, textvariable=self.opt_wm_text).pack(side=tk.LEFT, fill=tk.X, expand=True)

        wr3 = ttk.Frame(wf, style="Card.TFrame")
        wr3.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(wr3, text="Logo", width=9).pack(side=tk.LEFT)
        ttk.Entry(wr3, textvariable=self.opt_wm_image).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        btn = ttk.Button(wr3, text="Procurar", style="Small.TButton", command=self._browse_wm_logo)
        btn.pack(side=tk.RIGHT)
        self._enable_hover(btn, "Small.TButton", "SmallHover.TButton")

        wr4 = ttk.Frame(wf, style="Card.TFrame")
        wr4.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(wr4, text="Posição").pack(side=tk.LEFT)
        ttk.Combobox(wr4, textvariable=self.opt_wm_position, width=16,
                     values=["bottom-right", "bottom-left", "top-right", "top-left", "center"],
                     state="readonly").pack(side=tk.LEFT, padx=(8, 18))
        ttk.Label(wr4, text="Opacidade").pack(side=tk.LEFT)
        ttk.Scale(wr4, from_=0.0, to=1.0, variable=self.opt_wm_opacity,
                  orient=tk.HORIZONTAL, length=180,
                  command=lambda _v: self._on_watermark_preview_change()).pack(side=tk.LEFT, padx=(8, 8))
        ttk.Label(wr4, textvariable=self.opt_wm_opacity_percent, width=5, style="Section.TLabel").pack(side=tk.LEFT)

        preview_box = ttk.Frame(wf, style="Card.TFrame")
        preview_box.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(preview_box, text="Preview da marca d'água", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(preview_box, text="A prévia muda em tempo real quando você altera texto, logo, posição ou opacidade.",
                  style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 6))
        self.wm_preview_label = tk.Label(preview_box, bd=0, highlightthickness=1, highlightbackground=self.BORDER)
        self.wm_preview_label.pack(anchor=tk.W, fill=tk.X)
        self._update_watermark_preview()

        gf = self._card(inner, "Galeria HTML", "Personalize os textos usados na galeria gerada pelo sistema.")
        gr1 = ttk.Frame(gf, style="Card.TFrame")
        gr1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(gr1, text="Título", width=10).pack(side=tk.LEFT)
        ttk.Entry(gr1, textvariable=self.opt_gallery_title).pack(side=tk.LEFT, fill=tk.X, expand=True)
        gr2 = ttk.Frame(gf, style="Card.TFrame")
        gr2.pack(fill=tk.X)
        ttk.Label(gr2, text="Subtítulo", width=10).pack(side=tk.LEFT)
        ttk.Entry(gr2, textvariable=self.opt_gallery_subtitle).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(gf, text="Exemplo: Apartamento 3 quartos — Rua das Flores, 123", style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 0))

        mf = self._card(inner, "Metadados e copyright", "Use esses campos se quiser registrar autoria nas imagens processadas.")
        mr1 = ttk.Frame(mf, style="Card.TFrame")
        mr1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(mr1, text="Fotógrafo", width=10).pack(side=tk.LEFT)
        ttk.Entry(mr1, textvariable=self.opt_photographer).pack(side=tk.LEFT, fill=tk.X, expand=True)
        mr2 = ttk.Frame(mf, style="Card.TFrame")
        mr2.pack(fill=tk.X)
        ttk.Label(mr2, text="Copyright", width=10).pack(side=tk.LEFT)
        ttk.Entry(mr2, textvariable=self.opt_copyright).pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ──────────────────────────────────────────────────────────────
    #  ABA 3: TREINAR ESTILO
    # ──────────────────────────────────────────────────────────────

    def _build_train_tab(self):
        inner = self._create_scrolled_page(self.tab_train)

        ttk.Label(inner, text="Treinar estilo", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 2))
        ttk.Label(inner, text="Ensine o agente usando pares de fotos: original (antes) e editada (depois).",
                  style="Hero.TLabel").pack(anchor=tk.W, pady=(0, 12))

        af = self._card(inner, "Adicionar par de exemplo", "Use um par individual para começar o treinamento do seu estilo.")
        self.before_var = tk.StringVar()
        self.after_var = tk.StringVar()

        r1 = ttk.Frame(af, style="Card.TFrame")
        r1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(r1, text="ANTES", width=9).pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self.before_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        btn = ttk.Button(r1, text="Procurar", command=self._browse_before)
        btn.pack(side=tk.RIGHT)
        self._enable_hover(btn, "TButton", "Hover.TButton")

        r2 = ttk.Frame(af, style="Card.TFrame")
        r2.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(r2, text="DEPOIS", width=9).pack(side=tk.LEFT)
        ttk.Entry(r2, textvariable=self.after_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        btn = ttk.Button(r2, text="Procurar", command=self._browse_after)
        btn.pack(side=tk.RIGHT)
        self._enable_hover(btn, "TButton", "Hover.TButton")

        btn_add = ttk.Button(af, text="Adicionar par", command=self._add_pair)
        btn_add.pack(anchor=tk.W)
        self._enable_hover(btn_add, "TButton", "Hover.TButton")

        bf = self._card(inner, "Carregar pares por pasta", "Use duas pastas com arquivos de mesmo nome para adicionar vários pares de uma vez.")
        self.batch_before_var = tk.StringVar()
        self.batch_after_var = tk.StringVar()

        r3 = ttk.Frame(bf, style="Card.TFrame")
        r3.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(r3, text="Pasta ANTES", width=12).pack(side=tk.LEFT)
        ttk.Entry(r3, textvariable=self.batch_before_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        btn = ttk.Button(r3, text="Procurar", command=lambda: self._browse_folder(self.batch_before_var))
        btn.pack(side=tk.RIGHT)
        self._enable_hover(btn, "TButton", "Hover.TButton")

        r4 = ttk.Frame(bf, style="Card.TFrame")
        r4.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(r4, text="Pasta DEPOIS", width=12).pack(side=tk.LEFT)
        ttk.Entry(r4, textvariable=self.batch_after_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        btn = ttk.Button(r4, text="Procurar", command=lambda: self._browse_folder(self.batch_after_var))
        btn.pack(side=tk.RIGHT)
        self._enable_hover(btn, "TButton", "Hover.TButton")

        btn_load = ttk.Button(bf, text="Carregar pares", command=self._load_batch_pairs)
        btn_load.pack(anchor=tk.W)
        self._enable_hover(btn_load, "TButton", "Hover.TButton")

        lf = self._card(inner, "Pares adicionados", "Confira a lista atual antes de treinar o perfil.")
        self.pairs_frame = tk.Frame(lf, bg=self.DARK_PANEL, bd=0, highlightthickness=1, highlightbackground=self.DARK_PANEL_BORDER)
        self.pairs_frame.pack(fill=tk.BOTH, expand=True)
        self.pairs_listbox = tk.Listbox(self.pairs_frame, font=("Consolas", 9), bg=self.DARK_PANEL, fg=self.DARK_PANEL_TEXT,
                                        height=7, relief="flat", bd=0, highlightthickness=0,
                                        selectbackground=self.SELECT_BG, selectforeground="#FFFFFF")
        sb = ttk.Scrollbar(self.pairs_frame, command=self.pairs_listbox.yview)
        self.pairs_listbox.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.pairs_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        tb = ttk.Frame(inner, style="App.TFrame")
        tb.pack(fill=tk.X, pady=(4, 0))
        self.btn_train = ttk.Button(tb, text="Treinar perfil", style="Accent.TButton", command=self._train_style)
        self.btn_train.pack(side=tk.LEFT)
        self._enable_hover(self.btn_train, "Accent.TButton", "AccentHover.TButton")
        btn_clear = ttk.Button(tb, text="Limpar lista", command=self._clear_pairs)
        btn_clear.pack(side=tk.LEFT, padx=(8, 0))
        self._enable_hover(btn_clear, "TButton", "Hover.TButton")

        self.train_status = ttk.Label(inner, text="", style="Hero.TLabel")
        self.train_status.pack(anchor=tk.W, pady=(8, 0))

    # ══════════════════════════════════════════════════════════════
    #  HANDLERS — PROCESSAR
    # ══════════════════════════════════════════════════════════════

    def _browse_input(self):
        p = filedialog.askdirectory(title="Pasta com as fotos")
        if p:
            self.input_dir.set(p)

    def _browse_output(self):
        p = filedialog.askdirectory(title="Pasta de saída")
        if p:
            self.output_dir.set(p)

    def _browse_style(self):
        p = filedialog.askopenfilename(title="Perfil de estilo", filetypes=[("JSON", "*.json")])
        if p:
            self.style_profile_path.set(p)

    def _browse_wm_logo(self):
        p = filedialog.askopenfilename(title="Logo para marca d'água", filetypes=[("Imagens", "*.png *.jpg *.jpeg")])
        if p:
            self.opt_wm_image.set(p)
            self._update_watermark_preview()

    def _on_watermark_preview_change(self):
        try:
            opacity = float(self.opt_wm_opacity.get())
        except Exception:
            opacity = 0.0
        opacity = max(0.0, min(1.0, opacity))
        self.opt_wm_opacity_percent.set(f"{int(round(opacity * 100))}%")
        self._update_watermark_preview()

    def _update_watermark_preview(self):
        if self.wm_preview_label is None:
            return

        width, height = 560, 170
        bg_hex = self.CARD_ALT if self.theme_mode == "light" else self.ENTRY_BG
        bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (1, 3, 5))
        img = Image.new("RGB", (width, height), bg_rgb)

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        opacity = max(0.0, min(1.0, float(self.opt_wm_opacity.get())))
        alpha = int(opacity * 255)
        position = self.opt_wm_position.get()

        margin = 16
        mode = self.opt_wm_mode.get()

        if mode == "image" and self.opt_wm_image.get().strip() and os.path.exists(self.opt_wm_image.get().strip()):
            try:
                logo = Image.open(self.opt_wm_image.get().strip()).convert("RGBA")
                logo.thumbnail((150, 60), Image.LANCZOS)
                if alpha < 255:
                    r, g, b, a = logo.split()
                    a = a.point(lambda px: int(px * opacity))
                    logo.putalpha(a)
                wm_w, wm_h = logo.size
                x, y = self._watermark_position(position, width, height, wm_w, wm_h, margin)
                overlay.alpha_composite(logo, (x, y))
            except Exception:
                text = "Logo inválida"
                font = ImageFont.load_default()
                bbox = odraw.textbbox((0, 0), text, font=font)
                wm_w, wm_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                x, y = self._watermark_position(position, width, height, wm_w, wm_h, margin)
                odraw.text((x, y), text, fill=((235, 241, 245, alpha) if self.theme_mode == "dark" else (60, 66, 77, alpha)), font=font)
        else:
            text = self.opt_wm_text.get().strip() or "© Minha Empresa"
            try:
                font = ImageFont.truetype("arial.ttf", 22)
            except Exception:
                font = ImageFont.load_default()
            bbox = odraw.textbbox((0, 0), text, font=font)
            wm_w, wm_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x, y = self._watermark_position(position, width, height, wm_w, wm_h, margin)

            text_fill = (255, 255, 255, alpha) if self.theme_mode == "dark" else (35, 41, 52, alpha)
            odraw.text((x, y), text, fill=text_fill, font=font)

        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        self._wm_preview_photo = ImageTk.PhotoImage(img)
        self.wm_preview_label.configure(image=self._wm_preview_photo, bg=self.CARD, highlightbackground=self.BORDER)

    def _watermark_position(self, position: str, img_w: int, img_h: int, wm_w: int, wm_h: int, margin: int) -> tuple[int, int]:
        if position == "top-left":
            return margin, margin
        if position == "top-right":
            return img_w - wm_w - margin, margin
        if position == "bottom-left":
            return margin, img_h - wm_h - margin
        if position == "center":
            return (img_w - wm_w) // 2, (img_h - wm_h) // 2
        return img_w - wm_w - margin, img_h - wm_h - margin

    # ══════════════════════════════════════════════════════════════
    #  PERFIS DE CONFIGURAÇÃO
    # ══════════════════════════════════════════════════════════════

    def _project_root(self) -> str:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def _config_profiles_dir(self) -> str:
        path = os.path.join(self._project_root(), "config_profiles")
        os.makedirs(path, exist_ok=True)
        return path

    def _safe_profile_filename(self, name: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name.strip())
        safe = safe.strip().replace(" ", "_")
        return safe or "perfil"

    def _load_config_profile_names(self) -> list[str]:
        folder = self._config_profiles_dir()
        names = []
        for file in sorted(os.listdir(folder)):
            if file.lower().endswith(".json"):
                path = os.path.join(folder, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    names.append(data.get("name") or os.path.splitext(file)[0])
                except Exception:
                    names.append(os.path.splitext(file)[0])
        return names

    def _refresh_config_profile_combo(self):
        if self.config_profile_combo is not None:
            self.config_profile_combo.configure(values=self._load_config_profile_names())

    def _get_config_profile_path(self, name: str) -> str:
        return os.path.join(self._config_profiles_dir(), self._safe_profile_filename(name) + ".json")

    def _collect_config_profile_data(self, name: str) -> dict:
        return {
            "name": name,
            "version": 1,
            "settings": {
                "intensity": self.opt_intensity.get(),
                "color_mode": self.opt_color_mode.get(),
                "preview_mode": self.opt_preview_mode.get(),
                "upscale_enabled": self.opt_upscale_enabled.get(),
                "upscale_factor": self.opt_upscale_factor.get(),
                "upscale_preset": self.opt_upscale_preset.get(),
                "style_profile_path": self.style_profile_path.get(),
                "duplicates_enabled": self.opt_duplicates.get(),
                "rename_enabled": self.opt_rename.get(),
                "rename_prefix": self.opt_rename_prefix.get(),
                "rename_code": self.opt_rename_code.get(),
                "watermark_enabled": self.opt_watermark.get(),
                "wm_mode": self.opt_wm_mode.get(),
                "wm_text": self.opt_wm_text.get(),
                "wm_image": self.opt_wm_image.get(),
                "wm_position": self.opt_wm_position.get(),
                "wm_opacity": self.opt_wm_opacity.get(),
                "contact_sheet": self.opt_contact_sheet.get(),
                "before_after": self.opt_before_after.get(),
                "gallery": self.opt_gallery.get(),
                "gallery_title": self.opt_gallery_title.get(),
                "gallery_subtitle": self.opt_gallery_subtitle.get(),
                "exif_preserve": self.opt_exif.get(),
                "photographer": self.opt_photographer.get(),
                "copyright": self.opt_copyright.get(),
            },
        }

    def _apply_config_profile_data(self, data: dict):
        settings = data.get("settings", {})
        self.opt_intensity.set(settings.get("intensity", self.opt_intensity.get()))
        self.opt_color_mode.set(settings.get("color_mode", self.opt_color_mode.get()))
        self.opt_preview_mode.set(bool(settings.get("preview_mode", self.opt_preview_mode.get())))
        self.opt_upscale_enabled.set(bool(settings.get("upscale_enabled", self.opt_upscale_enabled.get())))
        self.opt_upscale_factor.set(settings.get("upscale_factor", self.opt_upscale_factor.get()))
        self.opt_upscale_preset.set(settings.get("upscale_preset", self.opt_upscale_preset.get()))
        self.style_profile_path.set(settings.get("style_profile_path", self.style_profile_path.get()))
        self.opt_duplicates.set(bool(settings.get("duplicates_enabled", self.opt_duplicates.get())))
        self.opt_rename.set(bool(settings.get("rename_enabled", self.opt_rename.get())))
        self.opt_rename_prefix.set(settings.get("rename_prefix", self.opt_rename_prefix.get()))
        self.opt_rename_code.set(settings.get("rename_code", self.opt_rename_code.get()))
        self.opt_watermark.set(bool(settings.get("watermark_enabled", self.opt_watermark.get())))
        self.opt_wm_mode.set(settings.get("wm_mode", self.opt_wm_mode.get()))
        self.opt_wm_text.set(settings.get("wm_text", self.opt_wm_text.get()))
        self.opt_wm_image.set(settings.get("wm_image", self.opt_wm_image.get()))
        self.opt_wm_position.set(settings.get("wm_position", self.opt_wm_position.get()))
        try:
            self.opt_wm_opacity.set(float(settings.get("wm_opacity", self.opt_wm_opacity.get())))
        except Exception:
            pass
        self.opt_contact_sheet.set(bool(settings.get("contact_sheet", self.opt_contact_sheet.get())))
        self.opt_before_after.set(bool(settings.get("before_after", self.opt_before_after.get())))
        self.opt_gallery.set(bool(settings.get("gallery", self.opt_gallery.get())))
        self.opt_gallery_title.set(settings.get("gallery_title", self.opt_gallery_title.get()))
        self.opt_gallery_subtitle.set(settings.get("gallery_subtitle", self.opt_gallery_subtitle.get()))
        self.opt_exif.set(bool(settings.get("exif_preserve", self.opt_exif.get())))
        self.opt_photographer.set(settings.get("photographer", self.opt_photographer.get()))
        self.opt_copyright.set(settings.get("copyright", self.opt_copyright.get()))
        self._on_watermark_preview_change()

    def _save_current_config_profile(self):
        name = simpledialog.askstring("Salvar perfil", "Nome do perfil de configuração:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        path = self._get_config_profile_path(name)
        if os.path.exists(path):
            ok = messagebox.askyesno("Substituir perfil", f"O perfil '{name}' já existe. Deseja substituir?")
            if not ok:
                return
        data = self._collect_config_profile_data(name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.config_profile_name.set(name)
            self._refresh_config_profile_combo()
            messagebox.showinfo("Perfil salvo", f"Perfil '{name}' salvo com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível salvar o perfil:\n{e}")

    def _load_selected_config_profile(self):
        name = self.config_profile_name.get().strip()
        if not name:
            messagebox.showinfo("Perfil", "Selecione um perfil para carregar.")
            return
        path = self._get_config_profile_path(name)
        if not os.path.exists(path):
            messagebox.showerror("Erro", "Arquivo do perfil não encontrado.")
            self._refresh_config_profile_combo()
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_config_profile_data(data)
            messagebox.showinfo("Perfil carregado", f"Perfil '{name}' carregado.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível carregar o perfil:\n{e}")

    def _delete_selected_config_profile(self):
        name = self.config_profile_name.get().strip()
        if not name:
            messagebox.showinfo("Perfil", "Selecione um perfil para excluir.")
            return
        path = self._get_config_profile_path(name)
        if not os.path.exists(path):
            messagebox.showerror("Erro", "Arquivo do perfil não encontrado.")
            self._refresh_config_profile_combo()
            return
        ok = messagebox.askyesno("Excluir perfil", f"Deseja excluir o perfil '{name}'?")
        if not ok:
            return
        try:
            os.remove(path)
            self.config_profile_name.set("")
            self._refresh_config_profile_combo()
            messagebox.showinfo("Perfil excluído", "Perfil excluído com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível excluir o perfil:\n{e}")

    def _parse_upscale_factor(self, value) -> float:
        try:
            return float(str(value).lower().replace("x", "").strip())
        except Exception:
            return 2.0

    def _collect_options(self) -> dict:
        wm_config = None
        if self.opt_watermark.get():
            wm_config = {
                "mode": self.opt_wm_mode.get(),
                "text": self.opt_wm_text.get(),
                "image_path": self.opt_wm_image.get(),
                "position": self.opt_wm_position.get(),
                "opacity": self.opt_wm_opacity.get(),
                "font_size": 28,
                "color": (255, 255, 255),
            }

        return {
            "intensity": self.opt_intensity.get(),
            "color_mode": self.opt_color_mode.get(),
            "preview_mode": self.opt_preview_mode.get(),
            "upscale_enabled": self.opt_upscale_enabled.get(),
            "upscale_factor": self._parse_upscale_factor(self.opt_upscale_factor.get()),
            "upscale_preset": self.opt_upscale_preset.get(),
            "duplicates_enabled": self.opt_duplicates.get(),
            "duplicates_threshold": 10,
            "rename_enabled": self.opt_rename.get(),
            "rename_prefix": self.opt_rename_prefix.get(),
            "rename_code": self.opt_rename_code.get(),
            "watermark_enabled": self.opt_watermark.get(),
            "watermark_config": wm_config,
            "contact_sheet": self.opt_contact_sheet.get(),
            "before_after": self.opt_before_after.get(),
            "gallery": self.opt_gallery.get(),
            "gallery_title": self.opt_gallery_title.get(),
            "gallery_subtitle": self.opt_gallery_subtitle.get(),
            "exif_preserve": self.opt_exif.get(),
            "photographer": self.opt_photographer.get(),
            "copyright": self.opt_copyright.get(),
        }

    def _start_processing(self):
        inp = self.input_dir.get().strip()
        out = self.output_dir.get().strip()
        if not inp or not os.path.isdir(inp):
            messagebox.showerror("Erro", "Selecione uma pasta de entrada válida.")
            return
        if not out:
            messagebox.showerror("Erro", "Selecione uma pasta de saída.")
            return

        os.makedirs(out, exist_ok=True)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.progress_var.set(0.0)
        self.btn_process.configure(state=tk.DISABLED)
        self.btn_cancel.configure(state=tk.NORMAL)

        style_path = self.style_profile_path.get().strip() or None
        options = self._collect_options()

        self.pipeline = ProcessingPipeline(inp, out, self._on_progress, style_profile_path=style_path, options=options)
        self.pipeline.start()

    def _cancel_processing(self):
        if self.pipeline:
            self.pipeline.cancel()

    def _on_progress(self, message: str, pct: float):
        self.after(0, self._update_ui, message, pct)

    def _update_ui(self, message: str, pct: float):
        self.progress_var.set(pct)
        self.status_label.configure(text=message)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
        if pct >= 1.0:
            self.btn_process.configure(state=tk.NORMAL)
            self.btn_cancel.configure(state=tk.DISABLED)

    def _open_output_folder(self):
        p = self.output_dir.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)
        else:
            messagebox.showinfo("Info", "Defina uma pasta de saída primeiro.")

    # ══════════════════════════════════════════════════════════════
    #  HANDLERS — TREINAR
    # ══════════════════════════════════════════════════════════════

    def _browse_before(self):
        p = filedialog.askopenfilename(title="Foto ANTES", filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp")])
        if p:
            self.before_var.set(p)

    def _browse_after(self):
        p = filedialog.askopenfilename(title="Foto DEPOIS", filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp")])
        if p:
            self.after_var.set(p)

    def _browse_folder(self, var: tk.StringVar):
        p = filedialog.askdirectory(title="Selecione a pasta")
        if p:
            var.set(p)

    def _add_pair(self):
        b = self.before_var.get().strip()
        a = self.after_var.get().strip()
        if not b or not os.path.exists(b):
            messagebox.showerror("Erro", "Selecione uma foto ANTES válida.")
            return
        if not a or not os.path.exists(a):
            messagebox.showerror("Erro", "Selecione uma foto DEPOIS válida.")
            return
        self.train_pairs.append({"before": b, "after": a})
        self.pairs_listbox.insert(tk.END, f"{os.path.basename(b)}  →  {os.path.basename(a)}")
        self.before_var.set("")
        self.after_var.set("")
        self.train_status.configure(text=f"{len(self.train_pairs)} par(es) carregados.")

    def _load_batch_pairs(self):
        bd = self.batch_before_var.get().strip()
        ad = self.batch_after_var.get().strip()
        if not bd or not os.path.isdir(bd):
            messagebox.showerror("Erro", "Pasta ANTES inválida.")
            return
        if not ad or not os.path.isdir(ad):
            messagebox.showerror("Erro", "Pasta DEPOIS inválida.")
            return
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
        bf = {f for f in os.listdir(bd) if os.path.splitext(f)[1].lower() in exts}
        af = {f for f in os.listdir(ad) if os.path.splitext(f)[1].lower() in exts}
        matched = sorted(bf & af)
        if not matched:
            messagebox.showwarning("Nenhum par", "Nenhum arquivo com mesmo nome nas duas pastas.")
            return
        for f in matched:
            self.train_pairs.append({"before": os.path.join(bd, f), "after": os.path.join(ad, f)})
            self.pairs_listbox.insert(tk.END, f"{f}  (antes → depois)")
        self.train_status.configure(text=f"+{len(matched)} par(es) adicionados. Total: {len(self.train_pairs)}")

    def _clear_pairs(self):
        self.train_pairs.clear()
        self.pairs_listbox.delete(0, tk.END)
        self.train_status.configure(text="Lista limpa.")

    def _train_style(self):
        if not self.train_pairs:
            messagebox.showerror("Erro", "Adicione pelo menos um par de fotos.")
            return
        self.train_status.configure(text="Treinando perfil...")
        self.btn_train.configure(state=tk.DISABLED)
        self.update_idletasks()

        def do_train():
            try:
                trainer = StyleTrainer()
                for pair in self.train_pairs:
                    trainer.add_pair(pair["before"], pair["after"])
                trainer.learn()
                self.after(0, lambda: self._save_trained_profile(trainer))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", str(e)))
                self.after(0, lambda: self.btn_train.configure(state=tk.NORMAL))

        threading.Thread(target=do_train, daemon=True).start()

    def _save_trained_profile(self, trainer: StyleTrainer):
        p = filedialog.asksaveasfilename(
            title="Salvar perfil de estilo",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="meu_estilo.json",
        )
        if p:
            trainer.save_profile(p)
            self.style_profile_path.set(p)
            self.train_status.configure(text=f"✅ Perfil salvo com sucesso. {len(self.train_pairs)} par(es) usados.")
        else:
            self.train_status.configure(text="Treinamento concluído (perfil não salvo).")
        self.btn_train.configure(state=tk.NORMAL)
