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

_GUARD = ("Photorealistic, cinematic, natural, no warping, no morphing, steady gentle camera. No "
          "text, no logos. Ambient sound: an immersive rainforest soundscape — birdsong, insects, "
          "dripping water, distant calls and a soft breeze. No music.")
_BASE = ("Cinematic vertical 9:16 video, shot like a cozy phone video. {who} {action} a {plant}, "
         "lifting it gently toward the camera and slowly turning it to show the leaves, smiling "
         "softly, in {room}. ")

# (who, plant, room) — varied leaf forms, hair, and interiors.
# Atmospheric rainforest reels — a woman seen FROM BEHIND, sipping coffee, gazing into a named real rainforest.
_RF = ("Cinematic vertical 9:16 video, calm, slow and immersive. Seen from behind, over her shoulder, a "
       "young woman {who} sits quietly at the edge of {place}, holding a cup of coffee and slowly sipping "
       "as she gazes out at the lush, misty understory — {detail}. Her face is not shown. Soft natural "
       "light, gentle drifting mist, a deep sense of peace. ")
RF_SPECS = [
    ("with long dark hair", "the dripping, ultra-wet Chocó rainforest of Colombia", "giant philodendrons and velvet anthuriums, thick mist, water beading on every leaf"),
    ("with a loose braid", "the vast Amazon rainforest in Peru", "a slow river below a dense green canopy, morning mist rising, tangled lush understory"),
    ("with dark wavy hair", "the Monteverde cloud forest of Costa Rica", "moss-draped trees, ferns and bromeliads everywhere, swirling mist, soft filtered light"),
    ("with straight black hair", "the ancient rainforest of Borneo", "enormous buttress-rooted trees, giant Alocasia leaves, humid jungle, shafts of light"),
    ("with curly hair", "the dense Atlantic Forest of Brazil", "a layered green canopy, tree ferns and epiphytes, warm golden light filtering through"),
    ("with long brown hair", "the Mindo cloud forest in the Andes of Ecuador", "misty mountain rainforest, hanging mosses, hummingbirds, dramatic green ridges"),
    ("with blonde hair", "the ancient Daintree rainforest of Australia", "primeval ferns and fan palms, a clear creek, dappled emerald light"),
    ("with dark coiled hair", "the deep Congo Basin rainforest of Africa", "towering old-growth trees, broad green leaves, humid haze, a sense of vastness"),
    ("with straight dark hair", "the steaming lowland rainforest of Gunung Leuser in Sumatra", "dense dripping jungle, huge leaves, fog drifting over the canopy"),
    ("with long dark hair", "the emerald rainforest of Kauai, Hawaii", "jagged misty green cliffs, ferns and tropical foliage, a distant waterfall, soft rain"),
]
PROMPTS = [_RF.format(who=w, place=p, detail=d) + _GUARD for (w, p, d) in RF_SPECS]


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
