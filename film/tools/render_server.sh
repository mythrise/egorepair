#!/bin/bash
# Parallel 4K render for a many-core server: every scene is split into chunks, chunks render concurrently,
# chunks are stitched per scene (stream copy), then the film is assembled and encoded to the size budget.
#
#   cd film && JOBS=24 bash tools/render_server.sh
#
# env: JOBS (parallel Chromium workers, default = cores/4), CHUNK (seconds per chunk, default 6),
#      W/H (default 3840x2160), FPS (30), MB (final size budget in decimal MB, default 145),
#      CHROME_PATH (use an existing Chrome/Chromium), CHROME_GL (GL flags, see engine/render.mjs),
#      SCENES (subset, space separated), SKIP_FINAL=1 (only render scenes)
set -euo pipefail
cd "$(dirname "$0")/.."
JOBS=${JOBS:-$(( $(nproc) / 4 > 1 ? $(nproc) / 4 : 1 ))}
CHUNK=${CHUNK:-6}; W=${W:-3840}; H=${H:-2160}; FPS=${FPS:-30}; MB=${MB:-145}
OUT=${OUT:-out/4k}; CH=${CH:-out/chunks}
mkdir -p "$OUT" "$CH"
[ -f assets/audio/score.wav ] || { echo "assets missing: run tools/unpack_assets.sh first"; exit 1; }

SCENES=${SCENES:-$(python3 -c "import json;print(' '.join(s['id'] for s in json.load(open('timeline.json'))['scenes']))")}
echo "render ${W}x${H}@${FPS}  jobs=$JOBS  chunk=${CHUNK}s  scenes: $SCENES"

# job list: scene from to  (longest scenes first for better packing)
python3 - "$CHUNK" $SCENES > "$CH/jobs.txt" <<'PY'
import json, sys
chunk = float(sys.argv[1]); want = sys.argv[2:]
d = {s['id']: s['dur'] for s in json.load(open('timeline.json'))['scenes']}
jobs = []
for sid in want:
    t = 0.0
    while t < d[sid] - 1e-6:
        jobs.append((d[sid], sid, t, min(t + chunk, d[sid]))); t += chunk
for _, sid, a, b in sorted(jobs, key=lambda j: -j[0]):
    print(sid, f"{a:g}", f"{b:g}")
PY
echo "$(wc -l < "$CH/jobs.txt") chunks"

render_chunk() {
  sid=$1; a=$2; b=$3
  out="$CH/${sid}__$(printf '%07.2f' "$a").mp4"
  [ -s "$out.ok" ] && return 0
  node engine/render.mjs --scene "$sid" --w "$W" --h "$H" --fps "$FPS" --from "$a" --to "$b" \
       --fmt jpeg --crf 12 --preset veryfast --out "$out" > "$out.log" 2>&1 && echo ok > "$out.ok" \
       || { echo "FAILED $sid $a-$b (see $out.log)"; return 1; }
  echo "  done $sid [$a,$b)"
}
export -f render_chunk; export W H FPS CH
start=$(date +%s)
xargs -a "$CH/jobs.txt" -P "$JOBS" -n 3 bash -c 'render_chunk "$@"' _
echo "chunks rendered in $(( $(date +%s) - start ))s"

# stitch chunks per scene (identical encoder settings -> lossless stream copy)
for sid in $SCENES; do
  ls "$CH/${sid}__"*.mp4 | sort | sed "s#^#file '$PWD/#; s#\$#'#" > "$CH/${sid}.txt"
  ffmpeg -v error -y -f concat -safe 0 -i "$CH/${sid}.txt" -c copy "$OUT/$sid.mp4"
  echo "done $OUT/$sid.mp4 $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$sid.mp4")s"
done

[ "${SKIP_FINAL:-0}" = "1" ] && exit 0
python3 tools/assemble.py final "$OUT" out/EgoRepair_Launch_Film_4K.mp4 --mb "$MB"
echo "total $(( $(date +%s) - start ))s"
