"""Widget da Área de Detecção.

Exibe o vídeo da câmera em tempo real, ocupando toda a região destinada à
visualização (referência visual da issue #7).

O widget recebe quadros já em memória (``numpy`` BGR) do :class:`FrameBuffer` e
apenas os converte para exibição. Nenhuma chamada de captura é feita aqui, de
forma que a renderização nunca bloqueia na câmera.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageTk

from ..config import COLORS


class DetectionArea(tk.Frame):
    """Área principal onde o vídeo da câmera é exibido."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_resize: Callable[[int, int], None] | None = None,
        show_overlay: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(master, bg=COLORS["fundo_video"], **kwargs)
        self._on_resize = on_resize
        self._show_overlay = show_overlay

        self._canvas = tk.Canvas(
            self,
            bg=COLORS["fundo_video"],
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        #: Referência obrigatória: sem ela o garbage collector descarta a imagem.
        self._photo: ImageTk.PhotoImage | None = None
        self._image_id: int | None = None
        self._last_size: tuple[int, int] = (0, 0)
        self._message_id: int | None = None
        self._message_text: str | None = None

        self._canvas.bind("<Configure>", self._handle_resize)

    # -- API pública ------------------------------------------------------

    @property
    def canvas(self) -> tk.Canvas:
        """Canvas interno (exposto para testes e sobreposições futuras)."""
        return self._canvas

    @property
    def viewport_size(self) -> tuple[int, int]:
        """Tamanho atual (largura, altura) da região de desenho."""
        return (self._canvas.winfo_width(), self._canvas.winfo_height())

    def show_frame(self, frame_bgr: np.ndarray) -> None:
        """Desenha um quadro BGR, mantendo a proporção dentro do widget.

        O quadro é redimensionado para preencher a área preservando o aspect
        ratio (letterbox), garantindo que o operador veja o produto inteiro.
        """
        width, height = self.viewport_size
        if width <= 1 or height <= 1:
            # Widget ainda não foi mapeado; a próxima atualização desenhará.
            return

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)

        scale = min(width / image.width, height / image.height)
        target = (
            max(1, int(image.width * scale)),
            max(1, int(image.height * scale)),
        )
        if target != image.size:
            image = image.resize(target, Image.BILINEAR)

        self._photo = ImageTk.PhotoImage(image)

        center_x, center_y = width // 2, height // 2
        if self._image_id is None:
            self._image_id = self._canvas.create_image(
                center_x, center_y, image=self._photo, anchor=tk.CENTER
            )
        else:
            self._canvas.coords(self._image_id, center_x, center_y)
            self._canvas.itemconfigure(self._image_id, image=self._photo)

        # A imagem deve ficar atrás de qualquer mensagem/sobreposição.
        self._canvas.tag_lower(self._image_id)
        self.clear_message()

        if self._show_overlay:
            self._draw_overlay(target)

    def show_message(self, text: str, *, color: str | None = None) -> None:
        """Exibe uma mensagem centralizada no lugar do vídeo.

        Utilizada quando a câmera ainda não forneceu quadros, mantendo a Área
        de Detecção sempre com conteúdo visível ao operador.
        """
        if text == self._message_text:
            return
        width, height = self.viewport_size
        color = color or COLORS["cinza"]
        self._clear_image()
        self._message_text = text
        if self._message_id is None:
            self._message_id = self._canvas.create_text(
                width // 2,
                height // 2,
                text=text,
                fill=color,
                font=("TkDefaultFont", 14),
                justify=tk.CENTER,
            )
        else:
            self._canvas.coords(self._message_id, width // 2, height // 2)
            self._canvas.itemconfigure(self._message_id, text=text, fill=color)

    def clear_message(self) -> None:
        """Remove a mensagem centralizada, se estiver visível."""
        if self._message_id is not None:
            self._canvas.delete(self._message_id)
            self._message_id = None
        self._message_text = None

    def release(self) -> None:
        """Libera referências de imagem ao encerrar a aplicação."""
        self._photo = None
        self._image_id = None
        self.clear_message()

    # -- Internos ---------------------------------------------------------

    def _clear_image(self) -> None:
        if self._image_id is not None:
            self._canvas.delete(self._image_id)
            self._image_id = None
        self._photo = None

    def _draw_overlay(self, target_size: tuple[int, int]) -> None:
        """Desenha o retângulo-guia da área de análise e a linha de varredura.

        Referência visual da issue #4: sinaliza ao operador o enquadramento
        esperado para que "o operador consiga visualizar os produtos
        posicionados para análise".
        """
        self._canvas.delete("overlay")
        width, height = self.viewport_size
        if width <= 1 or height <= 1:
            return

        center_x, center_y = width // 2, height // 2
        box_w = int(target_size[0] * 0.6)
        box_h = int(target_size[1] * 0.6)
        x0, y0 = center_x - box_w // 2, center_y - box_h // 2
        x1, y1 = x0 + box_w, y0 + box_h

        self._canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            outline=COLORS["azul"],
            width=2,
            dash=(6, 4),
            tags="overlay",
        )
        self._canvas.create_line(
            x0,
            center_y,
            x1,
            center_y,
            fill=COLORS["verde"],
            width=1,
            tags="overlay",
        )
        self._canvas.create_text(
            x0,
            y0 - 14,
            text="Área de Detecção",
            anchor=tk.W,
            fill=COLORS["azul"],
            font=("TkDefaultFont", 9, "bold"),
            tags="overlay",
        )

    def _handle_resize(self, event: tk.Event) -> None:
        size = (event.width, event.height)
        if size == self._last_size:
            return
        self._last_size = size
        # Reposiciona a mensagem centralizada após redimensionar a janela.
        if self._message_id is not None:
            self._canvas.coords(self._message_id, event.width // 2, event.height // 2)
        if self._on_resize is not None:
            self._on_resize(event.width, event.height)