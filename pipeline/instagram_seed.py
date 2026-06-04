#!/usr/bin/env python3
"""
instagram_seed.py — generate the Instagram content calendar for /instagram.

Writes:
  instagram/branches.json  — strategy tree (phases, branches, fortnight goals, config)
  instagram/library.json   — the full image library, each tagged with the branches it suits,
                             its kind (app|id|mood|stock) and (for stock) iNaturalist credit.
  instagram/posts.json     — 60-day calendar.
                             Days 1-15  WELCOME  — introduce Leaf People + rainforest immersion (authored)
                             Days 16-30 SHOWCASE — the rarest leaves, up close (authored)
                             Days 31-45 CONCEPT  — tie beauty to the app (skeleton)
                             Days 46-60 CONVERT  — articles, site, installs (skeleton)

Images: the /instagram page builds each post's refresh options from library.json, filtered by
the post's branch, EXCLUDING any image already chosen on another post (global exclusivity — no
image appears on two posts). Each authored post is seeded with a UNIQUE default image here.

Sources: the app's own Plant-Profile photos (/images/instagram/, owned) lead; the head-to-head ID
shots; curated mood shots (/images/plants/); and 88 iNaturalist CC-BY stock heroes
(/images/source/stock/) for volume + jungle/in-habitat feel. Stock carries attribution.

Phase 1 is MANUAL-ASSIST. Re-run to regenerate from scratch.
"""

import json
import os
import glob
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

START = date(2026, 6, 2)
# Calendar runs day 1 (Jun 2) through the end of the year (Dec 31 = day 213).
# Days 1-90 are the original authored arc; days 91-213 are the rest-of-year wave,
# generated from the published Understory/Field-Guide stories + their curated images.
END = date(2026, 12, 31)
N_DAYS = (END - START).days + 1  # 213
HANDLE = "leafpeople.app"
SITE = "leafpeople.app"

IG = "/images/instagram/"
STK = "/images/source/stock/"
PLT = "/images/plants/"
CMP = "/images/compare/"
APP = "/images/app/"
INAT = "/images/source/inat/"

# slug -> app plant-profile photo (all 68), built alongside the Understory queue.
# Used to give later showcase posts fresh-species heroes and to enrich the library.
PROFILE = {}
try:
    PROFILE = json.loads(open(os.path.join(HERE, "profile_images.json")).read())
except Exception:
    PROFILE = {}

# --- Hashtags ----------------------------------------------------------------
BRAND_TAGS = ["#leafpeople", "#leafpeopleapp"]
DISCOVERY = ["#plantsofinstagram", "#rareplants", "#aroidaddicts", "#foliage",
             "#houseplantsofinstagram", "#indoorjungle", "#botanical", "#plantcollector"]
NICHE = {
    "welcome-leafpeople": ["#rareplantsofinstagram", "#plantcommunity", "#aroidaddicts", "#rarearoids"],
    "jungle-escape":      ["#rainforest", "#jungle", "#biophilia", "#naturelovers", "#botanicalescape", "#calm"],
    "rarest-jungle":      ["#rarearoids", "#anthurium", "#velvetanthurium", "#unicornplant", "#aroidsofinstagram"],
    "velvet-anthurium":   ["#anthurium", "#velvetanthurium", "#rarearoids", "#aroidsofinstagram", "#anthuriumlove"],
    "rainforest-beauty":  ["#rainforest", "#understory", "#junglevibes", "#tropicalplants", "#greenery"],
    "leaf-texture":       ["#leafporn", "#venation", "#botanicaldetail", "#macrophotography", "#foliagelove"],
    "rarity-value":       ["#rareplants", "#variegata", "#plantcollector", "#aroidcollector", "#unicornplant"],
    "collector-culture":  ["#plantcommunity", "#planthobby", "#plantpeople", "#aroidcollector", "#planthoarder"],
}

def tags(branch):
    return BRAND_TAGS + DISCOVERY + NICHE.get(branch, [])

# --- Strategy tree -----------------------------------------------------------
BRANCHES = {
    "welcome-leafpeople": {"phase": "welcome", "color": "#34c759", "label": "Welcome · Leaf People",
                           "intent": "Introduce the app & mission — the daily escape to the jungle."},
    "jungle-escape": {"phase": "welcome", "color": "#2f8f6b", "label": "Jungle Escape",
                      "intent": "Immersive, sensory escapism — transport them to the rainforest."},
    "rarest-jungle": {"phase": "welcome", "color": "#7c5cff", "label": "Rarest Jungle Plants",
                      "intent": "The wow — the rarest leaves on earth, revealed."},
    "velvet-anthurium": {"phase": "showcase", "color": "#9a7bff", "label": "Velvet Anthuriums",
                         "intent": "Dark, suede, dramatic — the plant that stops the scroll."},
    "rainforest-beauty": {"phase": "showcase", "color": "#2fae6b", "label": "Rainforest Beauty",
                          "intent": "Understory mood, light, lush foliage. Aspiration & calm."},
    "leaf-texture": {"phase": "showcase", "color": "#d98a3a", "label": "Leaf Texture",
                     "intent": "Macro veining, iridescence, crystalline surfaces."},
    "rarity-value": {"phase": "showcase", "color": "#e0556d", "label": "Rarity & Value",
                     "intent": "The $400-$12k stories. Desire, scarcity, the hunt."},
    "collector-culture": {"phase": "showcase", "color": "#46a7e0", "label": "Collector Culture",
                          "intent": "The people & the obsession. Belonging."},
    "app-identify": {"phase": "concept", "color": "#5bd17a", "label": "App · Identify",
                     "intent": "Name any rare aroid from a leaf — the head-to-head proof."},
    "app-track-care": {"phase": "concept", "color": "#46c0c0", "label": "App · Track & Care",
                       "intent": "Care tracker, reminders, regional guidance."},
    "app-learn": {"phase": "concept", "color": "#8fb04a", "label": "App · Learn",
                  "intent": "Field guide & Understory deep-dives in the app."},
    "app-collect": {"phase": "concept", "color": "#c08a46", "label": "App · Collect",
                    "intent": "Collection log + the collector's marketplace."},
    "article-fieldguide": {"phase": "convert", "color": "#9a7bd1", "label": "Article · Field Guide",
                           "intent": "Species spotlight -> 'read the full guide, link in bio'."},
    "article-understory": {"phase": "convert", "color": "#d17b9a", "label": "Article · Understory",
                           "intent": "Story/culture spotlight -> 'read it, link in bio'."},
    "app-cta": {"phase": "convert", "color": "#3ec98a", "label": "App · Get it",
                "intent": "Direct install CTA, 7-day trial, $0.99/mo."},
    "community-ugc": {"phase": "convert", "color": "#e0a13a", "label": "Community / UGC",
                      "intent": "Prompt followers to share + tag; reshare the best."},
}

PHASES = {
    "welcome": "Days 1-15 · Introduce Leaf People + immerse in the rainforest — earn the follow.",
    "showcase": "Days 16-30 · The rarest leaves, up close — go deeper.",
    "concept": "Days 31-45 · Tie the beauty to what Leaf People does.",
    "convert": "Days 46-60 · Drive to articles, site & installs.",
}

FORTNIGHT_GOALS = [
    {"weeks": "Days 1-14", "theme": "Welcome the world — establish the immersive Leaf People vibe",
     "followers": 150, "avg_likes": 40, "extra": "Find which welcome angle hooks hardest: escape, the rarest, or the app itself."},
    {"weeks": "Days 15-28", "theme": "Go deeper — showcase the rarest leaves",
     "followers": 400, "avg_likes": 80, "extra": "Double down on the winning welcome angle; 50+ bio-link clicks."},
    {"weeks": "Days 29-42", "theme": "Bridge into the app — concept posts",
     "followers": 800, "avg_likes": 120, "extra": "150+ link clicks; first attributed installs."},
    {"weeks": "Days 43-56", "theme": "Articles & CTAs convert lookers to users",
     "followers": 1500, "avg_likes": 180, "extra": "300+ clicks; 30+ attributed installs."},
    {"weeks": "Days 57-70", "theme": "Second wave — fresh species, deeper cuts",
     "followers": 2500, "avg_likes": 250, "extra": "Article tie-ins driving real traffic; lean hard into the winning branches."},
    {"weeks": "Days 71-84", "theme": "Authority — the rare-plant destination",
     "followers": 4000, "avg_likes": 320, "extra": "UGC compounding; collaborations & reshares from the community."},
    {"weeks": "Days 85-98", "theme": "Rolling funnel — exploit winners, keep exploring",
     "followers": 5500, "avg_likes": 400, "extra": "Self-sustaining cadence; every posted day informs the next."},
    {"weeks": "Days 99-126 · Sep", "theme": "Story engine — a spotlight a day from the published library",
     "followers": 7500, "avg_likes": 500, "extra": "Each post drives to a real Understory/Field-Guide article — track bio-link clicks per genus."},
    {"weeks": "Days 127-160 · Oct", "theme": "Genus depth — lean into whichever genus converts best",
     "followers": 10000, "avg_likes": 650, "extra": "Double down on the top-performing species branch; reshare the strongest UGC."},
    {"weeks": "Days 161-190 · Nov", "theme": "Authority — the rare-plant reference people send each other",
     "followers": 14000, "avg_likes": 800, "extra": "Article tie-ins compounding; collaborations and creator reshares."},
    {"weeks": "Days 191-213 · Dec", "theme": "Year-end push — convert the audience into subscribers",
     "followers": 18000, "avg_likes": 950, "extra": "Gift-the-collector angle; $0.99 trial CTAs; close the year on installs."},
]

CTA = {
    "welcome": "Welcome to Leaf People — follow @" + HANDLE + " and we'll take you to the jungle every day.",
    "showcase": "Follow @" + HANDLE + " for the rarest plants on earth, daily.",
    "concept": "We built the tool for this. @" + HANDLE + " · link in bio.",
    "convert": "Read it / get it — link in bio. @" + HANDLE,
}

# ============================================================================
# IMAGE LIBRARY — every candidate image, tagged with the branches it suits.
# ============================================================================
VELVET = ["velvet-anthurium", "rarest-jungle", "leaf-texture", "rarity-value"]
PHILO  = ["rainforest-beauty", "jungle-escape", "leaf-texture"]

APP_LIB = {
    "anthurium-warocqueanum.jpeg": VELVET, "anthurium-ace-of-spades.jpeg": VELVET,
    "anthurium-dark-mama.jpg": VELVET, "anthurium-papillilaminum.png": VELVET,
    "anthurium-carla-blackie.jpeg": VELVET, "anthurium-antolakii.jpeg": VELVET,
    "anthurium-morona.jpeg": VELVET, "anthurium-veitchii.jpeg": VELVET,
    "anthurium-cutucuence.jpeg": VELVET, "anthurium-corrugatum.jpeg": VELVET,
    "anthurium-cupulispathum.jpeg": VELVET, "anthurium-vittariifolium.jpg": ["rarest-jungle", "rainforest-beauty", "rarity-value"],
    "anthurium-forgetii.png": ["leaf-texture", "velvet-anthurium", "rarest-jungle"],
    "anthurium-kunayalense.png": VELVET, "anthurium-wendlingeri.png": ["rarest-jungle", "leaf-texture", "rainforest-beauty"],
    "anthurium-crystalanium.jpeg": ["leaf-texture", "velvet-anthurium", "rarest-jungle"],
    "philodendron-gloriosum.jpg": PHILO, "philodendron-verrucosum.png": PHILO,
    "philodendron-melanochrysum.jpeg": PHILO, "philodendron-gigas.jpg": PHILO,
    "philodendron-spiritus-sancti.jpg": ["rarity-value", "rainforest-beauty", "rarest-jungle"],
    # second batch — distinct species so Showcase posts don't repeat the Welcome stars
    "monstera-siltepecana.jpg": ["rainforest-beauty", "jungle-escape", "leaf-texture"],
    "hoya-callistophylla.png": ["leaf-texture", "rainforest-beauty"],
    "monstera-thai-constellation.jpg": ["rarity-value", "rarest-jungle", "rainforest-beauty"],
    "philodendron-squamiferum.png": ["rainforest-beauty", "leaf-texture"],
    "philodendron-white-knight.jpg": ["rarity-value", "rarest-jungle", "rainforest-beauty"],
    "philodendron-tortum.jpg": ["rainforest-beauty", "leaf-texture"],
    "philodendron-pink-princess.png": ["rarity-value", "rarest-jungle"],
    "begonia-maculata.jpg": ["leaf-texture", "rainforest-beauty"],
    "begonia-rex-escargot.jpg": ["leaf-texture", "rainforest-beauty"],
    "begonia-venosa.jpg": ["leaf-texture", "rainforest-beauty"],
    "monstera-albo-variegata.jpg": ["rarity-value", "rainforest-beauty"],
    "philodendron-burle-marx-variegata.jpg": ["rarity-value", "rainforest-beauty"],
}
# NOTE: lp-*.png are app identify-result SCREENSHOTS (UI), not clean photos — they belong
# only on app-identify posts, never on the beauty branches.
ID_LIB = {
    "lp-warocqueanum.png": ["app-identify"],
    "lp-ace-of-spades.png": ["app-identify"],
    "lp-crystallinum.png": ["app-identify"],
    "lp-papillilaminum.png": ["app-identify"],
    "lp-carla-blackie.png": ["app-identify"],
}
MOOD_LIB = {
    "aroid.jpg": ["rainforest-beauty", "jungle-escape"], "the-leaf.jpg": ["rainforest-beauty", "jungle-escape"],
    "anthurium.jpg": ["velvet-anthurium", "rarest-jungle"], "monstera.jpg": ["rainforest-beauty", "jungle-escape"],
    "philodendron.jpg": ["rainforest-beauty", "jungle-escape"], "begonia.jpg": ["rainforest-beauty", "leaf-texture"],
    "hoya.jpg": ["rainforest-beauty", "jungle-escape"], "collector-culture.jpg": ["collector-culture"],
    "field-skills.jpg": ["collector-culture", "rainforest-beauty"],
    **{f"plant-{i:02d}.jpg": (["rainforest-beauty", "jungle-escape"] + (["leaf-texture"] if i % 3 == 0 else []))
       for i in list(range(1, 7)) + list(range(8, 19))},
}
# app UI screenshots — for the concept phase (and app-cta in convert)
APP_UI = {f"shot-{i:02d}.png": ["app-identify", "app-track-care", "app-learn", "app-collect", "app-cta"]
          for i in range(1, 11)}

def stock_branches(slug):
    b = set()
    has = lambda *ks: any(k in slug for k in ks)
    if "anthurium" in slug: b |= {"velvet-anthurium", "rarest-jungle", "leaf-texture", "rarity-value"}
    if has("philodendron", "gloriosum", "mamei", "verrucosum", "melano", "pastazanum", "gigas", "luxurians"): b |= {"rainforest-beauty", "jungle-escape", "rarity-value"}
    if "monstera" in slug: b |= {"rainforest-beauty", "jungle-escape"}
    if has("begonia", "calathea", "ctenanthe", "stromanthe", "geogenanthus", "maranta", "vriesea"): b |= {"rainforest-beauty", "leaf-texture"}
    if "hoya" in slug: b |= {"rainforest-beauty", "jungle-escape"}
    if has("alocasia", "caladium", "amorphophallus", "syngonium", "scindapsus", "epipremnum", "rhaphidophora", "amydrium", "homalomena", "schismatoglottis", "aglaonema", "spathiphyllum", "pothos", "tradescantia"): b |= {"rainforest-beauty", "jungle-escape"}
    if has("velvet", "venation", "anatomy", "reading-aroid", "cataphyll"): b |= {"leaf-texture"}
    if has("price", "trade", "buying", "wholesale", "customs", "decoding", "listing", "phyto"): b |= {"rarity-value", "collector-culture"}
    if has("collector", "burnout", "community"): b |= {"collector-culture"}
    if not b: b = {"rainforest-beauty", "jungle-escape"}
    # most in-situ aroid shots read as jungle/immersion
    if has("anthurium", "philodendron", "monstera", "aroid"): b |= {"jungle-escape"}
    # every stock hero is a field-guide article hero; story-ish ones suit Understory + UGC
    b |= {"article-fieldguide"}
    if has("collector", "burnout", "buying", "wholesale", "decoding", "listing", "price", "trade", "customs", "community"):
        b |= {"article-understory", "community-ugc"}
    return sorted(b)

def load_credits():
    path = os.path.join(ROOT, "images", "source", "stock", "attributions.json")
    out = {}
    try:
        for e in json.load(open(path)):
            out[e["file"]] = {"credit": e.get("attribution", "iNaturalist (CC BY)"), "license": e.get("license", "cc-by")}
    except Exception:
        pass
    return out

def profile_branches(slug):
    b = set()
    if slug.startswith("anthurium"):     b |= {"velvet-anthurium", "rarest-jungle", "leaf-texture", "rarity-value"}
    elif slug.startswith("philodendron"): b |= {"rainforest-beauty", "leaf-texture", "rarity-value"}
    elif slug.startswith("monstera"):     b |= {"rainforest-beauty", "jungle-escape", "rarity-value"}
    elif slug.startswith("hoya"):         b |= {"rainforest-beauty", "leaf-texture"}
    elif slug.startswith("begonia"):      b |= {"leaf-texture", "rainforest-beauty"}
    b |= {"article-fieldguide", "article-understory", "community-ugc", "welcome-leafpeople"}
    return sorted(b)


def build_library(articles=None):
    lib = []
    seen = {}
    def add(src, branches, kind, credit=""):
        if src in seen:
            # already in the library — just widen the branch set so this image
            # also surfaces for the rest-of-year post that curated it.
            e = seen[src]
            e["branches"] = sorted(set(e["branches"]) | set(branches))
            return
        e = {"src": src, "branches": branches, "kind": kind, "credit": credit}
        seen[src] = e
        lib.append(e)

    for f, br in APP_LIB.items():  add(IG + f, br, "app")
    for f, br in ID_LIB.items():   add(CMP + f, br, "id")
    for f, br in MOOD_LIB.items(): add(PLT + f, br, "mood")
    for f, br in APP_UI.items():   add(APP + f, br, "appui")

    # All 68 app plant-profile photos (deduped against the IG set by slug/basename).
    ig_slugs = {os.path.splitext(f)[0] for f in APP_LIB}
    for slug, src in PROFILE.items():
        if slug in ig_slugs:
            continue
        add(src, profile_branches(slug), "profile")

    credits = load_credits()
    for full in sorted(glob.glob(os.path.join(ROOT, "images", "source", "stock", "*-hero.jpg"))):
        src = "/" + os.path.relpath(full, ROOT)
        c = credits.get(src, {})
        add(src, stock_branches(os.path.basename(src)), "stock", c.get("credit", "iNaturalist (CC BY)"))

    # Curated story images — the hero + body photos the user picked inside each
    # published article. Owned shots ("Leaf People") carry no credit; iNat/stock
    # shots carry the photographer attribution so it can be appended when posting.
    for a in (articles or []):
        br = article_image_branches(a.get("category", ""))
        for src, attr in ((a.get("hero"), a.get("hero_attribution")),
                          (a.get("body_image"), a.get("body_image_attribution"))):
            if not src:
                continue
            owned = (attr or "").strip().lower() in ("", "leaf people")
            if owned:
                add(src, br, "profile")
            else:
                add(src, br, "stock", attr or "iNaturalist (CC BY)")

    # welcome-leafpeople can pull from the whole "pretty" pool
    for e in lib:
        if {"velvet-anthurium", "rainforest-beauty", "rarest-jungle"} & set(e["branches"]):
            if "welcome-leafpeople" not in e["branches"]:
                e["branches"] = e["branches"] + ["welcome-leafpeople"]
    # App-feature posts can lead with a striking plant photo, not only a UI screenshot.
    for e in lib:
        if {"velvet-anthurium", "rarest-jungle", "leaf-texture", "rarity-value"} & set(e["branches"]):
            for b in ("app-identify", "app-collect", "app-track-care", "app-learn", "app-cta"):
                if b not in e["branches"]:
                    e["branches"].append(b)
    return lib

KIND_ORDER = {"app": 0, "appui": 1, "id": 2, "profile": 3, "mood": 4, "stock": 5}

def candidates_for(branch, lib):
    c = [e for e in lib if branch in e["branches"]]
    c.sort(key=lambda e: KIND_ORDER.get(e["kind"], 9))
    return c

# ============================================================================
# AUTHORED POSTS — caption + preferred default image (must end up unique).
# ============================================================================
WELCOME_POSTS = [
    {"branch": "welcome-leafpeople", "title": "Welcome home", "prefer": IG+"philodendron-gloriosum.jpg",
     "caption": "Welcome to Leaf People. \U0001F33F\n\nForget the inbox, the traffic, the noise. For the next sixty seconds you're somewhere else — a Colombian cloud forest, ankle-deep in leaf litter, the air thick and green.\n\nThis is an app, and a world, built around one thing: the rarest rainforest plants on earth.\n\nStay a while. leafpeople.app"},
    {"branch": "jungle-escape", "title": "Breathe in", "prefer": IG+"philodendron-melanochrysum.jpeg",
     "caption": "Breathe in.\n\nWet earth, crushed leaves, something sweet flowering far overhead. The rainforest floor doesn't smell like anything you keep in a pot — it smells alive.\n\nWe can't bottle it. But we can bring you the plants that grow in it. Every single day.\n\n\U0001F33F leafpeople.app"},
    {"branch": "rarest-jungle", "title": "Meet the Queen", "prefer": IG+"anthurium-warocqueanum.jpeg",
     "caption": "Meet the Queen. \U0001F451\n\nAnthurium warocqueanum — three feet of black-green velvet hung from a rainforest tree, one of the most coveted plants on the planet.\n\nMost people will never see one in person. Here, she's only the beginning.\n\nleafpeople.app"},
    {"branch": "welcome-leafpeople", "title": "What is Leaf People", "prefer": IG+"philodendron-verrucosum.png",
     "caption": "So what is Leaf People?\n\nA field guide, a care tracker, an ID engine and a collector's marketplace — built only for rare rainforest plants. Not ten thousand species skimmed. The ones actually worth knowing, studied deep.\n\nBy plant people, for plant people. leafpeople.app \U0001F33F"},
    {"branch": "jungle-escape", "title": "Find the light", "prefer": IG+"philodendron-gigas.jpg",
     "caption": "Find the light.\n\nOn the forest floor it arrives in pieces — a shaft here, a glow there, filtered through a hundred feet of canopy. It's why these leaves grow so big, so dark, so hungry.\n\nSlow down. Let your eyes adjust. There's a whole world down here.\n\n\U0001F33F #leafpeople"},
    {"branch": "rarest-jungle", "title": "Blackest leaf", "prefer": IG+"anthurium-ace-of-spades.jpeg",
     "caption": "The blackest leaf in the room.\n\nAnthurium 'Ace of Spades' drinks the light — velvet so dark it reads almost black, with an oil-slick shimmer when it turns.\n\nSome plants are pretty. This one is a statement.\n\nleafpeople.app \U0001F5A4"},
    {"branch": "welcome-leafpeople", "title": "Why we built it", "prefer": IG+"anthurium-antolakii.jpeg",
     "caption": "Why we built Leaf People.\n\nBecause if you've ever fallen down a 1am rabbit hole trying to tell two velvet anthuriums apart, you know the tools out there weren't made for us.\n\nSo we made our own. Identify, track, learn, collect — all in one place.\n\n\U0001F33F leafpeople.app"},
    {"branch": "jungle-escape", "title": "Rain on leaves", "prefer": IG+"anthurium-dark-mama.jpg",
     "caption": "The sound of rain on leaves.\n\nNot the city kind — the jungle kind. Fat drops drumming on giant foliage, running down a leaf the size of your arm, feeding roots that never go thirsty.\n\nClose your eyes. You're there.\n\n\U0001F33F #rainforest #leafpeople"},
    {"branch": "rarest-jungle", "title": "Silver lightning", "prefer": IG+"anthurium-crystalanium.jpeg",
     "caption": "Silver lightning.\n\nThose veins on Anthurium crystallinum aren't painted — it's the way the velvet scatters light. Sugar-white over deep forest green.\n\nNature engineered this. We just can't stop staring.\n\nleafpeople.app ✨"},
    {"branch": "welcome-leafpeople", "title": "Deep not wide", "prefer": IG+"anthurium-veitchii.jpeg",
     "caption": "We went deep, not wide.\n\nAnyone can list ten thousand plants. We chose a handful of genera — the rare rainforest aroids and their cousins — and learned them properly. Light, humidity, substrate, the lot.\n\nQuality over quantity. Always.\n\n\U0001F33F leafpeople.app"},
    {"branch": "jungle-escape", "title": "Morning mist", "prefer": IG+"philodendron-spiritus-sancti.jpg",
     "caption": "Morning mist.\n\nFor an hour after dawn the cloud forest disappears into white — every leaf beaded with water, the whole world hushed and dripping.\n\nThis is the calm we're chasing. A pocket of jungle, two feet from your couch.\n\n\U0001F33F #leafpeople #calm"},
    {"branch": "rarest-jungle", "title": "The deep end", "prefer": IG+"anthurium-papillilaminum.png",
     "caption": "The ones collectors whisper about.\n\nAnthurium papillilaminum — deep, suede-dark, impossibly velvet. The kind of plant that starts bidding wars and long flights to nurseries you've never heard of.\n\nThis is the deep end. Welcome.\n\n\U0001F33F leafpeople.app"},
    {"branch": "welcome-leafpeople", "title": "You're not the only one", "prefer": PLT+"collector-culture.jpg",
     "caption": "You're not the only one. \U0001F33F\n\nThere's a whole community of people who love these plants like family — who name them, photograph them, mourn a lost leaf.\n\nLeaf People is home base for all of us. Pull up a chair.\n\nleafpeople.app"},
    {"branch": "jungle-escape", "title": "Your pocket of jungle", "prefer": PLT+"plant-14.jpg",
     "caption": "Your own pocket of jungle.\n\nYou don't need a greenhouse or a plane ticket. One rare leaf on a shelf, catching the morning light, is enough to take your whole mind somewhere greener.\n\nThat's the magic. That's why we're here.\n\n\U0001F33F #leafpeople #biophilia"},
    {"branch": "welcome-leafpeople", "title": "Welcome home (bridge)", "prefer": IG+"anthurium-carla-blackie.jpeg",
     "caption": "If you've made it this far — welcome home. \U0001F33F\n\nLeaf People is your daily escape to the rainforest, plus the tools to bring a piece of it home: identify any rare aroid, track its care, learn from a real field guide, trade with collectors.\n\nHit follow. Tomorrow we go deeper — the rarest, strangest, most beautiful leaves on earth.\n\nleafpeople.app"},
]

# Distinct species from the Welcome arc (which names warocqueanum, Ace of Spades,
# crystallinum, papillilaminum) — Showcase goes DEEPER on different plants.
SHOWCASE_POSTS = [
    {"branch": "velvet-anthurium", "title": "Cutucuense — the drape", "prefer": IG+"anthurium-cutucuence.jpeg",
     "caption": "Velvet that drapes.\n\nAnthurium cutucuense unrolls long, rippling, suede-dark leaves that hang like fabric from the stem. The texture stops people mid-sentence — you don't display this plant, you introduce it."},
    {"branch": "rainforest-beauty", "title": "Siltepecana — silver", "prefer": IG+"monstera-siltepecana.jpg",
     "caption": "Silver in the shade.\n\nMonstera siltepecana climbs the understory in dusty, blue-silver leaves, fenestrating as it matures. A little piece of the canopy's edge, on your wall."},
    {"branch": "leaf-texture", "title": "Callistophylla — stained glass", "prefer": IG+"hoya-callistophylla.png",
     "caption": "Stained glass.\n\nThe veins on Hoya callistophylla are pressed into the leaf like dark leading in stained glass — a map you could trace for hours. Texture is the whole event."},
    {"branch": "rarity-value", "title": "Thai Constellation", "prefer": IG+"monstera-thai-constellation.jpg",
     "caption": "Painted by chance.\n\nMonstera 'Thai Constellation' is splattered with creamy variegation no two plants share — stable, slow, and coveted. A galaxy on a leaf, priced like one."},
    {"branch": "collector-culture", "title": "The hunt", "prefer": PLT+"field-skills.jpg",
     "caption": "The hunt is half the fun.\n\nLearning to read a petiole, a cataphyll, a new leaf unfurling — the skills that turn a buyer into a grower. Nobody's born knowing this. You pick it up, one plant at a time."},
    {"branch": "velvet-anthurium", "title": "Vittariifolium — the ribbon", "prefer": IG+"anthurium-vittariifolium.jpg",
     "caption": "The ribbon.\n\nAnthurium vittariifolium drops pendant, strap-thin leaves up to a metre long — a living green curtain. Strange, elegant, unmistakably rare."},
    {"branch": "rainforest-beauty", "title": "Squamiferum — fuzzy petioles", "prefer": IG+"philodendron-squamiferum.png",
     "caption": "Look at that stem.\n\nPhilodendron squamiferum grows fuzzy, red-bristled petioles you'll want to touch, holding up oak-leaf foliage. Half the beauty of an aroid is the parts that aren't the leaf."},
    {"branch": "leaf-texture", "title": "Forgetii — bone-white rim", "prefer": IG+"anthurium-forgetii.png",
     "caption": "Bone-white, edge to edge.\n\nAnthurium forgetii rounds its dark leaves into near-perfect ovals, rimmed and veined in pale bone-white. No lobes, no drama — just a clean, gleaming disc."},
    {"branch": "rarity-value", "title": "White Knight", "prefer": IG+"philodendron-white-knight.jpg",
     "caption": "Half-and-half.\n\nPhilodendron 'White Knight' throws near-black stems against crisp white-variegated leaves. High contrast, high demand, slow to climb — the collector's tax."},
    {"branch": "collector-culture", "title": "First rare plant", "prefer": PLT+"plant-10.jpg",
     "caption": "Remember your first 'real' rare plant?\n\nThe one you saved for, tracked down, unboxed with your heart in your throat — then checked on six times a day for a week.\n\nDrop it in the comments. \U0001F447"},
    {"branch": "velvet-anthurium", "title": "Wendlingeri — pendant velvet", "prefer": IG+"anthurium-wendlingeri.png",
     "caption": "Velvet, but make it alive.\n\nAnthurium wendlingeri hangs in long, quilted, light-eating ribbons — matte enough to read as shadow. Feels like suede, photographs like a void. No filter."},
    {"branch": "rainforest-beauty", "title": "Tortum — living sculpture", "prefer": IG+"philodendron-tortum.jpg",
     "caption": "Almost not there.\n\nPhilodendron tortum splits its leaves into thin, twisting, skeletal fingers — more sculpture than foliage. The jungle's idea of minimalism."},
    {"branch": "leaf-texture", "title": "Corrugatum — quilted", "prefer": IG+"anthurium-corrugatum.jpeg",
     "caption": "Quilted.\n\nAnthurium corrugatum puckers between every vein — a three-dimensional, bullate surface that catches light in a dozen directions at once. Run your eyes over it slowly."},
    {"branch": "rarity-value", "title": "Pink Princess", "prefer": IG+"philodendron-pink-princess.png",
     "caption": "The variegation lottery.\n\nPhilodendron 'Pink Princess' can throw a leaf of pure bubblegum pink — or revert to plain green and break your heart. You can't farm luck. That's why collectors chase it."},
    {"branch": "velvet-anthurium", "title": "Morona — the bridge", "prefer": IG+"anthurium-morona.jpeg",
     "caption": "If you've made it this far, you're one of us. \U0001F33F\n\nThere's a whole world of rare aroids — and almost nothing built for the people who love them. So we built it. Leaf People: identify to the species, track care, learn from a real field guide, trade with collectors. All at leafpeople.app."},
]

BRANCH_SCHEDULE = (
    ["app-identify", "app-track-care", "app-learn", "app-collect", "app-identify",
     "app-track-care", "app-learn", "app-identify", "app-collect", "app-learn",
     "app-identify", "app-track-care", "app-learn", "app-collect", "app-identify"]
    + ["article-fieldguide", "app-cta", "article-understory", "community-ugc", "article-fieldguide",
       "app-cta", "article-understory", "article-fieldguide", "community-ugc", "app-cta",
       "article-fieldguide", "article-understory", "app-cta", "community-ugc", "app-cta"]
)

# CONCEPT (days 31-45) — tie the beauty to what the app does.
CONCEPT_POSTS = [
    {"branch": "app-identify", "title": "Point, shoot, know", "prefer": APP+"shot-04.png",
     "caption": "Point your camera at any leaf. Get the species — not 'it's a houseplant,' the actual species. That's the whole idea behind Leaf People."},
    {"branch": "app-track-care", "title": "Never miss a watering", "prefer": APP+"shot-07.png",
     "caption": "Velvet anthuriums don't forgive a missed week. Leaf People tracks water, food, foliar feed and more — and nudges you before it becomes a problem."},
    {"branch": "app-learn", "title": "Field guide in your pocket", "prefer": APP+"shot-02.png",
     "caption": "Every plant in the app comes with a real care guide — light, humidity, substrate, the lot. No more twelve open tabs at 1am."},
    {"branch": "app-identify", "title": "We name what others can't", "prefer": CMP+"lp-warocqueanum.png",
     "caption": "Other apps see a rare anthurium and shrug: 'Laceleaf.' Leaf People names the species. We tested it head-to-head — it isn't close."},
    {"branch": "app-collect", "title": "Your jungle, catalogued", "prefer": APP+"shot-05.png",
     "caption": "Every plant you own, in one place — what it is, how to care for it, when you last watered. Your collection, finally organized."},
    {"branch": "app-track-care", "title": "Care that knows your climate", "prefer": APP+"shot-08.png",
     "caption": "Phoenix isn't Singapore. Leaf People tunes its care guidance to where you actually grow — not one-size-fits-all."},
    {"branch": "app-learn", "title": "A new story every day", "prefer": PLT+"the-leaf.jpg",
     "caption": "Open the app to a fresh rare-plant story daily — field notes, deep dives, collector culture. Get sharper with every leaf."},
    {"branch": "app-identify", "title": "Even from a single leaf", "prefer": CMP+"lp-crystallinum.png",
     "caption": "No flower, no tag — just one leaf on a table? Still enough. Leaf People reads the veins, shape and texture, and names it."},
    {"branch": "app-collect", "title": "Trade with people who get it", "prefer": APP+"shot-09.png",
     "caption": "Buy, sell and trade in a marketplace built for collectors — not a yard sale. Secure, and plant-people only."},
    {"branch": "app-track-care", "title": "Six kinds of care, one timeline", "prefer": APP+"shot-06.png",
     "caption": "Water, fertilize, foliar feed, root check, substrate check, propagate — each on its own schedule, all on one timeline."},
    {"branch": "app-identify", "title": "crystallinum or clarinervium?", "prefer": STK+"anthurium-crystallinum-vs-clarinervium-hero.jpg",
     "caption": "The question that starts fights. Leaf People settles it — to the species — in about a second."},
    {"branch": "app-learn", "title": "Know why it's doing that", "prefer": PLT+"plant-08.jpg",
     "caption": "Yellow leaf? Crispy edge? Slow growth? The app's guides tell you why — and what to change — for the exact plants you own."},
    {"branch": "app-collect", "title": "Log every new leaf", "prefer": APP+"shot-03.png",
     "caption": "Watch your collection grow, literally. Track new leaves, milestones and progress on every plant you keep."},
    {"branch": "app-identify", "title": "Mystery to named species", "prefer": PLT+"anthurium.jpg",
     "caption": "That unlabeled plant from the sale table? Point, shoot, and finally know exactly what you brought home."},
    {"branch": "app-collect", "title": "The collection in your pocket", "prefer": APP+"shot-10.png",
     "caption": "Identify it, learn it, track it, trade it. Everything a collector needs — and nothing leaves your phone."},
]

# CONVERT (days 46-60) — drive to articles, the site, installs, community.
CONVERT_POSTS = [
    {"branch": "article-fieldguide", "title": "The Queen, in full", "prefer": STK+"anthurium-regale-hero.jpg",
     "caption": "The complete story of the Queen Anthurium — where she grows, why she's coveted, how to keep her alive. Full guide, link in bio."},
    {"branch": "app-cta", "title": "All of it. $0.99/mo", "prefer": APP+"shot-01.png",
     "caption": "The ID engine, the field guide, the care tracker, the marketplace — one subscription, $0.99 a month, 7-day free trial. Link in bio."},
    {"branch": "article-understory", "title": "Ghost of Espírito Santo", "prefer": STK+"philodendron-luxurians-hero.jpg",
     "caption": "A philodendron down to a handful of wild plants, and the most coveted leaf in the hobby. We told its story — read it, link in bio."},
    {"branch": "community-ugc", "title": "Show us your grail", "prefer": PLT+"plant-09.jpg",
     "caption": "What's the one plant you'd save in a fire? Show us. Tag #leafpeople and we'll reshare our favorites. 🌿"},
    {"branch": "article-fieldguide", "title": "Velvets, demystified", "prefer": STK+"treating-leaf-spot-on-velvets-hero.jpg",
     "caption": "Why velvet anthuriums are so hard to tell apart — and how to actually do it. Full guide, link in bio."},
    {"branch": "app-cta", "title": "Less than a coffee", "prefer": PLT+"plant-16.jpg",
     "caption": "Seven days free. Then $0.99 a month — less than one coffee — for the whole collector's toolkit. Link in bio."},
    {"branch": "article-understory", "title": "Why a leaf costs $5k", "prefer": STK+"wholesale-vs-retail-in-the-aroid-trade-hero.jpg",
     "caption": "How does a single leaf cost more than a flight? Scarcity, slow growth, and a wall of demand. We broke down the economics — link in bio."},
    {"branch": "article-fieldguide", "title": "Crystallinum vs clarinervium", "prefer": STK+"anthurium-clarinervium-id-gold-standard-hero.jpg",
     "caption": "Two famous velvet hearts, endlessly confused. Our guide settles which is which, for good. Read it — link in bio."},
    {"branch": "community-ugc", "title": "Your first rare plant", "prefer": PLT+"plant-17.jpg",
     "caption": "Everyone remembers their first 'real' rare plant. Drop yours in the comments 👇 — the saga, the price, the panic."},
    {"branch": "app-cta", "title": "The collector's app", "prefer": STK+"repotting-mature-anthuriums-hero.jpg",
     "caption": "Identify, track, learn, trade — built only for rare plants, by people who grow them. Free to try. leafpeople.app"},
    {"branch": "article-fieldguide", "title": "Pink Princess, honestly", "prefer": STK+"anthurium-magnificum-clarinervium-hybrids-hero.jpg",
     "caption": "Pink Princess: the variegation lottery, the reversion heartbreak, the scams. The honest full guide — link in bio."},
    {"branch": "article-understory", "title": "The Pink Congo scam", "prefer": STK+"buying-a-rare-plant-without-getting-burned-hero.jpg",
     "caption": "How thousands got burned buying a 'pink' philodendron that turned plain green in months. The cautionary tale — link in bio."},
    {"branch": "app-cta", "title": "Identify. Track. Trade.", "prefer": APP+"shot-04.png",
     "caption": "Three taps from 'what is this?' to a named, tracked, traded plant. The whole loop lives in Leaf People. Link in bio."},
    {"branch": "community-ugc", "title": "Tag us in your jungle", "prefer": PLT+"plant-15.jpg",
     "caption": "Building a jungle? Tag @leafpeople.app — we reshare the best corners of the community every week. 🌿"},
    {"branch": "app-cta", "title": "Start your collection", "prefer": STK+"mounting-mature-aroids-on-wood-hero.jpg",
     "caption": "However many plants you've got, Leaf People makes them a collection. Start today — 7 days free. leafpeople.app"},
]

# EXTENDED (days 61-90) — a second wave: fresh species + more app/article/community.
EXTENDED_POSTS = [
    {"branch": "leaf-texture", "title": "Begonia 'Fireworks'", "prefer": PROFILE.get("begonia-rex-fireworks", ""),
     "caption": "Silver and plum, set off like a firework. Rex begonias are painted by structure, not pigment — the leaf itself scatters light into colour."},
    {"branch": "rainforest-beauty", "title": "Monstera obliqua", "prefer": PROFILE.get("monstera-obliqua", ""),
     "caption": "More hole than leaf. The real M. obliqua is mostly air — and so rare that 99% of plants sold as 'obliqua' are actually adansonii. The ghost of the genus."},
    {"branch": "velvet-anthurium", "title": "Anthurium dressleri", "prefer": PROFILE.get("anthurium-dressleri", ""),
     "caption": "The Panama grail. Bullet-dark, velvet, and so tied to provenance that collectors trade its lineage like baseball cards."},
    {"branch": "rarity-value", "title": "Monstera 'Aurea'", "prefer": PROFILE.get("monstera-aurea", ""),
     "caption": "Variegation in gold. Where albo splits white, aurea marbles mustard-yellow — rarer, moodier, and a nightmare to keep balanced. Collector catnip."},
    {"branch": "collector-culture", "title": "The plant I lost", "prefer": PLT+"plant-09.jpg",
     "caption": "Every collector has one — the plant they killed and still think about. Rot, shock, a missed week. What did yours teach you? 👇"},
    {"branch": "leaf-texture", "title": "Begonia ferox", "prefer": PROFILE.get("begonia-ferox", ""),
     "caption": "The fierce one. Black-tipped bullate spikes across a puckered leaf — discovered shockingly recently in China. A begonia that looks armored."},
    {"branch": "rainforest-beauty", "title": "Monstera dubia", "prefer": PROFILE.get("monstera-dubia", ""),
     "caption": "The great shapeshifter. A juvenile that shingles flat against bark like coins, then matures into something unrecognizable. The best glow-up in aroids."},
    {"branch": "app-identify", "title": "What is that?", "prefer": "",
     "caption": "Found an unlabeled velvet at a sale? Point Leaf People at it — it names the species other apps just call 'Laceleaf.'"},
    {"branch": "velvet-anthurium", "title": "Anthurium kunayalense", "prefer": PROFILE.get("anthurium-kunayalense", ""),
     "caption": "Named for Guna Yala, the indigenous comarca in Panama it comes from. Every rare plant has a homeland — and a name that carries it."},
    {"branch": "rarity-value", "title": "Monstera 'Mint'", "prefer": PROFILE.get("monstera-mint", ""),
     "caption": "The mint unicorn. Green-on-green variegation so rare and unstable it's nearly myth — and priced like one. Most people will only see it on a screen."},
    {"branch": "article-fieldguide", "title": "Keep a velvet alive", "prefer": STK+"light-for-velvet-aroids-hero.jpg",
     "caption": "Want to actually keep a velvet anthurium alive? Our guide covers light, humidity, substrate and the mistakes that kill them. Link in bio."},
    {"branch": "leaf-texture", "title": "Begonia paulensis", "prefer": PROFILE.get("begonia-paulensis", ""),
     "caption": "Seersucker leaves — heavily puckered, glossy, ruffle-edged. A Brazilian begonia grown entirely for texture. One touch and you're hooked."},
    {"branch": "rainforest-beauty", "title": "Monstera pinnatipartita", "prefer": PROFILE.get("monstera-pinnatipartita", ""),
     "caption": "The climber that splits. Solid juvenile leaves tear into deep pinnate fingers once it catches a pole. Patience isn't a bug — it's the show."},
    {"branch": "community-ugc", "title": "Your jungle wall", "prefer": PLT+"plant-12.jpg",
     "caption": "Show us your plant wall 🌿 The greener and messier the better. Tag #leafpeople — we reshare favorites every week."},
    {"branch": "rarity-value", "title": "Philodendron 'Jose Buono'", "prefer": PROFILE.get("philodendron-jose-buono", ""),
     "caption": "Big paddles, bold cream splashes — and refreshingly stable. Jose Buono is the variegated philodendron that won't betray you by reverting to green."},
    {"branch": "app-collect", "title": "Catalogue it all", "prefer": APP+"shot-05.png",
     "caption": "Twenty plants? Two hundred? Leaf People keeps every one — what it is, how to care for it, when you last watered. Your whole jungle, in your pocket."},
    {"branch": "leaf-texture", "title": "Begonia listada", "prefer": PROFILE.get("begonia-listada", ""),
     "caption": "One bright stripe down deep green velvet. Begonia listada keeps it simple — herringbone texture, a chartreuse chevron, quiet confidence."},
    {"branch": "rainforest-beauty", "title": "Burle Marx Flame", "prefer": PROFILE.get("monstera-burle-marx-flame", ""),
     "caption": "Fenestration like fire. The flame-shaped windows set this one apart — named, like so much great planting, for Roberto Burle Marx."},
    {"branch": "article-understory", "title": "Why a leaf costs a car", "prefer": STK+"anthurium-price-history-hero.jpg",
     "caption": "Scarcity, slow growth, and a wall of demand. How a single leaf ends up worth more than a used car — the full breakdown, link in bio."},
    {"branch": "rarity-value", "title": "Strawberry Shake", "prefer": PROFILE.get("philodendron-strawberry-shake", ""),
     "caption": "Pink, cream and green confetti on every new leaf. Strawberry Shake sells itself on the flush — then settles. Chasing the perfect leaf is the game."},
    {"branch": "collector-culture", "title": "Unboxing day", "prefer": PLT+"plant-18.jpg",
     "caption": "Nothing beats unboxing day — bubble wrap, a heat pack, and a leaf you've wanted for a year. Best box you ever opened? 📦🌿"},
    {"branch": "leaf-texture", "title": "Hoya 'Hindu Rope'", "prefer": PROFILE.get("hoya-hindu-rope", ""),
     "caption": "The curled classic your grandmother grew. A mutation twists every leaf into a contorted rope — proof a 'common' plant can still be deeply strange."},
    {"branch": "rainforest-beauty", "title": "Philodendron 'Florida Ghost'", "prefer": PROFILE.get("philodendron-florida-ghost", ""),
     "caption": "Ghost leaves. New growth emerges spectral white and ages to deep green — a living before-and-after on one plant. Half the fun is the wait."},
    {"branch": "app-learn", "title": "A story for every plant", "prefer": PLT+"the-leaf.jpg",
     "caption": "We're publishing a story for all 68 plants in the app — origins, lore, the hunt. Open Leaf People to a fresh one every day. 🌿"},
    {"branch": "rarity-value", "title": "Philodendron billietiae", "prefer": PROFILE.get("philodendron-billietiae", ""),
     "caption": "Tangerine petioles, strap leaves, and a variegated form that broke the bank. The orange-stemmed climber that made everyone fall for petioles."},
    {"branch": "rainforest-beauty", "title": "Hoya linearis", "prefer": PROFILE.get("hoya-linearis", ""),
     "caption": "A waterfall of soft green needles. Linearis grows like hair off a Himalayan cliff — and hates exactly what most hoyas love. Cool, bright, a little spoiled."},
    {"branch": "community-ugc", "title": "Name your grail", "prefer": PLT+"plant-13.jpg",
     "caption": "Quick: the one plant you'd sell a kidney for. No wrong answers 👇 — we're building the ultimate Leaf People wishlist."},
    {"branch": "rainforest-beauty", "title": "Hoya obovata", "prefer": PROFILE.get("hoya-obovata", ""),
     "caption": "Round, silver-splashed, forgiving — obovata flowers like clockwork and turns houseplant people into hoya people. The friendliest gateway in the genus."},
    {"branch": "velvet-anthurium", "title": "Anthurium cupulispathum", "prefer": PROFILE.get("anthurium-cupulispathum", ""),
     "caption": "Deep-cut rarity. The cup-spathe anthurium you only meet far down the rabbit hole — the kind nobody at the party will recognize. That's the appeal."},
    {"branch": "app-cta", "title": "All of it, $0.99", "prefer": APP+"shot-01.png",
     "caption": "Identify, track, learn, trade — every plant in this feed, and the tools to keep them. One subscription, $0.99/month, 7 days free. leafpeople.app"},
]

AUTHORED = WELCOME_POSTS + SHOWCASE_POSTS + CONCEPT_POSTS + CONVERT_POSTS + EXTENDED_POSTS


# ============================================================================
# REST-OF-YEAR (days 91-213) — one spotlight per published story.
# Each post draws its image straight from THAT story's curated hero/body picks,
# so the species always matches the photo (a gloriosum post uses gloriosum imagery,
# by construction). No image repeats across the whole calendar (global `used` set);
# stories whose lead image was already used in days 1-90 fall back to their other
# curated image. Captions are seeded from each article's deck + a "link in bio" CTA.
# ============================================================================

# Species categories -> rotating beauty branches (keeps the calendar colourful and
# lets the bandit learn which genus/angle performs). Story categories -> convert/community.
ROY_BRANCHES = {
    "Anthurium":         ["velvet-anthurium", "leaf-texture", "rarity-value", "rarest-jungle"],
    "Philodendron":      ["rainforest-beauty", "leaf-texture", "rarity-value"],
    "Monstera":          ["rainforest-beauty", "jungle-escape", "rarity-value"],
    "Hoya":              ["rainforest-beauty", "leaf-texture"],
    "Begonia":           ["leaf-texture", "rainforest-beauty"],
    "The Market":        ["rarity-value", "article-understory"],
    "Collector Culture": ["collector-culture", "community-ugc", "article-understory"],
    "Field Skills":      ["app-learn", "article-fieldguide"],
}
SPECIES_CATS = ["Anthurium", "Philodendron", "Monstera", "Hoya", "Begonia"]
# round-robin interleave order so consecutive days vary in genus/branch/colour
INTERLEAVE = ["Anthurium", "Philodendron", "The Market", "Hoya",
              "Collector Culture", "Monstera", "Field Skills", "Begonia"]
ROY_TAIL = {
    "The Market":        "\n\nThe economics, in full — link in bio.",
    "Collector Culture": "\n\nThe full story's in bio. 🌿",
    "Field Skills":      "\n\nThe complete how-to — link in bio.",
}
SPECIES_TAIL = "\n\nFull field guide on Leaf People — link in bio. 🌿"


def load_articles():
    arts = []
    for dj in sorted(glob.glob(os.path.join(ROOT, "the-leaf", "*", "_data.json"))):
        try:
            d = json.loads(open(dj).read())
        except Exception:
            continue
        if not d.get("slug") or not d.get("category"):
            continue
        arts.append(d)
    return arts


def article_image_branches(category):
    """Branches an article's hero/body image suits, for the library + picker."""
    b = set(ROY_BRANCHES.get(category, ["rainforest-beauty"]))
    b |= {"article-fieldguide", "article-understory", "community-ugc"}
    if category in SPECIES_CATS:
        b |= {"welcome-leafpeople"}
    return sorted(b)


def roy_caption(art):
    deck = (art.get("deck") or art.get("meta_description") or "").strip()
    cat = art.get("category", "")
    tail = SPECIES_TAIL if cat in SPECIES_CATS else ROY_TAIL.get(cat, "\n\nRead it — link in bio. 🌿")
    return deck + tail


def build_roy_posts():
    """One post per published story, interleaved by category for day-to-day variety.
    Returns authored-post dicts (branch/title/caption/prefer_list) for the build loop."""
    arts = load_articles()
    by_cat = {}
    for a in arts:
        by_cat.setdefault(a["category"], []).append(a)
    for cat in by_cat:
        by_cat[cat].sort(key=lambda a: a["slug"])  # deterministic

    counters = {cat: 0 for cat in ROY_BRANCHES}
    order, idx = [], {cat: 0 for cat in by_cat}
    remaining = sum(len(v) for v in by_cat.values())
    while remaining:
        for cat in INTERLEAVE:
            lst = by_cat.get(cat, [])
            if idx[cat] < len(lst):
                order.append(lst[idx[cat]]); idx[cat] += 1; remaining -= 1

    posts = []
    for a in order:
        cat = a["category"]
        rot = ROY_BRANCHES.get(cat, ["rainforest-beauty"])
        branch = rot[counters.get(cat, 0) % len(rot)]
        counters[cat] = counters.get(cat, 0) + 1
        # curated picks first (hero is the article's lead image, then the body image),
        # both guaranteed to be the right species for a species story.
        prefer_list = [s for s in (a.get("hero"), a.get("body_image")) if s]
        posts.append({
            "branch": branch,
            "title": a.get("title", a["slug"]),
            "caption": roy_caption(a),
            "prefer_list": prefer_list,
            "slug": a["slug"],
            # species posts are image-strict: ONLY their own curated photos are
            # acceptable (a Monstera story must never show a Philodendron). If none
            # is free, the post is dropped and a beauty top-up takes the slot.
            "species": cat in SPECIES_CATS,
        })
    return posts


def exists(src):
    return os.path.exists(os.path.join(ROOT, src.lstrip("/")))


def build_topups(n):
    """Pure-beauty showcase posts to top up any days the stories don't cover.
    No preferred image — the loop fills each from the first unused on-branch photo."""
    beauty = ["rainforest-beauty", "velvet-anthurium", "leaf-texture", "rarity-value", "jungle-escape"]
    out = []
    for i in range(max(0, n)):
        out.append({
            "branch": beauty[i % len(beauty)], "title": "Rare & beautiful",
            "caption": "More from the rarest corners of the rainforest — a fresh rare-plant story every day on Leaf People. \U0001F33F leafpeople.app",
            "prefer_list": [],
        })
    return out


def build():
    articles = load_articles()
    lib = build_library(articles)
    lib = [e for e in lib if exists(e["src"])]

    # Preserve already-assigned default images for existing days, so regenerating to add
    # later days never reshuffles days the user has reviewed. (Their picker choices live in
    # localStorage and override regardless; this keeps the underlying defaults stable too.)
    old = {}
    posts_path = os.path.join(ROOT, "instagram", "posts.json")
    if os.path.exists(posts_path):
        try:
            for op in json.load(open(posts_path)):
                if op.get("image"):
                    old[op["id"]] = op["image"]
        except Exception:
            pass

    # Full-year line-up: the original authored arc (days 1-90), then one spotlight per
    # published story (rest-of-year wave), then beauty top-ups to fill out to Dec 31.
    queue = AUTHORED + build_roy_posts()
    used = set()      # global: every chosen image is unique across the calendar
    assigned = []     # (post-spec, image) in final order; dropped specs are skipped

    def pick_image(p, day_hint):
        prev = old.get(f"d{day_hint:02d}") if day_hint else None
        prefers = p.get("prefer_list") or ([p["prefer"]] if p.get("prefer") else [])
        order = ([prev] if prev else []) + list(prefers)
        if not p.get("species"):            # non-species posts may fall back to any on-branch photo
            order += [e["src"] for e in candidates_for(p["branch"], lib)]
        return next((s for s in order if s and exists(s) and s not in used), "")

    for idx, p in enumerate(queue):
        img = pick_image(p, idx + 1 if idx < len(AUTHORED) else 0)
        if not img:
            if p.get("species"):
                continue  # image-strict species post with no free own-species photo — drop it
            print(f"  ! ({p['branch']}): no free image, kept empty")
        used.add(img)
        assigned.append((p, img))
        if len(assigned) >= N_DAYS:
            break

    # Top up any remaining days with pure-beauty showcase posts (generic caption, any free photo).
    for tp in build_topups(N_DAYS - len(assigned)):
        img = pick_image(tp, 0)
        used.add(img)
        assigned.append((tp, img))

    posts = []
    for i, (p, img) in enumerate(assigned[:N_DAYS]):
        day = i + 1
        d = START + timedelta(days=i)
        branch = p["branch"]
        phase = BRANCHES[branch]["phase"]
        posts.append({
            "id": f"d{day:02d}", "day": day, "date": d.isoformat(),
            "phase": phase, "branch": branch, "status": "draft",
            "title": p["title"], "image": img,
            "caption": p["caption"], "hashtags": tags(branch), "cta": CTA[phase],
            "metrics": {"likes": 0, "comments": 0, "saves": 0, "follows": 0, "reach": 0},
        })

    branches_out = {
        "handle": HANDLE, "site": SITE, "phases": PHASES, "branches": BRANCHES,
        "goals": FORTNIGHT_GOALS,
        "hashtagTiers": {"brand": BRAND_TAGS, "discovery": DISCOVERY, "niche": NICHE},
    }

    os.makedirs(os.path.join(ROOT, "instagram"), exist_ok=True)
    json.dump(posts, open(os.path.join(ROOT, "instagram", "posts.json"), "w"), indent=2)
    json.dump(branches_out, open(os.path.join(ROOT, "instagram", "branches.json"), "w"), indent=2)
    json.dump(lib, open(os.path.join(ROOT, "instagram", "library.json"), "w"), indent=2)

    authored = sum(1 for p in posts if p["status"] == "draft")
    # report option-depth per branch (how many free options the page can offer)
    print(f"\nWrote posts.json ({len(posts)} days, {authored} authored), branches.json, library.json ({len(lib)} images)")
    print("Option depth per branch (library size):")
    for b in BRANCHES:
        n = len(candidates_for(b, lib))
        print(f"  {b:22s} {n}")


if __name__ == "__main__":
    build()
