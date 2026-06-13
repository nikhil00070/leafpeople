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
OUT_DIR = Path(os.environ.get("REEL_OUT_DIR") or (ROOT / "videos" / "instagram"))
OUT_SUFFIX = os.environ.get("REEL_OUT_SUFFIX", "")  # e.g. "-veo" -> dNN-veo.mp4 (for A/B tests)
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
# Drive SCENE motion (the plant is alive), NOT a camera zoom. Prompts are picked PER POST
# (rain posts get rain; everything else gets subtle motion + drifting mist) by prompts_for().
NEG = ("zoom, push-in, dolly, fast camera movement, distortion, morphing, melting, warping, "
       "extra leaves, text, watermark, people, hands")
AUDIO_MODEL = "zsxkib/mmaudio"

DEFAULT_MOTION = (
    "Locked-off static camera, no zoom. The plant is alive: leaves breathe and sway almost "
    "imperceptibly, soft light shimmers across the leaf surface and veins, faint mist drifts through "
    "the scene, dappled rainforest light shifts slowly. Photorealistic, cinematic, calm, lush. No people, no text.")
DEFAULT_AUDIO = ("soft rainforest ambience, faint dripping water, distant birdsong, gentle wind through "
                 "leaves. No music, no speech.")
RAIN_MOTION = (
    "Locked-off static camera, no zoom. Steady rain falls through the frame; raindrops streak down and "
    "splash on the broad wet leaf, water trickles along the veins, the leaf quivers gently, dappled "
    "rainforest light shifts. Photorealistic, cinematic, lush. No people, no text.")
RAIN_AUDIO = ("steady rainfall, water droplets dripping on broad leaves, soft rainforest ambience, "
              "distant birdsong. No music, no speech.")
STATE = {"prompt": DEFAULT_MOTION, "audio": DEFAULT_AUDIO}  # set per-post by main()


def prompts_for(post):
    """(motion, audio) prompt for a post. REEL_PROMPT env overrides for one-off tests."""
    if os.environ.get("REEL_PROMPT"):
        return os.environ["REEL_PROMPT"], os.environ.get("REEL_AUDIO_PROMPT", DEFAULT_AUDIO)
    t = (str(post.get("title", "")) + " " + str(post.get("caption", ""))).lower()
    if any(w in t for w in ("rain", "mist", "wet", "drip", "cloud forest", "monsoon", "humid", "dew", "fog")):
        return RAIN_MOTION, RAIN_AUDIO
    return DEFAULT_MOTION, DEFAULT_AUDIO


# Swap with REEL_MODEL=kling|seedance|veo (default veo). 'audio' = model emits its own sound.
PROFILES = {
    "kling": {"model": "kwaivgi/kling-v2.1-master", "audio": False,
              "input": lambda u: {"start_image": u, "prompt": STATE["prompt"], "negative_prompt": NEG, "duration": DURATION}},
    "seedance": {"model": "bytedance/seedance-1-pro", "audio": False,
                 "input": lambda u: {"image": u, "prompt": STATE["prompt"], "aspect_ratio": "9:16",
                                     "resolution": "1080p", "duration": DURATION, "camera_fixed": True}},
    "veo": {"model": "google/veo-3-fast", "audio": True,
            "input": lambda u: {"image": u, "prompt": STATE["prompt"], "aspect_ratio": "9:16",
                                "resolution": os.environ.get("VEO_RES", "720p"),
                                "duration": int(os.environ.get("VEO_DUR", "4")),
                                "generate_audio": True, "negative_prompt": NEG}},
}
PROFILE = PROFILES[os.environ.get("REEL_MODEL", "veo")]
MODEL = PROFILE["model"]


def build_input(image_data_uri):
    return PROFILE["input"](image_data_uri)
# ─────────────────────────────────────────────────────────────────────────────────────


def token():
    t = os.environ.get("REPLICATE_API_TOKEN")
    if not t:
        sys.exit("Set REPLICATE_API_TOKEN — get one at replicate.com/account/api-tokens")
    return t


def ffmpeg_exe():
    return os.environ.get("FFMPEG") or __import__("imageio_ffmpeg").get_ffmpeg_exe()


def nine_sixteen_jpeg(src: Path, dst: Path):
    """9:16 full-bleed JPEG for the model: cover-crop the photo to fill the frame, NO blur bars.
    Wide photos lose some sides; vertical photos (most of ours) fill cleanly."""
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    out = ImageOps.fit(im, REEL, method=Image.LANCZOS, centering=(0.5, 0.4))
    out.save(dst, "JPEG", quality=92)


UA = "Mozilla/5.0 (Macintosh) leafpeople-reels/1.0"
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", UA)]
urllib.request.install_opener(_opener)  # so urlretrieve() also sends a real UA (avoids CF 1010)


def api(method, path, tok, body=None):
    url = path if path.startswith("http") else f"{API}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(10):
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                                              "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 9:  # rate-limited (low-balance throttle) — wait + retry
                ra = (e.headers.get("retry-after") or "").strip()
                time.sleep(int(ra) + 1 if ra.isdigit() else 12)
                continue
            raise RuntimeError(f"Replicate {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")


def create_pred(model, inp, tok):
    """Create a prediction. Official models (Veo/Seedance/Kling) use models/<m>/predictions;
    community models (zsxkib/mmaudio) 404 there, so fall back to a version-pinned /predictions."""
    try:
        return api("POST", f"models/{model}/predictions", tok, {"input": inp})
    except RuntimeError as e:
        if "404" not in str(e):
            raise
        ver = (api("GET", f"models/{model}", tok).get("latest_version") or {}).get("id")
        if not ver:
            raise
        return api("POST", "predictions", tok, {"version": ver, "input": inp})


def run(model, inp, tok, tries=150):
    pred = create_pred(model, inp, tok)
    get_url = pred["urls"]["get"]
    for _ in range(tries):  # up to ~12 min (video gens are slow)
        if pred.get("status") in ("succeeded", "failed", "canceled"):
            break
        time.sleep(5)
        pred = api("GET", get_url, tok)
    if pred.get("status") != "succeeded":
        raise RuntimeError(f"{model} {pred.get('status')}: {pred.get('error')}")
    out = pred["output"]
    return out[-1] if isinstance(out, list) else out


def generate(image_uri, tok):
    return run(MODEL, build_input(image_uri), tok)


def upload_file(path, tok):
    """Upload a local file to Replicate's file store; returns a fetchable URL for model inputs."""
    boundary = "----lpboundary7MA4YWxkTrZu0gW"
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="content"; '
            f'filename="{path.name}"\r\nContent-Type: video/mp4\r\n\r\n').encode()
    body = head + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(f"{API}/files", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "User-Agent": UA,
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["urls"]["get"]


def add_audio(video_path, tok):
    """Generate scene-matched ambient audio for a silent clip via MMAudio; returns a video URL with sound."""
    url = upload_file(video_path, tok)
    return run(AUDIO_MODEL, {"video": url, "prompt": STATE["audio"], "duration": DURATION}, tok, tries=120)


def postprocess(in_mp4, out_mp4, keep_audio):
    # Normalize to exactly 1080x1920. Keep the clip's audio (Veo, or MMAudio-added) or add a
    # silent track so every reel has an audio stream.
    vf = (f"scale={REEL[0]}:{REEL[1]}:force_original_aspect_ratio=increase,"
          f"crop={REEL[0]}:{REEL[1]},format=yuv420p")
    cmd = [ffmpeg_exe(), "-y", "-i", str(in_mp4)]
    if not keep_audio:
        cmd += ["-f", "lavfi", "-t", str(DURATION), "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-vf", vf, "-r", str(FPS),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
    if not keep_audio:
        cmd += ["-shortest"]
    cmd.append(str(out_mp4))
    subprocess.run(cmd, check=True, capture_output=True)


def main(argv):
    tok = token()
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    single = len(argv) == 1
    if single:
        days = {int(argv[0])}                       # explicit single day: generate it (even or odd)
    elif len(argv) == 2:
        days = set(range(int(argv[0]), int(argv[1]) + 1))
    else:
        days = {p["day"] for p in posts if p.get("status") != "posted"}
    if not single:
        days = {d for d in days if d % 2 == 0}      # batch mode: even (reel) days only

    made = 0
    for p in posts:
        if p.get("day") not in days or not p.get("image"):
            continue
        if p.get("no_reel"):  # marked image-only (e.g. photo has a person AI would mangle)
            print(f"[ai-reels] SKIP day {p['day']}: no_reel")
            continue
        src = ROOT / p["image"].lstrip("/")
        if not src.exists():
            print(f"[ai-reels] SKIP day {p['day']}: missing {p['image']}")
            continue
        dst = OUT_DIR / f"d{p['day']:02d}{OUT_SUFFIX}.mp4"
        STATE["prompt"], STATE["audio"] = prompts_for(p)   # rain posts -> rain; else mist/shimmer
        print(f"[ai-reels] day {p['day']:>3}: compositing + sending to {MODEL} ({'rain' if STATE['prompt'] is RAIN_MOTION else 'ambient'}) …")
        with tempfile.TemporaryDirectory() as td:
            still = Path(td) / "still.jpg"
            nine_sixteen_jpeg(src, still)
            uri = "data:image/jpeg;base64," + base64.b64encode(still.read_bytes()).decode()
            raw = Path(td) / "raw.mp4"
            urllib.request.urlretrieve(generate(uri, tok), raw)
            keep_audio = PROFILE["audio"]
            if not keep_audio and os.environ.get("REEL_AUDIO") == "1":
                print(f"[ai-reels] day {p['day']:>3}: generating ambient audio via {AUDIO_MODEL} …")
                wa = Path(td) / "withaudio.mp4"
                urllib.request.urlretrieve(add_audio(raw, tok), wa)
                raw, keep_audio = wa, True
            dst.parent.mkdir(parents=True, exist_ok=True)
            postprocess(raw, dst, keep_audio)
        made += 1
        print(f"[ai-reels] day {p['day']:>3}  ->  {dst}")
    print(f"[ai-reels] generated {made} AI reel(s)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main(sys.argv[1:]))
