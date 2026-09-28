"""Ponto de entrada do Caixa Inteligente.

Uso:

    python -m caixa_inteligente.app

Variáveis de ambiente suportadas (ver :mod:`caixa_inteligente.config`):

* ``CAIXA_CAMERA_SOURCE`` — índice da câmera (``0``, ``1``, ...) ou caminho de
  vídeo/URL para testes sem webcam física;
* ``CAIXA_CAMERA_WIDTH`` / ``CAIXA_CAMERA_HEIGHT`` / ``CAIXA_CAMERA_FPS``.
"""

from __future__ import annotations

import logging
import sys

from .camera import CameraService
from .config import AppConfig
from .ui import MainWindow


def configure_logging() -> None:
    """Configura o log em nível INFO com formato legível."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    """Inicializa a configuração, o serviço de câmera e a interface."""
    configure_logging()
    config = AppConfig()

    camera = CameraService(config.camera)
    window = MainWindow(config, camera.buffer, camera)

    logging.getLogger(__name__).info(
        "Iniciando Caixa Inteligente (câmera=%r).", config.camera.source
    )
    window.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())