"""
Configurações globais do agente de fotos imobiliárias.
Ajuste os valores abaixo para personalizar o comportamento do sistema.
"""

# ─── Extensões de imagem aceitas ─────────────────────────────────
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".cr3", ".cr2", ".nef", ".arw", ".dng", ".raf", ".rw2", ".orf"}

# ─── Estrutura de pastas de saída ────────────────────────────────
FOLDER_ORIGINALS     = "01_ORIGINAIS"
FOLDER_CLASSIFIED    = "02_CLASSIFICADAS"
FOLDER_ENHANCED      = "03_MELHORADAS"
FOLDER_EXPORTS       = "04_EXPORTACOES"
FOLDER_DUPLICATES    = "00_DUPLICATAS"
FOLDER_COMPARISONS   = "05_COMPARACOES"
FOLDER_THUMBNAILS    = "06_THUMBNAILS"
FOLDER_BRACKETING    = "00_BRACKETING_FUSOES"
FOLDER_RAW_CONVERTED = "00_RAW_CONVERTIDOS"
REPORT_FILENAME      = "relatorio_processamento.txt"

# Subpastas de classificação
CLASS_INTERIOR  = "interior"
CLASS_EXTERIOR  = "exterior"
CLASS_DETAILS   = "detalhes"
CLASS_REVIEW    = "revisar"

ALL_CLASSES = [CLASS_INTERIOR, CLASS_EXTERIOR, CLASS_DETAILS, CLASS_REVIEW]

# ─── Parâmetros de melhoria de imagem ────────────────────────────
# Exposição: fator multiplicador (1.0 = sem alteração)
EXPOSURE_FACTOR = 1.15

# Contraste: fator CLAHE (Contrast Limited Adaptive Histogram Equalization)
CLAHE_CLIP_LIMIT = 2.0
CLAHE_GRID_SIZE  = (8, 8)

# Nitidez: intensidade do unsharp mask
SHARPEN_AMOUNT  = 1.3   # fator de mistura
SHARPEN_RADIUS  = 1     # raio gaussiano em pixels

# Redução de ruído (Non-Local Means)
DENOISE_STRENGTH    = 6    # h parameter — quanto maior, mais suavização
DENOISE_TEMPLATE_WS = 7    # templateWindowSize
DENOISE_SEARCH_WS   = 21   # searchWindowSize

# Balanço de branco: usa algoritmo Gray World
WHITE_BALANCE_ENABLED = True

# Correção de perspectiva: limiar de detecção de linhas
PERSPECTIVE_HOUGH_THRESHOLD = 80
PERSPECTIVE_MAX_ANGLE_DEG   = 5.0   # corrige até ±5° de inclinação

# ─── Perfis de exportação ────────────────────────────────────────
EXPORT_PROFILES = {
    "alta_qualidade": {
        "max_width":  16000,
        "max_height": 16000,
        "quality":    97,
        "suffix":     "_HQ",
    },
    "instagram": {
        "max_width":  1080,
        "max_height": 1080,
        "quality":    85,
        "suffix":     "_IG",
    },
    "whatsapp": {
        "max_width":  1280,
        "max_height": 960,
        "quality":    75,
        "suffix":     "_WA",
    },
}

# ─── Classificador ──────────────────────────────────────────────
# Limites de heurística (quando não usa modelo de IA)
# Percentual de pixels "verdes" para considerar exterior
GREEN_THRESHOLD_PCT   = 12.0
# Percentual de pixels "azul céu" para considerar exterior
SKY_BLUE_THRESHOLD_PCT = 8.0
# Área mínima relativa da imagem para considerar "detalhe" (imagem muito próxima)
DETAIL_EDGE_DENSITY_MIN = 0.35
# Brilho médio mínimo para não mandar para revisão
MIN_BRIGHTNESS = 40
# Brilho médio máximo para não mandar para revisão
MAX_BRIGHTNESS = 245
