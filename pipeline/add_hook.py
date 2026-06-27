#!/usr/bin/env python3
"""Burn a subtle WSJ/cinematic-style text hook onto a reel (no AI, just compositing).

A restrained lower-LEFT lower-third: a thin accent bar + a kicker in spaced caps + a
headline, over a soft bottom gradient scrim for legibility. Fades in slowly and holds —
classy, not flashy. The AI video underneath is untouched.

The hook text comes from the post's `hook` field in posts.json (or the HOOK env var).

    python3 pipeline/add_hook.py 10                 # hook from posts.json[day10].hook -> videos/instagram/d10.mp4
    HOOK="A room that's only Monstera" python3 pipeline/add_hook.py 10 /tmp/d10-hook.mp4   # explicit, to a test path
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920
KICKER = os.environ.get("HOOK_KICKER", "LEAF PEOPLE")
def _accent():
    v = os.environ.get("HOOK_ACCENT")   # "r,g,b" override (e.g. ForkFox pink 250,42,82); default leaf green
    if v:
        try:
            r, g, b = (int(x) for x in v.split(",")[:3])
            return (r, g, b, 255)
        except Exception:
            pass
    return (124, 179, 66, 255)


ACCENT = _accent()
LEFT = 84                            # left margin (the "one side")


def _font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            continue
    return ImageFont.load_default()


SERIF = ["/System/Library/Fonts/Supplemental/Georgia.ttf", "/System/Library/Fonts/Georgia.ttf",
         "/System/Library/Fonts/Supplemental/Times New Roman.ttf"]
SANS = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"]


def _wrap(draw, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def _emoji_img(ch, px):
    """Render a color emoji (e.g. 🦊) as an RGBA image ~px tall via Apple Color Emoji."""
    try:
        ef = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 160)  # valid Apple strike size
    except Exception:
        return None
    canvas = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((4, 4), ch, font=ef, embedded_color=True)
    bbox = canvas.getbbox()
    if not bbox:
        return None
    g = canvas.crop(bbox)
    return g.resize((max(1, int(g.width * px / g.height)), px), Image.LANCZOS)


def make_overlay(hook, dst):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # soft bottom gradient scrim (legibility) — 0 until ~52% height, ramp to ~170 at bottom
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        t = (y - H * 0.52) / (H * 0.48)
        grad.putpixel((0, y), int(max(0.0, min(1.0, t)) * 170))
    scrim = Image.new("RGBA", (W, H), (6, 10, 8, 0))
    scrim.putalpha(grad.resize((W, H)))
    img = Image.alpha_composite(img, scrim)

    d = ImageDraw.Draw(img)
    head_f = _font(SERIF, 62)
    kick_f = _font(SANS, 25)
    lh = 76
    lines = _wrap(d, hook, head_f, W - LEFT - 150)
    tx = LEFT + 26                       # text x (right of the accent bar)
    head_top = H - 220 - len(lines) * lh
    kick_y = head_top - 52

    # kicker — rendered AS GIVEN (no forced upper, so "ForkFox" stays proper case);
    # color emoji like 🦊 are drawn as an image since PIL can't render them with a text font.
    cx = tx
    for ch in KICKER:
        if not ch.isascii() and not ch.isspace():
            em = _emoji_img(ch, 31)
            if em is not None:
                img.alpha_composite(em, (int(cx), kick_y - 3))
                cx += em.width + 6
                continue
        d.text((cx, kick_y), ch, font=kick_f, fill=(235, 238, 235, 220))
        cx += d.textlength(ch, font=kick_f) + 6

    # thin accent bar spanning kicker + headline
    d.rectangle([LEFT, kick_y + 2, LEFT + 4, head_top + len(lines) * lh - 8], fill=ACCENT)

    # headline
    for i, ln in enumerate(lines):
        d.text((tx, head_top + i * lh), ln, font=head_f, fill=(255, 255, 255, 255))
    img.save(dst)


def ffmpeg():
    return os.environ.get("FFMPEG") or __import__("imageio_ffmpeg").get_ffmpeg_exe()


def main(argv):
    day = int(argv[0])
    posts = json.loads((ROOT / "instagram" / "posts.json").read_text())
    post = next((p for p in posts if p.get("day") == day), {})
    hook = os.environ.get("HOOK") or post.get("hook")
    if not hook:
        sys.exit(f"no hook for day {day} (set HOOK=... or add a 'hook' field)")
    import shutil
    live = ROOT / "videos" / "instagram" / f"d{day:02d}.mp4"
    masters = ROOT / "_reel_masters"
    master = masters / f"d{day:02d}.mp4"
    if not master.exists():                       # snapshot the clean (no-hook) reel once
        masters.mkdir(parents=True, exist_ok=True)
        shutil.copy(live, master)
    src = master                                  # always hook from the clean master (re-wordable)
    out = Path(argv[1]) if len(argv) > 1 else live
    with tempfile.TemporaryDirectory() as td:
        ov = Path(td) / "ov.png"
        make_overlay(hook, ov)
        tmp_out = Path(td) / "out.mp4"
        vf = ("[1:v]format=rgba,fade=in:st=0.3:d=0.7:alpha=1[ov];"
              "[0:v][ov]overlay=0:0,format=yuv420p")
        subprocess.run([ffmpeg(), "-y", "-i", str(src), "-loop", "1", "-i", str(ov),
                        "-filter_complex", vf, "-c:a", "copy", "-shortest", "-movflags", "+faststart",
                        str(tmp_out)], check=True, capture_output=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(tmp_out, out)
    print(f"[hook] day {day}: \"{hook}\"  ->  {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
