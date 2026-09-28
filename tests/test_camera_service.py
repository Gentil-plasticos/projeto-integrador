"""Testes do serviço de captura (thread separada, reconexão e métricas)."""

from __future__ import annotations

import time

import cv2
import numpy as np
import pytest

from caixa_inteligente.camera.capture import (
    CameraService,
    CameraState,
    read_source_fps,
)
from caixa_inteligente.camera.frame_buffer import FrameBuffer
from caixa_inteligente.config import CameraConfig


class FakeCapture:
    """Substituto de ``cv2.VideoCapture`` para testes determinísticos."""

    def __init__(
        self,
        opened: bool = True,
        frames: int | None = None,
        frame_value: int = 42,
        delay: float = 0.0,
        fail_after: int | None = None,
        source_fps: float = 0.0,
    ) -> None:
        self.opened = opened
        self.frames = frames
        self.frame_value = frame_value
        self.delay = delay
        self.fail_after = fail_after
        self.source_fps = source_fps
        self.reads = 0
        self.released = False
        self.settings: dict[int, float] = {}

    def isOpened(self) -> bool:  # noqa: N802 - segue a API do OpenCV
        return self.opened

    def read(self):
        if self.delay:
            time.sleep(self.delay)
        if self.frames is not None and self.reads >= self.frames:
            return False, None
        if self.fail_after is not None and self.reads >= self.fail_after:
            self.reads += 1
            return False, None
        self.reads += 1
        image = np.full((4, 4, 3), self.frame_value, dtype=np.uint8)
        return True, image

    def set(self, prop, value):  # noqa: A003 - segue a API do OpenCV
        self.settings[prop] = value
        return True

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return self.source_fps
        return 0.0

    def release(self) -> None:
        self.released = True


def _factory(capture: FakeCapture):
    return lambda source, config: capture


def test_service_publishes_frames_in_background_thread():
    capture = FakeCapture(delay=0.005)
    buffer = FrameBuffer()
    service = CameraService(
        CameraConfig(reconnect_delay_s=0.05), buffer, _factory(capture)
    )

    service.start()
    deadline = time.time() + 3
    while buffer.published_count < 5 and time.time() < deadline:
        time.sleep(0.02)

    assert buffer.published_count >= 5
    assert service.state is CameraState.STREAMING
    assert service.stats.frames_captured >= 5

    service.stop()
    assert capture.released
    assert service.state is CameraState.STOPPED


def test_service_never_blocks_caller():
    """``start`` retorna imediatamente; a leitura ocorre em outra thread."""
    capture = FakeCapture(delay=0.5)
    service = CameraService(CameraConfig(), FrameBuffer(), _factory(capture))

    started = time.monotonic()
    service.start()
    elapsed = time.monotonic() - started

    assert elapsed < 0.2, "start() não deve aguardar a captura"
    service.stop(timeout=2)


def test_service_reconnects_when_camera_unavailable():
    """Sem câmera, o serviço tenta reconectar em vez de encerrar."""
    attempts = {"count": 0}

    def factory(source, config):
        attempts["count"] += 1
        return FakeCapture(opened=False)

    service = CameraService(
        CameraConfig(reconnect_delay_s=0.02), FrameBuffer(), factory
    )
    service.start()
    time.sleep(0.3)
    service.stop()

    assert attempts["count"] >= 2, "deve haver múltiplas tentativas de reconexão"
    assert service.stats.reconnects >= 2


def test_service_recovers_when_camera_appears():
    """Cenário 1 da issue: câmera disponível após tentativas falhas."""
    state = {"opened": False}
    captures: list[FakeCapture] = []

    def factory(source, config):
        capture = FakeCapture(opened=state["opened"], delay=0.002)
        captures.append(capture)
        return capture

    buffer = FrameBuffer()
    service = CameraService(
        CameraConfig(reconnect_delay_s=0.02), buffer, factory
    )
    service.start()

    time.sleep(0.15)
    assert buffer.published_count == 0

    state["opened"] = True
    deadline = time.time() + 3
    while buffer.published_count == 0 and time.time() < deadline:
        time.sleep(0.02)

    assert buffer.published_count > 0, "captura deve iniciar quando a câmera aparece"
    assert service.state is CameraState.STREAMING
    service.stop()


def test_service_reopens_after_consecutive_read_failures():
    """Falhas seguidas de leitura disparam reabertura do dispositivo."""
    first = FakeCapture(fail_after=3, delay=0.001)
    second = FakeCapture(delay=0.002)
    captures = [first, second]

    def factory(source, config):
        return captures.pop(0) if captures else second

    buffer = FrameBuffer()
    service = CameraService(
        CameraConfig(reconnect_delay_s=0.01, max_consecutive_failures=5),
        buffer,
        factory,
    )
    service.start()

    # Aguarda a reabertura do dispositivo após as falhas consecutivas.
    deadline = time.time() + 4
    while service.stats.reconnects == 0 and time.time() < deadline:
        time.sleep(0.02)

    assert service.stats.read_failures > 0
    assert service.stats.reconnects >= 1

    # Após reconectar, a captura deve voltar a publicar quadros.
    baseline = buffer.published_count
    deadline = time.time() + 3
    while buffer.published_count <= baseline and time.time() < deadline:
        time.sleep(0.02)

    assert buffer.published_count > baseline, "captura deve retomar após reconectar"
    service.stop()


def test_stop_is_idempotent_and_clears_buffer():
    capture = FakeCapture(delay=0.002)
    buffer = FrameBuffer()
    service = CameraService(CameraConfig(), buffer, _factory(capture))

    service.start()
    time.sleep(0.1)
    service.stop()
    service.stop()

    assert buffer.latest() is None
    assert service.state is CameraState.STOPPED
    assert not service.is_running


def test_fps_metric_reflects_capture_rate():
    capture = FakeCapture(delay=0.01)  # ~100 fps teórico
    service = CameraService(CameraConfig(), FrameBuffer(), _factory(capture))
    service.start()
    time.sleep(0.5)

    assert service.stats.fps > 20, f"fps medido baixo: {service.stats.fps}"
    service.stop()


def test_stats_initial_values():
    service = CameraService(CameraConfig(), FrameBuffer())
    assert service.stats.frames_captured == 0
    assert service.stats.fps == 0.0
    assert service.state is CameraState.IDLE
    assert service.error is None


# ---------------------------------------------------------------------------
# Ritmo de leitura (exibição em tempo real para fontes de arquivo)
# ---------------------------------------------------------------------------


def test_read_source_fps_returns_declared_rate():
    assert read_source_fps(FakeCapture(source_fps=30.0)) == pytest.approx(30.0)


@pytest.mark.parametrize("value", [0.0, -1.0, 1e6, float("nan")])
def test_read_source_fps_rejects_unreliable_values(value):
    assert read_source_fps(FakeCapture(source_fps=value)) == 0.0


def test_file_source_is_paced_to_real_time():
    """Arquivo de vídeo deve ser exibido na velocidade original, não o mais rápido possível."""
    capture = FakeCapture(source_fps=25.0, delay=0.0)
    service = CameraService(
        CameraConfig(source="video.mp4", reconnect_delay_s=0.01),
        FrameBuffer(),
        lambda source, config: capture,
    )

    service.start()
    time.sleep(1.0)
    service.stop()

    # Em 1s a 25 fps espera-se ~25 quadros; sem pacing seriam centenas.
    assert 15 <= service.stats.frames_captured <= 40, service.stats.frames_captured
    assert service.stats.fps <= 40, f"fps acima do esperado: {service.stats.fps}"


def test_live_camera_is_not_paced():
    """Câmera ao vivo já entrega no ritmo do hardware; não deve haver atraso extra."""
    capture = FakeCapture(source_fps=30.0, delay=0.002)
    service = CameraService(
        CameraConfig(source=0, reconnect_delay_s=0.01),
        FrameBuffer(),
        lambda source, config: capture,
    )

    service.start()
    time.sleep(0.5)
    service.stop()

    assert service.stats.frames_captured > 100, (
        "captura ao vivo não deve ser limitada artificialmente"
    )
