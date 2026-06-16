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
# All six are funny "plant-person confession" concept reels — each its own distinct scene.
CONCEPT_PROMPTS = [
    ("Cinematic vertical 9:16 video, shot like a cozy phone video. A young smiling woman sits in the "
     "driver's seat of a car absolutely packed full of potted houseplants — plants filling the passenger "
     "seat, the back seats and the footwells, big green leaves and trailing vines pressed against every "
     "window. She turns to the camera with a guilty, delighted grin. Warm afternoon light. " + _GUARD),
    ("Cinematic vertical 9:16 video, shot like a cozy phone video. A young woman opens her front door with "
     "a delighted, surprised smile, and a cheerful little parade of small potted houseplants on tiny legs "
     "walks in through the doorway one after another into a sunlit living room. Whimsical and charming, "
     "photorealistic. " + _GUARD),
    ("Cinematic vertical 9:16 video, shot like a cozy phone video. A young woman stands in a lush plant "
     "shop holding a precarious overflowing armful of potted plants — far more than she can carry, leaves "
     "half-covering her face — grinning with delight, surrounded by shelves of greenery. Bright daylight. " + _GUARD),
    ("Cinematic vertical 9:16 video, shot like a cozy phone video. A young woman happily struggles to "
     "carry an enormous potted plant much bigger than herself across a sunlit living room, huge leaves "
     "towering over her, with a determined delighted smile. " + _GUARD),
    ("Cinematic vertical 9:16 video, shot like a cozy phone video. A young woman sits happily on a small "
     "couch that is completely surrounded and overtaken by dozens of potted houseplants — plants on every "
     "cushion and all around her, barely room for her — giving a playful shrug and grin to the camera. "
     "Warm cozy living room. " + _GUARD),
    ("Cinematic vertical 9:16 video, shot like a cozy phone video. A young woman kneels on the floor "
     "excitedly unboxing a mail-order plant from a cardboard shipping box, bubble wrap and packing paper "
     "around her, lifting out a healthy potted plant with an ecstatic delighted smile. Cozy home, warm light. " + _GUARD),
]
PROMPTS = CONCEPT_PROMPTS


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
