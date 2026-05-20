"""
Interface gráfica — CustomTkinter v19.
Visual premium, clean e moderno. Mesma lógica/handlers da versão anterior.
"""

import os
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageDraw, ImageFont, ImageTk

import customtkinter as ctk

from core.pipeline import ProcessingPipeline
from core.style_trainer import StyleTrainer

# ── Cores ────────────────────────────────────────────────────────
ACCENT = "#1B9E75"
ACCENT_HOVER = "#168A66"
ACCENT_DARK = "#14755A"
DANGER = "#DC3545"
MUTED_LIGHT = "#6B7280"
MUTED_DARK = "#9CA3B4"
CARD_LIGHT = "#FFFFFF"
CARD_DARK = "#1A1F2E"
BG_LIGHT = "#F0F2F5"
BG_DARK = "#111621"
BORDER_LIGHT = "#E0E4EA"
BORDER_DARK = "#2A3142"
LOG_BG = "#0D1117"
LOG_FG = "#C9D1D9"


class PhotoAgentApp(ctk.CTk):
    """Janela principal."""

    def __init__(self):
        super().__init__()

        ctk.set_default_color_theme("green")
        self.title("Agente de Fotos Imobiliárias")
        self.geometry("1020x780")
        self.minsize(900, 650)

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
        self.pipeline = None

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
        self.train_pairs = []
        self.before_var = tk.StringVar()
        self.after_var = tk.StringVar()
        self.batch_before_var = tk.StringVar()
        self.batch_after_var = tk.StringVar()

        # ── Refs de widgets ──
        self.log_textbox = None
        self.status_label = None
        self.progress_bar = None
        self.progress_var = tk.DoubleVar(value=0.0)
        self.btn_process = None
        self.btn_cancel = None
        self.pairs_textbox = None
        self.train_status = None
        self.btn_train = None
        self.summary_label = None

        # Traces
        self.opt_wm_opacity.trace_add("write", lambda *_: self._on_watermark_preview_change())
        self.opt_wm_text.trace_add("write", lambda *_: self._on_watermark_preview_change())
        self.opt_wm_image.trace_add("write", lambda *_: self._on_watermark_preview_change())
        self.opt_wm_mode.trace_add("write", lambda *_: self._on_watermark_preview_change())
        self.opt_wm_position.trace_add("write", lambda *_: self._on_watermark_preview_change())

        # Summary traces
        for var in [self.opt_intensity, self.opt_color_mode, self.opt_upscale_enabled,
                    self.opt_upscale_factor, self.opt_upscale_preset, self.opt_preview_mode]:
            var.trace_add("write", lambda *_: self._update_summary())

        self._build_ui()

    # ══════════════════════════════════════════════════════════════
    #  HELPERS VISUAIS
    # ══════════════════════════════════════════════════════════════

    def _card(self, parent, title=None, subtitle=None, **kw):
        """Cria um card com visual clean."""
        frame = ctk.CTkFrame(parent, corner_radius=12, border_width=1,
                             border_color=(BORDER_LIGHT, BORDER_DARK),
                             fg_color=(CARD_LIGHT, CARD_DARK))
        frame.pack(fill="x", pady=(0, 12), padx=2, **kw)
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=22, pady=18)
        if title:
            ctk.CTkLabel(inner, text=title, font=("Segoe UI", 14, "bold"),
                         anchor="w").pack(fill="x")
        if subtitle:
            ctk.CTkLabel(inner, text=subtitle, font=("Segoe UI", 12),
                         text_color=(MUTED_LIGHT, MUTED_DARK),
                         anchor="w").pack(fill="x", pady=(2, 0))
        if title or subtitle:
            spacer = ctk.CTkFrame(inner, fg_color="transparent", height=10)
            spacer.pack(fill="x")
        return inner

    def _section_label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=("Segoe UI", 12, "bold"),
                     anchor="w").pack(fill="x", pady=(0, 4))

    def _muted_label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=("Segoe UI", 11),
                     text_color=(MUTED_LIGHT, MUTED_DARK),
                     anchor="w").pack(fill="x")

    def _file_row(self, parent, var, label, command, clear=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(row, text=label, font=("Segoe UI", 11, "bold"),
                     width=90, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(row, textvariable=var, height=36, corner_radius=8)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if clear:
            ctk.CTkButton(row, text="✕", width=36, height=36, corner_radius=8,
                          fg_color="transparent", hover_color=("#E5E7EB", "#2A3142"),
                          text_color=(MUTED_LIGHT, MUTED_DARK),
                          command=lambda: var.set("")).pack(side="right", padx=(0, 4))
        ctk.CTkButton(row, text="Procurar", width=90, height=36, corner_radius=8,
                      fg_color=(ACCENT, ACCENT), hover_color=ACCENT_HOVER,
                      command=command).pack(side="right")

    def _preset_selector(self, parent, var, options, descriptions=None):
        """Cria botões de preset visual (segmented button style)."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))
        buttons = {}

        def select(value):
            var.set(value)
            for v, btn in buttons.items():
                if v == value:
                    btn.configure(fg_color=ACCENT, text_color="#FFFFFF",
                                  border_color=ACCENT, font=("Segoe UI", 11, "bold"))
                else:
                    btn.configure(fg_color="transparent",
                                  text_color=("#4B5563", "#E5E7EB"),
                                  border_color=(BORDER_LIGHT, BORDER_DARK),
                                  font=("Segoe UI", 11))

        for i, opt in enumerate(options):
            label = opt.replace("_", " ").title()
            if descriptions and i < len(descriptions):
                label = descriptions[i]
            btn = ctk.CTkButton(
                row, text=label, height=38, corner_radius=8,
                border_width=1.5, border_color=(BORDER_LIGHT, BORDER_DARK),
                fg_color="transparent", text_color=("#4B5563", "#E5E7EB"),
                hover_color=("#E5E7EB", "#2A3142"),
                font=("Segoe UI", 11),
                command=lambda v=opt: select(v),
            )
            btn.pack(side="left", padx=(0, 6), fill="x", expand=True)
            buttons[opt] = btn

        select(var.get())
        return buttons

    # ══════════════════════════════════════════════════════════════
    #  BUILD UI
    # ══════════════════════════════════════════════════════════════

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=60)
        header.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(header, text="Agente de Fotos Imobiliárias",
                     font=("Segoe UI", 22, "bold"), anchor="w").pack(side="left")

        theme_frame = ctk.CTkFrame(header, fg_color="transparent")
        theme_frame.pack(side="right")
        ctk.CTkLabel(theme_frame, text="Claro / Escuro", font=("Segoe UI", 11),
                     text_color=(MUTED_LIGHT, MUTED_DARK)).pack(side="left", padx=(0, 8))
        self._theme_switch = ctk.CTkSwitch(
            theme_frame, text="", width=44,
            command=self._toggle_theme,
            onvalue=1, offvalue=0,
            progress_color=ACCENT,
        )
        self._theme_switch.pack(side="left")

        # Tabs
        self.tabview = ctk.CTkTabview(self, corner_radius=12,
                                       segmented_button_fg_color=(BG_LIGHT, "#1A2033"),
                                       segmented_button_selected_color=ACCENT,
                                       segmented_button_selected_hover_color=ACCENT_HOVER,
                                       segmented_button_unselected_color=("transparent", "transparent"),
                                       segmented_button_unselected_hover_color=("#E2E5EA", "#232D3F"))
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        self.tab_process = self.tabview.add("Processar")
        self.tab_settings = self.tabview.add("Configurações")
        self.tab_train = self.tabview.add("Treinar Estilo")

        self._build_process_tab()
        self._build_settings_tab()
        self._build_train_tab()

    def _toggle_theme(self):
        mode = "dark" if ctk.get_appearance_mode() == "Light" else "light"
        ctk.set_appearance_mode(mode)

    # ──────────────────────────────────────────────────────────────
    #  ABA 1: PROCESSAR
    # ──────────────────────────────────────────────────────────────

    def _build_process_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_process, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # -- Pastas --
        card = self._card(scroll, "Pastas", "Origem e destino das fotos.")
        self._file_row(card, self.input_dir, "Entrada", self._browse_input)
        self._file_row(card, self.output_dir, "Saída", self._browse_output)
        self._file_row(card, self.style_profile_path, "Estilo", self._browse_style, clear=True)

        # -- Edição --
        card = self._card(scroll, "Edição")

        self._section_label(card, "Intensidade")
        self._muted_label(card, "Quanto o agente altera a foto em relação à original.")
        self._intensity_btns = self._preset_selector(
            card, self.opt_intensity,
            ["suave", "normal", "forte"],
            ["Suave", "Normal", "Forte"],
        )

        sep = ctk.CTkFrame(card, fg_color="transparent", height=12)
        sep.pack(fill="x")

        self._section_label(card, "Modo de Cor")
        self._muted_label(card, "Estilo cromático aplicado às fotos.")
        self._color_btns = self._preset_selector(
            card, self.opt_color_mode,
            ["natural", "vibrant", "luxury"],
            ["Natural", "Vibrant", "Luxury"],
        )

        sep = ctk.CTkFrame(card, fg_color="transparent", height=12)
        sep.pack(fill="x")

        row_preview = ctk.CTkFrame(card, fg_color="transparent")
        row_preview.pack(fill="x")
        ctk.CTkSwitch(row_preview, text="Modo Preview (só 1 foto)",
                      variable=self.opt_preview_mode,
                      progress_color=ACCENT, font=("Segoe UI", 12)).pack(side="left")

        # -- Upscale --
        card = self._card(scroll, "Upscale", "Aumenta a resolução das fotos melhoradas.")

        row_up = ctk.CTkFrame(card, fg_color="transparent")
        row_up.pack(fill="x", pady=(0, 8))
        ctk.CTkSwitch(row_up, text="Ativar Upscale", variable=self.opt_upscale_enabled,
                      progress_color=ACCENT, font=("Segoe UI", 12)).pack(side="left")

        row_up2 = ctk.CTkFrame(card, fg_color="transparent")
        row_up2.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(row_up2, text="Fator:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 6))
        ctk.CTkSegmentedButton(
            row_up2, values=["1.5x", "2x", "3x", "4x"],
            variable=self.opt_upscale_factor,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
            font=("Segoe UI", 11),
        ).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(row_up2, text="Preset:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 6))
        ctk.CTkSegmentedButton(
            row_up2, values=["natural_pro", "strong_pro", "luxury"],
            variable=self.opt_upscale_preset,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
            font=("Segoe UI", 11),
        ).pack(side="left")

        # -- Extras --
        card = self._card(scroll, "Extras", "Materiais complementares gerados no processamento.")

        row_e1 = ctk.CTkFrame(card, fg_color="transparent")
        row_e1.pack(fill="x", pady=(0, 6))
        ctk.CTkSwitch(row_e1, text="Antes/Depois", variable=self.opt_before_after,
                      progress_color=ACCENT).pack(side="left", padx=(0, 20))
        ctk.CTkSwitch(row_e1, text="Folha de Contato", variable=self.opt_contact_sheet,
                      progress_color=ACCENT).pack(side="left", padx=(0, 20))
        ctk.CTkSwitch(row_e1, text="Galeria HTML", variable=self.opt_gallery,
                      progress_color=ACCENT).pack(side="left")

        row_e2 = ctk.CTkFrame(card, fg_color="transparent")
        row_e2.pack(fill="x")
        ctk.CTkSwitch(row_e2, text="Detectar Duplicatas", variable=self.opt_duplicates,
                      progress_color=ACCENT).pack(side="left", padx=(0, 20))
        ctk.CTkSwitch(row_e2, text="Preservar EXIF", variable=self.opt_exif,
                      progress_color=ACCENT).pack(side="left")

        # -- Summary --
        card = self._card(scroll, "Configuracao Atual")
        summary_bg = ctk.CTkFrame(card, corner_radius=8,
                                   fg_color=("#F3F5F8", "#141B2A"))
        summary_bg.pack(fill="x")
        self.summary_label = ctk.CTkLabel(
            summary_bg, text="", font=("Segoe UI", 12),
            text_color=("#374151", "#E5E7EB"), anchor="w", justify="left",
        )
        self.summary_label.pack(fill="x", padx=16, pady=12)
        self._update_summary()

        # -- Actions --
        card = self._card(scroll)
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x")

        self.btn_process = ctk.CTkButton(
            actions, text="Processar Fotos", height=46, width=200, corner_radius=10,
            font=("Segoe UI", 14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._start_processing,
        )
        self.btn_process.pack(side="left")

        self.btn_cancel = ctk.CTkButton(
            actions, text="Cancelar", height=46, corner_radius=10,
            fg_color="transparent", hover_color=("#E5E7EB", "#2A3142"),
            border_width=1.5, border_color=(BORDER_LIGHT, BORDER_DARK),
            text_color=("#4B5563", "#E5E7EB"),
            font=("Segoe UI", 12),
            command=self._cancel_processing, state="disabled",
        )
        self.btn_cancel.pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            actions, text="Abrir Saida", height=46, corner_radius=10,
            fg_color="transparent", hover_color=("#E5E7EB", "#2A3142"),
            border_width=1.5, border_color=(BORDER_LIGHT, BORDER_DARK),
            text_color=("#4B5563", "#E5E7EB"),
            font=("Segoe UI", 12),
            command=self._open_output_folder,
        ).pack(side="right")

        # -- Progress --
        card = self._card(scroll, "Status")
        self.progress_bar = ctk.CTkProgressBar(card, height=10, corner_radius=5,
                                                progress_color=ACCENT)
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(card, text="Pronto para processar.",
                                          font=("Segoe UI", 12, "bold"),
                                          text_color=("#374151", "#E5E7EB"),
                                          anchor="w")
        self.status_label.pack(fill="x")

        # -- Log --
        card = self._card(scroll, "Log")
        self.log_textbox = ctk.CTkTextbox(
            card, height=180, corner_radius=8,
            font=("Consolas", 11),
            fg_color=(LOG_BG, LOG_BG),
            text_color=(LOG_FG, LOG_FG),
            state="disabled",
        )
        self.log_textbox.pack(fill="both", expand=True)

    # ──────────────────────────────────────────────────────────────
    #  ABA 2: CONFIGURAÇÕES
    # ──────────────────────────────────────────────────────────────

    def _build_settings_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # -- Perfis --
        card = self._card(scroll, "Perfis de Configuração",
                          "Salve presets para clientes ou tipos de imóvel.")
        row_p = ctk.CTkFrame(card, fg_color="transparent")
        row_p.pack(fill="x", pady=(0, 8))
        self.config_profile_combo = ctk.CTkComboBox(
            row_p, variable=self.config_profile_name,
            values=self._load_config_profile_names(),
            width=260, height=36, corner_radius=8, state="readonly",
        )
        self.config_profile_combo.pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_p, text="Carregar", width=90, height=36, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._load_selected_config_profile).pack(side="left", padx=(0, 4))
        ctk.CTkButton(row_p, text="Excluir", width=80, height=36, corner_radius=8,
                      fg_color="transparent", hover_color=("#FEE2E2", "#3B1C1C"),
                      border_width=1, border_color=(DANGER, DANGER),
                      text_color=(DANGER, "#F87171"),
                      command=self._delete_selected_config_profile).pack(side="left")

        ctk.CTkButton(card, text="💾  Salvar configuração atual", height=40, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      font=("Segoe UI", 12, "bold"),
                      command=self._save_current_config_profile).pack(anchor="w")

        # -- Renomeação --
        card = self._card(scroll, "Renomeação Inteligente",
                          "Nomes organizados e consistentes nos arquivos.")
        ctk.CTkSwitch(card, text="Renomear arquivos automaticamente",
                      variable=self.opt_rename, progress_color=ACCENT,
                      font=("Segoe UI", 12)).pack(anchor="w", pady=(0, 8))
        row_r = ctk.CTkFrame(card, fg_color="transparent")
        row_r.pack(fill="x")
        ctk.CTkLabel(row_r, text="Prefixo:", font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkEntry(row_r, textvariable=self.opt_rename_prefix, width=120,
                     height=34, corner_radius=8).pack(side="left", padx=(6, 16))
        ctk.CTkLabel(row_r, text="Código:", font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkEntry(row_r, textvariable=self.opt_rename_code, width=140,
                     height=34, corner_radius=8).pack(side="left", padx=(6, 0))
        self._muted_label(card, "Exemplo: IMOVEL_001_interior_01.jpg")

        # -- Marca d'água --
        card = self._card(scroll, "Marca d'Água",
                          "Texto ou logo aplicado nas fotos finais.")
        ctk.CTkSwitch(card, text="Adicionar marca d'água",
                      variable=self.opt_watermark, progress_color=ACCENT,
                      font=("Segoe UI", 12)).pack(anchor="w", pady=(0, 8))

        row_wm = ctk.CTkFrame(card, fg_color="transparent")
        row_wm.pack(fill="x", pady=(0, 6))
        ctk.CTkRadioButton(row_wm, text="Texto", variable=self.opt_wm_mode,
                           value="text", radiobutton_width=18, radiobutton_height=18,
                           fg_color=ACCENT).pack(side="left", padx=(0, 14))
        ctk.CTkRadioButton(row_wm, text="Logo (imagem)", variable=self.opt_wm_mode,
                           value="image", radiobutton_width=18, radiobutton_height=18,
                           fg_color=ACCENT).pack(side="left")

        row_wt = ctk.CTkFrame(card, fg_color="transparent")
        row_wt.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(row_wt, text="Texto:", width=60, font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkEntry(row_wt, textvariable=self.opt_wm_text, height=34,
                     corner_radius=8).pack(side="left", fill="x", expand=True)

        row_wl = ctk.CTkFrame(card, fg_color="transparent")
        row_wl.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(row_wl, text="Logo:", width=60, font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkEntry(row_wl, textvariable=self.opt_wm_image, height=34,
                     corner_radius=8).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row_wl, text="Procurar", width=80, height=34, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._browse_wm_logo).pack(side="right")

        row_wp = ctk.CTkFrame(card, fg_color="transparent")
        row_wp.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(row_wp, text="Posição:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 6))
        ctk.CTkComboBox(row_wp, variable=self.opt_wm_position, width=160, height=34,
                        corner_radius=8, state="readonly",
                        values=["bottom-right", "bottom-left", "top-right", "top-left", "center"]
                        ).pack(side="left", padx=(0, 16))
        ctk.CTkLabel(row_wp, text="Opacidade:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 6))
        ctk.CTkSlider(row_wp, from_=0, to=1, variable=self.opt_wm_opacity,
                      width=160, height=18, progress_color=ACCENT, button_color=ACCENT,
                      button_hover_color=ACCENT_HOVER).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(row_wp, textvariable=self.opt_wm_opacity_percent,
                     font=("Segoe UI", 11, "bold"), width=40).pack(side="left")

        # Preview
        self._section_label(card, "Preview")
        self.wm_preview_label = tk.Label(card, bd=0, highlightthickness=1,
                                          highlightbackground=BORDER_LIGHT)
        self.wm_preview_label.pack(fill="x", pady=(4, 0))
        self._update_watermark_preview()

        # -- Galeria --
        card = self._card(scroll, "Galeria HTML")
        row_g1 = ctk.CTkFrame(card, fg_color="transparent")
        row_g1.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(row_g1, text="Título:", width=70, font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkEntry(row_g1, textvariable=self.opt_gallery_title, height=34,
                     corner_radius=8).pack(side="left", fill="x", expand=True)
        row_g2 = ctk.CTkFrame(card, fg_color="transparent")
        row_g2.pack(fill="x")
        ctk.CTkLabel(row_g2, text="Subtítulo:", width=70, font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkEntry(row_g2, textvariable=self.opt_gallery_subtitle, height=34,
                     corner_radius=8).pack(side="left", fill="x", expand=True)

        # -- Metadados --
        card = self._card(scroll, "Metadados e Copyright")
        row_m1 = ctk.CTkFrame(card, fg_color="transparent")
        row_m1.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(row_m1, text="Fotógrafo:", width=80, font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkEntry(row_m1, textvariable=self.opt_photographer, height=34,
                     corner_radius=8).pack(side="left", fill="x", expand=True)
        row_m2 = ctk.CTkFrame(card, fg_color="transparent")
        row_m2.pack(fill="x")
        ctk.CTkLabel(row_m2, text="Copyright:", width=80, font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkEntry(row_m2, textvariable=self.opt_copyright, height=34,
                     corner_radius=8).pack(side="left", fill="x", expand=True)

    # ──────────────────────────────────────────────────────────────
    #  ABA 3: TREINAR ESTILO
    # ──────────────────────────────────────────────────────────────

    def _build_train_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_train, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # -- Par individual --
        card = self._card(scroll, "Adicionar Par de Exemplo",
                          "Selecione uma foto original e sua versão editada.")
        self._file_row(card, self.before_var, "Antes", self._browse_before)
        self._file_row(card, self.after_var, "Depois", self._browse_after)
        ctk.CTkButton(card, text="➕  Adicionar Par", height=36, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._add_pair).pack(anchor="w")

        # -- Batch --
        card = self._card(scroll, "Carregar Pares por Pasta",
                          "Duas pastas com fotos de mesmo nome.")
        self._file_row(card, self.batch_before_var, "Antes",
                       lambda: self._browse_folder(self.batch_before_var))
        self._file_row(card, self.batch_after_var, "Depois",
                       lambda: self._browse_folder(self.batch_after_var))
        ctk.CTkButton(card, text="📂  Carregar Pares", height=36, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._load_batch_pairs).pack(anchor="w")

        # -- Lista --
        card = self._card(scroll, "Pares Adicionados")
        self.pairs_textbox = ctk.CTkTextbox(
            card, height=160, corner_radius=8,
            font=("Consolas", 11),
            fg_color=(LOG_BG, LOG_BG),
            text_color=(LOG_FG, LOG_FG),
            state="disabled",
        )
        self.pairs_textbox.pack(fill="both", expand=True)

        # -- Actions --
        card = self._card(scroll)
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x")
        self.btn_train = ctk.CTkButton(
            actions, text="🎓  Treinar Perfil", height=44, corner_radius=10,
            font=("Segoe UI", 14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._train_style,
        )
        self.btn_train.pack(side="left")
        ctk.CTkButton(
            actions, text="Limpar Lista", height=44, corner_radius=10,
            fg_color="transparent", hover_color=("#E5E7EB", "#2A3142"),
            border_width=1.5, border_color=(BORDER_LIGHT, BORDER_DARK),
            text_color=("#374151", "#D1D5DB"),
            command=self._clear_pairs,
        ).pack(side="left", padx=(8, 0))

        self.train_status = ctk.CTkLabel(
            scroll, text="", font=("Segoe UI", 12),
            text_color=(MUTED_LIGHT, MUTED_DARK), anchor="w",
        )
        self.train_status.pack(fill="x", padx=4, pady=(8, 0))

    # ══════════════════════════════════════════════════════════════
    #  SUMMARY
    # ══════════════════════════════════════════════════════════════

    def _update_summary(self):
        if self.summary_label is None:
            return
        intensity = self.opt_intensity.get().capitalize()
        color = self.opt_color_mode.get().capitalize()
        upscale = f"{self.opt_upscale_factor.get()} / {self.opt_upscale_preset.get().replace('_', ' ').title()}" if self.opt_upscale_enabled.get() else "Desligado"
        preview = "Ativo" if self.opt_preview_mode.get() else "Desligado"
        text = f"Intensidade: {intensity}    |    Cor: {color}    |    Upscale: {upscale}    |    Preview: {preview}"
        self.summary_label.configure(text=text)

    # ══════════════════════════════════════════════════════════════
    #  HANDLERS — PROCESSAR (preservados da versão anterior)
    # ══════════════════════════════════════════════════════════════

    def _browse_input(self):
        p = filedialog.askdirectory(title="Pasta com as fotos")
        if p: self.input_dir.set(p)

    def _browse_output(self):
        p = filedialog.askdirectory(title="Pasta de saída")
        if p: self.output_dir.set(p)

    def _browse_style(self):
        p = filedialog.askopenfilename(title="Perfil de estilo", filetypes=[("JSON", "*.json")])
        if p: self.style_profile_path.set(p)

    def _browse_wm_logo(self):
        p = filedialog.askopenfilename(title="Logo para marca d'água",
                                        filetypes=[("Imagens", "*.png *.jpg *.jpeg")])
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
        width, height = 560, 160
        mode = ctk.get_appearance_mode()
        bg_rgb = (30, 35, 50) if mode == "Dark" else (240, 242, 245)
        img = Image.new("RGB", (width, height), bg_rgb)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        opacity = max(0.0, min(1.0, float(self.opt_wm_opacity.get())))
        alpha = int(opacity * 255)
        position = self.opt_wm_position.get()
        margin = 16
        wm_mode = self.opt_wm_mode.get()

        if wm_mode == "image" and self.opt_wm_image.get().strip() and os.path.exists(self.opt_wm_image.get().strip()):
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
                pass
        else:
            text = self.opt_wm_text.get().strip() or "© Minha Empresa"
            try:
                font = ImageFont.truetype("arial.ttf", 22)
            except Exception:
                font = ImageFont.load_default()
            bbox = odraw.textbbox((0, 0), text, font=font)
            wm_w, wm_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x, y = self._watermark_position(position, width, height, wm_w, wm_h, margin)
            fill = (255, 255, 255, alpha) if mode == "Dark" else (35, 41, 52, alpha)
            odraw.text((x, y), text, fill=fill, font=font)

        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        self._wm_preview_photo = ImageTk.PhotoImage(img)
        self.wm_preview_label.configure(image=self._wm_preview_photo)

    def _watermark_position(self, position, img_w, img_h, wm_w, wm_h, margin):
        if position == "top-left": return margin, margin
        if position == "top-right": return img_w - wm_w - margin, margin
        if position == "bottom-left": return margin, img_h - wm_h - margin
        if position == "center": return (img_w - wm_w) // 2, (img_h - wm_h) // 2
        return img_w - wm_w - margin, img_h - wm_h - margin

    def _collect_options(self):
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
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.progress_bar.set(0)
        self.btn_process.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        style_path = self.style_profile_path.get().strip() or None
        options = self._collect_options()
        self.pipeline = ProcessingPipeline(inp, out, self._on_progress,
                                            style_profile_path=style_path, options=options)
        self.pipeline.start()

    def _cancel_processing(self):
        if self.pipeline:
            self.pipeline.cancel()

    def _on_progress(self, message, pct):
        self.after(0, self._update_ui, message, pct)

    def _update_ui(self, message, pct):
        self.progress_bar.set(pct)
        self.status_label.configure(text=message)
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        if pct >= 1.0:
            self.btn_process.configure(state="normal")
            self.btn_cancel.configure(state="disabled")

    def _open_output_folder(self):
        p = self.output_dir.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)
        else:
            messagebox.showinfo("Info", "Defina uma pasta de saída primeiro.")

    # ══════════════════════════════════════════════════════════════
    #  HANDLERS — TREINAR (preservados)
    # ══════════════════════════════════════════════════════════════

    def _browse_before(self):
        p = filedialog.askopenfilename(title="Foto ANTES",
                                        filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp")])
        if p: self.before_var.set(p)

    def _browse_after(self):
        p = filedialog.askopenfilename(title="Foto DEPOIS",
                                        filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp")])
        if p: self.after_var.set(p)

    def _browse_folder(self, var):
        p = filedialog.askdirectory(title="Selecione a pasta")
        if p: var.set(p)

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
        self.pairs_textbox.configure(state="normal")
        self.pairs_textbox.insert("end", f"{os.path.basename(b)}  →  {os.path.basename(a)}\n")
        self.pairs_textbox.configure(state="disabled")
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
        self.pairs_textbox.configure(state="normal")
        for f in matched:
            self.train_pairs.append({"before": os.path.join(bd, f), "after": os.path.join(ad, f)})
            self.pairs_textbox.insert("end", f"{f}  (antes → depois)\n")
        self.pairs_textbox.configure(state="disabled")
        self.train_status.configure(text=f"+{len(matched)} par(es). Total: {len(self.train_pairs)}")

    def _clear_pairs(self):
        self.train_pairs.clear()
        self.pairs_textbox.configure(state="normal")
        self.pairs_textbox.delete("1.0", "end")
        self.pairs_textbox.configure(state="disabled")
        self.train_status.configure(text="Lista limpa.")

    def _train_style(self):
        if not self.train_pairs:
            messagebox.showerror("Erro", "Adicione pelo menos um par de fotos.")
            return
        self.train_status.configure(text="Treinando perfil...")
        self.btn_train.configure(state="disabled")
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
                self.after(0, lambda: self.btn_train.configure(state="normal"))

        threading.Thread(target=do_train, daemon=True).start()

    def _save_trained_profile(self, trainer):
        p = filedialog.asksaveasfilename(title="Salvar perfil de estilo",
                                          defaultextension=".json",
                                          filetypes=[("JSON", "*.json")],
                                          initialfile="meu_estilo.json")
        if p:
            trainer.save_profile(p)
            self.style_profile_path.set(p)
            self.train_status.configure(text=f"✅ Perfil salvo. {len(self.train_pairs)} par(es) usados.")
        else:
            self.train_status.configure(text="Treinamento concluído (perfil não salvo).")
        self.btn_train.configure(state="normal")

    # ══════════════════════════════════════════════════════════════
    #  PERFIS DE CONFIGURAÇÃO (preservados)
    # ══════════════════════════════════════════════════════════════

    def _project_root(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def _config_profiles_dir(self):
        path = os.path.join(self._project_root(), "config_profiles")
        os.makedirs(path, exist_ok=True)
        return path

    def _safe_profile_filename(self, name):
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name.strip())
        return safe.strip().replace(" ", "_") or "perfil"

    def _load_config_profile_names(self):
        folder = self._config_profiles_dir()
        names = []
        for file in sorted(os.listdir(folder)):
            if file.lower().endswith(".json"):
                try:
                    with open(os.path.join(folder, file), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    names.append(data.get("name") or os.path.splitext(file)[0])
                except Exception:
                    names.append(os.path.splitext(file)[0])
        return names

    def _refresh_config_profile_combo(self):
        if self.config_profile_combo:
            self.config_profile_combo.configure(values=self._load_config_profile_names())

    def _get_config_profile_path(self, name):
        return os.path.join(self._config_profiles_dir(), self._safe_profile_filename(name) + ".json")

    def _collect_config_profile_data(self, name):
        return {
            "name": name, "version": 1,
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

    def _apply_config_profile_data(self, data):
        s = data.get("settings", {})
        self.opt_intensity.set(s.get("intensity", self.opt_intensity.get()))
        self.opt_color_mode.set(s.get("color_mode", self.opt_color_mode.get()))
        self.opt_preview_mode.set(bool(s.get("preview_mode", self.opt_preview_mode.get())))
        self.opt_upscale_enabled.set(bool(s.get("upscale_enabled", self.opt_upscale_enabled.get())))
        self.opt_upscale_factor.set(s.get("upscale_factor", self.opt_upscale_factor.get()))
        self.opt_upscale_preset.set(s.get("upscale_preset", self.opt_upscale_preset.get()))
        self.style_profile_path.set(s.get("style_profile_path", self.style_profile_path.get()))
        self.opt_duplicates.set(bool(s.get("duplicates_enabled", self.opt_duplicates.get())))
        self.opt_rename.set(bool(s.get("rename_enabled", self.opt_rename.get())))
        self.opt_rename_prefix.set(s.get("rename_prefix", self.opt_rename_prefix.get()))
        self.opt_rename_code.set(s.get("rename_code", self.opt_rename_code.get()))
        self.opt_watermark.set(bool(s.get("watermark_enabled", self.opt_watermark.get())))
        self.opt_wm_mode.set(s.get("wm_mode", self.opt_wm_mode.get()))
        self.opt_wm_text.set(s.get("wm_text", self.opt_wm_text.get()))
        self.opt_wm_image.set(s.get("wm_image", self.opt_wm_image.get()))
        self.opt_wm_position.set(s.get("wm_position", self.opt_wm_position.get()))
        try: self.opt_wm_opacity.set(float(s.get("wm_opacity", self.opt_wm_opacity.get())))
        except: pass
        self.opt_contact_sheet.set(bool(s.get("contact_sheet", self.opt_contact_sheet.get())))
        self.opt_before_after.set(bool(s.get("before_after", self.opt_before_after.get())))
        self.opt_gallery.set(bool(s.get("gallery", self.opt_gallery.get())))
        self.opt_gallery_title.set(s.get("gallery_title", self.opt_gallery_title.get()))
        self.opt_gallery_subtitle.set(s.get("gallery_subtitle", self.opt_gallery_subtitle.get()))
        self.opt_exif.set(bool(s.get("exif_preserve", self.opt_exif.get())))
        self.opt_photographer.set(s.get("photographer", self.opt_photographer.get()))
        self.opt_copyright.set(s.get("copyright", self.opt_copyright.get()))
        self._on_watermark_preview_change()

    def _save_current_config_profile(self):
        name = simpledialog.askstring("Salvar perfil", "Nome do perfil:", parent=self)
        if not name or not name.strip(): return
        name = name.strip()
        path = self._get_config_profile_path(name)
        if os.path.exists(path):
            if not messagebox.askyesno("Substituir", f"'{name}' já existe. Substituir?"): return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._collect_config_profile_data(name), f, indent=2, ensure_ascii=False)
            self.config_profile_name.set(name)
            self._refresh_config_profile_combo()
            messagebox.showinfo("Salvo", f"Perfil '{name}' salvo.")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _load_selected_config_profile(self):
        name = self.config_profile_name.get().strip()
        if not name:
            messagebox.showinfo("Perfil", "Selecione um perfil.")
            return
        path = self._get_config_profile_path(name)
        if not os.path.exists(path):
            messagebox.showerror("Erro", "Perfil não encontrado.")
            self._refresh_config_profile_combo()
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._apply_config_profile_data(json.load(f))
            messagebox.showinfo("Carregado", f"Perfil '{name}' aplicado.")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _delete_selected_config_profile(self):
        name = self.config_profile_name.get().strip()
        if not name:
            messagebox.showinfo("Perfil", "Selecione um perfil.")
            return
        path = self._get_config_profile_path(name)
        if not os.path.exists(path):
            messagebox.showerror("Erro", "Perfil não encontrado.")
            self._refresh_config_profile_combo()
            return
        if not messagebox.askyesno("Excluir", f"Excluir '{name}'?"): return
        try:
            os.remove(path)
            self.config_profile_name.set("")
            self._refresh_config_profile_combo()
            messagebox.showinfo("Excluído", "Perfil removido.")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _parse_upscale_factor(self, value):
        try: return float(str(value).lower().replace("x", "").strip())
        except: return 2.0
