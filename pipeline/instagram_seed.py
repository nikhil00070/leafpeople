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
N_DAYS = 60
HANDLE = "leafpeople.app"
SITE = "leafpeople.app"

IG = "/images/instagram/"
STK = "/images/source/stock/"
PLT = "/images/plants/"
CMP = "/images/compare/"
APP = "/images/app/"

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
    {"weeks": "Days 57-60+", "theme": "Rolling funnel — exploit winners, keep exploring",
     "followers": 2000, "avg_likes": 220, "extra": "Self-sustaining: each posted day spawns a fresh skeleton."},
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

def build_library():
    lib = []
    seen = set()
    def add(src, branches, kind, credit=""):
        if src in seen: return
        seen.add(src)
        lib.append({"src": src, "branches": branches, "kind": kind, "credit": credit})

    for f, br in APP_LIB.items():  add(IG + f, br, "app")
    for f, br in ID_LIB.items():   add(CMP + f, br, "id")
    for f, br in MOOD_LIB.items(): add(PLT + f, br, "mood")
    for f, br in APP_UI.items():   add(APP + f, br, "appui")

    credits = load_credits()
    for full in sorted(glob.glob(os.path.join(ROOT, "images", "source", "stock", "*-hero.jpg"))):
        src = "/" + os.path.relpath(full, ROOT)
        c = credits.get(src, {})
        add(src, stock_branches(os.path.basename(src)), "stock", c.get("credit", "iNaturalist (CC BY)"))

    # welcome-leafpeople can pull from the whole "pretty" pool
    for e in lib:
        if {"velvet-anthurium", "rainforest-beauty", "rarest-jungle"} & set(e["branches"]):
            if "welcome-leafpeople" not in e["branches"]:
                e["branches"] = e["branches"] + ["welcome-leafpeople"]
    return lib

KIND_ORDER = {"app": 0, "appui": 1, "id": 2, "mood": 3, "stock": 4}

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

AUTHORED = WELCOME_POSTS + SHOWCASE_POSTS


def exists(src):
    return os.path.exists(os.path.join(ROOT, src.lstrip("/")))


def build():
    lib = build_library()
    lib = [e for e in lib if exists(e["src"])]
    used = set()  # global: every chosen default is unique across posts

    posts = []
    for i in range(N_DAYS):
        day = i + 1
        d = START + timedelta(days=i)
        if i < len(AUTHORED):
            p = AUTHORED[i]
            branch = p["branch"]
            phase = BRANCHES[branch]["phase"]
            # default = preferred image if free+real, else first branch candidate not yet used
            order = ([p["prefer"]] if p.get("prefer") else []) + [e["src"] for e in candidates_for(branch, lib)]
            default = next((s for s in order if exists(s) and s not in used), "")
            if not default:
                print(f"  ! day {day} ({branch}): no free image!")
                default = p.get("prefer", "")
            used.add(default)
            posts.append({
                "id": f"d{day:02d}", "day": day, "date": d.isoformat(),
                "phase": phase, "branch": branch, "status": "draft",
                "title": p["title"], "image": default,
                "caption": p["caption"], "hashtags": tags(branch), "cta": CTA[phase],
                "metrics": {"likes": 0, "comments": 0, "saves": 0, "follows": 0, "reach": 0},
            })
        else:
            j = i - len(AUTHORED)
            branch = BRANCH_SCHEDULE[j] if j < len(BRANCH_SCHEDULE) else "app-cta"
            phase = BRANCHES[branch]["phase"]
            posts.append({
                "id": f"d{day:02d}", "day": day, "date": d.isoformat(),
                "phase": phase, "branch": branch, "status": "skeleton",
                "title": BRANCHES[branch]["label"], "image": "",
                "caption": "", "hashtags": tags(branch), "cta": CTA[phase],
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
