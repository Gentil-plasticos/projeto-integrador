"""Painéis laterais da interface principal.

O painel implementado aqui é o **Status da Câmera**, diretamente relacionado à
issue #7: informa ao operador se o vídeo está ativo. O layout reserva ainda os
espaços previstos para os painéis das issues #8 (Status do Caixa) e #9
(Peso do Produto), que serão preenchidos pelas respectivas features.
"""

from __future__ import annotations

import tkinter as tk

from ..camera import CameraState
from ..config import COLORS

#: Rótulo e cor apresentados para cada estado da câmera.
_STATE_PRESENTATION: dict[CameraState, tuple[str, str]] = {
    CameraState.IDLE: ("Inicializando", COLORS["cinza_escuro"]),
    CameraState.CONNECTING: ("Conectando", COLORS["laranja"]),
    CameraState.STREAMING: ("Câmera ativa", COLORS["verde"]),
    CameraState.RECONNECTING: ("Reconectando", COLORS["vermelho"]),
    CameraState.STOPPED: ("Encerrada", COLORS["cinza_escuro"]),
}


class CameraStatusPanel(tk.Frame):
    """Painel que reflete o estado atual da captura de vídeo."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, bg=COLORS["branco"], **kwargs)

        title = tk.Label(
            self,
            text="STATUS DA CÂMERA",
            bg=COLORS["branco"],
            fg=COLORS["cinza_escuro"],
            font=("TkDefaultFont", 9, "bold"),
            anchor=tk.W,
        )
        title.pack(fill=tk.X, padx=16, pady=(14, 2))

        self._indicator = tk.Canvas(
            self, width=14, height=14, bg=COLORS["branco"], highlightthickness=0
        )
        self._dot = self._indicator.create_oval(
            2, 2, 12, 12, fill=COLORS["cinza_escuro"], outline=""
        )

        row = tk.Frame(self, bg=COLORS["branco"])
        row.pack(fill=tk.X, padx=16, pady=(2, 4))
        self._indicator.pack(in_=row, side=tk.LEFT)
        self._label = tk.Label(
            row,
            text="—",
            bg=COLORS["branco"],
            fg=COLORS["cinza_texto"],
            font=("TkDefaultFont", 13, "bold"),
            anchor=tk.W,
        )
        self._label.pack(side=tk.LEFT, padx=(8, 0))

        self._detail = tk.Label(
            self,
            text="",
            bg=COLORS["branco"],
            fg=COLORS["cinza_escuro"],
            font=("TkDefaultFont", 9),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=260,
        )
        self._detail.pack(fill=tk.X, padx=16, pady=(0, 14))

        self._current: CameraState | None = None

    def update_state(self, state: CameraState, detail: str = "—") -> None:
        """Atualiza o painel com o novo estado e a informação auxiliar."""
        if state == self._current and self._detail.cget("text") == detail:
            return
        self._current = state
        text, color = _STATE_PRESENTATION.get(
            state, (state.value, COLORS["cinza_escuro"])
        )
        self._label.configure(text=text, fg=color)
        self._indicator.itemconfigure(self._dot, fill=color)
        self._detail.configure(text=detail)


class PlaceholderPanel(tk.Frame):
    """Espaço reservado para painéis de features futuras (#8 e #9)."""

    def __init__(self, master: tk.Misc, title: str, note: str, **kwargs) -> None:
        super().__init__(master, bg=COLORS["branco"], **kwargs)
        tk.Label(
            self,
            text=title,
            bg=COLORS["branco"],
            fg=COLORS["cinza_escuro"],
            font=("TkDefaultFont", 9, "bold"),
            anchor=tk.W,
        ).pack(fill=tk.X, padx=16, pady=(14, 2))
        tk.Label(
            self,
            text=note,
            bg=COLORS["branco"],
            fg=COLORS["cinza"],
            font=("TkDefaultFont", 9),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=260,
        ).pack(fill=tk.X, padx=16, pady=(0, 14))