"""Concatenate rendered scenes (timeline.json order) and mux the score.

usage:
  assemble.py preview SHOT_DIR OUT.mp4            # fast, CRF
  assemble.py final SHOT_DIR OUT.mp4 [--mb 145]   # two-pass H.264 sized to the budget (decimal MB)
"""
import json, os, subprocess, sys

mode, shot_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
budget_mb = float(sys.argv[sys.argv.index("--mb") + 1]) if "--mb" in sys.argv else 145.0
film = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tl = json.load(open(os.path.join(film, "timeline.json")))
audio = os.path.join(film, "assets", "audio", "score.wav")


def probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True)
    return float(r.stdout.strip())


lst = os.path.join(shot_dir, "concat.txt")
total = 0.0
with open(lst, "w") as f:
    for s in tl["scenes"]:
        p = os.path.abspath(os.path.join(shot_dir, s["id"] + ".mp4"))
        if not os.path.exists(p):
            sys.exit(f"missing {p}")
        d = probe_dur(p)
        if abs(d - s["dur"]) > 0.15:
            print(f"warning: {s['id']} is {d:.2f}s, timeline says {s['dur']}s")
        total += s["dur"]
        f.write(f"file '{p}'\n")

common_in = ["-f", "concat", "-safe", "0", "-i", lst, "-i", audio]
if mode == "preview":
    cmd = ["ffmpeg", "-v", "error", "-y", *common_in, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
else:
    a_kbps = 192
    v_kbps = int((budget_mb * 1e6 * 8 / total) / 1000 - a_kbps - 30)  # 30 kbps container margin
    print(f"duration {total:.1f}s -> video {v_kbps} kbps, audio {a_kbps} kbps")
    x264 = "aq-mode=3:aq-strength=0.9:psy-rd=1.0,0.10:deblock=-1,-1:keyint=120:min-keyint=12:bframes=5:ref=4:rc-lookahead=60"
    base = ["ffmpeg", "-v", "error", "-y", *common_in, "-map", "0:v", "-c:v", "libx264", "-preset", "medium", "-profile:v", "high", "-level:v", "5.1",
            "-b:v", f"{v_kbps}k", "-maxrate", f"{int(v_kbps * 2.2)}k", "-bufsize", f"{int(v_kbps * 4)}k", "-x264-params", x264,
            "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-passlogfile", out + ".2pass"]
    subprocess.run(base + ["-pass", "1", "-an", "-f", "mp4", "/dev/null"], check=True)
    subprocess.run(base + ["-pass", "2", "-map", "1:a", "-c:a", "aac", "-b:a", f"{a_kbps}k", "-shortest", "-movflags", "+faststart", out], check=True)
size = os.path.getsize(out)
print(f"wrote {out}  {size / 1e6:.1f} MB  ({size / 2**20:.1f} MiB)")
