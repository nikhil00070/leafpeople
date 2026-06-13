#!/usr/bin/env python3
"""Generate TRUE AI image-to-video Reels via Replicate, replacing the plain-zoom baseline.

For each reel-day (even day) post: composite the photo onto a clean 9:16 still, send it to
an image-to-video model on Replicate which ANIMATES it (slow camera push-in, gently swaying
leaves, shifting light), then post-process to a 1080x1920 H.264 reel + silent audio track.
Output overwrites videos/instagram/dNN.mp4. Runs locally and commits the mp4s — the daily
cron just posts the committed file, so NO API call happens at post time.

Setup (one time):
  1. Get a token at https://replicate.com/account/api-tokens (needs billing on the account).
  2.  export REPLICATE_API_TOKEN=r8_xxx

Usage:
  python3 pipeline/make_reels_ai.py 8          # JUST day 8 — always test one first
  python3 pipeline/make_reels_ai.py 8 90       # even days 8..90 (batch)

Cost: pay-per-clip, set by the chosen model (typically ~$0.10–0.50 per 5s clip).
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "instagram" / "posts.json"
OUT_DIR = ROOT / "videos" / "instagram"
API = "https://api.replicate.com/v1"
REEL = (1080, 1920)
FPS = 30
DURATION = 5

# ── MODEL CONFIG ─────────────────────────────────────────────────────────────────────
# Swap MODEL freely. Input field names differ per model — confirm on the first test run
# (Replicate returns a clear schema error if a field is wrong, and we adjust here).
#   kwaivgi/kling-v1.6-standard : start_image, prompt, aspect_ratio, duration   (great quality)
#   minimax/video-01           : first_frame_image, prompt
#   stability-ai/stable-video-diffusion : input_image (no text prompt; subtle motion, cheapest)
MODEL = "kwaivgi/kling-v1.6-standard"
PROMPT = ("Subtle cinematic motion: a slow camera push-in on the plant, leaves sway gently, "
          "soft shifting light through a rainforest canopy. Photorealistic, calm, no people, no text.")


def build_input(image_data_uri):
    return {
        "start_image": image_data_uri,
        "prompt": PROMPT,
        "negative_prompt": "distortion, morphing, melting, extra leaves, text, watermark, people, hands",
        "aspect_ratio": "9:16",
        "duration": DURATION,
    }
# ─────────────────────────────────────────────────────────────────────────────────────


def token():
    t = os.environ.get("REPLICATE_API_TOKEN")
    if not t:
        sys.exit("Set REPLICATE_API_TOKEN — get one at replicate.com/account/api-tokens")
    return t


def ffmpeg_exe():
    return os.environ.get("FFMPEG") or __import__("imageio_ffmpeg").get_ffmpeg_exe()


def nine_sixteen_jpeg(src: Path, dst: Path):
    """9:16 composite (sharp photo on a blurred/darkened fill) as a compact JPEG for the model."""
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    bg = ImageOps.fit(im, REEL, method=Image.LANCZOS, centering=(0.5, 0.4)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.eval(bg, lambda p: int(p * 0.82))
    fg = ImageOps.contain(im, REEL, method=Image.LANCZOS)
    bg.paste(fg, ((REEL[0] - fg.width) // 2, (REEL[1] - fg.height) // 2))
    bg.save(dst, "JPEG", quality=90)


def api(method, path, tok, body=None):
    url = path if path.startswith("http") else f"{API}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Replicate {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")


def generate(image_uri, tok):
    pred = api("POST", f"models/{MODEL}/predictions", tok, {"input": build_input(image_uri)})
    get_url = pred["urls"]["get"]
    for _ in range(150):  # up to ~12 min (video gens are slow)
        if pred.get("status") in ("succeeded", "failed", "canceled"):
            break
        time.sleep(5)
        pred = api("GET", get_url, tok)
    if pred.get("status") != "succeeded":
        raise RuntimeError(f"prediction {pred.get('status')}: {pred.get('error')}")
    out = pred["output"]
    return out[-1] if isinstance(out, list) else out


def postprocess(in_mp4, out_mp4):
    vf = (f"scale={REEL[0]}:{REEL[1]}:force_original_aspect_ratio=increase,"
          f"crop={REEL[0]}:{REEL[1]},format=yuv420p")
    cmd = [ffmpeg_exe(), "-y", "-i", str(in_mp4),
           "-f", "lavfi", "-t", str(DURATION), "-i", "anullsrc=r=44100:cl=stereo",
           "-vf", vf, "-r", str(FPS), "-t", str(DURATION),
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", str(out_mp4)]
    subprocess.run(cmd, check=True, capture_output=True)


def main(argv):
    tok = token()
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    if len(argv) == 1:
        days = {int(argv[0])}
    elif len(argv) == 2:
        days = set(range(int(argv[0]), int(argv[1]) + 1))
    else:
        days = {p["day"] for p in posts if p.get("status") != "posted"}
    days = {d for d in days if d % 2 == 0}

    made = 0
    for p in posts:
        if p.get("day") not in days or not p.get("image"):
            continue
        src = ROOT / p["image"].lstrip("/")
        if not src.exists():
            print(f"[ai-reels] SKIP day {p['day']}: missing {p['image']}")
            continue
        dst = OUT_DIR / f"d{p['day']:02d}.mp4"
        print(f"[ai-reels] day {p['day']:>3}: compositing + sending to {MODEL} …")
        with tempfile.TemporaryDirectory() as td:
            still = Path(td) / "still.jpg"
            nine_sixteen_jpeg(src, still)
            uri = "data:image/jpeg;base64," + base64.b64encode(still.read_bytes()).decode()
            video_url = generate(uri, tok)
            raw = Path(td) / "raw.mp4"
            urllib.request.urlretrieve(video_url, raw)
            dst.parent.mkdir(parents=True, exist_ok=True)
            postprocess(raw, dst)
        made += 1
        print(f"[ai-reels] day {p['day']:>3}  ->  {dst.relative_to(ROOT)}")
    print(f"[ai-reels] generated {made} AI reel(s)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main(sys.argv[1:]))
