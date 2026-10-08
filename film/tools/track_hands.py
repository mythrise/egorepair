"""Run MediaPipe Hands on every frame of a clip; save 2D (normalized image) and 3D world landmarks.

usage: track_hands.py IN_VIDEO OUT_JSON
"""
import json, sys
import cv2
import mediapipe as mp

inp, out = sys.argv[1], sys.argv[2]
cap = cv2.VideoCapture(inp)
hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=2, model_complexity=1,
                                 min_detection_confidence=0.4, min_tracking_confidence=0.4)
frames = []
while True:
    ok, bgr = cap.read()
    if not ok:
        break
    res = hands.process(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    hs = []
    if res.multi_hand_landmarks:
        for lm, wl, hd in zip(res.multi_hand_landmarks, res.multi_hand_world_landmarks, res.multi_handedness):
            hs.append({
                "label": hd.classification[0].label, "score": round(hd.classification[0].score, 3),
                "img": [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in lm.landmark],
                "world": [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in wl.landmark],
            })
    frames.append(hs)
h, w = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
json.dump({"w": w, "h": h, "n": len(frames), "frames": frames,
           "edges": [list(c) for c in mp.solutions.hands.HAND_CONNECTIONS]}, open(out, "w"))
det = sum(1 for f in frames if f)
print("frames", len(frames), "with hands", det, "two hands", sum(1 for f in frames if len(f) == 2))
