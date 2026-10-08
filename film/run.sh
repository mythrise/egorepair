#!/bin/bash
# EgoRepair launch film — one-command 4K render.
#   bash run.sh                 # full film -> out/EgoRepair_Launch_Film_4K.mp4
#   JOBS=16 bash run.sh         # parallel workers (default: CPU cores / 4)
#   W=1920 H=1080 MB=60 OUT=out/1080 bash run.sh   # quick 1080p version
set -euo pipefail
cd "$(dirname "$0")"
need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 ($2)"; exit 1; }; }
need node "Node.js >= 18"; need npm "npm"; need ffmpeg "ffmpeg with libx264 + aac"; need ffprobe "ffmpeg"; need python3 "python3"
node -e 'process.exit(+process.versions.node.split(".")[0] >= 18 ? 0 : 1)' || { echo "Node.js >= 18 required"; exit 1; }
ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libx264 || { echo "ffmpeg lacks libx264"; exit 1; }

# headless Chromium via Playwright (installed into ./.pw unless CHROME_PATH points to an existing Chrome/Chromium)
if [ ! -d .pw/node_modules/playwright ]; then
  echo "installing playwright 1.56.1 into ./.pw ..."
  npm install --silent --no-audit --no-fund --prefix .pw playwright@1.56.1
fi
export PLAYWRIGHT_PATH="$PWD/.pw/node_modules/playwright"
if [ -z "${CHROME_PATH:-}" ]; then .pw/node_modules/.bin/playwright install chromium; fi

# score
[ -f assets/audio/score.wav ] || ffmpeg -v error -y -i assets/audio/score.m4a -c:a pcm_s24le assets/audio/score.wav

bash tools/render_server.sh
