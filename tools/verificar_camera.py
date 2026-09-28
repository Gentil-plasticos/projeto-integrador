"""Diagnóstico da câmera do Caixa Inteligente.

Verifica se a câmera padrão está acessível, mede a taxa de quadros real e
confirma que os frames chegam pela thread de captura — útil antes de abrir a
interface no caixa físico.

Uso::

    python tools/verificar_camera.py
    python tools/verificar_camera.py --source 1
    python tools/verificar_camera.py --source videos/demo.mp4 --duration 5
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from caixa_inteligente.camera import CameraService, CameraState, list_available_cameras  # noqa: E402
from caixa_inteligente.camera.frame_buffer import FrameBuffer  # noqa: E402
from caixa_inteligente.config import CameraConfig  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verifica a câmera do sistema.")
    parser.add_argument(
        "--source",
        default=None,
        help="Índice do dispositivo (0, 1, ...) ou caminho de vídeo para teste.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Tempo de observação da captura, em segundos.",
    )
    return parser.parse_args()


def resolve_source(value: str | None) -> int | str:
    if value is None:
        return CameraConfig.from_env().source
    return int(value) if value.strip().lstrip("-").isdigit() else value


def main() -> int:
    args = parse_args()
    source = resolve_source(args.source)
    config = CameraConfig.from_env()
    config = CameraConfig(
        source=source,
        width=config.width,
        height=config.height,
        target_fps=config.target_fps,
    )

    print("=== Diagnóstico da câmera ===")
    print(f"Fonte configurada: {source!r}")
    print(f"Resolução desejada: {config.width}x{config.height} @ {config.target_fps} fps")

    if isinstance(source, int):
        devices = list_available_cameras()
        print(f"Dispositivos detectados: {devices or 'nenhum'}")

    buffer = FrameBuffer()
    service = CameraService(config, buffer)
    service.start()

    print(f"Capturando por {args.duration:.1f}s...")
    time.sleep(args.duration)
    service.stop()

    stats = service.stats
    frame = buffer.latest()

    print("\n=== Resultado ===")
    print(f"Estado final: {service.state.value}")
    print(f"Quadros capturados: {stats.frames_captured}")
    print(f"Falhas de leitura: {stats.read_failures}")
    print(f"Reconexões: {stats.reconnects}")
    print(f"FPS medido: {stats.fps:.1f}")
    if service.error:
        print(f"Último erro: {service.error}")

    if stats.frames_captured == 0:
        print("\n[FALHA] Nenhum quadro recebido. Verifique se a câmera está")
        print("conectada e se o sistema operacional concedeu permissão de acesso.")
        return 1

    print("\n[OK] A câmera está transmitindo quadros para o sistema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())