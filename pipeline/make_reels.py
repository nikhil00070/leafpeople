#!/usr/bin/env python3
"""Pre-render Reels (9:16 MP4s) from post images for the 'every 3rd post' cadence.

Static photos barely reach a cold account; Reels get pushed to non-followers. This turns
a post's still into a 6s 1080x1920 Reel: the photo is composited onto a blurred, darkened
9:16 canvas (same look as the feed images, rendered 2x for zoom headroom), then ffmpeg adds
a slow Ken Burns zoom and a silent AAC track (Reels need an audio stream), H.264 + faststart.
Output: videos/instagram/dNN.mp4 — committed so it's public via Vercel (what the Graph API fetches).

ffmpeg comes from the pip package imageio-ffmpeg (no Homebrew needed); override with FFMPEG=path.

Usage:
  python3 pipeline/make_reels.py            # all reel-days (day%3==0) that aren't posted yet
  python3 pipeline/make_reels.py 6 60       # reel-days in 6..60
  python3 pipeline/make_reels.py 6          # just day 6
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "instagram" / "posts.json"
OUT_DIR = ROOT / "videos" / "instagram"
REEL = (1080, 1920)            # 9:16
SUPER = (REEL[0] * 2, REEL[1] * 2)  # render 2x so the zoom stays sharp
DURATION = 6                   # seconds
FPS = 30


def ffmpeg_exe():
    env = os.environ.get("FFMPEG")
    if env:
        return env
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def composite_still(src: Path, dst: Path):
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    bg = ImageOps.fit(im, SUPER, method=Image.LANCZOS, centering=(0.5, 0.4))
    bg = bg.filter(ImageFilter.GaussianBlur(80))
    bg = Image.eval(bg, lambda p: int(p * 0.80))
    fg = ImageOps.contain(im, SUPER, method=Image.LANCZOS)
    canvas = bg.copy()
    canvas.paste(fg, ((SUPER[0] - fg.width) // 2, (SUPER[1] - fg.height) // 2))
    canvas.save(dst, "PNG")


def render_reel(src: Path, dst: Path):
    frames = DURATION * FPS
    with tempfile.TemporaryDirectory() as td:
        still = Path(td) / "still.png"
        composite_still(src, still)
        # slow zoom 1.00 -> 1.10 across the clip; pan stays centered
        zoom = f"zoompan=z='min(zoom+{0.10/frames:.6f},1.10)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={REEL[0]}x{REEL[1]}:fps={FPS}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg_exe(), "-y",
            "-i", str(still),
            "-f", "lavfi", "-t", str(DURATION), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf", f"{zoom},format=yuv420p",
            "-t", str(DURATION), "-r", str(FPS),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", "-shortest",
            str(dst),
        ]
        subprocess.run(cmd, check=True, capture_output=True)


def main(argv):
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    if len(argv) == 1:
        days = {int(argv[0])}
    elif len(argv) == 2:
        days = set(range(int(argv[0]), int(argv[1]) + 1))
    else:
        days = {p["day"] for p in posts if p.get("status") != "posted"}
    days = {d for d in days if d % 3 == 0}  # every 3rd post is a Reel

    made, skipped = 0, []
    for p in posts:
        if p.get("day") not in days or not p.get("image"):
            continue
        src = ROOT / p["image"].lstrip("/")
        if not src.exists():
            skipped.append(f"day {p['day']}: missing {p['image']}")
            continue
        dst = OUT_DIR / f"d{p['day']:02d}.mp4"
        render_reel(src, dst)
        made += 1
        print(f"[reels] day {p['day']:>3} -> {dst.relative_to(ROOT)}")
    print(f"[reels] rendered {made} reel(s)")
    for s in skipped:
        print(f"[reels] SKIP {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
