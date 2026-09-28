# Caixa Inteligente

Sistema de autoatendimento de supermercado com visão computacional. O operador
posiciona os produtos na **Área de Detecção** e o sistema reconhece os itens
para montar a venda automaticamente.

Este repositório contém a aplicação desktop (Python + OpenCV + Tkinter)
responsável pela interface do caixa.

## Estado atual

| Feature | Issue | Situação |
| --- | --- | --- |
| Exibição da Câmera | [#7](https://github.com/rickboone1/projeto-integrador/issues/7) | Implementada |
| Status do Caixa | [#8](https://github.com/rickboone1/projeto-integrador/issues/8) | Espaço reservado no layout |
| Exibição do Peso | [#9](https://github.com/rickboone1/projeto-integrador/issues/9) | Espaço reservado no layout |

## Requisitos

* Python 3.11 ou superior
* Tkinter (`sudo apt install python3-tk` no Debian/Ubuntu)
* Uma câmera acessível pelo sistema operacional, ou um arquivo de vídeo para testes

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Execução

```bash
python -m caixa_inteligente.app
```

O aplicativo abre a janela principal e exibe o vídeo da câmera padrão na Área
de Detecção. Para testar sem uma webcam física, aponte para um arquivo de vídeo:

```bash
CAIXA_CAMERA_SOURCE=videos/demo_produtos.mp4 python -m caixa_inteligente.app
```

### Variáveis de ambiente

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `CAIXA_CAMERA_SOURCE` | `0` | Índice da câmera (`0`, `1`, ...) ou caminho de vídeo/URL |
| `CAIXA_CAMERA_WIDTH` | `1280` | Largura solicitada à câmera |
| `CAIXA_CAMERA_HEIGHT` | `720` | Altura solicitada à câmera |
| `CAIXA_CAMERA_FPS` | `30` | Taxa de quadros solicitada à câmera |
| `CAIXA_FONT_FAMILY` | `Inter` | Fonte da interface (issue #2) |

## Diagnóstico da câmera

Antes de abrir o caixa no equipamento real, verifique se a câmera está
transmitindo:

```bash
python tools/verificar_camera.py                # câmera padrão
python tools/verificar_camera.py --source 1     # segunda câmera
python tools/verificar_camera.py --source videos/demo_produtos.mp4
```

O utilitário informa quantos quadros foram recebidos, o FPS medido e o número
de falhas de leitura.

## Testes

```bash
pytest                       # com servidor gráfico
xvfb-run -a pytest           # em ambiente headless (CI)
```

Os testes cobrem o buffer thread-safe, o serviço de captura (reconexão,
métricas e ritmo de exibição), a Área de Detecção e a integração completa
captura → interface.

Para capturar evidências visuais da interface em execução:

```bash
xvfb-run -a python tools/capturar_evidencia.py \
    --source videos/demo_produtos.mp4 --output docs/evidencias
```

## Estrutura

```
src/caixa_inteligente/
├── app.py                  # ponto de entrada
├── config.py               # configuração e identidade visual (issues #1–#3)
├── camera/
│   ├── capture.py          # captura em thread separada, reconexão e métricas
│   └── frame_buffer.py     # buffer thread-safe do quadro mais recente
└── ui/
    ├── detection_area.py   # Área de Detecção (exibição do vídeo)
    ├── panels.py           # painéis laterais de status
    └── main_window.py      # layout e ciclo de atualização
tools/
├── verificar_camera.py     # diagnóstico da câmera
└── capturar_evidencia.py   # captura de telas para aceite
```

## Documentação

* [Feature 1 — Exibição da Câmera](docs/feature-1-exibicao-camera.md):
  arquitetura, critérios de aceitação verificados e decisões técnicas.

## Identidade visual

Definida nas issues [#1](https://github.com/rickboone1/projeto-integrador/issues/1)
(cores), [#2](https://github.com/rickboone1/projeto-integrador/issues/2) (fonte
Inter) e [#3](https://github.com/rickboone1/projeto-integrador/issues/3) (logo).
As constantes estão centralizadas em `src/caixa_inteligente/config.py`.
