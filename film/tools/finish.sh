#!/bin/bash
# wait for all 13 4K scenes, then build the final film (two-pass H.264 sized to <=145 MB)
cd "$(dirname "$0")/.."
SCENES="s01_open s02_scale s03_anatomy s04_eef s05_storm s06_title s07_pipeline s08_agents s09_review s10_result s11_ladder s12_studio s13_finale"
while true; do
  n=0; for s in $SCENES; do grep -aq "done out/4k/$s.mp4" out/4k_log_a.txt out/4k_log_b.txt 2>/dev/null && n=$((n+1)); done
  [ $n -eq 13 ] && break
  if ! pgrep -f "render_all.sh 3840" > /dev/null && ! pgrep -f "queue_b.sh" > /dev/null; then echo "RENDER QUEUE STOPPED with $n/13 scenes"; exit 1; fi
  sleep 20
done
echo "all scenes rendered $(date +%H:%M:%S)"
python3 tools/assemble.py final out/4k out/EgoRepair_Launch_Film_4K.mp4 --mb 145 && echo "FINAL DONE $(date +%H:%M:%S)"
