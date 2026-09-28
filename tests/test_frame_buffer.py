"""Testes do buffer de frames thread-safe."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from caixa_inteligente.camera.frame_buffer import FrameBuffer


def _frame(value: int = 0, size: int = 8) -> np.ndarray:
    return np.full((size, size, 3), value, dtype=np.uint8)


def test_buffer_starts_empty():
    buffer = FrameBuffer()
    assert buffer.latest() is None
    assert buffer.published_count == 0


def test_publish_then_latest_returns_same_frame():
    buffer = FrameBuffer()
    image = _frame(7)
    frame = buffer.publish(image)

    latest = buffer.latest()
    assert latest is not None
    assert latest.sequence == frame.sequence == 1
    assert np.array_equal(latest.image, image)


def test_publish_discards_previous_frame():
    """Apenas o frame mais recente é mantido (evita latência acumulada)."""
    buffer = FrameBuffer()
    buffer.publish(_frame(1))
    buffer.publish(_frame(2))
    frame = buffer.publish(_frame(3))

    assert frame.sequence == 3
    assert buffer.published_count == 3
    assert buffer.latest().image[0, 0, 0] == 3


def test_clear_removes_frame():
    buffer = FrameBuffer()
    buffer.publish(_frame())
    buffer.clear()
    assert buffer.latest() is None


def test_frame_age_is_non_negative():
    buffer = FrameBuffer()
    frame = buffer.publish(_frame(), timestamp=time.monotonic() - 0.5)
    assert frame.age_s >= 0.5


def test_concurrent_read_write_never_returns_partial_frame():
    """A interface nunca deve ler um frame parcialmente escrito.

    A thread de captura publica quadros com valor uniforme; qualquer leitura
    que devolvesse um quadro misto indicaria condição de corrida.
    """
    buffer = FrameBuffer()
    stop = threading.Event()
    errors: list[str] = []

    def writer() -> None:
        value = 0
        while not stop.is_set():
            value = (value + 1) % 250 + 1
            buffer.publish(_frame(value))

    def reader() -> None:
        while not stop.is_set():
            frame = buffer.latest()
            if frame is None:
                continue
            # min/max evitam import tardio do numpy dentro da thread.
            low = int(frame.image.min())
            high = int(frame.image.max())
            if low != high:
                errors.append(f"frame misto: min={low} max={high}")
                return

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    time.sleep(0.5)
    stop.set()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors, errors
    assert buffer.published_count > 0


def test_sequences_are_monotonic_under_concurrency():
    buffer = FrameBuffer()
    seen: list[int] = []
    stop = threading.Event()

    def writer() -> None:
        while not stop.is_set():
            buffer.publish(_frame())

    def reader() -> None:
        while not stop.is_set():
            frame = buffer.latest()
            if frame is not None:
                seen.append(frame.sequence)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    time.sleep(0.3)
    stop.set()
    for thread in threads:
        thread.join(timeout=5)

    assert seen == sorted(seen), "sequências devem ser monotônicas"
