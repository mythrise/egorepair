#!/bin/bash
# wait for batch A, then render batch B at 4K
cd "$(dirname "$0")/.."
while pgrep -f "render_all.sh 3840 2160 30 4k s05" > /dev/null; do sleep 15; done
CRF=12 PRESET=veryfast ./tools/render_all.sh 3840 2160 30 4k s01_open s02_scale s03_anatomy s04_eef s10_result s12_studio
echo "batch B finished"
