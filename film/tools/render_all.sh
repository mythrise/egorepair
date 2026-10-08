#!/bin/bash
# render every scene to out/<prefix>/<scene>.mp4 ; usage: render_all.sh W H FPS PREFIX [scenes...]
W=$1; H=$2; FPS=$3; PRE=$4; shift 4
SCENES=${@:-s01_open s02_scale s03_anatomy s04_eef s05_storm s06_title s07_pipeline s08_agents s09_review s10_result s11_ladder s12_studio s13_finale}
mkdir -p out/$PRE
for s in $SCENES; do
  node engine/render.mjs --scene $s --w $W --h $H --fps $FPS --fmt jpeg --crf ${CRF:-18} --preset ${PRESET:-veryfast} --out out/$PRE/$s.mp4 2>&1 | grep -E "done|Error|error" 
done
