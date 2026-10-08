"""Dense optical flow (Farneback) sampled on a coarse grid for every frame; plus per-frame global ego-motion.

usage: flow_grid.py IN_VIDEO OUT_JSON [gx=40] [gy=22]
"""
import json, sys
import cv2
import numpy as np

inp, out = sys.argv[1], sys.argv[2]
gx = int(sys.argv[3]) if len(sys.argv) > 3 else 40
gy = int(sys.argv[4]) if len(sys.argv) > 4 else 22
cap = cv2.VideoCapture(inp)
ok, prev = cap.read()
prev = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
H, W = prev.shape
xs = ((np.arange(gx) + 0.5) * W / gx).astype(int)
ys = ((np.arange(gy) + 0.5) * H / gy).astype(int)
frames = [[[0.0, 0.0]] * (gx * gy)]
glob = [[0.0, 0.0]]
while True:
    ok, f = cap.read()
    if not ok:
        break
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 4, 21, 3, 7, 1.5, 0)
    flow = cv2.GaussianBlur(flow, (0, 0), 3)
    s = flow[ys][:, xs].reshape(-1, 2) / np.array([W, H])  # normalized units / frame
    frames.append(np.round(s, 5).tolist())
    glob.append(np.round(np.median(flow.reshape(-1, 2), axis=0) / np.array([W, H]), 5).tolist())
    prev = g
json.dump({"gx": gx, "gy": gy, "n": len(frames), "flow": frames, "global": glob}, open(out, "w"))
mag = np.linalg.norm(np.array(glob), axis=1) * W
print("frames", len(frames), "median global motion px/frame", float(np.median(mag)), "max", float(mag.max()))
