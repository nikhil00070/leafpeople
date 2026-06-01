#!/usr/bin/env python3
"""
instagram_seed.py — generate the Instagram content calendar for /instagram.

Writes two files the /instagram admin page reads:
  instagram/branches.json  — the strategy tree (phases, branches, fortnight goals, config)
  instagram/posts.json     — 60-day calendar. Days 1-15 fully authored intro posts;
                             days 16-60 skeletons with a branch assigned (the learning
                             loop re-biases these later).

Design notes
------------
- Phase 1 is MANUAL-ASSIST: you post by hand from the tab; metrics are entered manually
  (or, in Phase 2, pulled from the Instagram Graph API insights endpoint). The learning
  loop (a multi-armed bandit over `branch`) runs on whatever metrics exist.
- Every post carries a curated `pool` of candidate images from the existing repo library
  so the tab's "refresh image" button has real options to cycle through.
- Re-running this script regenerates the calendar from scratch. The "rolling funnel"
  (append a fresh skeleton day each time one is posted) is a later extension of this same
  script — keep authored posts in INTRO_POSTS and skeleton scheduling in BRANCH_SCHEDULE.
"""

import json
import os
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Day 1 = tomorrow relative to seeding (2026-06-02). Hardcoded so the file is deterministic.
START = date(2026, 6, 2)
N_DAYS = 60
HANDLE = "leafpeople.app"
SITE = "leafpeople.app"

# --- Hashtag tiers -----------------------------------------------------------
BRAND_TAGS = ["#leafpeople", "#leafpeopleapp"]
DISCOVERY = ["#plantsofinstagram", "#rareplants", "#aroidaddicts", "#foliage",
             "#houseplantsofinstagram", "#indoorjungle", "#botanical", "#plantcollector"]
NICHE = {
    "velvet-anthurium": ["#anthurium", "#velvetanthurium", "#rarearoids", "#aroidsofinstagram", "#anthuriumlove"],
    "rainforest-beauty": ["#rainforest", "#understory", "#junglevibes", "#tropicalplants", "#greenery"],
    "leaf-texture":      ["#leafporn", "#venation", "#botanicaldetail", "#macrophotography", "#foliagelove"],
    "rarity-value":      ["#rareplants", "#variegata", "#plantcollector", "#aroidcollector", "#unicornplant"],
    "collector-culture": ["#plantcommunity", "#planthobby", "#plantpeople", "#aroidcollector", "#planthoarder"],
}

def tags(branch):
    return BRAND_TAGS + DISCOVERY + NICHE.get(branch, [])

# --- The strategy tree -------------------------------------------------------
BRANCHES = {
    # INTRO (1-15): pure beauty + identity. Goal: earn the follow.
    "velvet-anthurium": {"phase": "intro", "color": "#7c5cff", "label": "Velvet Anthuriums",
                         "intent": "The hero look — dark, suede, dramatic. The plant that stops the scroll."},
    "rainforest-beauty": {"phase": "intro", "color": "#2fae6b", "label": "Rainforest Beauty",
                          "intent": "Understory mood, light, lush foliage. Aspiration & calm."},
    "leaf-texture": {"phase": "intro", "color": "#d98a3a", "label": "Leaf Texture",
                     "intent": "Macro veining, iridescence, crystalline surfaces. The 'how is that real' shot."},
    "rarity-value": {"phase": "intro", "color": "#e0556d", "label": "Rarity & Value",
                     "intent": "The $400-$12k stories. Desire, scarcity, the hunt."},
    "collector-culture": {"phase": "intro", "color": "#46a7e0", "label": "Collector Culture",
                          "intent": "The people & the obsession. Belonging."},
    # CONCEPT (16-35): tie the beauty to what Leaf People does.
    "app-identify": {"phase": "concept", "color": "#5bd17a", "label": "App · Identify",
                     "intent": "Name any rare aroid from a leaf — the head-to-head proof."},
    "app-track-care": {"phase": "concept", "color": "#46c0c0", "label": "App · Track & Care",
                       "intent": "Care tracker, reminders, regional guidance."},
    "app-learn": {"phase": "concept", "color": "#8fb04a", "label": "App · Learn",
                  "intent": "Field guide & Understory deep-dives in the app."},
    "app-collect": {"phase": "concept", "color": "#c08a46", "label": "App · Collect",
                    "intent": "Collection log + the collector's marketplace."},
    # CONVERT (36-60): drive to articles, site, installs.
    "article-fieldguide": {"phase": "convert", "color": "#9a7bd1", "label": "Article · Field Guide",
                           "intent": "Species spotlight -> 'read the full guide, link in bio'."},
    "article-understory": {"phase": "convert", "color": "#d17b9a", "label": "Article · Understory",
                           "intent": "Story/culture spotlight -> 'read it, link in bio'."},
    "app-cta": {"phase": "convert", "color": "#3ec98a", "label": "App · Get it",
                "intent": "Direct install CTA, 7-day trial, $0.99/mo."},
    "community-ugc": {"phase": "convert", "color": "#e0a13a", "label": "Community / UGC",
                      "intent": "Prompt followers to share + tag; reshare the best."},
}

FORTNIGHT_GOALS = [
    {"weeks": "Days 1-14", "theme": "Establish the look & find the winning intro branch",
     "followers": 150, "avg_likes": 40, "extra": "Identify the top-performing intro branch by day 14."},
    {"weeks": "Days 15-28", "theme": "Bridge beauty -> the app",
     "followers": 400, "avg_likes": 80, "extra": "50+ bio-link clicks; double down on the proven branch."},
    {"weeks": "Days 29-42", "theme": "Concept posts turn lookers into learners",
     "followers": 800, "avg_likes": 120, "extra": "150+ link clicks; first attributed installs."},
    {"weeks": "Days 43-56", "theme": "Article tie-ins drive the site & app",
     "followers": 1500, "avg_likes": 180, "extra": "300+ clicks; 30+ attributed installs."},
    {"weeks": "Days 57-60+", "theme": "Rolling funnel — exploit winners, keep exploring",
     "followers": 2000, "avg_likes": 220, "extra": "Self-sustaining: each posted day spawns a fresh skeleton."},
]

# Skeleton branch rotation for days 16-60 (the bandit re-biases these later).
BRANCH_SCHEDULE = (
    ["app-identify", "app-track-care", "app-learn", "app-identify", "app-collect",
     "app-identify", "app-track-care", "app-learn", "app-collect", "app-identify",  # 16-25
     "app-track-care", "app-learn", "app-identify", "app-collect", "app-learn",     # 26-30
     "app-identify", "app-track-care", "app-learn", "app-collect", "app-identify"]  # 31-35
    + ["article-fieldguide", "app-cta", "article-understory", "community-ugc", "article-fieldguide",  # 36-40
       "app-cta", "article-understory", "article-fieldguide", "community-ugc", "app-cta",             # 41-45
       "article-fieldguide", "article-understory", "app-cta", "community-ugc", "article-fieldguide",  # 46-50
       "article-understory", "app-cta", "article-fieldguide", "community-ugc", "article-understory",  # 51-55
       "app-cta", "article-fieldguide", "community-ugc", "article-understory", "app-cta"]             # 56-60
)

STK = "/images/source/stock/"
PLT = "/images/plants/"
CMP = "/images/compare/"

# --- The 15 authored intro posts --------------------------------------------
# Each: branch, title (internal), caption, pool (candidate images; first is default).
INTRO_POSTS = [
    {"branch": "velvet-anthurium", "title": "The Queen",
     "caption": "Meet the Queen.\n\nAnthurium warocqueanum doesn't grow leaves — it grows banners. Two, three feet of black-green velvet hung from a rainforest tree in Colombia, catching light like crushed silk.\n\nYou don't decorate with a plant like this. You keep it.\n\nThis is the world we live in at leafpeople.app — the rare aroids most people have never seen.",
     "pool": [CMP + "lp-warocqueanum.png", STK + "anthurium-regale-hero.jpg", PLT + "anthurium.jpg"]},

    {"branch": "rainforest-beauty", "title": "Understory light",
     "caption": "This is where they actually live.\n\nNot a windowsill — the understory. Dappled light, dripping humidity, a canopy a hundred feet up. Every rare houseplant you've ever wanted is a refugee from a place that looks like this.\n\nUnderstand the home, and you understand the plant.",
     "pool": [PLT + "aroid.jpg", PLT + "the-leaf.jpg", STK + "begonia-luxurians-palm-leaf-hero.jpg"]},

    {"branch": "leaf-texture", "title": "Silver lightning",
     "caption": "Look closer.\n\nThose silver veins on Anthurium crystallinum aren't painted on — it's the way the cells scatter light across a velvet surface. Sugar-white lightning over deep green.\n\nNature did this. We just can't stop staring.",
     "pool": [CMP + "lp-crystallinum.png", STK + "anthurium-crystallinum-vs-clarinervium-hero.jpg", STK + "reading-aroid-venation-hero.jpg"]},

    {"branch": "rarity-value", "title": "More than a phone",
     "caption": "Yes, people pay thousands for a single plant.\n\nA variegated Anthurium can change hands for the price of a used car. Sounds insane — until you see one in person and watch the room go quiet.\n\nRarity, slow growth, and a leaf that looks engineered by an alien. That's the math.",
     "pool": [STK + "anthurium-luxurians-hero.jpg", STK + "anthurium-magnificum-clarinervium-hybrids-hero.jpg", PLT + "plant-03.jpg"]},

    {"branch": "collector-culture", "title": "The obsession",
     "caption": "It starts with one leaf.\n\nThen you're three forums deep at 1am learning to tell two species apart by their petioles. Welcome — you're one of us now.\n\nThere's a whole community of people who love these plants like family. We built leafpeople.app for them.",
     "pool": [PLT + "collector-culture.jpg", PLT + "field-skills.jpg", PLT + "plant-09.jpg"]},

    {"branch": "velvet-anthurium", "title": "Ace of Spades",
     "caption": "The blackest leaf in the room.\n\nAnthurium 'Ace of Spades' — velvet so dark it drinks the light. In the right corner it reads almost black, with a faint oil-slick sheen when it turns.\n\nSome plants are pretty. This one is intimidating.",
     "pool": [CMP + "lp-ace-of-spades.png", PLT + "plant-05.jpg", STK + "anthurium-besseae-aff-complex-hero.jpg"]},

    {"branch": "rainforest-beauty", "title": "Green wall",
     "caption": "Imagine your whole wall doing this.\n\nLayered leaves, every shade of green, a private little rainforest two feet from your couch. This is what the hobby is really chasing — not a plant, a feeling.\n\nCalm, alive, yours.",
     "pool": [PLT + "plant-12.jpg", PLT + "plant-14.jpg", STK + "philodendron-luxurians-hero.jpg"]},

    {"branch": "leaf-texture", "title": "Gold standard",
     "caption": "The gold standard of veining.\n\nAnthurium clarinervium: thick, heart-shaped, with bone-white veins carved into deep green velvet. It's the leaf people draw when they imagine a 'jungle plant.'\n\nReal. Living. Growing on someone's shelf right now.",
     "pool": [STK + "anthurium-clarinervium-id-gold-standard-hero.jpg", STK + "reading-aroid-venation-hero.jpg", PLT + "plant-02.jpg"]},

    {"branch": "rarity-value", "title": "Why so rare",
     "caption": "Why is it so hard to get?\n\nMany of these grow on one mountainside, in one country, and take years to reach a single sellable leaf. Add export rules, slow propagation, and a wall of collector demand.\n\nScarcity isn't hype here. It's botany.",
     "pool": [STK + "anthurium-regale-hero.jpg", STK + "wholesale-vs-retail-in-the-aroid-trade-hero.jpg", PLT + "plant-16.jpg"]},

    {"branch": "collector-culture", "title": "First rare plant",
     "caption": "Remember your first 'real' rare plant?\n\nThe one you saved for, tracked down, unboxed with your heart in your throat — then checked on six times a day for a week.\n\nDrop it in the comments. We want to hear the story. 👇",
     "pool": [PLT + "plant-10.jpg", PLT + "field-skills.jpg", PLT + "plant-18.jpg"]},

    {"branch": "velvet-anthurium", "title": "Velvet up close",
     "caption": "Velvet, but make it alive.\n\nThe matte, light-eating surface of a velvet Anthurium comes from tiny cell structures that kill reflection. The result feels like suede and photographs like a shadow.\n\nNo filter. Just a leaf doing what it evolved to do.",
     "pool": [CMP + "lp-papillilaminum.png", STK + "the-velvet-anthurium-problem-body.jpg", STK + "light-for-velvet-aroids-body.jpg"]},

    {"branch": "rainforest-beauty", "title": "Morning dew",
     "caption": "Morning, in the jungle and on your shelf.\n\nDew beads on a waxy leaf, the light goes soft, and for a second your apartment is a cloud forest. This is the 6am-before-coffee reward of growing these plants.\n\nWho else checks their plants before they check their phone?",
     "pool": [PLT + "plant-06.jpg", PLT + "plant-11.jpg", STK + "hoya-callistophylla-splash-leaf-hero.jpg"]},

    {"branch": "leaf-texture", "title": "Quilted & bullate",
     "caption": "Run your eyes over that surface.\n\nBullate leaves pucker between the veins — quilted, three-dimensional, catching light in a dozen directions at once. Anthurium regale and luxurians turn a flat leaf into a landscape.\n\nTexture is the whole point.",
     "pool": [STK + "anthurium-luxurians-hero.jpg", STK + "anthurium-regale-hero.jpg", PLT + "plant-04.jpg"]},

    {"branch": "rarity-value", "title": "Variegation lottery",
     "caption": "The variegation lottery.\n\nEvery so often a leaf unfurls half-cream, half-green — a random mutation no grower can guarantee. Those are the plants that go for eye-watering money.\n\nYou can't farm luck. That's exactly why collectors chase it.",
     "pool": [STK + "anthurium-magnificum-clarinervium-hybrids-hero.jpg", PLT + "plant-13.jpg", PLT + "plant-17.jpg"]},

    {"branch": "velvet-anthurium", "title": "The bridge",
     "caption": "If you've made it this far, you're one of us. 🌿\n\nThere's a whole world of rare aroids — and almost nothing built for the people who actually love them. So we built it.\n\nLeaf People: identify your plants down to the species, track their care, learn from a real field guide, and trade with collectors. All of it at leafpeople.app.\n\nFollow along — it only gets better from here.",
     "pool": [CMP + "lp-carla-blackie.png", PLT + "anthurium.jpg", PLT + "plant-01.jpg"]},
]

CTA = {
    "intro": "Follow @" + HANDLE + " for a daily dose of the rarest plants on earth.",
    "concept": "We made the tool for this. @" + HANDLE + " · link in bio.",
    "convert": "Read it / get it — link in bio. @" + HANDLE,
}


def validate(path):
    """Return only candidate paths that exist on disk; warn on misses."""
    rel = path.lstrip("/")
    full = os.path.join(ROOT, rel)
    if os.path.exists(full):
        return True
    print(f"  ! missing image: {path}")
    return False


def build():
    posts = []
    for i in range(N_DAYS):
        day = i + 1
        d = START + timedelta(days=i)
        if i < len(INTRO_POSTS):
            p = INTRO_POSTS[i]
            branch = p["branch"]
            pool = [x for x in p["pool"] if validate(x)] or p["pool"][:1]
            phase = "intro"
            post = {
                "id": f"d{day:02d}",
                "day": day,
                "date": d.isoformat(),
                "phase": phase,
                "branch": branch,
                "status": "draft",
                "title": p["title"],
                "image": pool[0],
                "pool": pool,
                "caption": p["caption"],
                "hashtags": tags(branch),
                "cta": CTA[phase],
                "metrics": {"likes": 0, "comments": 0, "saves": 0, "follows": 0, "reach": 0},
            }
        else:
            branch = BRANCH_SCHEDULE[i - len(INTRO_POSTS)] if (i - len(INTRO_POSTS)) < len(BRANCH_SCHEDULE) else "app-cta"
            phase = BRANCHES[branch]["phase"]
            post = {
                "id": f"d{day:02d}",
                "day": day,
                "date": d.isoformat(),
                "phase": phase,
                "branch": branch,
                "status": "skeleton",
                "title": BRANCHES[branch]["label"],
                "image": "",
                "pool": [],
                "caption": "",
                "hashtags": tags(branch),
                "cta": CTA.get(phase, CTA["intro"]),
                "metrics": {"likes": 0, "comments": 0, "saves": 0, "follows": 0, "reach": 0},
            }
        posts.append(post)

    branches_out = {
        "handle": HANDLE,
        "site": SITE,
        "phases": {
            "intro": "Days 1-15 · Beauty & identity — earn the follow.",
            "concept": "Days 16-35 · Tie the beauty to what Leaf People does.",
            "convert": "Days 36-60 · Drive to articles, site & installs.",
        },
        "branches": BRANCHES,
        "goals": FORTNIGHT_GOALS,
        "hashtagTiers": {"brand": BRAND_TAGS, "discovery": DISCOVERY, "niche": NICHE},
    }

    os.makedirs(os.path.join(ROOT, "instagram"), exist_ok=True)
    with open(os.path.join(ROOT, "instagram", "posts.json"), "w") as f:
        json.dump(posts, f, indent=2)
    with open(os.path.join(ROOT, "instagram", "branches.json"), "w") as f:
        json.dump(branches_out, f, indent=2)

    authored = sum(1 for p in posts if p["status"] == "draft")
    print(f"\nWrote instagram/posts.json ({len(posts)} days, {authored} authored, {len(posts)-authored} skeleton)")
    print("Wrote instagram/branches.json")


if __name__ == "__main__":
    build()
