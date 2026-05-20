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

import json
import os
import shutil
import threading
import concurrent.futures
from typing import Callable

from utils.config import (
    SUPPORTED_EXTENSIONS,
    FOLDER_ORIGINALS, FOLDER_CLASSIFIED, FOLDER_ENHANCED, FOLDER_EXPORTS,
    FOLDER_DUPLICATES, FOLDER_COMPARISONS, FOLDER_THUMBNAILS,
    FOLDER_BRACKETING, FOLDER_RAW_CONVERTED,
    ALL_CLASSES, REPORT_FILENAME,
)
from core.classifier import ImageClassifier
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
from core.bracketing import BracketingProcessor, BracketItem
from core.raw_support import RawSupportError, is_raw_file, convert_raw_to_jpeg



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

        # Thread-safety para processamento paralelo
        self._lock = threading.Lock()
        self._thread_local = threading.local()
        self._style_profile_path = style_profile_path

        # Módulos
        self.classifier = ImageClassifier(
            classifier_profile_path=self.opts.get("classifier_profile_path")
        )

        self.intensity = self.opts.get("intensity", "normal")
        self.color_mode = self.opts.get("color_mode", "natural")
        self.preview_mode = bool(self.opts.get("preview_mode", False))
        self.upscale_enabled = bool(self.opts.get("upscale_enabled", False))
        self.upscale_factor = float(self.opts.get("upscale_factor", 2.0) or 2.0)
        self.upscale_preset = self.opts.get("upscale_preset", "natural_pro")

        # Bracketing / HDR imobiliário
        self.bracketing_enabled = bool(self.opts.get("bracketing_enabled", False))
        self.bracketing_group_size = self.opts.get("bracketing_group_size", "auto")
        self.bracketing_fusion_preset = self.opts.get("bracketing_fusion_preset", "natural")
        # Quando False, grupos HDR não passam pelo StyledEnhancer / Modo Automático.
        # Isso permite testar o merge HDR puro sem Luxury/Strong/Color Mode interferindo.
        self.bracketing_apply_auto_enhance = bool(self.opts.get("bracketing_apply_auto_enhance", False))
        self.bracketing_processor = BracketingProcessor(
            group_size=self.bracketing_group_size,
            fusion_preset=self.bracketing_fusion_preset,
            auto_chromatic_aberration=bool(self.opts.get("bracketing_auto_chromatic_aberration", True)),
            auto_lens_correction=bool(self.opts.get("bracketing_auto_lens_correction", True)),
            auto_geometry_correction=bool(self.opts.get("bracketing_auto_geometry_correction", True)),
            profile_path=style_profile_path,
            skip_lightroom_finish=self.bracketing_apply_auto_enhance,
        ) if self.bracketing_enabled else None

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


    # ── Suporte RAW / CR3 ────────────────────────────────────────

    def _source_path_for(self, filename: str) -> str:
        """Caminho processável para um item: JPEG convertido no caso de RAW."""
        overrides = getattr(self, "_source_overrides", {})
        if filename in overrides:
            return overrides[filename]
        subfolder_map = getattr(self, "_subfolder_map", {})
        if filename in subfolder_map:
            return subfolder_map[filename]
        return os.path.join(self.input_dir, filename)

    def _original_path_for(self, filename: str) -> str:
        """Caminho original real para preservação/cópia."""
        return getattr(self, "_original_overrides", {}).get(
            filename,
            self._source_path_for(filename),
        )

    def _prepare_raw_sources(self, filenames: list[str], raw_dir: str) -> list[str]:
        """
        Converte RAW/CR3 em JPEG temporário para o pipeline existente.
        Retorna uma lista de nomes processáveis. O original RAW continua rastreado.
        """
        self._source_overrides = {}
        self._original_overrides = {}

        prepared: list[str] = []
        raw_count = 0
        raw_errors: list[str] = []

        for filename in filenames:
            original = getattr(self, "_subfolder_map", {}).get(
                filename, os.path.join(self.input_dir, filename)
            )
            if is_raw_file(original):
                try:
                    self.progress(f"Convertendo RAW/CR3: {filename}", 0.025)
                    # preserve_exposure=True mantém diferença de exposição entre bracketing shots
                    converted = convert_raw_to_jpeg(
                        original, raw_dir, suffix="_CR3", quality=96,
                        preserve_exposure=self.bracketing_enabled,
                    )
                    converted_name = os.path.basename(converted)
                    self._source_overrides[converted_name] = converted
                    self._original_overrides[converted_name] = original
                    prepared.append(converted_name)
                    raw_count += 1
                except RawSupportError as exc:
                    raw_errors.append(f"{filename}: {exc}")
                    self.progress(f"RAW/CR3 ignorado ({filename}): {exc}", 0.025)
                except Exception as exc:
                    raw_errors.append(f"{filename}: {exc}")
                    self.progress(f"RAW/CR3 ignorado ({filename}): {exc}", 0.025)
            else:
                prepared.append(filename)

        if raw_count:
            self.progress(f"RAW/CR3: {raw_count} arquivo(s) convertido(s) para processamento.", 0.025)

        if raw_errors:
            for err in raw_errors[:10]:
                try:
                    self.reporter.add_error(f"RAW/CR3: {err}")
                except Exception:
                    pass
            if raw_count == 0 and all(is_raw_file(os.path.join(self.input_dir, f)) for f in filenames):
                raise RuntimeError(
                    "Nenhum arquivo RAW/CR3 pôde ser convertido. "
                    "Instale/atualize rawpy com 'python -m pip install -U rawpy' ou converta os CR3 para DNG/JPEG antes. "
                    f"Primeiro erro: {raw_errors[0]}"
                )

        return prepared

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

            total_images = len(images)
            self.progress(f"Encontradas {total_images} imagens na entrada.", 0.02)

            # RAW/CR3: converte para JPEG temporário para compatibilidade com OpenCV/Pillow.
            images = self._prepare_raw_sources(images, paths["raw_converted"])
            if not images:
                self.progress("Nenhuma imagem processável encontrada após conversão RAW/CR3.", 1.0)
                return

            # ── Etapa 0: Detectar duplicatas ──
            removed_dupes = []
            if self.duplicate_detector and not self.bracketing_processor:
                self.progress("Detectando duplicatas...", 0.03)
                full_paths = [self._source_path_for(f) for f in images]
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
            elif self.duplicate_detector and self.bracketing_processor:
                self.progress("Bracketing ativo: detecção de duplicatas ignorada para não separar exposições do mesmo grupo.", 0.08)

            if len(images) == 0:
                self.progress("Todas as imagens são duplicatas.", 1.0)
                return

            # ── Etapa 0.5: Bracketing / HDR imobiliário ──
            if self.bracketing_processor:
                self.progress("Detectando grupos de bracketing/HDR...", 0.09)
                image_paths = [self._source_path_for(f) for f in images]
                original_path_map = {self._source_path_for(f): self._original_path_for(f) for f in images}
                items = self.bracketing_processor.build_items(
                    image_paths,
                    paths["bracketing"],
                    original_path_map=original_path_map,
                )
                bracket_count = sum(1 for item in items if item.is_bracket)
                if bracket_count:
                    self.progress(
                        f"Bracketing: {bracket_count} grupo(s) fusionado(s), {len(items)} item(ns) finais.",
                        0.10,
                    )
                else:
                    self.progress("Bracketing: nenhum grupo detectado; processando fotos individuais.", 0.10)
            else:
                items = [
                    BracketItem(
                        filename=f,
                        source_path=self._source_path_for(f),
                        base_source=self._original_path_for(f),
                        source_paths=[self._original_path_for(f)],
                        is_bracket=False,
                        log=["RAW/CR3 convertido para JPEG temporário antes do enhance"] if is_raw_file(self._original_path_for(f)) else [],
                    )
                    for f in images
                ]

            if self.preview_mode:
                items = items[:1]
                self.progress("Modo preview ativo: processando apenas o primeiro item.", 0.11)

            total = len(items)
            if total == 0:
                self.progress("Nenhum item para processar.", 1.0)
                return
            self.progress(f"Preparado(s) {total} item(ns) para processar.", 0.12)

            # Processamento paralelo por imagem ou grupo HDR
            classifications = []  # para renomeação
            processed_info = []   # para galeria e contact sheet
            before_after_pairs = []

            _mw = int(self.opts.get("max_workers", 0) or 0)
            max_workers = _mw if _mw >= 2 else min(os.cpu_count() or 1, 4)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map: dict[concurrent.futures.Future, int] = {}
                for idx, item in enumerate(items):
                    if self._cancelled:
                        break
                    future_map[executor.submit(self._process_single_item, idx, item, total, paths)] = idx

                for future in concurrent.futures.as_completed(future_map):
                    if self._cancelled:
                        for f in future_map:
                            f.cancel()
                        self.progress("Cancelado pelo usuário.", 1.0)
                        return
                    result = future.result()
                    if result:
                        with self._lock:
                            classifications.append(result["class_entry"])
                            processed_info.append(result["info_entry"])
                            before_after_pairs.append(result["ba_entry"])

            # ── Etapa 6: Renomear ──
            if self.renamer and classifications:
                self.progress("Renomeando arquivos...", 0.75)
                mapping = self.renamer.generate_mapping(classifications)
                # Renomeia nas pastas de saída
                for folder_key in ["enhanced", "originals"]:
                    self.renamer.reset()
                    m = self.renamer.generate_mapping(classifications)
                    self.renamer.apply_renaming(paths[folder_key], m)
                # Renomeia nas subpastas de classificação
                for cls in ALL_CLASSES:
                    cls_folder = os.path.join(paths["classified"], cls)
                    cls_files = [c for c in classifications
                                 if c["classification"] == cls]
                    if cls_files:
                        self.renamer.reset()
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

            # Compute per-class counts from successfully processed items
            class_count: dict[str, int] = {}
            for c in classifications:
                cls = c["classification"]
                class_count[cls] = class_count.get(cls, 0) + 1

            duration_sec = 0
            if self.reporter.start_time and self.reporter.end_time:
                duration_sec = int(
                    (self.reporter.end_time - self.reporter.start_time).total_seconds()
                )

            per_image = [
                {"orig": c.get("orig", ""), "cls": c["classification"]}
                for c in classifications
            ]
            stats = {
                "total": total,
                "processed": len(classifications),
                "by_class": class_count,
                "per_image": per_image,
                "errors": len(self.reporter.errors),
                "duration_sec": duration_sec,
                "report_path": report_path,
                "enhanced_files": [p["path"] for p in processed_info],
                "ba_pairs": [{"after": p["after"], "before": p["before"]} for p in before_after_pairs],
            }
            self.progress(
                f"Concluído! {len(classifications)} imagem(ns) processada(s). Relatório salvo.",
                0.99,
            )
            self.progress(f"STATS:{json.dumps(stats)}", 1.0)

        except Exception as e:
            self.reporter.add_error(str(e))
            self.progress(f"ERRO: {e}", 1.0)

    # ── Enhancer por thread ──────────────────────────────────────

    def _get_enhancer(self) -> StyledEnhancer:
        """Retorna um StyledEnhancer exclusivo para a thread atual (thread-safe)."""
        if not hasattr(self._thread_local, "enhancer"):
            if self._style_profile_path and os.path.exists(self._style_profile_path):
                self._thread_local.enhancer = StyledEnhancer.from_file(
                    self._style_profile_path,
                    intensity=self.intensity,
                    color_mode=self.color_mode,
                )
            else:
                self._thread_local.enhancer = StyledEnhancer(
                    {}, intensity=self.intensity, color_mode=self.color_mode
                )
        return self._thread_local.enhancer

    # ── Processamento de item único (thread-safe) ────────────────

    def _process_single_item(
        self, idx: int, item: BracketItem, total: int, paths: dict
    ) -> dict | None:
        """Processa uma imagem ou grupo HDR. Pode ser chamado de múltiplas threads."""
        filename = item.filename
        pct = 0.12 + (idx + 1) / total * 0.58
        try:
            src_path = item.source_path
            base_source = item.base_source
            base_name = os.path.splitext(filename)[0]

            if item.is_bracket:
                originals = ", ".join(os.path.basename(p) for p in item.source_paths)
                self.progress(f"[{idx+1}/{total}] HDR {filename} ({len(item.source_paths)} fotos)", pct)
            else:
                originals = filename
                self.progress(f"[{idx+1}/{total}] {filename}", pct)

            # Etapa 1: Copia original/is (bracket: plano no dir raiz, sem subpasta)
            if item.is_bracket:
                for original_path in item.source_paths:
                    shutil.copy2(original_path, os.path.join(paths["originals"], os.path.basename(original_path)))
            else:
                orig_dst = os.path.join(paths["originals"], os.path.basename(base_source))
                shutil.copy2(base_source, orig_dst)

            # Etapa 2: Classifica (cria subpasta de classe somente quando usada)
            classification = self.classifier.classify(src_path)
            class_dir = os.path.join(paths["classified"], classification)
            os.makedirs(class_dir, exist_ok=True)
            shutil.copy2(src_path, os.path.join(class_dir, filename))

            # Etapa 3: Aplica melhorias (enhancer por thread)
            enhanced_path = os.path.join(paths["enhanced"], filename)
            if item.is_bracket and not self.bracketing_apply_auto_enhance:
                shutil.copy2(src_path, enhanced_path)
                enhancements = (
                    item.log
                    + [f"Bracketing: originais agrupados: {originals}"]
                    + ["HDR puro: Modo Automático/Enhance ignorado após o merge"]
                )
            else:
                enhancer = self._get_enhancer()
                enhancements = enhancer.enhance(src_path, enhanced_path, category=classification)
                if item.is_bracket:
                    enhancements = (
                        item.log
                        + [f"Bracketing: originais agrupados: {originals}"]
                        + ["HDR + acabamento automático aplicado"]
                        + enhancements
                    )

            # Etapa 3.4: Upscale opcional
            if self.upscaler:
                upscale_log = self.upscaler.upscale_file(enhanced_path)
                enhancements.append(upscale_log)

            # Etapa 3.5: Preserva EXIF
            if self.exif_handler:
                self.exif_handler.copy_exif(base_source, enhanced_path)
                exif_summary = self.exif_handler.get_summary(base_source)
                enhancements.append(f"EXIF: {exif_summary}")

            # Etapa 4: Marca d'água
            if self.watermarker:
                if self.watermarker.apply(enhanced_path):
                    enhancements.append("Marca d'água aplicada")

            # Etapa 5: Exporta versões
            exports = self.exporter.export(
                enhanced_path, paths["exports"], base_name,
                profiles=self.opts.get("export_profiles") or None,
            )

            # Registra no reporter (protegido por lock)
            with self._lock:
                self.reporter.add_entry(filename, classification, enhancements, exports)

            return {
                "class_entry": {"filename": filename, "classification": classification, "orig": base_source},
                "info_entry": {"path": enhanced_path, "filename": filename, "classification": classification},
                "ba_entry": {"before": base_source, "after": enhanced_path, "name": filename},
            }

        except Exception as exc:
            with self._lock:
                self.reporter.add_error(f"{filename}: {exc}")
            self.progress(f"[{idx+1}/{total}] ERRO em {filename} — ignorado: {exc}", pct)
            return None

    # ── Utilidades ───────────────────────────────────────────────

    def _create_folder_structure(self) -> dict[str, str]:
        paths = {
            "originals":  os.path.join(self.output_dir, FOLDER_ORIGINALS),
            "classified": os.path.join(self.output_dir, FOLDER_CLASSIFIED),
            "enhanced":   os.path.join(self.output_dir, FOLDER_ENHANCED),
            "exports":    os.path.join(self.output_dir, FOLDER_EXPORTS),
            "bracketing": os.path.join(self.output_dir, FOLDER_BRACKETING),
            "raw_converted": os.path.join(self.output_dir, FOLDER_RAW_CONVERTED),
        }
        for p in paths.values():
            os.makedirs(p, exist_ok=True)
        # Subpastas de classificação criadas sob demanda em _process_single_item
        return paths

    def _list_images(self) -> list[str]:
        self._subfolder_map: dict[str, str] = {}
        files: list[str] = []

        if self.opts.get("subfolder_recursive", False):
            for root, dirs, fnames in os.walk(self.input_dir):
                dirs.sort()
                for f in sorted(fnames):
                    if os.path.splitext(f)[1].lower() not in SUPPORTED_EXTENSIONS:
                        continue
                    full_path = os.path.join(root, f)
                    rel_dir = os.path.relpath(root, self.input_dir)
                    if rel_dir == ".":
                        keyed = f
                    else:
                        prefix = rel_dir.replace(os.sep, "_").replace(" ", "_")
                        keyed = f"{prefix}__{f}"
                    files.append(keyed)
                    self._subfolder_map[keyed] = full_path
        else:
            allowed = self.opts.get("allowed_files")
            allowed_set = set(allowed) if allowed else None
            for f in sorted(os.listdir(self.input_dir)):
                if os.path.splitext(f)[1].lower() not in SUPPORTED_EXTENSIONS:
                    continue
                if allowed_set is not None and os.path.join(self.input_dir, f) not in allowed_set:
                    continue
                files.append(f)

        return files
