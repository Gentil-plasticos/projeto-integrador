"""Buffer de frames thread-safe.

A thread de captura escreve nesta estrutura e a thread da interface lê. O
acesso é protegido por ``threading.Lock`` para garantir que a interface nunca
leia um frame parcialmente escrito, atendendo à nota técnica da issue #7:
"Atualização dos frames em thread separada para evitar travamentos da interface".

Estratégia de descarte: apenas o frame mais recente é mantido. Se a interface
estiver mais lenta que a câmera, frames antigos são descartados em vez de
acumulados, evitando latência crescente e consumo ilimitado de memória —
requisito de "transmissão em tempo real".
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Frame:
    """Um quadro de vídeo com o instante em que foi capturado."""

    image: np.ndarray
    timestamp: float
    sequence: int

    @property
    def age_s(self) -> float:
        """Segundos desde a captura deste quadro."""
        return max(0.0, time.monotonic() - self.timestamp)


class FrameBuffer:
    """Guarda o frame mais recente com acesso sincronizado."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Frame | None = None
        self._sequence = 0
        self._published = 0

    def publish(self, image: np.ndarray, timestamp: float | None = None) -> Frame:
        """Armazena um novo frame, descartando o anterior.

        Retorna o :class:`Frame` criado para que a thread de captura possa
        registrar métricas sem consultar o buffer novamente.
        """
        with self._lock:
            self._sequence += 1
            frame = Frame(
                image=image,
                timestamp=timestamp if timestamp is not None else time.monotonic(),
                sequence=self._sequence,
            )
            self._frame = frame
            self._published += 1
            return frame

    def latest(self) -> Frame | None:
        """Retorna o frame mais recente ou ``None`` se nada foi capturado."""
        with self._lock:
            return self._frame

    def clear(self) -> None:
        """Remove o frame armazenado (usado ao encerrar a captura)."""
        with self._lock:
            self._frame = None

    @property
    def published_count(self) -> int:
        """Total de frames publicados desde a criação do buffer."""
        with self._lock:
            return self._published