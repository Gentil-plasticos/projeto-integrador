"""Serviço de captura de vídeo executado em thread separada.

Responsabilidades:

* abrir a câmera padrão configurada pelo sistema;
* ler continuamente os quadros em uma thread dedicada;
* publicar cada quadro no :class:`FrameBuffer` para consumo da interface;
* reconectar automaticamente quando a câmera é desconectada ou falha.

A interface nunca chama ``cv2.VideoCapture.read()`` diretamente — todo o I/O
de vídeo ocorre nesta thread, conforme a nota técnica da issue #7, para que a
interface permaneça responsiva.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

import cv2
import numpy as np

from ..config import CameraConfig
from .frame_buffer import FrameBuffer

logger = logging.getLogger(__name__)


class CameraState(str, Enum):
    """Estado do serviço de captura."""

    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"


@dataclass
class CameraStats:
    """Métricas de captura para diagnóstico e testes."""

    frames_captured: int = 0
    frames_dropped: int = 0
    read_failures: int = 0
    reconnects: int = 0
    last_frame_at: float | None = None
    _timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=90))

    def register_frame(self, timestamp: float) -> None:
        """Contabiliza um frame capturado com sucesso."""
        self.frames_captured += 1
        self.last_frame_at = timestamp
        self._timestamps.append(timestamp)

    @property
    def fps(self) -> float:
        """FPS medido sobre a janela dos últimos frames."""
        if len(self._timestamps) < 2:
            return 0.0
        span = self._timestamps[-1] - self._timestamps[0]
        if span <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / span


def open_capture(source: int | str, config: CameraConfig) -> cv2.VideoCapture:
    """Abre o dispositivo de captura e aplica a resolução desejada.

    Função isolada para permitir substituição nos testes (injeção de um vídeo
    ou de uma câmera simulada).
    """
    backend = cv2.CAP_V4L2 if isinstance(source, int) else cv2.CAP_ANY
    capture = cv2.VideoCapture(source, backend)
    if not capture.isOpened() and isinstance(source, int):
        # Alguns ambientes não expõem o backend V4L2 explicitamente.
        capture.release()
        capture = cv2.VideoCapture(source)
    if capture.isOpened():
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
        capture.set(cv2.CAP_PROP_FPS, config.target_fps)
    return capture


def read_source_fps(capture) -> float:
    """Lê a taxa de quadros declarada pela fonte de vídeo.

    Retorna ``0.0`` quando o valor não é confiável (fonte ao vivo que não
    informa FPS, ou valor fora da faixa plausível). O resultado é usado para
    regular o ritmo de leitura de arquivos de vídeo, garantindo a exibição em
    tempo real em vez de consumir o arquivo o mais rápido possível.
    """
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
    except Exception:  # pragma: no cover - proteção defensiva
        return 0.0
    if not 1.0 <= fps <= 120.0:
        return 0.0
    return fps


class CameraService:
    """Lê a câmera continuamente em uma thread dedicada."""

    def __init__(
        self,
        config: CameraConfig,
        buffer: FrameBuffer | None = None,
        capture_factory=open_capture,
    ) -> None:
        self.config = config
        self.buffer = buffer if buffer is not None else FrameBuffer()
        self.stats = CameraStats()
        self._capture_factory = capture_factory

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state = CameraState.IDLE
        self._state_lock = threading.Lock()
        self._error: str | None = None

    # -- Estado -----------------------------------------------------------

    @property
    def state(self) -> CameraState:
        with self._state_lock:
            return self._state

    @property
    def error(self) -> str | None:
        """Última mensagem de erro de captura, se houver."""
        with self._state_lock:
            return self._error

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _set_state(self, state: CameraState, error: str | None = None) -> None:
        with self._state_lock:
            self._state = state
            self._error = error

    # -- Ciclo de vida ----------------------------------------------------

    def start(self) -> None:
        """Inicia a thread de captura (idempotente)."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="camera-capture", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Sinaliza a parada e aguarda o encerramento da thread."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
        self.buffer.clear()
        self._set_state(CameraState.STOPPED)

    # -- Loop de captura --------------------------------------------------

    def _run(self) -> None:
        """Loop principal: conecta, lê frames e reconecta quando necessário."""
        while not self._stop_event.is_set():
            self._set_state(
                CameraState.CONNECTING
                if self.stats.reconnects == 0
                else CameraState.RECONNECTING
            )
            capture = self._open()

            if not capture.isOpened():
                capture.release()
                self._set_state(
                    CameraState.RECONNECTING,
                    f"Não foi possível abrir a câmera (fonte: {self.config.source!r}).",
                )
                logger.warning(
                    "Câmera indisponível (fonte=%r). Nova tentativa em %.1fs.",
                    self.config.source,
                    self.config.reconnect_delay_s,
                )
                self.stats.reconnects += 1
                if self._stop_event.wait(self.config.reconnect_delay_s):
                    break
                continue

            self._set_state(CameraState.STREAMING)
            logger.info("Câmera conectada (fonte=%r).", self.config.source)
            failures = 0

            # Fontes de arquivo entregam quadros muito mais rápido que o tempo
            # real (ex.: ~900 fps). O ritmo é limitado ao FPS declarado para
            # que a exibição seja fiel à velocidade original.
            pacing_fps = read_source_fps(capture) if isinstance(
                self.config.source, str
            ) else 0.0
            frame_interval = 1.0 / pacing_fps if pacing_fps > 0 else 0.0
            next_frame_at = 0.0

            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    failures += 1
                    self.stats.read_failures += 1
                    if failures >= self.config.max_consecutive_failures:
                        self._set_state(
                            CameraState.RECONNECTING, "Falha consecutiva de leitura."
                        )
                        break
                    # Pequena pausa evita busy-wait em falha persistente.
                    self._stop_event.wait(0.01)
                    continue

                failures = 0
                timestamp = time.monotonic()
                self.buffer.publish(frame, timestamp)
                self.stats.register_frame(timestamp)

                if frame_interval > 0:
                    next_frame_at += frame_interval
                    delay = next_frame_at - time.monotonic()
                    if delay > 0:
                        self._stop_event.wait(delay)
                    elif delay < -1.0:
                        # Atraso grande (ex.: máquina sobrecarregada): realinha
                        # o relógio em vez de tentar recuperar o atraso.
                        next_frame_at = time.monotonic()

            capture.release()
            if self._stop_event.is_set():
                break

            self.stats.reconnects += 1
            if self._stop_event.wait(self.config.reconnect_delay_s):
                break

        self.buffer.clear()
        self._set_state(CameraState.STOPPED)

    def _open(self) -> cv2.VideoCapture:
        try:
            return self._capture_factory(self.config.source, self.config)
        except Exception as exc:  # pragma: no cover - proteção defensiva
            logger.exception("Erro ao abrir a câmera: %s", exc)
            return cv2.VideoCapture()


# ---------------------------------------------------------------------------
# Utilitários de descoberta de dispositivos
# ---------------------------------------------------------------------------

def list_available_cameras(max_devices: int = 5) -> list[int]:
    """Retorna os índices de câmeras abertas com sucesso.

    Usado pelo utilitário de diagnóstico ``tools/verificar_camera.py``.
    """
    found: list[int] = []
    for index in range(max_devices):
        capture = cv2.VideoCapture(index)
        try:
            if capture.isOpened():
                ok, _ = capture.read()
                if ok:
                    found.append(index)
        finally:
            capture.release()
    return found


def placeholder_frame(width: int = 1280, height: int = 720) -> np.ndarray:
    """Gera um quadro neutro para exibição quando não há sinal de vídeo.

    Mantém a área de detecção com o fundo escuro definido no layout, em vez de
    deixar um espaço vazio.
    """
    frame = np.full((height, width, 3), 16, dtype=np.uint8)
    return frame
