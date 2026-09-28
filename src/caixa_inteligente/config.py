"""Configuração central do Caixa Inteligente.

Reúne os parâmetros de captura de vídeo e as constantes de identidade visual
definidas nas issues #1 (cores), #2 (fonte) e #3 (logo) do projeto.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Identidade visual (issues #1, #2 e #3)
# ---------------------------------------------------------------------------

#: Paleta aprovada na issue #1 - Escolha de cores do sistema.
COLORS: dict[str, str] = {
    "azul": "#3498DB",
    "verde": "#2FAF5A",
    "vermelho": "#E74C3C",
    "cinza": "#E5E5E5",
    "branco": "#FFFFFF",
    # Cores da logo (issue #3) - usadas apenas como acento de marca.
    "laranja": "#F48B03",
    "rosa": "#ED0C96",
    # Derivadas para hierarquia visual (contraste com o branco minimalista).
    "cinza_escuro": "#5A6672",
    "cinza_texto": "#2C3E50",
    "fundo_app": "#F4F6F8",
    "fundo_video": "#101418",
}

#: Fonte oficial escolhida na issue #2 (Inter), com alternativas equivalentes.
FONT_FAMILY = os.environ.get("CAIXA_FONT_FAMILY", "Inter")
FONT_FALLBACKS: tuple[str, ...] = (
    "Inter",
    "Noto Sans",
    "DejaVu Sans",
    "Helvetica Neue",
    "Segoe UI",
    "Arial",
)


@dataclass(frozen=True)
class CameraConfig:
    """Parâmetros da câmera padrão configurada pelo sistema.

    ``source`` segue a convenção do OpenCV: um inteiro para dispositivos
    locais (``0`` = primeira webcam) ou uma string com caminho/URL de vídeo.
    Pode ser sobrescrito pela variável de ambiente ``CAIXA_CAMERA_SOURCE``,
    o que permite apontar para um vídeo de teste sem alterar o código.
    """

    source: int | str = 0
    width: int = 1280
    height: int = 720
    target_fps: int = 30
    #: Intervalo entre tentativas de reconexão quando a câmera falha (segundos).
    reconnect_delay_s: float = 2.0
    #: Quantos erros consecutivos de leitura antes de reabrir o dispositivo.
    max_consecutive_failures: int = 30

    @classmethod
    def from_env(cls) -> "CameraConfig":
        """Cria a configuração aplicando as variáveis de ambiente suportadas."""
        raw = os.environ.get("CAIXA_CAMERA_SOURCE")
        source: int | str = cls.source
        if raw not in (None, ""):
            source = int(raw) if raw.strip().lstrip("-").isdigit() else raw

        def _int_env(name: str, default: int) -> int:
            try:
                return int(os.environ[name])
            except (KeyError, ValueError):
                return default

        return cls(
            source=source,
            width=_int_env("CAIXA_CAMERA_WIDTH", cls.width),
            height=_int_env("CAIXA_CAMERA_HEIGHT", cls.height),
            target_fps=_int_env("CAIXA_CAMERA_FPS", cls.target_fps),
        )


@dataclass(frozen=True)
class UiConfig:
    """Layout da interface principal."""

    title: str = "Caixa Inteligente"
    #: Taxa de atualização da área de detecção (ms entre repinturas).
    refresh_interval_ms: int = 33
    #: Largura da coluna lateral que hospeda os painéis de status e peso.
    sidebar_width: int = 320
    min_width: int = 1024
    min_height: int = 640
    #: Mostrar sobreposições de diagnóstico na área de detecção.
    show_overlay: bool = True
    #: Caminho opcional para a logo exibida no cabeçalho (issue #3).
    logo_path: Path | None = field(default=None)


@dataclass(frozen=True)
class AppConfig:
    """Configuração agregada da aplicação."""

    camera: CameraConfig = field(default_factory=CameraConfig.from_env)
    ui: UiConfig = field(default_factory=UiConfig)