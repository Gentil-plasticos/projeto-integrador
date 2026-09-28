"""Janela principal do Caixa Inteligente.

Monta o layout da interface e conecta a Área de Detecção ao serviço de captura.

Fluxo de dados (issue #7):

    thread de captura  →  FrameBuffer  →  loop da interface (after)  →  Canvas

A interface consulta o buffer a cada ``refresh_interval_ms`` milissegundos por
meio de ``widget.after``, que roda no thread principal do Tkinter. Isso mantém
o desenho em tempo real sem que a thread de vídeo toque em objetos de UI —
prática obrigatória no Tkinter e que atende ao requisito de não travar a
interface.
"""

from __future__ import annotations

import logging
import tkinter as tk

from ..camera import CameraService, CameraState, FrameBuffer
from ..config import AppConfig, COLORS, FONT_FALLBACKS, FONT_FAMILY
from .detection_area import DetectionArea
from .panels import CameraStatusPanel, PlaceholderPanel

logger = logging.getLogger(__name__)

NO_SIGNAL_MESSAGE = "Aguardando sinal da câmera..."


class MainWindow:
    """Controla a janela principal e o ciclo de atualização da Área de Detecção."""

    def __init__(
        self,
        config: AppConfig,
        buffer: FrameBuffer,
        camera_service: CameraService | None = None,
    ) -> None:
        self.config = config
        self.buffer = buffer
        self.camera = camera_service

        self.root = tk.Tk()
        self.root.title(config.ui.title)
        self.root.configure(bg=COLORS["fundo_app"])
        self.root.minsize(config.ui.min_width, config.ui.min_height)

        self._font_family = self._resolve_font()
        self._last_sequence = 0
        self._closed = False
        self._refresh_job: str | None = None

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # -- Construção do layout --------------------------------------------

    def _resolve_font(self) -> str:
        """Seleciona a fonte oficial (Inter) ou a alternativa disponível."""
        try:
            available = set(tk.font.families())  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - depende do ambiente gráfico
            available = set()
        for family in (FONT_FAMILY, *FONT_FALLBACKS):
            if family in available:
                return family
        return FONT_FAMILY

    def _build_layout(self) -> None:
        """Monta o cabeçalho, a Área de Detecção e o painel lateral."""
        header = tk.Frame(self.root, bg=COLORS["branco"], height=64)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Caixa Inteligente",
            bg=COLORS["branco"],
            fg=COLORS["cinza_texto"],
            font=(self._font_family, 17, "bold"),
        ).pack(side=tk.LEFT, padx=20)
        tk.Label(
            header,
            text="Autoatendimento com visão computacional",
            bg=COLORS["branco"],
            fg=COLORS["cinza_escuro"],
            font=(self._font_family, 10),
        ).pack(side=tk.LEFT, padx=(4, 0), pady=(6, 0))

        body = tk.Frame(self.root, bg=COLORS["fundo_app"])
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Área de Detecção: ocupa toda a região principal da interface.
        detection_container = tk.Frame(body, bg=COLORS["fundo_app"])
        detection_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            detection_container,
            text="Área de Detecção",
            bg=COLORS["fundo_app"],
            fg=COLORS["cinza_texto"],
            font=(self._font_family, 12, "bold"),
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 8))

        self.detection_area = DetectionArea(
            detection_container, show_overlay=self.config.ui.show_overlay
        )
        self.detection_area.pack(fill=tk.BOTH, expand=True)

        self._fps_label = tk.Label(
            detection_container,
            text="",
            bg=COLORS["fundo_app"],
            fg=COLORS["cinza_escuro"],
            font=(self._font_family, 9),
            anchor=tk.W,
        )
        self._fps_label.pack(fill=tk.X, pady=(6, 0))

        # Coluna lateral com painéis de status.
        sidebar = tk.Frame(body, bg=COLORS["fundo_app"], width=self.config.ui.sidebar_width)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(16, 0))
        sidebar.pack_propagate(False)

        self.camera_panel = CameraStatusPanel(sidebar)
        self.camera_panel.pack(fill=tk.X)

        PlaceholderPanel(
            sidebar,
            "STATUS DO CAIXA",
            "Disponível na Feature 2 (issue #8).",
        ).pack(fill=tk.X, pady=(12, 0))

        PlaceholderPanel(
            sidebar,
            "PESO DO PRODUTO",
            "Disponível na Feature 3 (issue #9).",
        ).pack(fill=tk.X, pady=(12, 0))

    # -- Ciclo de atualização --------------------------------------------

    def start(self) -> None:
        """Inicia a captura e agenda o primeiro ciclo de atualização."""
        if self.camera is not None:
            self.camera.start()
        self.detection_area.show_message(NO_SIGNAL_MESSAGE)
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        self._refresh_job = self.root.after(
            self.config.ui.refresh_interval_ms, self._refresh
        )

    def _refresh(self) -> None:
        """Lê o frame mais recente e atualiza a Área de Detecção."""
        if self._closed:
            return

        frame = self.buffer.latest()
        if frame is not None and frame.sequence != self._last_sequence:
            self._last_sequence = frame.sequence
            try:
                self.detection_area.show_frame(frame.image)
            except Exception:  # pragma: no cover - proteção da UI
                logger.exception("Falha ao renderizar o quadro da câmera.")

        self._update_camera_panel()
        self._schedule_refresh()

    def _update_camera_panel(self) -> None:
        """Reflete o estado da captura no painel lateral."""
        if self.camera is None:
            return
        state = self.camera.state
        stats = self.camera.stats

        if state is CameraState.STREAMING:
            detail = (
                f"{stats.frames_captured} quadros • {stats.fps:.1f} fps\n"
                f"Fonte: {self.config.camera.source!r}"
            )
        elif state is CameraState.RECONNECTING:
            detail = self.camera.error or "Sem sinal de vídeo."
        else:
            detail = "Aguardando inicialização da captura."

        self.camera_panel.update_state(state, detail)
        if state is CameraState.STREAMING:
            self._fps_label.configure(
                text=f"Tempo real — {stats.fps:.1f} fps • {stats.frames_captured} quadros"
            )
        else:
            self._fps_label.configure(text="")

        # Mantém a mensagem de espera enquanto não houver quadro disponível.
        if self.buffer.latest() is None:
            self.detection_area.show_message(NO_SIGNAL_MESSAGE)

    # -- Encerramento -----------------------------------------------------

    def run(self) -> None:
        """Inicia o ciclo completo e entra no loop de eventos do Tkinter."""
        self.start()
        self.root.mainloop()

    def close(self) -> None:
        """Encerra captura, cancela atualizações pendentes e fecha a janela."""
        if self._closed:
            return
        self._closed = True
        if self._refresh_job is not None:
            try:
                self.root.after_cancel(self._refresh_job)
            except tk.TclError:  # pragma: no cover - janela já destruída
                pass
            self._refresh_job = None
        if self.camera is not None:
            self.camera.stop()
        self.detection_area.release()
        try:
            self.root.destroy()
        except tk.TclError:  # pragma: no cover - já destruída
            pass