"""
Pipeline principal de processamento.

Orquestra todas as etapas:
  1. Detecta e remove duplicatas
  2. Copia originais
  3. Classifica imagens
  4. Renomeia de forma inteligente
  5. Aplica melhorias
  6. Aplica marca d'água (se configurada)
  7. Exporta versões
  8. Gera comparações antes/depois
  9. Gera folha de contato
  10. Gera galeria HTML
  11. Gera relatório final

Funciona em thread separada para não travar a interface gráfica.
"""

import os
import shutil
import threading
from typing import Callable

from utils.config import (
    SUPPORTED_EXTENSIONS,
    FOLDER_ORIGINALS, FOLDER_CLASSIFIED, FOLDER_ENHANCED, FOLDER_EXPORTS,
    ALL_CLASSES, REPORT_FILENAME,
)
from core.classifier import ImageClassifier
from core.enhancer import ImageEnhancer
from core.styled_enhancer import StyledEnhancer
from core.exporter import ImageExporter
from core.reporter import ReportGenerator
from core.duplicates import DuplicateDetector
from core.renamer import SmartRenamer
from core.watermark import Watermarker
from core.contact_sheet import ContactSheetGenerator
from core.before_after import BeforeAfterGenerator
from core.gallery import GalleryGenerator
from core.exif_handler import ExifHandler
from core.upscaler import ImageUpscaler


# Pastas extras
FOLDER_DUPLICATES  = "00_DUPLICATAS"
FOLDER_COMPARISONS = "05_COMPARACOES"
FOLDER_THUMBNAILS  = "06_THUMBNAILS"


class ProcessingPipeline:
    """
    Pipeline completo de processamento de fotos imobiliárias.

    Uso:
        pipeline = ProcessingPipeline(input_dir, output_dir, callback, options)
        pipeline.start()
        pipeline.cancel()
    """

    def __init__(self, input_dir: str, output_dir: str,
                 progress_callback: Callable[[str, float], None] | None = None,
                 style_profile_path: str | None = None,
                 options: dict | None = None):
        """
        Args:
            input_dir:  pasta com as fotos originais.
            output_dir: pasta raiz de saída.
            progress_callback: função(mensagem, percentual).
            style_profile_path: caminho para perfil de estilo JSON (opcional).
            options: dicionário de opções:
                rename_enabled:      bool (renomear arquivos)
                rename_prefix:       str  (prefixo, ex: "IMOVEL")
                rename_code:         str  (código do imóvel)
                watermark_enabled:   bool
                watermark_config:    dict (config do Watermarker)
                duplicates_enabled:  bool (detectar duplicatas)
                duplicates_threshold: int (sensibilidade 0-20)
                contact_sheet:       bool (gerar folha de contato)
                before_after:        bool (gerar comparações)
                gallery:             bool (gerar galeria HTML)
                gallery_title:       str
                gallery_subtitle:    str
                exif_preserve:       bool (preservar metadados)
                photographer:        str  (nome do fotógrafo)
                copyright:           str  (texto de copyright)
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.progress = progress_callback or (lambda msg, pct: None)
        self.opts = options or {}

        # Módulos
        self.classifier = ImageClassifier()

        self.intensity = self.opts.get("intensity", "normal")
        self.color_mode = self.opts.get("color_mode", "natural")
        self.preview_mode = bool(self.opts.get("preview_mode", False))
        self.upscale_enabled = bool(self.opts.get("upscale_enabled", False))
        self.upscale_factor = float(self.opts.get("upscale_factor", 2.0) or 2.0)
        self.upscale_preset = self.opts.get("upscale_preset", "natural_pro")

        if style_profile_path and os.path.exists(style_profile_path):
            self.enhancer = StyledEnhancer.from_file(
                style_profile_path, intensity=self.intensity, color_mode=self.color_mode)
        else:
            self.enhancer = StyledEnhancer(
                {}, intensity=self.intensity, color_mode=self.color_mode)

        self.exporter = ImageExporter()
        self.upscaler = ImageUpscaler(self.upscale_factor, preset=self.upscale_preset) if self.upscale_enabled else None
        self.reporter = ReportGenerator()

        # Módulos opcionais
        self.duplicate_detector = DuplicateDetector(
            threshold=self.opts.get("duplicates_threshold", 10)
        ) if self.opts.get("duplicates_enabled", False) else None

        self.renamer = SmartRenamer(
            prefix=self.opts.get("rename_prefix", "IMOVEL"),
            property_code=self.opts.get("rename_code", ""),
        ) if self.opts.get("rename_enabled", False) else None

        self.watermarker = Watermarker(
            self.opts.get("watermark_config")
        ) if self.opts.get("watermark_enabled", False) else None

        self.exif_handler = ExifHandler(
            photographer=self.opts.get("photographer", ""),
            copyright_text=self.opts.get("copyright", ""),
        ) if self.opts.get("exif_preserve", True) else None

        self._cancelled = False
        self._thread: threading.Thread | None = None

    # ── Controle ─────────────────────────────────────────────────

    def start(self):
        self._cancelled = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancelled = True

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── Pipeline principal ───────────────────────────────────────

    def _run(self):
        try:
            self.reporter.start()
            self.progress("Preparando pastas...", 0.0)
            paths = self._create_folder_structure()

            # Lista imagens
            images = self._list_images()
            if not images:
                self.progress("Nenhuma imagem encontrada na pasta de entrada.", 1.0)
                return

            if self.preview_mode:
                images = images[:1]
                self.progress("Modo preview ativo: processando apenas a primeira imagem.", 0.02)

            total = len(images)
            self.progress(f"Encontradas {total} imagens para processar.", 0.02)

            # ── Etapa 0: Detectar duplicatas ──
            removed_dupes = []
            if self.duplicate_detector:
                self.progress("Detectando duplicatas...", 0.03)
                full_paths = [os.path.join(self.input_dir, f) for f in images]
                groups = self.duplicate_detector.find_duplicates(full_paths)

                if groups:
                    dupes_dir = os.path.join(self.output_dir, FOLDER_DUPLICATES)
                    for g in groups:
                        for dup in g["duplicates"]:
                            dup_name = os.path.basename(dup)
                            removed_dupes.append(dup_name)
                            # Copia para pasta de duplicatas (não remove da entrada)
                            os.makedirs(dupes_dir, exist_ok=True)
                            shutil.copy2(dup, os.path.join(dupes_dir, dup_name))

                    images = [f for f in images if f not in removed_dupes]
                    self.progress(
                        f"Duplicatas: {len(removed_dupes)} encontradas e separadas.",
                        0.08,
                    )

            total = len(images)
            if total == 0:
                self.progress("Todas as imagens são duplicatas.", 1.0)
                return

            # Processamento por imagem
            classifications = []  # para renomeação
            processed_info = []   # para galeria e contact sheet
            before_after_pairs = []

            for idx, filename in enumerate(images):
                if self._cancelled:
                    self.progress("Cancelado pelo usuário.", 1.0)
                    return

                src_path = os.path.join(self.input_dir, filename)
                base_name = os.path.splitext(filename)[0]
                pct = 0.10 + (idx + 1) / total * 0.60

                self.progress(f"[{idx+1}/{total}] {filename}", pct)

                # ── Etapa 1: Copia original ──
                orig_dst = os.path.join(paths["originals"], filename)
                shutil.copy2(src_path, orig_dst)

                # ── Etapa 2: Classifica ──
                classification = self.classifier.classify(src_path)
                class_dst = os.path.join(paths["classified"], classification, filename)
                shutil.copy2(src_path, class_dst)
                classifications.append({
                    "filename": filename, "classification": classification
                })

                # ── Etapa 3: Aplica melhorias ──
                enhanced_path = os.path.join(paths["enhanced"], filename)
                if isinstance(self.enhancer, StyledEnhancer):
                    enhancements = self.enhancer.enhance(src_path, enhanced_path, category=classification)
                else:
                    enhancements = self.enhancer.enhance(src_path, enhanced_path)

                # ── Etapa 3.4: Upscale opcional ──
                if self.upscaler:
                    upscale_log = self.upscaler.upscale_file(enhanced_path)
                    enhancements.append(upscale_log)

                # ── Etapa 3.5: Preserva EXIF ──
                if self.exif_handler:
                    self.exif_handler.copy_exif(src_path, enhanced_path)
                    exif_summary = self.exif_handler.get_summary(src_path)
                    enhancements.append(f"EXIF: {exif_summary}")

                # ── Etapa 4: Marca d'água ──
                if self.watermarker:
                    if self.watermarker.apply(enhanced_path):
                        enhancements.append("Marca d'água aplicada")

                # ── Etapa 5: Exporta versões ──
                exports = self.exporter.export(
                    enhanced_path, paths["exports"], base_name
                )

                # Registra
                self.reporter.add_entry(filename, classification, enhancements, exports)
                processed_info.append({
                    "path": enhanced_path,
                    "filename": filename,
                    "classification": classification,
                })
                before_after_pairs.append({
                    "before": src_path,
                    "after": enhanced_path,
                    "name": filename,
                })

            # ── Etapa 6: Renomear ──
            if self.renamer and classifications:
                self.progress("Renomeando arquivos...", 0.75)
                mapping = self.renamer.generate_mapping(classifications)
                # Renomeia nas pastas de saída
                for folder_key in ["enhanced", "originals"]:
                    self.renamer._counters.clear()
                    m = self.renamer.generate_mapping(classifications)
                    self.renamer.apply_renaming(paths[folder_key], m)
                # Renomeia nas subpastas de classificação
                for cls in ALL_CLASSES:
                    cls_folder = os.path.join(paths["classified"], cls)
                    cls_files = [c for c in classifications
                                 if c["classification"] == cls]
                    if cls_files:
                        self.renamer._counters.clear()
                        m = self.renamer.generate_mapping(cls_files)
                        self.renamer.apply_renaming(cls_folder, m)

            # ── Etapa 7: Comparações antes/depois ──
            if self.opts.get("before_after", True) and before_after_pairs:
                self.progress("Gerando comparações antes/depois...", 0.80)
                comp_dir = os.path.join(self.output_dir, FOLDER_COMPARISONS)
                generator = BeforeAfterGenerator()
                generator.generate_batch(before_after_pairs, comp_dir)

            # ── Etapa 8: Folha de contato ──
            if self.opts.get("contact_sheet", True) and processed_info:
                self.progress("Gerando folha de contato...", 0.85)
                sheet = ContactSheetGenerator()
                sheet_path = os.path.join(self.output_dir, "folha_contato.jpg")
                sheet.generate(processed_info, sheet_path,
                               title=self.opts.get("gallery_title", "Fotos do Imóvel"))

                # Thumbnails
                thumb_dir = os.path.join(self.output_dir, FOLDER_THUMBNAILS)
                sheet.generate_thumbnails(
                    [p["path"] for p in processed_info], thumb_dir
                )

            # ── Etapa 9: Galeria HTML ──
            if self.opts.get("gallery", True) and processed_info:
                self.progress("Gerando galeria HTML...", 0.90)
                gallery = GalleryGenerator(
                    title=self.opts.get("gallery_title", "Galeria de Fotos"),
                    subtitle=self.opts.get("gallery_subtitle", ""),
                )
                gallery_path = os.path.join(self.output_dir, "galeria.html")
                gallery.generate(processed_info, gallery_path)

            # ── Etapa 10: Relatório ──
            self.progress("Gerando relatório...", 0.95)

            # Adiciona info de duplicatas ao relatório
            if removed_dupes:
                self.reporter.add_error(
                    f"DUPLICATAS SEPARADAS ({len(removed_dupes)}): "
                    + ", ".join(removed_dupes)
                )

            report_path = os.path.join(self.output_dir, REPORT_FILENAME)
            self.reporter.save(report_path)

            self.progress(
                f"Concluído! {total} imagens processadas. Relatório salvo.",
                1.0,
            )

        except Exception as e:
            self.reporter.add_error(str(e))
            self.progress(f"ERRO: {e}", 1.0)

    # ── Utilidades ───────────────────────────────────────────────

    def _create_folder_structure(self) -> dict[str, str]:
        paths = {
            "originals":  os.path.join(self.output_dir, FOLDER_ORIGINALS),
            "classified": os.path.join(self.output_dir, FOLDER_CLASSIFIED),
            "enhanced":   os.path.join(self.output_dir, FOLDER_ENHANCED),
            "exports":    os.path.join(self.output_dir, FOLDER_EXPORTS),
        }
        for p in paths.values():
            os.makedirs(p, exist_ok=True)
        for cls in ALL_CLASSES:
            os.makedirs(os.path.join(paths["classified"], cls), exist_ok=True)
        return paths

    def _list_images(self) -> list[str]:
        files = []
        for f in sorted(os.listdir(self.input_dir)):
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                files.append(f)
        return files
