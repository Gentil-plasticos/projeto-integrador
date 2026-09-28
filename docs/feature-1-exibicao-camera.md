# Feature 1 — Exibição da Câmera (issue #7)

Documentação da implementação da exibição do vídeo da câmera na Área de
Detecção, conforme a [issue #7](https://github.com/rickboone1/projeto-integrador/issues/7).

## Objetivo

> **Como** operador do caixa inteligente
> **eu quero** visualizar o vídeo da câmera em tempo real
> **para que** eu possa posicionar corretamente os produtos na área de detecção.

## Arquitetura

O fluxo de dados separa completamente o I/O de vídeo da renderização da
interface:

```
┌──────────────────────┐   publish()   ┌──────────────┐   latest()   ┌──────────────────┐
│ Thread de captura    │ ────────────► │ FrameBuffer  │ ───────────► │ Loop da interface│
│ (CameraService)      │               │ (thread-safe)│              │ (Tkinter after)  │
│ cv2.VideoCapture.read│               │ 1 quadro     │              │ Canvas + Pillow  │
└──────────────────────┘               └──────────────┘              └──────────────────┘
```

### Por que uma thread separada

A nota técnica da issue exige explicitamente:

> Atualização dos frames em thread separada para evitar travamentos da interface.

`cv2.VideoCapture.read()` é uma chamada bloqueante. Se fosse executada no
thread do Tkinter, cada leitura travaria o processamento de eventos — a janela
deixaria de responder a redimensionamento, cliques e fechamento. Toda a captura
ocorre em `CameraService`, que roda em uma thread própria (`camera-capture`).

### Por que apenas o quadro mais recente é mantido

`FrameBuffer` guarda **somente o último quadro**, descartando os anteriores. Se
a interface estiver momentaneamente mais lenta que a câmera, uma fila
acumularia quadros antigos e o vídeo exibido ficaria progressivamente atrasado
em relação à realidade — o oposto do requisito de tempo real. O descarte
mantém a latência constante e o uso de memória limitado.

### Por que a thread de vídeo nunca toca na interface

O Tkinter não é thread-safe: manipular widgets fora do thread principal causa
falhas intermitentes e travamentos difíceis de reproduzir. A sincronização
ocorre pelo buffer, e o desenho acontece no thread principal através de
`widget.after(refresh_interval_ms)`, que reprograma a si mesmo.

### Ritmo de exibição

Câmeras ao vivo entregam quadros no ritmo do hardware. Arquivos de vídeo, no
entanto, são lidos tão rápido quanto o disco permite — na medição inicial, o
vídeo de teste de 30 fps era consumido a **924 fps**, esgotando o arquivo em
poucos segundos e provocando reconexões em cascata.

`read_source_fps()` consulta o FPS declarado pela fonte e o loop de captura
regula a leitura por `threading.Event.wait()`. O ritmo só é aplicado a fontes
que não são dispositivos locais (caminhos/URLs), preservando a captura ao vivo
sem atraso artificial.

## Requisitos × implementação

| Regra de negócio | Onde é atendida |
| --- | --- |
| O vídeo deve ser exibido na área principal | `DetectionArea` ocupa a região central com `expand=True` |
| A transmissão deve ocorrer em tempo real | Thread de captura + ciclo de atualização a cada 33 ms |
| A câmera padrão configurada deve ser utilizada | `CameraConfig.source` (padrão `0`), sobrescrevível por ambiente |
| O vídeo deve permanecer ativo durante toda a operação | `CameraService` reconecta automaticamente em falhas |

## Critérios de aceitação verificados

| Critério | Verificação | Evidência |
| --- | --- | --- |
| O vídeo da câmera é exibido na área de detecção | `test_window_shows_camera_video_on_startup` | `docs/evidencias/area_deteccao_1.png` |
| O vídeo é atualizado continuamente em tempo real | `test_video_keeps_updating_in_real_time` | 3 capturas distintas; 266 quadros renderizados |
| A área de visualização respeita o layout definido | `test_layout_has_detection_area_and_sidebar` | painel lateral fixo de 320 px |
| O operador consegue visualizar os produtos posicionados | Redimensionamento com preservação de proporção (letterbox) | `test_frame_is_scaled_preserving_aspect_ratio` |

### Cenários da issue

**Cenário 1 — Inicialização da câmera**

* **Dado que** o sistema foi iniciado
* **Quando** a tela principal for carregada
* **Então** o vídeo da câmera deve ser exibido na área de detecção

Verificado por `test_window_shows_camera_video_on_startup`, que inicia a janela
real, aguarda o primeiro quadro e confirma a presença do item de imagem no
canvas. Enquanto a câmera não fornece quadros, a área exibe a mensagem
"Aguardando sinal da câmera..." em vez de ficar vazia.

**Cenário 2 — Monitoramento do produto**

* **Dado que** a câmera está ativa
* **Quando** um produto for colocado em frente à câmera
* **Então** ele deve ser visível na área de detecção

Verificado por `test_video_keeps_updating_in_real_time` (novos quadros chegam
continuamente) e pelas três capturas de tela consecutivas da execução real, que
registram quadros diferentes com 16.504 e 19.645 pixels alterados entre elas.

## Resultado medido na execução real

Execução com `videos/demo_produtos.mp4` (1280×720, 30 fps):

| Métrica | Valor |
| --- | --- |
| Quadros capturados | 267 |
| FPS medido | 30,0 |
| Falhas de leitura | 0 |
| Reconexões | 0 |
| Quadros renderizados na interface | 266 |

A diferença de um quadro entre captura e renderização é o comportamento
esperado do descarte do buffer no instante da última leitura.

## Resiliência

| Situação | Comportamento |
| --- | --- |
| Câmera desconectada na inicialização | Estado "Conectando"; novas tentativas a cada 2 s |
| Câmera desconectada durante a operação | Estado "Reconectando"; reabre o dispositivo |
| Falhas consecutivas de leitura | Reabre o dispositivo após 30 falhas |
| Câmera volta a responder | Retoma a transmissão automaticamente |
| Sem sinal de vídeo | Mensagem centralizada na Área de Detecção |

O painel "Status da Câmera" reflete o estado atual e exibe o contador de quadros
e o FPS medido, permitindo ao operador confirmar rapidamente que o vídeo está
ativo.

## Integração futura com YOLO

A nota técnica da issue menciona o uso do YOLO V8. A arquitetura já está
preparada para essa integração:

* a detecção deve consumir quadros de `FrameBuffer.latest()` ou receber os
  quadros publicados pelo `CameraService`;
* o processamento de inferência deve ocorrer em thread separada da interface,
  pelo mesmo motivo que a captura;
* a sobreposição de resultados (caixas delimitadoras) pode ser desenhada no
  `Canvas` da `DetectionArea`, que já reserva a tag `overlay` para elementos
  gráficos.

O retângulo-guia e a linha de varredura exibidos na área de detecção seguem a
referência visual da [issue #4](https://github.com/rickboone1/projeto-integrador/issues/4)
e sinalizam o enquadramento esperado para a análise.

## Decisões técnicas

| Decisão | Justificativa |
| --- | --- |
| `opencv-python-headless` | A exibição usa Tkinter + Pillow; a variante headless evita conflito de janelas nativas do OpenCV e reduz dependências |
| Tkinter para a interface | Biblioteca padrão do Python, sem dependências externas de GUI; adequada ao hardware modesto do caixa |
| Desenho via `Canvas` + `ImageTk.PhotoImage` | Controle preciso do redimensionamento com preservação de proporção e suporte a sobreposições |
| Descarte do quadro antigo no buffer | Mantém a latência constante e o uso de memória limitado |
| Configuração por variáveis de ambiente | Permite testar com vídeo sem alterar código e ajustar a câmera no equipamento real |

## Testes

```
tests/test_frame_buffer.py     — buffer thread-safe, concorrência, descarte
tests/test_camera_service.py   — captura em thread, reconexão, métricas, ritmo
tests/test_detection_area.py   — renderização, proporção, mensagens, sobreposição
tests/test_main_window.py      — integração captura → interface (critérios de aceitação)
tests/test_config.py           — câmera padrão, ambiente, identidade visual
```

Execução:

```bash
xvfb-run -a pytest
```
