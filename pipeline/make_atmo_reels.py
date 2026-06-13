#!/usr/bin/env python3
"""Atmospheric 'plant wall' brand reels via Veo TEXT-to-video (no source photo).

Cinematic establishing scenes — a slow walk through a moody indoor jungle to a towering
living plant wall, a styled living-room plant wall, a misty greenhouse aisle. AI-imagined
(no real-species claim), so they're safe as brand atmosphere sprinkled between the
plant-spotlight reels. Veo generates the video + ambient audio from the prompt alone.

    export REPLICATE_API_TOKEN=...
    python3 pipeline/make_atmo_reels.py 1        # just prompt #1 (test one first)
    python3 pipeline/make_atmo_reels.py          # all prompts
Override length/res with VEO_DUR / VEO_RES; output dir with REEL_OUT_DIR (default videos/instagram, named atmo-NN.mp4).
"""
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_reels_ai as M  # reuse run(), postprocess(), token(), ffmpeg_exe()

MODEL = "google/veo-3-fast"
OUT_DIR = Path(os.environ.get("REEL_OUT_DIR") or (HERE.parent / "videos" / "instagram"))
DUR = int(os.environ.get("VEO_DUR", "8"))   # longer than spotlights — needs room to move
RES = os.environ.get("VEO_RES", "720p")

# Each: a distinct cinematic jungle-room scene. #1 is the (kept) all-Monstera wall; #2+ MUST
# show a deliberately DIVERSE mix of species (varied leaf shapes), not one type. No people/text.
DIVERSE = ("a DIVERSE mix of rare tropical plants — dark velvet heart-shaped anthurium leaves, long "
           "pendant strap leaves, silver-veined philodendrons, a few fenestrated monstera leaves, round "
           "coin-leaf plants, fuzzy textured begonias, trailing hoyas — many DIFFERENT species and leaf "
           "shapes, deliberately varied, no two leaves alike")
PROMPTS = [
    # #1 — KEEP (already generated as the Monstera wall)
    "Cinematic slow forward walk through a dark, moody indoor jungle room along a gently curved "
    "stone path toward a towering floor-to-ceiling living wall of Monstera deliciosa. Soft "
    "volumetric light, faint drifting mist, deep greens. Photorealistic, no people, no text. "
    "Ambient sound: tropical birdsong and a soft breeze.",
    "Cinematic slow forward walk along a curved stone path toward a towering floor-to-ceiling living "
    f"plant wall displaying {DIVERSE}. Dark moody greens, soft volumetric light, drifting mist. "
    "Photorealistic, no people, no text. Ambient sound: tropical birdsong and a soft breeze.",
    f"Slow cinematic dolly along a styled modern living-room plant wall overflowing with {DIVERSE}, "
    "warm low light, cozy dark interior, shelves and a moss wall. Photorealistic, no people, no text. "
    "Ambient sound: gentle indoor calm with faint birdsong.",
    f"Cinematic walk into a misty tropical greenhouse aisle flanked by {DIVERSE}, shafts of soft "
    "morning light, dewy leaves, deep green atmosphere, gentle push forward. Photorealistic, no people, "
    "no text. Ambient sound: dripping water and distant birds.",
    f"Slow reveal panning across a dramatic dark-green collector's plant wall of {DIVERSE} under soft "
    "spotlights, glossy wet leaves, museum-like moody lighting, faint mist. Photorealistic, no people, "
    "no text. Ambient sound: quiet ambient hum and soft birdsong.",
]


def build_input(prompt):
    return {"prompt": prompt, "aspect_ratio": "9:16", "resolution": RES,
            "duration": DUR, "generate_audio": True}


def main(argv):
    tok = M.token()
    idxs = [int(argv[0]) - 1] if argv else range(len(PROMPTS))
    made = 0
    for i in idxs:
        if i < 0 or i >= len(PROMPTS):
            continue
        dst = OUT_DIR / f"atmo-{i + 1:02d}.mp4"
        print(f"[atmo] #{i + 1}: text->video via {MODEL} ({DUR}s) …")
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "raw.mp4"
            urllib.request.urlretrieve(M.run(MODEL, build_input(PROMPTS[i]), tok), raw)
            dst.parent.mkdir(parents=True, exist_ok=True)
            M.postprocess(raw, dst, keep_audio=True)
        made += 1
        print(f"[atmo] #{i + 1}  ->  {dst}")
    print(f"[atmo] generated {made} atmosphere reel(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
