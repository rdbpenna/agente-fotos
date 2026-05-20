# 🏠 Agente de Fotos Imobiliárias — MVP

Ferramenta local para Windows que automatiza a organização e pré-edição de fotos de imóveis.
Feita em Python com interface gráfica (tkinter). Não precisa de internet para funcionar.

**Status:** MVP funcional — em fase de testes e ajustes.

---

## O que faz

Você seleciona uma pasta com fotos de imóveis, clica em "Processar" e o sistema:

1. Faz backup das fotos originais (nunca altera os arquivos de entrada)
2. Detecta e separa fotos duplicadas
3. Classifica cada foto em: interior, exterior, detalhes ou revisar
4. Aplica melhorias automáticas (exposição, contraste, nitidez, ruído, perspectiva)
5. Exporta em 3 perfis: alta qualidade, Instagram e WhatsApp
6. Opcionalmente: marca d'água, renomeação inteligente, comparação antes/depois
7. Gera uma galeria HTML, folha de contato e relatório completo em .txt

---

## Pré-requisitos

- Windows 10 ou 11
- Python 3.10 ou superior (baixe em python.org — marque "Add to PATH" na instalação)

---

## Instalação

Abra o terminal (PowerShell ou Prompt de Comando) e execute:

```cmd
cd "CAMINHO_DA_PASTA_DO_PROJETO"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Substitua `CAMINHO_DA_PASTA_DO_PROJETO` pelo caminho real.
Se o caminho tiver espaços, use aspas duplas.

---

## Como executar

**Opção A — pelo terminal:**
```cmd
venv\Scripts\activate
python main.py
```

**Opção B — atalho rápido:**
Dê dois cliques no arquivo `iniciar.bat`.

---

## Interface — 3 abas

| Aba | O que faz |
|-----|-----------|
| **▶ Processar** | Seleciona pastas, escolhe opções e processa as fotos |
| **⚙ Configurações** | Marca d'água, renomeação, galeria, metadados |
| **🎓 Treinar Estilo** | Ensina o agente com pares de fotos antes/depois |

---

## Estrutura de saída gerada

```
Pasta_de_Saida/
├── 00_DUPLICATAS/            ← fotos duplicadas separadas
├── 01_ORIGINAIS/             ← cópias de segurança intactas
├── 02_CLASSIFICADAS/
│   ├── interior/
│   ├── exterior/
│   ├── detalhes/
│   └── revisar/
├── 03_MELHORADAS/            ← fotos com melhorias aplicadas
├── 04_EXPORTACOES/
│   ├── alta_qualidade/       ← JPEG 95%
│   ├── instagram/            ← 1080px, JPEG 85%
│   └── whatsapp/             ← 1280px, JPEG 75%
├── 05_COMPARACOES/           ← imagens lado a lado antes/depois
├── 06_THUMBNAILS/            ← miniaturas
├── folha_contato.jpg
├── galeria.html
└── relatorio_processamento.txt
```

---

## Resolução de problemas

| Problema | Solução |
|----------|---------|
| `python` não é reconhecido | Reinstale Python marcando "Add to PATH" |
| Erro de ExecutionPolicy no PowerShell | Execute: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Caminho com espaços dá erro | Use aspas duplas: `cd "C:\Meu Caminho"` |
| Erro ao instalar OpenCV | Tente: `pip install opencv-python-headless` |
| Fotos não aparecem | Verifique se são .jpg, .png, .bmp, .tiff ou .webp |

---

## Documentação para desenvolvedores

- `CLAUDE.md` — instruções para IAs e desenvolvedores continuarem o projeto
- `PROGRESSO.md` — estado atual, bugs conhecidos e próximos passos
- `PROMPT_CONTINUAR.txt` — prompt pronto para abrir em outra IA

---

## Licença

MIT — use, modifique e distribua livremente.

## v7 — Intensidade, Preview e Natural Imobiliário

A versão v7 adiciona controles para evitar o problema de a edição ficar forte demais ou fraca demais.

Novidades:

- **Intensidade**: `suave`, `normal` e `forte`.
- **Modo preview**: processa apenas a primeira foto para teste rápido.
- **Preset base Natural Imobiliário**: abre sombras e meios-tons, protege altas-luzes e mantém aparência natural.
- **Perfis por categoria**: interior, exterior, detalhes e revisar recebem ajustes diferentes.
- **Estilo aprendido com limites**: o estilo treinado influencia o resultado, mas não domina a foto nem deve estourar brancos.

Sugestão de uso:

1. Comece em `normal` com o modo preview ligado.
2. Use `forte` apenas em fotos sem vida/apagadas.
3. Use `suave` quando a foto já estiver boa e você só quiser acabamento leve.
4. Depois de aprovar o preview, desmarque o modo preview e processe o lote.


## Atualização v8 - intensidade corrigida
- O preset Natural Imobiliário agora é usado mesmo sem perfil de estilo treinado.
- O seletor suave/normal/forte agora realmente altera a força da edição.
- A intensidade forte ficou mais visível, mas ainda com proteção de altas-luzes.
- A intensidade suave ficou mais segura e discreta.


## Interface visual mais clean
Esta versão recebeu uma melhoria visual focada em estética e organização da interface, com layout mais limpo, cartões por seção e aparência mais moderna.

### Correção de abertura da interface
Caso versões anteriores tenham mostrado o erro `expected integer but got "UI"`, esta versão corrige a forma como a fonte Segoe UI é aplicada no Tkinter.

## Tema visual e scroll
A interface agora conta com:
- scroll funcional nas abas com muito conteúdo
- modo claro
- modo escuro
- alternância de tema direto no cabeçalho

## Ajustes visuais recentes
A interface recebeu novos refinamentos de design:
- remoção do selo decorativo no topo
- preview de marca d’água mais limpo
- fontes refinadas
- hover visual nos botões

## Perfis de configuração
A partir da v13, a aba **Configurações** permite salvar e carregar perfis prontos.

Exemplos de uso:
- Remax padrão
- Imóvel luxo
- Sem marca d’água
- Cliente Instagram

Os perfis ficam salvos em `config_profiles/` e guardam opções como intensidade, marca d’água, logo, posição, opacidade, galeria, EXIF e renomeação.

## Upscale funcional
A aba Processar agora possui uma opção de Upscale. Ao ativar, o sistema aumenta a resolução das fotos melhoradas antes das exportações finais.

Fatores disponíveis: 1.5x, 2x, 3x e 4x. O recomendado é 2x para uso geral.

O upscale é local, usando interpolação Lanczos com nitidez leve. Não é uma IA generativa e não inventa detalhes, mas aumenta o tamanho final com boa qualidade para entregas maiores.
