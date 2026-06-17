#!/usr/bin/env python3
"""Batch 3 — weave the 10 'imagine you're here' rainforest reels into the IG calendar.

Same reflow-safe approach as batches 1–2: pin un-pinned future posts, interleave the new reels
at sprinkled day positions, renumber. Spread ~weekly (evergreen calming content). Guarded.
"""
import datetime as dt
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "instagram" / "posts.json"
START = dt.date(2026, 6, 7)
FREEZE = 14
POSITIONS = [17, 23, 29, 35, 41, 47, 53, 59, 65, 71]   # ~weekly, Jun23 → Aug16
PREFIX = "b3-"

CTA = "Leaf People — bring the rainforest home. The rare-plant app, link in bio \U0001F33F"
HASHTAGS = ["#leafpeopleapp", "#rainforest", "#cloudforest", "#nature", "#jungle",
            "#rareplants", "#aroidsofinstagram", "#plantsofinstagram", "#wanderlust", "#calm"]

# (title, hook[burned in], caption) in reel order 1..10
REELS = [
    ("The Chocó", "The Chocó · Colombia",
     "Imagine you're here right now. The Chocó, Colombia — the wettest forest on Earth, and the birthplace of half the velvet anthuriums you covet. Just birdsong, dripping leaves, and your coffee. Breathe. \U0001F33F"),
    ("The Amazon", "The Amazon · Peru",
     "Imagine you're here right now. The Amazon — the largest rainforest on the planet, breathing mist off the river at dawn. Sip slowly. \U0001F33F"),
    ("Monteverde", "Monteverde Cloud Forest · Costa Rica",
     "Imagine you're here right now. Monteverde — a cloud forest so wet the trees wear moss like coats. Just the drip, the birds, and your coffee. \U0001F33F"),
    ("Borneo", "The Rainforests of Borneo",
     "Imagine you're here right now. Borneo — ancient jungle where the giant Alocasia grow wild. Steam rising, light cutting through the canopy. \U0001F33F"),
    ("The Atlantic Forest", "The Atlantic Forest · Brazil",
     "Imagine you're here right now. Brazil's Atlantic Forest — golden light through the tree ferns, alive with sound. Stay a while. \U0001F33F"),
    ("Mindo", "Mindo Cloud Forest · Ecuador",
     "Imagine you're here right now. Mindo, in the Andes of Ecuador — cloud-forest ridges, hummingbirds, and a hush you can feel. \U0001F33F"),
    ("The Daintree", "The Daintree · Australia",
     "Imagine you're here right now. The Daintree — 180 million years old, the oldest rainforest on Earth. Ferns, a clear creek, and quiet. \U0001F33F"),
    ("The Congo Basin", "The Congo Basin",
     "Imagine you're here right now. The Congo Basin — the planet's second lung, vast and green and humming. Just you and the canopy. \U0001F33F"),
    ("Gunung Leuser", "Gunung Leuser · Sumatra",
     "Imagine you're here right now. Gunung Leuser, Sumatra — steaming lowland jungle, leaves the size of doors, rain on the canopy. \U0001F33F"),
    ("Kauaʻi", "Kauai · Hawaii",
     "Imagine you're here right now. The rainforests of Kauaʻi — emerald cliffs, a distant waterfall, soft rain. Paradise, quietly. \U0001F33F"),
]


def date_for(day):
    return (START + dt.timedelta(days=day - 1)).isoformat()


def reel_post(i, title, hook, caption):
    n = f"{i:02d}"
    return {
        "id": f"{PREFIX}{n}", "day": None, "date": None,
        "phase": "lifestyle", "branch": "model-reels", "status": "draft",
        "title": title,
        "image": f"/images/instagram/{PREFIX}{n}-cover.jpg",
        "img_ready": f"/images/instagram/{PREFIX}{n}-cover.jpg",
        "video": f"/videos/instagram/{PREFIX}{n}.mp4",
        "reel": True,
        "caption": caption,
        "hashtags": list(HASHTAGS),
        "cta": CTA,
        "hook": hook,
        "metrics": {"likes": 0, "comments": 0, "saves": 0, "follows": 0, "reach": 0},
    }


def main():
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    if any(str(p.get("id", "")).startswith(PREFIX) for p in posts):
        raise SystemExit("batch-3 reels already inserted — aborting.")

    frozen = [p for p in posts if p["day"] <= FREEZE]
    future = sorted((p for p in posts if p["day"] > FREEZE), key=lambda p: p["day"])
    for p in future:
        if "img_ready" not in p:
            d = p["day"]
            ig = ROOT / "images" / "ig_ready" / f"d{d:02d}.jpg"
            p["img_ready"] = f"/images/ig_ready/d{d:02d}.jpg" if ig.exists() else p["image"]
        if p.get("reel") and "video" not in p:
            vid = ROOT / "videos" / "instagram" / f"d{p['day']:02d}.mp4"
            if vid.exists():
                p["video"] = f"/videos/instagram/d{p['day']:02d}.mp4"

    reels = [reel_post(i + 1, *REELS[i]) for i in range(len(REELS))]
    out, fi, mi, new_day = [], 0, 0, FREEZE + 1
    while fi < len(future) or mi < len(reels):
        if mi < len(reels) and new_day == POSITIONS[mi]:
            p = reels[mi]; mi += 1
        else:
            p = future[fi]; fi += 1
        p["day"] = new_day
        p["date"] = date_for(new_day)
        out.append(p)
        new_day += 1

    new_posts = frozen + out
    days = [p["day"] for p in new_posts]
    assert days == list(range(1, len(new_posts) + 1)), "days not contiguous"
    assert len(new_posts) == len(posts) + 10, "expected +10 posts"

    shutil.copy(POSTS, POSTS.with_suffix(".json.bak"))
    POSTS.write_text(json.dumps(new_posts, indent=2) + "\n", encoding="utf-8")
    print(f"inserted 10 batch-3 rainforest reels. {len(posts)} -> {len(new_posts)} posts.")
    for m in reels:
        print(f"  day {m['day']:>3}  {m['date']}  {m['id']}  \"{m['hook']}\"")


if __name__ == "__main__":
    main()
