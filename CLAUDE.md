# CLAUDE.md — Guia para continuar este projeto

Este arquivo é destinado a qualquer IA ou desenvolvedor que vá trabalhar
neste projeto. Leia inteiro antes de fazer qualquer alteração.

---

## O que é este projeto

Um agente local (Windows) que organiza e pré-edita fotos de imóveis.
Interface gráfica feita com tkinter. Processamento com OpenCV/Pillow/NumPy.
Roda 100% offline. Não usa API externa.

---

## Regras para trabalhar neste projeto

1. **Não recrie o projeto do zero.** Sempre trabalhe sobre o código existente.
2. **Não altere funcionalidades sem explicar antes** ao usuário o que vai mudar.
3. **Teste mentalmente** cada alteração — pergunte-se se pode quebrar algo.
4. **Preserve os arquivos originais** — o sistema nunca deve alterar fotos de entrada.
5. **Mantenha comentários em português.**
6. **Atualize PROGRESSO.md** sempre que fizer uma mudança significativa.

---

## Como o projeto está organizado

```
realestate_photo_agent/
│
├── main.py                  ← PONTO DE ENTRADA. Abre a GUI. Execute: python main.py
│
├── gui/
│   └── app.py               ← INTERFACE GRÁFICA (tkinter, 3 abas)
│                                - Aba Processar: pastas + opções + botão processar
│                                - Aba Configurações: watermark, renomeação, galeria, EXIF
│                                - Aba Treinar Estilo: pares antes/depois → perfil .json
│
├── core/                    ← MÓDULOS DE PROCESSAMENTO (cada um faz uma coisa)
│   ├── pipeline.py          ← ORQUESTRADOR CENTRAL — chama todos os módulos abaixo
│   ├── classifier.py        ← classifica imagem em interior/exterior/detalhes/revisar
│   ├── enhancer.py          ← melhorias padrão (exposição, contraste, nitidez, etc.)
│   ├── styled_enhancer.py   ← melhorias baseadas em perfil treinado (.json)
│   ├── style_trainer.py     ← analisa pares antes/depois e gera perfil de estilo
│   ├── exporter.py          ← exporta em 3 perfis (HQ, Instagram, WhatsApp)
│   ├── watermark.py         ← marca d'água (texto ou logo PNG)
│   ├── duplicates.py        ← detecção de duplicatas via perceptual hash (pHash)
│   ├── renamer.py           ← renomeação inteligente (IMOVEL_001_interior_01.jpg)
│   ├── contact_sheet.py     ← gera folha de contato (grade de thumbnails)
│   ├── before_after.py      ← gera imagens de comparação lado a lado
│   ├── gallery.py           ← gera galeria HTML com lightbox
│   ├── exif_handler.py      ← lê/preserva/adiciona metadados EXIF
│   └── reporter.py          ← gera relatório .txt final
│
├── utils/
│   └── config.py            ← TODAS AS CONSTANTES e parâmetros ajustáveis
│
├── requirements.txt         ← dependências pip (opencv-python, numpy, Pillow)
├── iniciar.bat              ← atalho Windows para abrir o programa
├── README.md                ← documentação para o usuário final
├── CLAUDE.md                ← este arquivo (instruções para devs/IAs)
├── PROGRESSO.md             ← estado atual, bugs, próximos passos
└── PROMPT_CONTINUAR.txt     ← prompt pronto para copiar em outra IA
```

---

## Fluxo de dados principal

```
Usuário clica "Processar"
        │
        ▼
gui/app.py → coleta opções → cria ProcessingPipeline
        │
        ▼
core/pipeline.py._run()  (roda em thread separada)
        │
        ├─ 1. duplicates.py     → separa duplicatas
        ├─ 2. shutil.copy2      → copia originais
        ├─ 3. classifier.py     → classifica cada imagem
        ├─ 4. enhancer.py       → aplica melhorias (ou styled_enhancer.py se tiver perfil)
        ├─ 5. exif_handler.py   → preserva metadados
        ├─ 6. watermark.py      → aplica marca d'água
        ├─ 7. exporter.py       → gera versões HQ/IG/WA
        ├─ 8. renamer.py        → renomeia arquivos
        ├─ 9. before_after.py   → gera comparações
        ├─10. contact_sheet.py  → gera folha de contato
        ├─11. gallery.py        → gera galeria HTML
        └─12. reporter.py       → gera relatório .txt
```

---

## Dependências

Apenas 3 bibliotecas externas (instaladas via pip):
- `opencv-python` — processamento de imagem
- `numpy` — cálculos numéricos
- `Pillow` — manipulação de imagens (marca d'água, EXIF, thumbnails)

A GUI usa `tkinter`, que vem embutido no Python.

Opcional: `onnxruntime` para classificação com modelo de IA (não está em uso atualmente).

---

## Onde ficam as configurações

Arquivo: `utils/config.py`

Contém todas as constantes: nomes de pastas, parâmetros de melhoria de imagem,
perfis de exportação e limiares do classificador. Qualquer ajuste de
comportamento padrão deve ser feito aqui.

**Atenção:** Existem 3 constantes de pasta definidas em `core/pipeline.py`
(FOLDER_DUPLICATES, FOLDER_COMPARISONS, FOLDER_THUMBNAILS) que deveriam
estar em `config.py`. Isso é uma inconsistência conhecida — veja PROGRESSO.md.

---

## Como a GUI se comunica com o pipeline

1. `gui/app.py` monta um dicionário `options` com todas as escolhas do usuário
2. Passa esse dicionário para `ProcessingPipeline.__init__()`
3. O pipeline roda em thread separada (daemon) para não travar a interface
4. A cada etapa, chama `progress_callback(mensagem, percentual)`
5. O callback usa `self.after()` do tkinter para atualizar a interface na thread principal

---

## O que cada módulo sabe/não sabe

- Cada módulo em `core/` funciona de forma independente — pode ser testado isoladamente
- Nenhum módulo sabe da GUI — só o pipeline conhece todos os módulos
- A GUI só conhece o pipeline e o style_trainer
- O `config.py` é acessado diretamente por quem precisa (sem intermediários)

---

## Convenções do código

- Linguagem dos comentários e docstrings: português
- Type hints usados em assinaturas de funções (sintaxe Python 3.10+: `str | None`)
- Cada módulo tem docstring no topo explicando o que faz
- Métodos privados começam com `_`
- Sem testes unitários no momento (área de melhoria)

## Nota para próximas IAs — perfis de configuração
O projeto agora possui um recurso de perfis na interface (`gui/app.py`). Os arquivos JSON ficam em `config_profiles/`. Preserve esse recurso ao alterar configurações ou interface.

## Histórico recente
- v14_upscale: voltou para a base visual anterior e adicionou upscale funcional local na aba Processar.
