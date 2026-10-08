"""Approximate 3D reconstruction of one ego frame from planar scene structure (table + two walls).

Stand-in until real MoGe3 depth arrives. Output: <out>/cloud.f32 (N x [x,y,z,r,g,b]) and <out>/meta.json.
World: metres, Y up, table plane Y=0, camera at height h looking toward +Z.
usage: recon_planar.py FRAME.png OUTDIR
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
im = np.asarray(Image.open(src).convert("RGB")).astype(np.float32) / 255.0
H, W = im.shape[:2]
sx = W / 640.0  # annotations below are in 640x360 coordinates
C = np.array([392, 186]) * sx        # back corner where walls meet the table
A = np.array([0, 225]) * sx          # point on left wall/table boundary
B = np.array([460, 222]) * sx        # point on right wall/table boundary
cam_h = 0.34
f = 0.70 * W
cx, cy = W / 2, H / 2


def rays(u, v, pitch):
    x = (u - cx) / f
    y = (v - cy) / f
    fw = np.array([0, -math.sin(pitch), math.cos(pitch)])
    up = np.array([0, math.cos(pitch), math.sin(pitch)])
    rt = np.array([1, 0, 0])
    d = x[..., None] * rt + (-y)[..., None] * up + fw
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def on_table(p, pitch):
    d = rays(np.array([p[0]]), np.array([p[1]]), pitch)[0]
    t = -cam_h / d[1]
    return np.array([0, cam_h, 0]) + t * d


# choose pitch so that the two wall/table boundaries meet at a right angle
best = None
for pitch in np.linspace(0.2, 1.2, 2001):
    c, a, b = on_table(C, pitch), on_table(A, pitch), on_table(B, pitch)
    if min(c[2], a[2], b[2]) <= 0:
        continue
    va, vb = (a - c)[[0, 2]], (b - c)[[0, 2]]
    cosang = abs(va @ vb) / (np.linalg.norm(va) * np.linalg.norm(vb))
    if best is None or cosang < best[0]:
        best = (cosang, pitch)
pitch = best[1]
c3, a3, b3 = on_table(C, pitch), on_table(A, pitch), on_table(B, pitch)
print("pitch(deg)", math.degrees(pitch), "cos", best[0], "corner", c3)

# masks
uu, vv = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
_j = np.random.default_rng(3)
uu = uu + _j.uniform(-0.5, 0.5, uu.shape); vv = vv + _j.uniform(-0.5, 0.5, vv.shape)
def boundary_v(u):
    left = C[1] + (A[1] - C[1]) * (C[0] - u) / (C[0] - A[0])
    right = C[1] + (B[1] - C[1]) * (u - C[0]) / (B[0] - C[0])
    return np.where(u < C[0], left, right)
bv = boundary_v(uu)
table = vv > bv
leftwall = (~table) & (uu < C[0] + (C[1] - vv) * 0.03)
rightwall = (~table) & ~leftwall

# hands / arms polygons (640x360 coords) removed from the static scene
mask = Image.new("L", (W, H), 0)
dr = ImageDraw.Draw(mask)
for poly in ([(215, 360), (240, 300), (262, 262), (300, 258), (330, 270), (332, 290), (300, 300), (250, 330), (250, 360)],
             [(440, 300), (455, 285), (500, 282), (540, 298), (560, 330), (575, 360), (500, 360)]):
    dr.polygon([(x * sx, y * sx) for x, y in poly], fill=255)
hand = np.asarray(mask) > 0
# fill the removed hands with surrounding table texture so the static scene has no holes
import cv2
im8 = (im * 255).astype(np.uint8)
im8 = cv2.inpaint(im8, (hand.astype(np.uint8) * 255), 9, cv2.INPAINT_TELEA)
im = im8.astype(np.float32) / 255.0

d = rays(uu, vv, pitch)
P = np.zeros((H, W, 3))
o = np.array([0, cam_h, 0])
t_tab = -cam_h / np.minimum(d[..., 1], -1e-6)
P[table] = o + t_tab[table][:, None] * d[table]

def wall_hit(p0, p1, sel):
    # vertical plane through p0,p1 (table points)
    tdir = (p1 - p0); tdir[1] = 0; tdir /= np.linalg.norm(tdir)
    n = np.array([-tdir[2], 0, tdir[0]])
    dd = d[sel]
    t = ((p0 - o) @ n) / (dd @ n)
    return o + t[:, None] * dd

P[leftwall] = wall_hit(c3, a3, leftwall)
P[rightwall] = wall_hit(c3, b3, rightwall)
valid = np.isfinite(P).all(-1) & (np.linalg.norm(P - o, axis=-1) < 3.0)
valid &= P[..., 1] < 0.9

pts = P[valid]
col = im[valid]
# subsample to a budget
budget = int(sys.argv[3]) if len(sys.argv) > 3 else 400000
if len(pts) > budget:
    idx = np.random.default_rng(0).choice(len(pts), budget, replace=False)
    pts, col = pts[idx], col[idx]
kind = (pts[:, 1] > 0.004).astype(np.float32)[:, None]  # 1 = wall
arr = np.concatenate([pts, col], axis=1).astype(np.float32)
arr.tofile(os.path.join(out, "cloud.f32"))
# depth visualization (turbo colormap of camera distance) for overlay use
dist = np.linalg.norm(P - o, axis=-1)
dn = np.clip((dist - 0.25) / (1.35 - 0.25), 0, 1)
turbo = cv2.applyColorMap((dn * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
cv2.imwrite(os.path.join(out, "depth_turbo.png"), turbo)
meta = dict(n=int(len(arr)), cam=dict(pos=[0, cam_h, 0], pitch=pitch, f=f, w=W, h=H),
            corner=c3.tolist(), left=a3.tolist(), right=b3.tolist(), source=os.path.basename(src),
            note="planar stand-in reconstruction (table+walls); replace with MoGe3 depth")
json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1)
print("points", len(arr), "bounds", pts.min(0), pts.max(0))
