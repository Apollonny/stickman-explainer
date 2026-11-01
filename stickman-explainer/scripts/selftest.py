#!/usr/bin/env python3
"""Self-test for render.py. Run after ANY change to the renderer:  python scripts/selftest.py
Renders stills only (fast); the audio test also needs ffmpeg. Exit code 0 = all passed."""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render.py")
EX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "example_storyboard.json")
tmp = tempfile.mkdtemp()
fails = []


def run(sb, argfn, name="t"):
    path = os.path.join(tmp, name + ".json")
    json.dump(sb, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    out = os.path.join(tmp, "out_" + name)
    r = subprocess.run([sys.executable, R, path, *argfn(out)], capture_output=True, text=True)
    return r, out


def stills(sb, name):
    return run(sb, lambda o: ["--stills", o], name=name)


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def sc(els, **kw):
    return {"scenes": [{"duration": 2, "elements": els, **kw}]}


def dark_cols(png, y0, y1, thr=120):
    im = np.array(Image.open(png).convert("L"))[y0:y1] < thr
    xs = np.where(im.any(0))[0]
    return (xs[0], xs[-1]) if len(xs) else None


# every option of every element renders
combos = []
for pose in ["stand", "arms_open", "point", "wave", "think", "shrug", "sit"]:
    combos.append({"type": "figure", "x": 540, "ground": 1400, "h": 600, "pose": pose})
for face in ["neutral", "smile", "happy", "sad", "surprised", "angry"]:
    combos.append({"type": "figure", "x": 540, "ground": 1400, "h": 600, "face": face})
for acc in ["helmet", "crown", "hat", "glasses"]:
    combos.append({"type": "figure", "x": 540, "ground": 1400, "h": 600, "accessory": acc, "cape": True})
for kind in ["barrel", "bowl", "bucket", "house", "book", "box", "triangle", "coins", "tree"]:
    combos.append({"type": "prop", "kind": kind, "x": 300, "y": 600, "w": 200, "h": 150, "cross": True, "flip": True})
r, _ = stills(sc(combos), "all_options")
check(r.returncode == 0, "all poses/faces/accessories/props render" + ("" if r.returncode == 0 else ": " + r.stderr[-200:]))

# example storyboard + carry
r, out = stills(json.load(open(EX, encoding="utf-8")), "example")
check(r.returncode == 0 and len(os.listdir(out)) == 3, "example storyboard renders 3 stills")

# ground defaults span the canvas
r, out = stills(sc([{"type": "ground", "y": 1400}]), "ground")
span = dark_cols(os.path.join(out, "scene_01.png"), 1380, 1420) if r.returncode == 0 else None
check(span is not None and span[0] < 80 and span[1] > 1000, f"ground without x/x2 spans the canvas (got {span})")

# long caption wraps inside the margins
r, out = stills(sc([], caption="çok uzun bir altyazı cümlesi " * 8), "longcap")
span = dark_cols(os.path.join(out, "scene_01.png"), 1380, 1600) if r.returncode == 0 else None
check(span is not None and span[0] >= 40 and span[1] <= 1040, f"long caption stays inside margins (got {span})")

# friendly validation errors (non-zero exit, no traceback)
bad = {
    "unknown pose": sc([{"type": "figure", "x": 5, "ground": 9, "h": 9, "pose": "dance"}]),
    "unknown prop": sc([{"type": "prop", "kind": "ufo", "x": 1, "y": 1}]),
    "unknown type": sc([{"type": "banana"}]),
    "missing field": sc([{"type": "sun"}]),
    "bad font": sc([{"type": "text", "text": "a", "x": .5, "y": 5, "font": "comic"}]),
    "single-point path": sc([{"type": "lines", "paths": [[[1, 1]]]}]),
    "null at": sc([{"type": "sun", "x": 5, "y": 5, "at": None}]),
    "duplicate ids": sc([{"id": "a", "type": "sun", "x": 5, "y": 5}, {"id": "a", "type": "sun", "x": 9, "y": 5}]),
    "zero duration": {"scenes": [{"duration": 0}]},
    "no scenes": {"scenes": []},
    "odd size": {"meta": {"width": 1081, "height": 1921}, "scenes": [{"duration": 1}]},
    "carry unknown id": {"scenes": [{"duration": 1}, {"duration": 1, "carry": ["nope"]}]},
}
for i, (n, sb) in enumerate(bad.items()):
    r, _ = stills(sb, f"bad{i}")
    check(r.returncode != 0 and "Traceback" not in r.stderr, f"clean error for: {n}")

# valid edge cases
r, _ = stills(sc([{"type": "sun", "x": 500, "y": 500, "r": 50, "color": "#abc"}]), "hex3")
check(r.returncode == 0, "3-digit hex colour accepted")
r, _ = stills({"scenes": [{"duration": 1, "carry": "all"}]}, "carry_first")
check(r.returncode == 0, "carry 'all' on first scene is harmless")

# CLI + audio (needs ffmpeg)
r = subprocess.run([sys.executable, R, EX], capture_output=True, text=True)
check(r.returncode != 0 and "Traceback" not in r.stderr, "no output + no --stills gives usage error")
try:
    a = os.path.join(tmp, "a.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=1", a], check=True)
    sb = {"scenes": [{"duration": 3, "elements": [{"type": "ground", "y": 1400}]}]}
    path = os.path.join(tmp, "vid.json")
    json.dump(sb, open(path, "w"))
    mp4 = os.path.join(tmp, "v.mp4")
    r = subprocess.run([sys.executable, R, path, mp4, "--draft", "--audio", a], capture_output=True, text=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                             capture_output=True, text=True).stdout.strip())
    check(r.returncode == 0 and abs(d - 3.0) < 0.2, f"video keeps full length when audio is shorter ({d:.2f}s)")
    r = subprocess.run([sys.executable, R, path, mp4, "--draft", "--audio", os.path.join(tmp, "missing.mp3")],
                       capture_output=True, text=True)
    check(r.returncode != 0 and "Traceback" not in r.stderr, "missing audio file gives a clean error")
except (FileNotFoundError, subprocess.CalledProcessError):
    print("SKIP audio tests (ffmpeg not available)")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)

