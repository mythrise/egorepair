#!/bin/bash
# Build film assets from the uploaded source package (EgoRepair_Studio_视频制作素材_原始文件).
set -e
R="${1:-/home/user/egorepair/EgoRepair_Studio_视频制作素材_原始文件}"
A="$(cd "$(dirname "$0")/.." && pwd)/assets"
EGO="$R/P0/EgoDex"
A4="$R/P0/All_original_videos/01_视频/A4_INPUT_AND_INVENTORY_REFERENCE/home/xklv/ego_robot/a4_experiment"
mkdir -p "$A/footage" "$A/stills"

# 1) full-resolution basic_pick_place_117 (the episode the whole film follows)
mkdir -p "$A/footage/ego_raw"
ffmpeg -v error -y -i "$EGO/basic_pick_place_117/basic_pick_place_117.mp4" -q:v 2 -start_number 0 "$A/footage/ego_raw/%04d.jpg"

# 2) opening montage: 2 s from each task, original 1920x1080
for spec in pour_32:2.4 stack_unstack_cups_5:3.2 legos_33:4.0 fold_paper_10:3.6 screw_allen_10:20 sort_beads_1:3.0 bagging_10:4.0; do
  c=${spec%%:*}; ss=${spec##*:}
  mkdir -p "$A/footage/m_$c"
  ffmpeg -v error -y -ss "$ss" -i "$EGO/$c/$c.mp4" -frames:v 66 -q:v 2 -start_number 0 "$A/footage/m_$c/%04d.jpg"
done

# 3) EEF-only reference video (absolute end-effector poses rendered on the original view)
mkdir -p "$A/footage/eef_ref"
ffmpeg -v error -y -i "$A4/inputs/a2_pick_place_117_a1x_dual/standard_io/eef_view/eef_reference.mp4" -vf "scale=1280:720:flags=lanczos" -q:v 2 -start_number 0 "$A/footage/eef_ref/%04d.jpg"

# 4) MuJoCo presentation frames (1280x800)
mkdir -p "$A/footage/mujoco"
i=0; for f in $(ls "$R/P0/Extra_original_MuJoCo_presentation_frames/deployment_v2/site/assets/frames/"f*.jpg | sort); do cp "$f" "$A/footage/mujoco/$(printf %04d $i).jpg"; i=$((i+1)); done

# 5) PlanningDemo302: A1X full planning trajectory panel (1080p source)
mkdir -p "$A/footage/plan_a1x"
ffmpeg -v error -y -i "$R/P0/All_original_videos/01_视频/data_runs/planning_demo302_20261008_01/PlanningDemo302.mp4" -vf "crop=1144:900:760:72" -q:v 2 -start_number 0 "$A/footage/plan_a1x/%04d.jpg"

# 6) Studio 2xDPI captures (top of page)
for p in M2_多智能体协作 M6_物理回放 M7_机器人轨迹 M5_审计; do
  ffmpeg -v error -y -i "$R/P1/Studio_新2xDPI截图/$p.png" -vf "crop=3200:2120:0:1360" -q:v 2 "$A/stills/studio_$p.jpg"
done
ffmpeg -v error -y -i "$R/P1/Studio_新2xDPI截图/M4_轨迹修复.png" -q:v 2 "$A/stills/studio_M4_轨迹修复.jpg"
echo "materials ready"
