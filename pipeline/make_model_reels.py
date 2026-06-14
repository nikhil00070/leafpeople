#!/usr/bin/env python3
"""Lifestyle 'model holds a rare plant in her living room' reels via Veo text-to-video + music.

A young woman gently lifts/turns a potted rare plant in a cozy modern room. AI-imagined plant
(no real-species claim) — aspirational brand reels. Each gets a soft AI music bed mixed under
the room tone (copyright-safe; the API can't add IG trending audio). Reuses make_reels_ai.

    export REPLICATE_API_TOKEN=...
    python3 pipeline/make_model_reels.py          # all (skips any model-NN.mp4 that already exists)
    python3 pipeline/make_model_reels.py 3        # just #3
Music beds: /tmp/music_beds/bed-*.mp3 (rotated). Output: /tmp/model_reels/model-NN.mp4 (override REEL_OUT_DIR).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_reels_ai as M  # run(), postprocess(), token()

MODEL = "google/veo-3-fast"
OUT_DIR = Path(os.environ.get("REEL_OUT_DIR") or "/tmp/model_reels")
BEDS_DIR = Path(os.environ.get("MUSIC_BEDS") or "/tmp/music_beds")
DUR = int(os.environ.get("VEO_DUR", "8"))
RES = os.environ.get("VEO_RES", "720p")
FF = imageio_ffmpeg.get_ffmpeg_exe()

_GUARD = ("Natural realistic hands, correct number of fingers, no warping, no morphing, steady "
          "gentle motion, photorealistic. No text, no logos. Ambient sound: calm indoor room tone "
          "with faint birdsong.")
_BASE = ("Cinematic vertical 9:16 video, shot like a cozy phone video. {who} {action} a {plant}, "
         "lifting it gently toward the camera and slowly turning it to show the leaves, smiling "
         "softly, in {room}. ")

# (who, plant, room) — varied leaf forms, hair, and interiors.
SPECS = [
    ("a young woman with long brunette hair in a cream knit sweater", "large potted dark velvety anthurium with big heart-shaped leaves and silvery veins", "a bright modern plant-filled living room with a linen sofa and soft morning light"),
    ("a young blonde woman in a beige tee", "tall potted Monstera deliciosa with big glossy fenestrated split leaves", "a sunny minimalist white living room with oak floors"),
    ("a young woman with dark wavy hair", "potted silvery velvet philodendron with pale-veined heart-shaped leaves", "a cozy boho reading nook with rattan and warm lamplight"),
    ("a young blonde woman in a linen shirt", "trailing hoya in a hanging terracotta pot with cascading waxy vines", "a bright sunroom window full of plants"),
    ("a young woman with brunette hair in a bun", "potted fuzzy textured begonia with patterned silver-spotted leaves", "a warm mid-century living room with wooden shelves"),
    ("a young blonde woman", "potted anthurium with very long strappy dark velvet leaves draping down", "a soft neutral modern apartment with a big window"),
    ("a young woman with long brown hair", "potted Philodendron melanochrysum with long dark velvet drop-shaped leaves", "a cozy green plant corner with a jute rug"),
    ("a young blonde woman in an oversized sweater", "potted variegated Monstera with white-and-green marbled split leaves", "a bright Scandinavian living room"),
    ("a young woman with dark hair", "potted Alocasia with dramatic dark arrow-shaped leaves and pale veins", "a moody modern loft with soft window light"),
    ("a young blonde woman", "potted philodendron with pink-and-green variegated heart-shaped leaves", "a cheerful sunlit living room with a cane chair"),
]
PROMPTS = [_BASE.format(who=w, action="holds", plant=p, room=r) + _GUARD for (w, p, r) in SPECS]


def build_input(prompt):
    return {"prompt": prompt, "aspect_ratio": "9:16", "resolution": RES, "duration": DUR, "generate_audio": True}


def mix_music(video, bed, dst):
    # groovy bed up front, ambient room tone low underneath (so the music carries it)
    subprocess.run([FF, "-y", "-i", str(video), "-i", str(bed),
                    "-filter_complex", "[0:a]volume=0.22[a0];[1:a]volume=1.0,afade=t=out:st=7:d=1.2[a1];[a0][a1]amix=inputs=2:duration=first[aout]",
                    "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(dst)],
                   check=True, capture_output=True)


def main(argv):
    tok = M.token()
    beds = sorted(BEDS_DIR.glob("bed-*.mp3"))
    idxs = [int(argv[0]) - 1] if argv else range(len(PROMPTS))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for i in idxs:
        if i < 0 or i >= len(PROMPTS):
            continue
        rawf = OUT_DIR / f"model-{i + 1:02d}-raw.mp4"   # no-music master (persisted, so music is a cheap re-mix)
        dst = OUT_DIR / f"model-{i + 1:02d}.mp4"         # final, with music
        if not rawf.exists():
            print(f"[model] #{i + 1}: text->video via {MODEL} ({DUR}s) …")
            with tempfile.TemporaryDirectory() as td:
                raw = Path(td) / "raw.mp4"
                urllib.request.urlretrieve(M.run(MODEL, build_input(PROMPTS[i]), tok), raw)
                M.postprocess(raw, rawf, keep_audio=True)
        else:
            print(f"[model] #{i + 1}: video master exists — re-mixing music only")
        bed = beds[i % len(beds)] if beds else None
        if bed:
            mix_music(rawf, bed, dst)
        else:
            shutil.copy(rawf, dst)
        print(f"[model] #{i + 1}  ->  {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
