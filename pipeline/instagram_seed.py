#!/usr/bin/env python3
"""
instagram_seed.py — generate the Instagram content calendar for /instagram.

Writes:
  instagram/branches.json  — strategy tree (phases, branches, fortnight goals, config)
  instagram/posts.json     — 60-day calendar.
                             Days 1-15  WELCOME  — introduce Leaf People + rainforest immersion (authored)
                             Days 16-30 SHOWCASE — the rarest leaves, up close (authored)
                             Days 31-45 CONCEPT  — tie beauty to the app (skeleton)
                             Days 46-60 CONVERT  — articles, site, installs (skeleton)

Images: real plant photos. The strongest are the app's own Plant-Profile shots
(/images/instagram/anthurium-*.jpeg, /images/instagram/philodendron-*) copied from the
Foliology Xcode asset catalog — the same photos tagged to those species inside the app.
Each post carries a `pool` of candidates so the tab's "refresh image" button has options.

Phase 1 is MANUAL-ASSIST (post by hand, enter metrics). The learning loop is a multi-armed
bandit over `branch`. Re-run this script to regenerate the calendar from scratch.
"""

import json
import os
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

START = date(2026, 6, 2)        # day 1 = tomorrow at seed time; deterministic
N_DAYS = 60
HANDLE = "leafpeople.app"
SITE = "leafpeople.app"

IG = "/images/instagram/"       # real app plant-profile photos
STK = "/images/source/stock/"
PLT = "/images/plants/"
CMP = "/images/compare/"        # the head-to-head ID shots

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
    # WELCOME (1-15): introduce the app + immerse in the rainforest. Earn the follow.
    "welcome-leafpeople": {"phase": "welcome", "color": "#34c759", "label": "Welcome · Leaf People",
                           "intent": "Introduce the app & mission — the daily escape to the jungle."},
    "jungle-escape": {"phase": "welcome", "color": "#2f8f6b", "label": "Jungle Escape",
                      "intent": "Immersive, sensory escapism — transport them to the rainforest."},
    "rarest-jungle": {"phase": "welcome", "color": "#7c5cff", "label": "Rarest Jungle Plants",
                      "intent": "The wow — the rarest leaves on earth, revealed."},
    # SHOWCASE (16-30): the rarest leaves up close, go deeper.
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
    # CONCEPT (31-45): tie the beauty to what Leaf People does.
    "app-identify": {"phase": "concept", "color": "#5bd17a", "label": "App · Identify",
                     "intent": "Name any rare aroid from a leaf — the head-to-head proof."},
    "app-track-care": {"phase": "concept", "color": "#46c0c0", "label": "App · Track & Care",
                       "intent": "Care tracker, reminders, regional guidance."},
    "app-learn": {"phase": "concept", "color": "#8fb04a", "label": "App · Learn",
                  "intent": "Field guide & Understory deep-dives in the app."},
    "app-collect": {"phase": "concept", "color": "#c08a46", "label": "App · Collect",
                    "intent": "Collection log + the collector's marketplace."},
    # CONVERT (46-60): drive to articles, site, installs.
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

# --- WELCOME (days 1-15) -----------------------------------------------------
WELCOME_POSTS = [
    {"branch": "welcome-leafpeople", "title": "Welcome home",
     "caption": "Welcome to Leaf People. \U0001F33F\n\nForget the inbox, the traffic, the noise. For the next sixty seconds you're somewhere else — a Colombian cloud forest, ankle-deep in leaf litter, the air thick and green.\n\nThis is an app, and a world, built around one thing: the rarest rainforest plants on earth.\n\nStay a while. leafpeople.app",
     "pool": [IG+"anthurium-warocqueanum.jpeg", IG+"philodendron-gloriosum.jpg", PLT+"aroid.jpg"]},

    {"branch": "jungle-escape", "title": "Breathe in",
     "caption": "Breathe in.\n\nWet earth, crushed leaves, something sweet flowering far overhead. The rainforest floor doesn't smell like anything you keep in a pot — it smells alive.\n\nWe can't bottle it. But we can bring you the plants that grow in it. Every single day.\n\n\U0001F33F leafpeople.app",
     "pool": [IG+"philodendron-melanochrysum.jpeg", IG+"philodendron-gloriosum.jpg", PLT+"the-leaf.jpg"]},

    {"branch": "rarest-jungle", "title": "Meet the Queen",
     "caption": "Meet the Queen. \U0001F451\n\nAnthurium warocqueanum — three feet of black-green velvet hung from a rainforest tree, one of the most coveted plants on the planet.\n\nMost people will never see one in person. Here, she's only the beginning.\n\nleafpeople.app",
     "pool": [IG+"anthurium-warocqueanum.jpeg", CMP+"lp-warocqueanum.png", IG+"anthurium-veitchii.jpeg"]},

    {"branch": "welcome-leafpeople", "title": "What is Leaf People",
     "caption": "So what is Leaf People?\n\nA field guide, a care tracker, an ID engine and a collector's marketplace — built only for rare rainforest plants. Not ten thousand species skimmed. The ones actually worth knowing, studied deep.\n\nBy plant people, for plant people. leafpeople.app \U0001F33F",
     "pool": [IG+"philodendron-verrucosum.png", IG+"anthurium-carla-blackie.jpeg", PLT+"aroid.jpg"]},

    {"branch": "jungle-escape", "title": "Find the light",
     "caption": "Find the light.\n\nOn the forest floor it arrives in pieces — a shaft here, a glow there, filtered through a hundred feet of canopy. It's why these leaves grow so big, so dark, so hungry.\n\nSlow down. Let your eyes adjust. There's a whole world down here.\n\n\U0001F33F #leafpeople",
     "pool": [IG+"philodendron-gigas.jpg", IG+"philodendron-gloriosum.jpg", PLT+"plant-12.jpg"]},

    {"branch": "rarest-jungle", "title": "Blackest leaf",
     "caption": "The blackest leaf in the room.\n\nAnthurium 'Ace of Spades' drinks the light — velvet so dark it reads almost black, with an oil-slick shimmer when it turns.\n\nSome plants are pretty. This one is a statement.\n\nleafpeople.app \U0001F5A4",
     "pool": [IG+"anthurium-ace-of-spades.jpeg", CMP+"lp-ace-of-spades.png", IG+"anthurium-dark-mama.jpg"]},

    {"branch": "welcome-leafpeople", "title": "Why we built it",
     "caption": "Why we built Leaf People.\n\nBecause if you've ever fallen down a 1am rabbit hole trying to tell two velvet anthuriums apart, you know the tools out there weren't made for us.\n\nSo we made our own. Identify, track, learn, collect — all in one place.\n\n\U0001F33F leafpeople.app",
     "pool": [IG+"anthurium-antolakii.jpeg", IG+"anthurium-carla-blackie.jpeg", PLT+"collector-culture.jpg"]},

    {"branch": "jungle-escape", "title": "Rain on leaves",
     "caption": "The sound of rain on leaves.\n\nNot the city kind — the jungle kind. Fat drops drumming on giant foliage, running down a leaf the size of your arm, feeding roots that never go thirsty.\n\nClose your eyes. You're there.\n\n\U0001F33F #rainforest #leafpeople",
     "pool": [IG+"philodendron-melanochrysum.jpeg", IG+"philodendron-gigas.jpg", PLT+"plant-06.jpg"]},

    {"branch": "rarest-jungle", "title": "Silver lightning",
     "caption": "Silver lightning.\n\nThose veins on Anthurium crystallinum aren't painted — it's the way the velvet scatters light. Sugar-white over deep forest green.\n\nNature engineered this. We just can't stop staring.\n\nleafpeople.app ✨",
     "pool": [IG+"anthurium-crystalanium.jpeg", CMP+"lp-crystallinum.png", IG+"anthurium-forgetii.png"]},

    {"branch": "welcome-leafpeople", "title": "Deep not wide",
     "caption": "We went deep, not wide.\n\nAnyone can list ten thousand plants. We chose a handful of genera — the rare rainforest aroids and their cousins — and learned them properly. Light, humidity, substrate, the lot.\n\nQuality over quantity. Always.\n\n\U0001F33F leafpeople.app",
     "pool": [IG+"anthurium-veitchii.jpeg", IG+"anthurium-warocqueanum.jpeg", IG+"anthurium-morona.jpeg"]},

    {"branch": "jungle-escape", "title": "Morning mist",
     "caption": "Morning mist.\n\nFor an hour after dawn the cloud forest disappears into white — every leaf beaded with water, the whole world hushed and dripping.\n\nThis is the calm we're chasing. A pocket of jungle, two feet from your couch.\n\n\U0001F33F #leafpeople #calm",
     "pool": [IG+"philodendron-gloriosum.jpg", IG+"philodendron-verrucosum.png", PLT+"plant-11.jpg"]},

    {"branch": "rarest-jungle", "title": "The deep end",
     "caption": "The ones collectors whisper about.\n\nAnthurium papillilaminum — deep, suede-dark, impossibly velvet. The kind of plant that starts bidding wars and long flights to nurseries you've never heard of.\n\nThis is the deep end. Welcome.\n\n\U0001F33F leafpeople.app",
     "pool": [IG+"anthurium-papillilaminum.png", IG+"anthurium-dark-mama.jpg", CMP+"lp-papillilaminum.png"]},

    {"branch": "welcome-leafpeople", "title": "You're not the only one",
     "caption": "You're not the only one. \U0001F33F\n\nThere's a whole community of people who love these plants like family — who name them, photograph them, mourn a lost leaf.\n\nLeaf People is home base for all of us. Pull up a chair.\n\nleafpeople.app",
     "pool": [PLT+"collector-culture.jpg", IG+"anthurium-morona.jpeg", PLT+"field-skills.jpg"]},

    {"branch": "jungle-escape", "title": "Your pocket of jungle",
     "caption": "Your own pocket of jungle.\n\nYou don't need a greenhouse or a plane ticket. One rare leaf on a shelf, catching the morning light, is enough to take your whole mind somewhere greener.\n\nThat's the magic. That's why we're here.\n\n\U0001F33F #leafpeople #biophilia",
     "pool": [IG+"philodendron-spiritus-sancti.jpg", IG+"philodendron-gigas.jpg", PLT+"plant-14.jpg"]},

    {"branch": "welcome-leafpeople", "title": "Welcome home (bridge)",
     "caption": "If you've made it this far — welcome home. \U0001F33F\n\nLeaf People is your daily escape to the rainforest, plus the tools to bring a piece of it home: identify any rare aroid, track its care, learn from a real field guide, trade with collectors.\n\nHit follow. Tomorrow we go deeper — the rarest, strangest, most beautiful leaves on earth.\n\nleafpeople.app",
     "pool": [IG+"anthurium-warocqueanum.jpeg", IG+"anthurium-carla-blackie.jpeg", CMP+"lp-carla-blackie.png"]},
]

# --- SHOWCASE (days 16-30) — the rarest leaves up close ----------------------
SHOWCASE_POSTS = [
    {"branch": "velvet-anthurium", "title": "The Queen, up close",
     "caption": "She doesn't grow leaves. She grows banners.\n\nAnthurium warocqueanum: two, three feet of black-green velvet catching light like crushed silk. You don't decorate with a plant like this — you keep it.",
     "pool": [IG+"anthurium-warocqueanum.jpeg", CMP+"lp-warocqueanum.png", IG+"anthurium-veitchii.jpeg"]},

    {"branch": "rainforest-beauty", "title": "Understory",
     "caption": "This is where they actually live.\n\nNot a windowsill — the understory. Dappled light, dripping humidity, a canopy a hundred feet up. Understand the home, and you understand the plant.",
     "pool": [IG+"philodendron-gloriosum.jpg", PLT+"aroid.jpg", IG+"philodendron-verrucosum.png"]},

    {"branch": "leaf-texture", "title": "Crystalline veins",
     "caption": "Look closer.\n\nThe silver veins on Anthurium crystallinum aren't painted on — it's how the velvet scatters light across the surface. Sugar-white lightning over deep green.",
     "pool": [IG+"anthurium-crystalanium.jpeg", CMP+"lp-crystallinum.png", IG+"anthurium-forgetii.png"]},

    {"branch": "rarity-value", "title": "More than a phone",
     "caption": "Yes, people pay thousands for a single plant.\n\nA Philodendron spiritus-sancti can change hands for the price of a used car. Sounds insane — until you see one in person and watch the room go quiet.",
     "pool": [IG+"philodendron-spiritus-sancti.jpg", IG+"anthurium-warocqueanum.jpeg", IG+"anthurium-dark-mama.jpg"]},

    {"branch": "collector-culture", "title": "The obsession",
     "caption": "It starts with one leaf.\n\nThen you're three forums deep at 1am learning to tell two species apart by their petioles. Welcome — you're one of us now.",
     "pool": [PLT+"collector-culture.jpg", PLT+"field-skills.jpg", IG+"anthurium-antolakii.jpeg"]},

    {"branch": "velvet-anthurium", "title": "Ace of Spades",
     "caption": "The blackest leaf in the room.\n\nAnthurium 'Ace of Spades' — velvet so dark it drinks the light, with a faint oil-slick sheen when it turns. Some plants are pretty. This one is intimidating.",
     "pool": [IG+"anthurium-ace-of-spades.jpeg", CMP+"lp-ace-of-spades.png", IG+"anthurium-dark-mama.jpg"]},

    {"branch": "rainforest-beauty", "title": "Green wall",
     "caption": "Imagine your whole wall doing this.\n\nLayered leaves, every shade of green, a private little rainforest two feet from your couch. Not a plant — a feeling. Calm, alive, yours.",
     "pool": [IG+"philodendron-melanochrysum.jpeg", PLT+"plant-12.jpg", IG+"philodendron-gigas.jpg"]},

    {"branch": "leaf-texture", "title": "Bone-white veins",
     "caption": "The gold standard of veining.\n\nThick, heart-shaped, bone-white veins carved into deep green velvet — the leaf people draw when they imagine a 'jungle plant.' Real. Living. Growing on someone's shelf right now.",
     "pool": [IG+"anthurium-forgetii.png", IG+"anthurium-carla-blackie.jpeg", STK+"anthurium-clarinervium-id-gold-standard-hero.jpg"]},

    {"branch": "rarity-value", "title": "Why so rare",
     "caption": "Why is it so hard to get?\n\nMany grow on one mountainside, in one country, and take years to reach a single sellable leaf. Add export rules, slow propagation, and a wall of demand. Scarcity isn't hype here — it's botany.",
     "pool": [IG+"anthurium-morona.jpeg", IG+"anthurium-warocqueanum.jpeg", STK+"anthurium-regale-hero.jpg"]},

    {"branch": "collector-culture", "title": "First rare plant",
     "caption": "Remember your first 'real' rare plant?\n\nThe one you saved for, tracked down, unboxed with your heart in your throat — then checked on six times a day for a week.\n\nDrop it in the comments. \U0001F447",
     "pool": [PLT+"plant-10.jpg", PLT+"field-skills.jpg", IG+"anthurium-antolakii.jpeg"]},

    {"branch": "velvet-anthurium", "title": "Velvet up close",
     "caption": "Velvet, but make it alive.\n\nThe matte, light-eating surface of a velvet Anthurium comes from tiny cell structures that kill reflection — it feels like suede and photographs like a shadow. No filter.",
     "pool": [IG+"anthurium-papillilaminum.png", CMP+"lp-papillilaminum.png", IG+"anthurium-dark-mama.jpg"]},

    {"branch": "rainforest-beauty", "title": "Morning dew",
     "caption": "Morning, in the jungle and on your shelf.\n\nDew beads on a waxy leaf, the light goes soft, and for a second your apartment is a cloud forest. Who else checks their plants before they check their phone?",
     "pool": [PLT+"plant-06.jpg", IG+"philodendron-gloriosum.jpg", PLT+"plant-11.jpg"]},

    {"branch": "leaf-texture", "title": "Quilted & bullate",
     "caption": "Run your eyes over that surface.\n\nBullate leaves pucker between the veins — quilted, three-dimensional, catching light in a dozen directions at once. Texture is the whole point.",
     "pool": [IG+"anthurium-corrugatum.jpeg", IG+"anthurium-cupulispathum.jpeg", STK+"anthurium-luxurians-hero.jpg"]},

    {"branch": "rarity-value", "title": "Variegation lottery",
     "caption": "The variegation lottery.\n\nEvery so often a leaf unfurls half-cream, half-green — a random mutation no grower can guarantee. You can't farm luck. That's exactly why collectors chase it.",
     "pool": [STK+"anthurium-magnificum-clarinervium-hybrids-hero.jpg", PLT+"plant-13.jpg", PLT+"plant-17.jpg"]},

    {"branch": "velvet-anthurium", "title": "The bridge",
     "caption": "If you've made it this far, you're one of us. \U0001F33F\n\nThere's a whole world of rare aroids — and almost nothing built for the people who actually love them. So we built it. Leaf People: identify down to the species, track care, learn from a real field guide, trade with collectors. All at leafpeople.app.",
     "pool": [IG+"anthurium-carla-blackie.jpeg", CMP+"lp-carla-blackie.png", IG+"anthurium-warocqueanum.jpeg"]},
]

# Skeleton branch rotation for days 31-60 (the bandit re-biases these later).
BRANCH_SCHEDULE = (
    # CONCEPT 31-45
    ["app-identify", "app-track-care", "app-learn", "app-collect", "app-identify",
     "app-track-care", "app-learn", "app-identify", "app-collect", "app-learn",
     "app-identify", "app-track-care", "app-learn", "app-collect", "app-identify"]
    # CONVERT 46-60
    + ["article-fieldguide", "app-cta", "article-understory", "community-ugc", "article-fieldguide",
       "app-cta", "article-understory", "article-fieldguide", "community-ugc", "app-cta",
       "article-fieldguide", "article-understory", "app-cta", "community-ugc", "app-cta"]
)

AUTHORED = WELCOME_POSTS + SHOWCASE_POSTS   # days 1-30


def validate(path):
    full = os.path.join(ROOT, path.lstrip("/"))
    if os.path.exists(full):
        return True
    print(f"  ! missing image: {path}")
    return False


def build():
    posts = []
    for i in range(N_DAYS):
        day = i + 1
        d = START + timedelta(days=i)
        if i < len(AUTHORED):
            p = AUTHORED[i]
            branch = p["branch"]
            phase = BRANCHES[branch]["phase"]
            pool = [x for x in p["pool"] if validate(x)] or p["pool"][:1]
            posts.append({
                "id": f"d{day:02d}", "day": day, "date": d.isoformat(),
                "phase": phase, "branch": branch, "status": "draft",
                "title": p["title"], "image": pool[0], "pool": pool,
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
                "title": BRANCHES[branch]["label"], "image": "", "pool": [],
                "caption": "", "hashtags": tags(branch), "cta": CTA[phase],
                "metrics": {"likes": 0, "comments": 0, "saves": 0, "follows": 0, "reach": 0},
            })

    branches_out = {
        "handle": HANDLE, "site": SITE, "phases": PHASES, "branches": BRANCHES,
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
