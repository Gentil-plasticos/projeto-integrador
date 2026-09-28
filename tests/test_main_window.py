"""Testes de integração da janela principal.

Verificam os critérios de aceitação da issue #7 de ponta a ponta:
captura em thread separada → buffer → Área de Detecção atualizada em tempo real.
"""

from __future__ import annotations

import time
import tkinter as tk

import numpy as np
import pytest

from caixa_inteligente.camera import CameraService, CameraState
from caixa_inteligente.camera.frame_buffer import FrameBuffer
from caixa_inteligente.config import AppConfig, CameraConfig, UiConfig
from caixa_inteligente.ui.main_window import MainWindow, NO_SIGNAL_MESSAGE

from test_camera_service import FakeCapture


@pytest.fixture()
def tk_available():
    try:
        probe = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - depende do ambiente
        pytest.skip(f"Ambiente sem display gráfico: {exc}")
    probe.destroy()


def _config() -> AppConfig:
    return AppConfig(
        camera=CameraConfig(reconnect_delay_s=0.02),
        ui=UiConfig(refresh_interval_ms=20, show_overlay=True),
    )


def _service(delay: float = 0.005) -> CameraService:
    capture = FakeCapture(delay=delay)
    return CameraService(
        CameraConfig(reconnect_delay_s=0.02),
        FrameBuffer(),
        lambda source, config: capture,
    )


def _pump(window: MainWindow, condition, timeout: float = 3.0) -> bool:
    """Processa o loop de eventos do Tk até ``condition()`` virar verdadeira.

    Evita condições de corrida: os testes aguardam a condição realmente
    verificada, e não um efeito colateral que pode ocorrer antes do primeiro
    ciclo de atualização da interface.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        window.root.update()
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_window_shows_camera_video_on_startup(tk_available):
    """Cenário 1: ao carregar a tela principal o vídeo é exibido."""
    config = _config()
    service = _service()
    window = MainWindow(config, service.buffer, service)

    try:
        window.start()
        displayed = _pump(window, lambda: window.detection_area._image_id is not None)

        assert displayed, (
            "a Área de Detecção deve exibir o vídeo da câmera"
        )
        assert window.camera_panel._current is CameraState.STREAMING
    finally:
        window.close()


def test_video_keeps_updating_in_real_time(tk_available):
    """O vídeo é atualizado continuamente (frames distintos ao longo do tempo)."""
    service = _service()
    window = MainWindow(_config(), service.buffer, service)

    try:
        window.start()
        assert _pump(window, lambda: window._last_sequence > 0), (
            "a interface deve exibir o primeiro quadro"
        )

        first_sequence = window._last_sequence
        assert _pump(window, lambda: window._last_sequence > first_sequence), (
            "novos quadros devem ser exibidos continuamente"
        )
    finally:
        window.close()


def test_window_remains_responsive_while_camera_streams(tk_available):
    """A interface responde a eventos mesmo com a captura ativa."""
    service = _service(delay=0.001)
    window = MainWindow(_config(), service.buffer, service)

    try:
        window.start()
        responsive = {"ok": False}

        def probe() -> None:
            responsive["ok"] = True

        for _ in range(3):
            window.root.after(10, probe)
            deadline = time.time() + 2
            while not responsive["ok"] and time.time() < deadline:
                window.root.update()
                time.sleep(0.005)
            assert responsive["ok"], "o loop de eventos deve continuar processando"
            responsive["ok"] = False
    finally:
        window.close()


def test_message_shown_when_no_frames_available(tk_available):
    """Sem sinal, a área exibe a mensagem de espera e o painel indica o estado."""
    def factory(source, config):
        return FakeCapture(opened=False)

    service = CameraService(CameraConfig(reconnect_delay_s=0.02), FrameBuffer(), factory)
    window = MainWindow(_config(), service.buffer, service)

    try:
        window.start()
        assert _pump(
            window,
            lambda: window.camera_panel._current is CameraState.RECONNECTING,
        ), "o painel deve indicar que a câmera está reconectando"

        message_id = window.detection_area._message_id
        assert message_id is not None, "a área deve exibir a mensagem de espera"
        assert NO_SIGNAL_MESSAGE in window.detection_area.canvas.itemcget(
            message_id, "text"
        )
    finally:
        window.close()


def test_close_stops_capture_and_releases_resources(tk_available):
    service = _service()
    window = MainWindow(_config(), service.buffer, service)

    window.start()
    time.sleep(0.1)
    window.close()

    assert service.state is CameraState.STOPPED
    assert not service.is_running
    assert window.detection_area._photo is None


def test_layout_has_detection_area_and_sidebar(tk_available):
    """A área de detecção respeita o layout: painéis de status na lateral."""
    service = _service()
    window = MainWindow(_config(), service.buffer, service)
    try:
        window.root.update()
        width, height = window.detection_area.viewport_size
        assert width > 0 and height > 0
        assert window.camera_panel.winfo_exists()
    finally:
        window.close()
