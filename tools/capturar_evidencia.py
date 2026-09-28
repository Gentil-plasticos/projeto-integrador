"""Captura evidências visuais da Área de Detecção em execução.

Executa a aplicação real (captura em thread separada + interface Tkinter),
aguarda a estabilização do vídeo e salva capturas de tela da janela. Serve
como verificação de aceite da issue #7 em ambiente gráfico (X11/Xvfb).

Uso::

    xvfb-run -a python tools/capturar_evidencia.py \
        --source videos/demo_produtos.mp4 --output docs/evidencias
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from caixa_inteligente.camera import CameraService, CameraState  # noqa: E402
from caixa_inteligente.config import AppConfig, CameraConfig, UiConfig  # noqa: E402
from caixa_inteligente.ui import MainWindow  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Captura evidências da interface.")
    parser.add_argument("--source", default="videos/demo_produtos.mp4")
    parser.add_argument("--output", default="docs/evidencias")
    parser.add_argument("--shots", type=int, default=3)
    parser.add_argument("--interval", type=float, default=1.5)
    return parser.parse_args()


def screenshot(window_id: str, destination: Path) -> bool:
    """Salva a captura da janela usando ``import`` (ImageMagick) ou ``xwd``."""
    try:
        subprocess.run(
            ["import", "-window", window_id, str(destination)],
            check=True,
            capture_output=True,
        )
        return destination.exists()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    try:
        raw = subprocess.run(
            ["xwd", "-id", window_id, "-silent"],
            check=True,
            capture_output=True,
        ).stdout
        converted = subprocess.run(
            ["convert", "xwd:-", str(destination)],
            input=raw,
            check=True,
            capture_output=True,
        )
        return converted.returncode == 0 and destination.exists()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def main() -> int:
    args = parse_args()
    source = args.source
    source_value: int | str = int(source) if source.isdigit() else source

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = AppConfig(
        camera=CameraConfig(source=source_value, reconnect_delay_s=0.5),
        ui=UiConfig(refresh_interval_ms=20),
    )
    camera = CameraService(config.camera)
    window = MainWindow(config, camera.buffer, camera)

    results: list[Path] = []
    try:
        window.start()
        window.root.update()

        # Aguarda o vídeo estabilizar na área de detecção.
        deadline = time.time() + 10
        while time.time() < deadline:
            window.root.update()
            if (
                camera.state is CameraState.STREAMING
                and window.detection_area._image_id is not None
            ):
                break
            time.sleep(0.05)

        print(f"Estado da câmera: {camera.state.value}")
        print(f"Quadros exibidos: {window._last_sequence}")

        window.root.after(100, lambda: None)
        for index in range(args.shots):
            for _ in range(30):
                window.root.update()
                time.sleep(0.02)

            destination = output_dir / f"area_deteccao_{index + 1}.png"
            window_id = window.root.winfo_id()
            if screenshot(str(window_id), destination):
                results.append(destination)
                print(f"Captura salva: {destination}")

            deadline = time.time() + args.interval
            while time.time() < deadline:
                window.root.update()
                time.sleep(0.02)

        stats = camera.stats
        print("\n=== Métricas de captura ===")
        print(f"Quadros capturados: {stats.frames_captured}")
        print(f"FPS medido: {stats.fps:.1f}")
        print(f"Falhas de leitura: {stats.read_failures}")
        print(f"Reconexões: {stats.reconnects}")
        print(f"Quadros renderizados na interface: {window._last_sequence}")

        ok = stats.frames_captured > 0 and window._last_sequence > 0
        print("\n[OK] Vídeo exibido e atualizado na Área de Detecção." if ok else "\n[FALHA]")
        return 0 if ok else 1
    finally:
        window.close()


if __name__ == "__main__":
    sys.exit(main())