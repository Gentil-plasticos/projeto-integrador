"""Testes de configuração: câmera padrão, variáveis de ambiente e identidade visual."""

from __future__ import annotations

import pytest

from caixa_inteligente.config import COLORS, CameraConfig


def test_default_camera_is_system_default():
    """A câmera padrão configurada pelo sistema é o dispositivo 0."""
    assert CameraConfig().source == 0


def test_source_accepts_video_path_for_tests(monkeypatch):
    monkeypatch.setenv("CAIXA_CAMERA_SOURCE", "/tmp/video.mp4")
    assert CameraConfig.from_env().source == "/tmp/video.mp4"


def test_source_accepts_device_index_from_env(monkeypatch):
    monkeypatch.setenv("CAIXA_CAMERA_SOURCE", "1")
    assert CameraConfig.from_env().source == 1


def test_resolution_and_fps_from_env(monkeypatch):
    monkeypatch.setenv("CAIXA_CAMERA_WIDTH", "640")
    monkeypatch.setenv("CAIXA_CAMERA_HEIGHT", "480")
    monkeypatch.setenv("CAIXA_CAMERA_FPS", "15")
    config = CameraConfig.from_env()
    assert (config.width, config.height, config.target_fps) == (640, 480, 15)


def test_invalid_env_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("CAIXA_CAMERA_WIDTH", "invalido")
    assert CameraConfig.from_env().width == CameraConfig.width


def test_palette_matches_issue_1_decision():
    """A paleta aprovada na issue #1 deve estar disponível na configuração."""
    assert COLORS["azul"] == "#3498DB"
    assert COLORS["verde"] == "#2FAF5A"
    assert COLORS["vermelho"] == "#E74C3C"
    assert COLORS["cinza"] == "#E5E5E5"
    assert COLORS["branco"] == "#FFFFFF"


def test_logo_colors_match_issue_3_decision():
    """Cores da logo definidas na issue #3."""
    assert COLORS["laranja"] == "#F48B03"
    assert COLORS["rosa"] == "#ED0C96"


def test_ui_defaults_are_within_layout_minimums():
    from caixa_inteligente.config import UiConfig

    ui = UiConfig()
    assert ui.min_width >= 1024 and ui.min_height >= 640
    assert ui.refresh_interval_ms <= 100, "atualização deve ser fluida (tempo real)"