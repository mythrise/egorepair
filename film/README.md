# EgoRepair launch film — render pipeline

Deterministic, frame-by-frame renderer: each scene is a three.js + DOM page driven by an explicit time `t`,
captured by headless Chromium and piped into ffmpeg. Output target: 3840×2160 · 30 fps · H.264 · ≤150 MB.

```
engine/      core runtime (post pipeline, easing, DOM text), fx primitives, robot arm, renderer driver
scenes/      one module per shot (see STORYBOARD.md); scenes/lib = shared world, HUD, agent emblems
tools/       asset preparation (reconstruction, footage extraction), audio, assembly
assets/      generated inputs (footage frames, point clouds) — not committed, rebuilt by tools/
```

Preview stills:  `node engine/render.mjs --scene s08_agents --w 1920 --h 1080 --stills 5,20,40 --fmt jpeg`
Render a shot:   `node engine/render.mjs --scene s08_agents --out out/shots/s08_agents.mp4 --fmt jpeg`

## Rendering on another machine
The generated assets (footage frames, reconstruction, score) are not committed. They are delivered as the
self-contained render package `EgoRepair_Film_Render.zip`; unzip it and run `JOBS=<cores/4> bash run.sh`
(see `README_渲染说明.md`). `tools/prepare_materials.sh`, `tools/recon_planar.py`, `tools/track_hands.py`,
`tools/flow_grid.py` and `tools/score.py` regenerate them from the source package.
