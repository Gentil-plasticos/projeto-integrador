#!/usr/bin/env bash
# Gera o vídeo de teste usado para validar a exibição sem uma webcam física.
#
# O arquivo resultante é ignorado pelo Git (ver .gitignore); recrie-o sempre
# que precisar rodar a aplicação ou os testes de evidência.
#
# Uso:
#   bash tools/gerar_video_teste.sh
#
# Requisitos: ffmpeg com suporte a libx264.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${PROJECT_ROOT}/videos"
OUTPUT_FILE="${OUTPUT_DIR}/demo_produtos.mp4"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg não encontrado. Instale com: sudo apt install ffmpeg" >&2
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

echo "Gerando ${OUTPUT_FILE} (1280x720, 30 fps, 10 s)..."
ffmpeg -y -loglevel error \
    -f lavfi -i "testsrc2=size=1280x720:rate=30:duration=10" \
    -vf "drawtext=text='CAIXA INTELIGENTE - VIDEO DE TESTE':fontsize=36:fontcolor=white:x=(w-text_w)/2:y=40:box=1:boxcolor=black@0.6:boxborderw=12" \
    -c:v libx264 -pix_fmt yuv420p \
    "${OUTPUT_FILE}"

echo "Vídeo gerado com sucesso."
echo "Execute a aplicação com:"
echo "  CAIXA_CAMERA_SOURCE=videos/demo_produtos.mp4 python -m caixa_inteligente.app"
