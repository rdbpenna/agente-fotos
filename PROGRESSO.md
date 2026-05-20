# PROGRESSO.md — Estado atual do projeto

Última atualização: maio/2025

---

## ✅ O que já está implementado

### Funcionalidades core
- [x] Interface gráfica com 3 abas (Processar, Configurações, Treinar Estilo)
- [x] Seleção de pasta de entrada e saída
- [x] Cópia de segurança dos originais (pasta 01_ORIGINAIS)
- [x] Classificação de imagens (interior/exterior/detalhes/revisar) por heurísticas de cor/textura
- [x] Melhorias automáticas: balanço de branco, exposição, contraste, ruído, nitidez, perspectiva
- [x] Exportação em 3 perfis: alta qualidade, Instagram, WhatsApp
- [x] Relatório .txt com detalhes de cada imagem processada
- [x] Barra de progresso e log em tempo real
- [x] Botão cancelar processamento
- [x] Processamento em thread separada (não trava a GUI)

### Funcionalidades extras
- [x] Detecção de duplicatas (perceptual hash)
- [x] Renomeação inteligente (IMOVEL_001_classe_seq.jpg)
- [x] Marca d'água (texto ou logo PNG, posição e opacidade configuráveis)
- [x] Comparação antes/depois (imagem lado a lado)
- [x] Folha de contato (grade de thumbnails)
- [x] Galeria HTML com lightbox e filtros
- [x] Preservação de metadados EXIF
- [x] Treino de estilo por exemplos (pares antes/depois → perfil .json)
- [x] Aplicação de perfil de estilo treinado no processamento
- [x] Arquivo iniciar.bat para abrir rápido no Windows

---

## ⚠️ Bugs conhecidos e problemas potenciais

### Alta prioridade
1. **Renomeação acessa atributo privado:** Em `pipeline.py` linha ~251,
   `self.renamer._counters.clear()` acessa atributo interno do renamer.
   Deveria ter um método público tipo `renamer.reset()`.

2. **Erro em imagem individual pode parar o lote:** Se uma imagem causar
   exceção durante o processamento (ex: arquivo corrompido), o try/catch
   está no nível do pipeline inteiro, não por imagem. Uma foto ruim pode
   abortar todas as seguintes.

3. **Constantes de pasta inconsistentes:** As pastas 00_DUPLICATAS,
   05_COMPARACOES e 06_THUMBNAILS estão definidas como constantes locais
   em `pipeline.py` em vez de ficarem centralizadas em `config.py` junto
   com as demais (FOLDER_ORIGINALS, FOLDER_CLASSIFIED, etc.).

### Média prioridade
4. **Import não utilizado:** `colorchooser` é importado em `gui/app.py`
   mas nunca é usado. Não causa erro, mas é código morto.

5. **Import não utilizado:** `os` é importado em `utils/config.py`
   mas não é usado em lugar nenhum do arquivo.

6. **Galeria HTML com caminhos relativos:** O gerador de galeria usa
   caminhos relativos para as imagens. Se o arquivo HTML for movido
   de pasta, as imagens não carregam. Considerar opção de embeber
   thumbnails em base64 (já existe o parâmetro `embed_thumbnails`
   mas não está exposto na GUI).

7. **Classificador por heurística é básico:** A classificação
   interior/exterior funciona razoavelmente com vegetação e céu,
   mas pode errar em fotos de varandas, áreas gourmet cobertas,
   ou ambientes com muitas plantas internas.

### Baixa prioridade
8. **Sem validação do perfil de estilo:** Se o usuário selecionar um
   arquivo .json que não é um perfil de estilo válido, o erro não é
   tratado de forma amigável.

9. **Configurações não persistem:** As configurações da aba "Configurações"
   são perdidas ao fechar o programa. Não existe salvar/carregar
   configurações.

10. **Sem testes automatizados:** Nenhum teste unitário ou de integração.

---

## 🔧 O que precisa melhorar (por ordem de importância)

1. **Tratamento de erro por imagem** — proteger cada imagem individualmente
   para que uma foto corrompida não pare o lote inteiro.

2. **Testar com fotos reais** — o sistema foi escrito mas precisa de
   validação prática com fotos reais de imóveis para ajustar parâmetros.

3. **Ajustar classificador** — os limiares em config.py (GREEN_THRESHOLD_PCT,
   SKY_BLUE_THRESHOLD_PCT, DETAIL_EDGE_DENSITY_MIN) podem precisar de
   calibração com fotos reais.

4. **Persistir configurações** — salvar as configurações da GUI em um
   arquivo settings.json para não perder ao fechar.

5. **Mover constantes para config.py** — centralizar FOLDER_DUPLICATES,
   FOLDER_COMPARISONS, FOLDER_THUMBNAILS.

6. **Adicionar testes básicos** — pelo menos testar que cada módulo
   importa sem erro e que o pipeline processa uma imagem simples.

---

## 💡 Próximos passos sugeridos

### Curto prazo (ajustes)
- Testar o sistema com um lote real de 10-20 fotos de imóveis
- Ajustar parâmetros de melhoria de imagem conforme resultado visual
- Corrigir o bug de erro por imagem (item 2 dos bugs)
- Limpar imports não utilizados

### Médio prazo (funcionalidades)
- Salvar/carregar configurações em arquivo
- Preview de uma foto antes de processar o lote inteiro
- Opção de desfazer/reprocessar uma imagem específica
- Suporte a subpastas na entrada (processar recursivamente)
- Melhorar classificador com modelo ONNX pré-treinado

### Longo prazo (evolução)
- Interface mais moderna (considerar CustomTkinter ou PyQt)
- Integração com APIs de imobiliárias para upload direto
- Remoção automática de objetos indesejados (IA generativa)
- Sky replacement (substituição de céu nublado)
- HDR merge (combinar bracketing de exposição)

---

## 📋 Versões

| Data | O que mudou |
|------|-------------|
| Maio/2025 | Versão inicial do MVP — todas as funcionalidades core implementadas |
| Maio/2025 | Adicionado: treino de estilo, marca d'água, duplicatas, renomeação, galeria, EXIF, comparações, folha de contato |
| Maio/2025 | Documentação de organização: CLAUDE.md, PROGRESSO.md, PROMPT_CONTINUAR.txt, .gitignore |

## Atualização v7 — Intensidade e edição mais inteligente
- Adicionado seletor de intensidade: suave, normal e forte.
- Adicionado modo preview para processar apenas 1 foto antes do lote.
- O perfil personalizado agora usa preset base “Natural Imobiliário” + estilo aprendido com limites.
- A edição agora considera a classificação da imagem: interior, exterior, detalhes ou revisar.
- Melhoradas as travas contra clipping/áreas estouradas.
- Logs indicam preset, intensidade, ajustes de sombras, meios-tons, luzes, contraste e saturação.

## Como testar a v7
1. Abra o `iniciar.bat`.
2. Selecione uma pasta com poucas fotos de teste.
3. Escolha o perfil de estilo, se quiser usar o seu estilo treinado.
4. Marque “Modo preview” e teste em intensidade `normal`.
5. Compare o antes/depois.
6. Se estiver fraco, teste `forte`; se estiver artificial, teste `suave`.
7. Desmarque preview apenas quando estiver satisfeito para processar o lote inteiro.


## Atualização v8 - intensidade corrigida
- O preset Natural Imobiliário agora é usado mesmo sem perfil de estilo treinado.
- O seletor suave/normal/forte agora realmente altera a força da edição.
- A intensidade forte ficou mais visível, mas ainda com proteção de altas-luzes.
- A intensidade suave ficou mais segura e discreta.

## Atualização visual — versão design clean
- Interface redesenhada com visual mais limpo e moderno.
- Novo cabeçalho superior com identidade visual mais agradável.
- Abas com estilo mais clean.
- Seções reorganizadas em cards para melhorar leitura e navegação.
- Campos, botões, progresso e logs com aparência mais refinada.
- Mudanças focadas apenas em design, sem alterar o fluxo principal do projeto.

## Correção v9.2 — fonte Tkinter
- Corrigido erro `_tkinter.TclError: expected integer but got "UI"`.
- Ajustado uso da fonte Segoe UI para formato compatível com Tkinter no Windows.
- Mudança apenas visual/técnica; sem alteração na lógica do agente.

## Atualização visual — v10
- Scroll corrigido nas abas Processar e Configurações.
- Adicionado modo claro e modo escuro na interface.
- Botões no cabeçalho para alternar tema visual.
- Mantida a lógica principal do projeto, com foco em usabilidade e estética.

## Atualização visual — v12
- Removido o selo “Interface clean” do cabeçalho.
- Preview de marca d’água simplificado: sem formas decorativas, mostrando apenas logo ou texto.
- Ajustes visuais em fontes para uma aparência mais limpa.
- Hover visual adicionado aos principais botões da interface.

## Atualização — v13 perfis de configuração
- Adicionado sistema de perfis de configuração na aba Configurações.
- Agora é possível salvar, carregar e excluir perfis com ajustes prontos.
- O perfil salva intensidade, preview, perfil de estilo, duplicatas, renomeação, marca d’água, galeria, EXIF e metadados.
- Os perfis são guardados na pasta `config_profiles` dentro do projeto.
- Mantidas as melhorias visuais, modo claro/escuro, hover, scroll e preview de marca d’água.

## Atualização — v14 upscale funcional
- Base visual voltou para a versão anterior aprovada, sem os refinamentos de design que não agradaram.
- Adicionada opção de upscale funcional na aba Processar.
- Upscale permite escolher 1.5x, 2x, 3x ou 4x.
- O upscale é aplicado após a melhoria da imagem e antes da marca d’água/exportações.
- Implementado localmente com Lanczos + nitidez leve, sem depender de internet.

## Atualização — v15 correção de cores "Natural Imobiliário"
Arquivo editado: `core/styled_enhancer.py` (único arquivo alterado).
Nenhum outro arquivo foi modificado.

### Problemas corrigidos:
1. **Parede amarela/cinza** — neutralize_ab de interior reforçado (-1.2, -2.5) e agora é seletivo: só aplica em pixels claros (paredes, teto), preserva móveis escuros e madeira.
2. **Branco estourado/sujo** — highlight_pull de interior subiu de 7 para 9, protege mais as altas-luzes sem escurecer meios-tons.
3. **Madeira saturada demais** — saturação de detalhes caiu de 1.05 para 1.02 com teto de 1.08. Perfil aprendido influencia menos (peso 0.25, era 0.35).
4. **Verde/céu artificial** — saturação exterior caiu de 1.08 para 1.04 com teto 1.12. Novo limitador seletivo: pixels já saturados recebem até 40% menos boost.
5. **Saturação global exagerada** — saturação agora é por-pixel: quanto mais saturado o pixel original, menos ele é empurrado. Teto geral caiu de 245 para 240.

### O que mudou tecnicamente:
- CATEGORY_PRESETS: novo campo max_saturation por categoria
- _apply_natural_real_estate_preset(): neutralização com light_mask seletiva
- _apply_saturation(): reescrita com limitador por-pixel e teto por categoria
- Nenhuma mudança na GUI, pipeline, config, ou outros módulos

## Atualização — v16 modos de cor + vibrance seletiva
Arquivos editados: `core/styled_enhancer.py`, `core/pipeline.py`, `gui/app.py`

### Novidades:
- 3 modos de cor: Natural, Vibrant, Luxury (combobox na aba Processar)
- Vibrance: satura pixels dessaturados sem explodir os já saturados
- Saturação hue-selective: limites separados por matiz (laranja/madeira, amarelo/parede, verde/vegetação, azul/céu)
- Warmth por modo: luxury = tom frio sofisticado, vibrant = levemente quente
- Neutralização de amarelo modulada pelo modo (luxury = mais neutro)
- Contraste modulado por modo
- Salvar/carregar perfis de configuração inclui o modo de cor

### O que cada modo faz:
- Natural: fiel à realidade, vibrance leve, madeira e verde contidos
- Vibrant: verde e céu mais ricos, vibrance forte em cinzas, leve calor
- Luxury: tom frio, paredes ultra-neutras, madeira sóbria, contraste elegante

### Técnico:
- COLOR_MODE_PRESETS com vibrance, saturation_mult, warmth, neutralize_mult, contrast_mult, hue_sat_limits
- _apply_saturation() reescrita com vibrance + hue masks + per-pixel protection
- Pipeline passa color_mode ao StyledEnhancer
- GUI: novo combobox ao lado de Intensidade

## Atualização — v17 brancos neutros + nitidez suave
Arquivos: `core/styled_enhancer.py`, `core/upscaler.py`

### Corrigido:
- **Brancos azulados/ciano**: neutralize_ab no canal b reduzido em todas as categorias (interior -2.5→-1.6, exterior -0.5→-0.3, detalhes -0.8→-0.5, revisar -1.2→-0.8). Luxury warmth -0.4→-0.15.
- **Pixelado/oversharpened**: sharpness cap 1.20→1.12, blur radius 0.9→1.2, learned influence reduzida.
- **Textura/claridade harsh**: contrast blend cap 0.70→0.50, max_contrast reduzido (normal 1.26→1.20, forte 1.38→1.30).
- **Upscale pixelado**: post-sharpen 1.12/-0.12→1.06/-0.06, blur 0.8→1.0.

## Atualização — v18 upscale profissional com presets
Arquivos: `core/upscaler.py` (reescrito), `core/pipeline.py` (2 linhas), `gui/app.py` (combobox preset)

### Novo pipeline de upscale:
1. Pré-denoise (NLM antes do resize para não ampliar ruído)
2. Upscale Lanczos
3. CLAHE suave + lift de sombras + proteção de altas-luzes
4. Neutralização seletiva de brancos (só pixels claros)
5. Vibrance leve (satura dessaturados, segura saturados)
6. Unsharp mask adaptativa (mais nitidez em bordas/detalhes, menos em paredes/céu)

### 3 presets:
- Natural Pro: denoise leve, CLAHE 1.4, sharpen 1.08 σ1.4, sat 1.01
- Strong Pro: denoise médio, CLAHE 1.8, sharpen 1.12 σ1.2, sat 1.03
- Luxury: denoise forte, CLAHE 1.5, sharpen 1.06 σ1.6, sat 1.00 (look premium limpo)

### Diferença do upscaler antigo:
- Antes: Lanczos + unsharp mask genérica (1 linha)
- Agora: pipeline de 6 etapas com denoise, luminância, cor e sharpening adaptativo
- Sharpening usa variância local — aplica mais em detalhes, menos em superfícies lisas

## Atualização — v19 migração para CustomTkinter
Arquivos: `gui/app.py` (reescrito visual), `requirements.txt` (+ customtkinter)
Backup da versão anterior: `gui/app_backup_v18.py`

### O que mudou:
- GUI inteira migrada de tkinter/ttk puro para CustomTkinter
- Cards com corner_radius, border sutil, padding interno generoso
- Switches modernos no lugar de checkboxes para toggles importantes
- Preset selectors visuais para Intensidade e Modo de Cor (botões estilizados)
- Segmented buttons para Fator e Preset de upscale
- Tema claro/escuro com switch no header (usa sistema nativo do CTk)
- Log e lista de pares em CTkTextbox com visual dark terminal
- Resumo visual da configuração atual na aba Processar
- Botão principal verde accent, secundários com borda transparente
- Toda a hierarquia visual mais clara (título > seção > muted)
- Espaçamento consistente entre cards e seções

### O que NÃO mudou:
- Nenhuma variável, handler ou lógica de processamento foi alterada
- _collect_options(), _start_processing(), _on_progress(), _update_ui() idênticos
- Config profiles (salvar/carregar/excluir) idênticos
- Watermark preview idêntico (mesmo algoritmo Pillow)
- Training handlers idênticos
- Pipeline, enhancer, upscaler, classifier — nenhum tocado

### Para rodar:
pip install customtkinter>=5.2.0
(ou: pip install -r requirements.txt)

## Atualização — v20 refinamento visual CustomTkinter
Arquivo: `gui/app.py` (edições cirúrgicas, nenhum outro arquivo tocado)

### Corrigido:
- Contraste dark mode: MUTED_DARK de #6B7A8D para #9CA3B4, botões secundários de #D1D5DB para #E5E7EB
- Emojis removidos dos presets (Suave/Normal/Forte, Natural/Vibrant/Luxury — texto limpo)
- Alinhamento inputs: label width 80→90, file_row padding 8→10, clear button antes do browse
- Card padding: inner 16→18 para consistência
- Preset selector: dict por instância (bug de shared dict corrigido), fonte bold no selecionado
- Abas: padding mais amplo, hover na unselected, sem espaços extras nos nomes
- Header: sem emoji, label "Claro / Escuro" no switch de tema
- Botão Processar: width fixa 200, height 46, mais proeminente
- Resumo: fundo sutil (#F3F5F8 / #141B2A), texto com capitalize, separadores |
- Barra de progresso: 8→10px altura
- Status label com text_color explícito para dark mode

## Atualização — v21 migração PySide6 Fase 1 (aba Processar)
Arquivos criados: `gui/app_qt.py` (nova GUI PySide6)
Arquivos alterados: `main.py` (PySide6 com fallback CTk), `requirements.txt` (+PySide6)
Backups: `gui/app_ctk_backup.py`, `main_ctk_backup.py`

### O que foi implementado:
- Layout 2 colunas fiel ao protótipo (left 460px + right flex)
- Title bar com nome da app
- Top bar com tabs (Processar ativo) + resumo (Intensidade/Cor/Upscale/Preview)
- Card Pastas com subcards para Entrada, Saída e Estilo
- Card Edição com SegButtonGroup para Intensidade e Modo de Cor
- Toggle switch custom para Preview e Upscale
- Card Upscale com toggle + fator segmentado
- Botão Processar primário (verde teal, 48px, destaque)
- Botão Abrir saída secundário
- Preview card com placeholder
- Bottom grid: Status (arquivo atual + progresso + barra) e Log (timestamps)
- Status bar no rodapé (pulse dot + contagem + dicas)
- Dark mode premium com tokens do CSS do mockup
- Sombras reais via QGraphicsDropShadowEffect
- QSS fiel aos tokens CSS do protótipo
- Signal bridge para thread-safe progress updates
- Todos os handlers de processamento conectados ao core.pipeline

### O que NÃO foi alterado:
- core/ — zero mudanças
- utils/ — zero mudanças
- gui/app.py — intacto (backup criado, disponível como fallback)

### O que ainda falta (fases 2-4):
- Preview antes/depois com split arrastável (Fase 2)
- Abas Configurações e Treinar Estilo (Fase 3)
- Polimento: fontes Inter, animações, hover states refinados (Fase 4)

### Para rodar:
pip install PySide6
python main.py

## Atualização — v22 correções de layout/espaçamento PySide6
Arquivo: `gui/app_qt.py` (reescrito com todas as correções)
Backup: `gui/app_qt_v21_backup.py`

### Problemas corrigidos:
1. Fundo branco entre cards — central widget, scroll area e body agora forçam bg0
2. Header/footer sobreposição — titlebar e topbar são fixedHeight, scroll fica no meio com stretch=1
3. Painel esquerdo apertado — width de 460→480-500 (min/max)
4. Botões seg cortando texto — setSizePolicy Expanding + minWidth 70
5. Inputs cortando caminho — QLineEdit usa padding em vez de height fixa no QSS
6. Preview desalinhado — minHeight 300, sizePolicy Expanding
7. Bottom grid — maxHeight 240 para não crescer demais
8. Cards — objectName removido (usava seletor por class), QSS aplicado diretamente
9. SubCard — QSS usa seletor por class name sem conflito
10. QSS global simplificado — wildcard font-family, transparent default em QWidget

## Atualização — v23 ícones + preview + layout refinado
Arquivo: `gui/app_qt.py` (reescrito)
Backup: `gui/app_qt_v22_backup.py`

### Ícones:
- Classe Icons com 13 ícones SVG inline (folder, edit, upscale, process, settings, star, intensity, palette, eye, expand, activity, list, open_folder)
- Ícones aplicados em: tabs, headers de cards, resumo superior, botões de ação

### Preview antes/depois:
- Novo widget CompareView(QWidget) com paintEvent custom
- Divisor vertical arrastável via mousePressEvent/mouseMoveEvent
- Handle circular teal com glow (como mockup)
- Labels "Antes"/"Depois" em pills com fundo semi-transparente e dots coloridos
- Corner markers nos 4 cantos (linhas L brancas)
- Clip arredondado via QPainterPath
- Placeholder com gradientes quando sem imagem
- Método set_images(before, after) para carregar par real

### Layout corrigido:
- Header 52px fixo com gradiente sutil
- Topbar 52px com ícones nas tabs e summary com ícones por item
- Summary chips com icon + label + value em layout horizontal
- Seg buttons com minWidth 80 e padding 6px 20px (elimina corte)
- Cards com spacing 12px entre eles
- Bottom row minHeight 180 maxHeight 240
- Footer 36px sem sobreposição
- Backgrounds explícitos em scroll area e body
- Zero alteração em core/

## v24.1 — Bracketing / HDR imobiliário

Implementado suporte inicial a bracketing sem alterar o motor visual existente.

Arquivos alterados/criados:
- `core/bracketing.py` — novo módulo para detectar grupos de 3/5 exposições, alinhar com OpenCV AlignMTB e fundir com MergeMertens exposure fusion.
- `core/pipeline.py` — integração opcional via opções `bracketing_enabled`, `bracketing_group_size` e `bracketing_fusion_preset`.
- `gui/app_qt.py` — novo card “Bracketing / HDR” na aba Processar, com toggle, grupo Auto/3/5 fotos e preset Natural/Janela/Interior/Luxury.
- Backups criados: `core/pipeline_backup_v23.py` e `gui/app_qt_backup_v23_before_bracketing.py`.

Fluxo:
1. Se bracketing estiver desligado, o app funciona como antes.
2. Se estiver ligado, o pipeline agrupa sequências por resolução, horário/EXIF e diferença de exposição.
3. Cada grupo gera um único arquivo `_HDR.jpg` em `00_BRACKETING_FUSOES`.
4. A fusão HDR segue pelo pipeline atual de enhance/upscale/exportação.

Testes realizados:
- `python -m py_compile main.py gui/app_qt.py core/pipeline.py core/bracketing.py`
- Teste sintético com 3 exposições gerando `IMG_0002_HDR.jpg`.

## v25 — Ajustes visuais PySide6

- Corrigida a barra nativa superior do Windows para tentar usar modo escuro via DWM quando disponível.
- Corrigidos estilos globais de QLabel/QFrame para reduzir fundos escuros duplicados/overlays em labels e cards.
- Ajustado SegGroup para calcular largura mínima pelos textos e evitar cortes nos botões.
- Refeito o card Bracketing / HDR com Grupo e Fusão em linhas separadas, corrigindo espaçamento e textos truncados.
- Melhorado carregamento de preview: procura imagens diretas e em subpastas rasas, carrega com QImageReader respeitando EXIF/orientação e atualiza status com a imagem usada.

Validação: `python -m py_compile main.py gui/app_qt.py core/pipeline.py core/bracketing.py`.

## v26 — Fluxo automático estilo Lightroom

Refeito `gui/app_qt.py` com foco em automação e fluxo familiar para fotógrafo, sem transformar o app em editor manual.

Principais mudanças:
- UI principal reorganizada em 3 áreas: fila/pastas à esquerda, preview + filmstrip no centro, automação à direita.
- Removidos controles manuais detalhados da tela principal; ajustes finos ficam em “Ajustes avançados”, recolhido por padrão.
- Painel direito agora tem controles simples: Preset, Intensidade, Modo de cor, Bracketing/HDR, Upscale e Exportação.
- Preview antes/depois continua com divisor arrastável e agora é acionado por pasta/miniatura.
- Filmstrip horizontal com miniaturas e seleção visual.
- Fila de processamento com miniaturas na lateral esquerda.
- Topbar custom frameless dark para evitar a barra branca nativa do Windows e aproximar do mockup premium.
- Botões inferiores: “Gerar preview” e “Processar lote”.
- Pipeline/core mantidos intactos; apenas a camada visual foi reescrita.

Backup criado:
- `gui/app_qt_backup_v25_before_auto_lightroom.py`

Validação:
- `python -m py_compile main.py gui/app_qt.py core/pipeline.py core/bracketing.py`

## v27 — HDR imobiliário Lightroom-like

Implementado pipeline de bracketing/HDR mais próximo do fluxo profissional descrito pelo fotógrafo:

- Agrupamento/stacking por horário/EXIF, resolução e variação de exposição.
- Priorização de grupos de 3 ou 5 fotos.
- Ordenação das exposições por ExposureBiasValue ou luminosidade média.
- Alinhamento das imagens com OpenCV AlignMTB.
- Photo Merge HDR natural com MergeMertens / fallback ponderado.
- Pós-processamento automático pós-HDR na ordem:
  - exposure
  - contraste
  - redução de aberração cromática
  - correção suave de distorção da lente
  - highlights
  - shadows
  - vibrance
  - clarity/nitidez local leve
  - correção geométrica segura por rotação leve quando necessário
- Novo preset interno: `lightroom_like`.
- UI Bracketing/HDR agora usa o preset `LR-like` por padrão.
- Opções automáticas enviadas ao pipeline:
  - `bracketing_auto_chromatic_aberration`
  - `bracketing_auto_lens_correction`
  - `bracketing_auto_geometry_correction`

Observação: correção de lente/geometria é conservadora para evitar deformar imóveis. Ajuste fino deve ser feito com fotos reais do fotógrafo.


## v28 — Suporte a RAW Canon .CR3

- Adicionado `core/raw_support.py`.
- `requirements.txt`: adicionada dependência opcional/necessária para RAW: `rawpy`.
- `utils/config.py`: extensões suportadas agora incluem `.cr3`, `.cr2`, `.nef`, `.arw`, `.dng`, `.raf`, `.rw2`, `.orf`.
- `gui/app_qt.py`: preview/lista/filmstrip agora reconhecem RAW e tentam renderizar `.CR3` com `rawpy`.
- `core/pipeline.py`: arquivos RAW são convertidos automaticamente para JPEG temporário em `00_RAW_CONVERTIDOS` antes do processamento OpenCV/Pillow.
- O arquivo RAW original é mantido como origem para cópia/preservação quando possível.
- Se `rawpy` não estiver instalado, o app informa a necessidade de instalar com `python -m pip install rawpy`.

Validação:

```powershell
python -m py_compile main.py gui/app_qt.py core/pipeline.py core/bracketing.py core/raw_support.py utils/config.py
```

## v29 — Correção preview/processamento CR3

- `core/raw_support.py`: leitura RAW mais robusta; preview tenta revelar em half-size e, se falhar, tenta extrair JPEG embutido.
- `gui/app_qt.py`: preview de RAW agora mostra mensagem clara se rawpy/LibRaw falhar em vez de ficar vazio.
- `core/pipeline.py`: conversão RAW/CR3 agora registra erros e interrompe com mensagem clara quando nenhum RAW pôde ser convertido.
- `gui/app_qt.py`: status inferior agora diferencia erro de conclusão real.

## v30 — Correção do fluxo Bracketing/HDR real

- Corrigido o problema em que brackets de 3 CR3 podiam ser processados como imagens individuais.
- Quando o usuário escolhe **Grupo: 3 fotos** ou **5 fotos**, o app força o modo HDR mesmo se o toggle não tiver sido clicado.
- A detecção de duplicatas é ignorada quando o bracketing está ativo, para não separar exposições do mesmo enquadramento.
- O agrupamento manual agora prioriza pilhas sequenciais por nome/horário, como no stacking do Lightroom.
- O resultado esperado agora é 1 imagem HDR final por grupo, por exemplo: `665A7497_CR3_HDR.jpg`.
- A comparação antes/depois de grupo HDR usa a exposição base/0EV como “antes” e a fusão final como “depois”.

## v31 — Bracketing HDR menos lavado / mais imobiliário

- Ajustado `core/bracketing.py` para evitar resultado HDR acinzentado/lavado.
- Merge HDR agora preserva parte da exposição base/0EV para manter contraste natural.
- Adicionado white balance automático conservador.
- Adicionado black point/dehaze leve pós-HDR.
- Adicionado contraste local leve em L* para recuperar textura de azulejo, box e bancada.
- Preset `LR-like` recalibrado para abrir sombras sem perder preto/contraste.
- Validação: `python -m py_compile main.py gui/app_qt.py core/pipeline.py core/bracketing.py core/raw_support.py`.

## v32 — Separação HDR puro vs Modo Automático

- Adicionada opção na UI: **Acabamento após HDR**.
- Padrão: desligado, para testar/usar **HDR puro** sem o preset Luxury/Strong interferindo.
- Quando ligado: o HDR passa depois pelo Modo Automático/StyledEnhancer.
- Pipeline atualizado com opção `bracketing_apply_auto_enhance`.
- Se desligado e o item for bracket/HDR, o app copia a fusão HDR diretamente para a saída enhanced, preservando o resultado do merge.
- Core principal de enhance/upscale continua intacto.

## v35 — Aba Treinar Estilo funcional no visual novo

- Reativei a aba **Treinar estilo** na GUI PySide6.
- A navegação superior agora alterna entre Processar, Configurações e Treinar estilo.
- A aba Treinar permite adicionar pares individuais ANTES/DEPOIS.
- A aba Treinar permite carregar pares em lote por duas pastas com arquivos de mesmo nome.
- O treinamento usa `core/style_trainer.py`, preservando a lógica antiga.
- O perfil treinado é salvo como `.json` e preenchido automaticamente em **Estilo (opcional)** na aba Processar.
- Adicionado suporte a RAW/CR3 no treinamento via conversão temporária com `rawpy` quando necessário.
- O processamento principal, bracketing, HDR e core do pipeline permanecem preservados.


## v36 — Treino separado de Bracketing/HDR

- Adicionado `core/hdr_trainer.py`.
- A aba **Treinar estilo** agora também permite treinar **Bracketing / HDR**.
- Novo fluxo HDR:
  - selecionar uma pasta com 3/5 fotos bracketadas;
  - selecionar a imagem final editada de referência;
  - adicionar grupo HDR;
  - clicar em **Treinar HDR**;
  - salvar `perfil_hdr_imobiliario.json`.
- O perfil HDR salvo pode ser usado em **Estilo (opcional)** na aba Processar.
- `core/bracketing.py` agora reconhece perfis `hdr_bracketing_profile` e aplica correções aprendidas após a fusão.
- `core/pipeline.py` passa o caminho do perfil `.json` para o processador de bracketing.
- O treino normal ANTES/DEPOIS continua funcionando.
