"""Testes da Área de Detecção e do layout da interface.

Os testes de UI exigem um servidor gráfico. Em ambiente headless, execute com
``xvfb-run -a pytest`` ou defina ``DISPLAY`` para um Xvfb em execução.
"""

from __future__ import annotations

import tkinter as tk

import numpy as np
import pytest

from caixa_inteligente.config import COLORS
from caixa_inteligente.ui.detection_area import DetectionArea


@pytest.fixture()
def root():
    """Cria uma janela Tkinter de teste, ignorando a suíte se não houver display."""
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - depende do ambiente
        pytest.skip(f"Ambiente sem display gráfico: {exc}")
    window.geometry("640x480")
    window.update()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


def _frame(value: int = 120, width: int = 320, height: int = 240) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def test_detection_area_uses_dark_video_background(root):
    area = DetectionArea(root)
    area.pack(fill=tk.BOTH, expand=True)
    root.update()

    assert area.cget("bg") == COLORS["fundo_video"]


def test_show_frame_renders_image_on_canvas(root):
    area = DetectionArea(root, show_overlay=False)
    area.pack(fill=tk.BOTH, expand=True)
    root.update()

    area.show_frame(_frame())
    root.update()

    assert area._image_id is not None, "um item de imagem deve existir no canvas"
    assert area._photo is not None, "a referência da imagem deve ser mantida"
    assert area.canvas.type(area._image_id) == "image"


def test_frames_update_continuously_without_duplicating_items(root):
    """O vídeo é atualizado continuamente reutilizando o mesmo item de canvas."""
    area = DetectionArea(root, show_overlay=False)
    area.pack(fill=tk.BOTH, expand=True)
    root.update()

    first_id = None
    for value in range(1, 8):
        area.show_frame(_frame(value))
        root.update()
        if first_id is None:
            first_id = area._image_id
        else:
            assert area._image_id == first_id, "o item deve ser reutilizado"

    items = [item for item in area.canvas.find_all() if area.canvas.type(item) == "image"]
    assert len(items) == 1, "não deve acumular itens de imagem"


def test_frame_is_scaled_preserving_aspect_ratio(root):
    """O vídeo preenche a região sem distorcer a imagem (letterbox)."""
    area = DetectionArea(root, show_overlay=False)
    area.pack(fill=tk.BOTH, expand=True)
    root.update()

    area.show_frame(_frame(width=640, height=480))
    root.update()

    photo = area._photo
    assert photo is not None
    width, height = photo.width(), photo.height()
    viewport_w, viewport_h = area.viewport_size

    assert width <= viewport_w + 1 and height <= viewport_h + 1
    assert abs((width / height) - (640 / 480)) < 0.02, "proporção deve ser preservada"


def test_show_frame_before_mapping_does_not_raise(root):
    """Chamar show_frame antes do widget ser mapeado não deve falhar."""
    area = DetectionArea(root)
    area.show_frame(_frame())  # widget ainda sem tamanho válido


def test_message_is_shown_and_cleared(root):
    area = DetectionArea(root)
    area.pack(fill=tk.BOTH, expand=True)
    root.update()

    area.show_message("Aguardando sinal da câmera...")
    root.update()
    assert area._message_id is not None
    assert "Aguardando" in area.canvas.itemcget(area._message_id, "text")

    area.show_frame(_frame())
    root.update()
    assert area._message_id is None, "a mensagem sai quando o vídeo chega"


def test_overlay_draws_analysis_guide(root):
    area = DetectionArea(root, show_overlay=True)
    area.pack(fill=tk.BOTH, expand=True)
    root.update()

    area.show_frame(_frame())
    root.update()

    overlay_items = area.canvas.find_withtag("overlay")
    assert len(overlay_items) >= 2, "guia da área de análise deve ser desenhada"
    kinds = {area.canvas.type(item) for item in overlay_items}
    assert "rectangle" in kinds


def test_overlay_is_optional(root):
    area = DetectionArea(root, show_overlay=False)
    area.pack(fill=tk.BOTH, expand=True)
    root.update()

    area.show_frame(_frame())
    root.update()

    assert len(area.canvas.find_withtag("overlay")) == 0


def test_release_clears_image_references(root):
    area = DetectionArea(root)
    area.pack(fill=tk.BOTH, expand=True)
    root.update()
    area.show_frame(_frame())
    root.update()

    area.release()
    assert area._photo is None
    assert area._image_id is None