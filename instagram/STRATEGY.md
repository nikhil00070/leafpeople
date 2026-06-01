# Leaf People — Instagram Growth Strategy

The fully-baked plan behind the `/instagram` calendar. Edit content in
`pipeline/instagram_seed.py` and re-run it to regenerate `posts.json` + `branches.json`.

## The funnel

```
   STOP THE SCROLL          →   EARN THE FOLLOW       →   SHOW THE TOOL       →   CONVERT
   (beauty / "how is             (identity, rarity,        (ID, track, learn,      (articles, app
    that real?")                  belonging)                collect)                installs)
   plant + nature lovers         they follow because       they see we're the      they read the guide,
                                  we blow their mind        people who *get* it     download the app
```

Every post traces back to **leafpeople.app** via the brand hashtags (`#leafpeople`,
`#leafpeopleapp`) and the handle in the caption — so even a pure-beauty post seeds the brand.

## The branch tree (the decision part)

Each post is tagged with a **branch**. The learning loop rewards branches that perform and
rotates away from ones that stall. Branches are grouped into three phases:

**Phase INTRO (days 1–15) — beauty & identity.** Earn the follow, find the winning angle.
- `velvet-anthurium` — the hero look (warocqueanum, Ace of Spades, papillilaminum)
- `rainforest-beauty` — understory mood, lush foliage, calm
- `leaf-texture` — macro veining, crystalline/bullate surfaces
- `rarity-value` — the $400–$12k stories, scarcity, the hunt
- `collector-culture` — the people & the obsession, belonging

**Phase CONCEPT (days 16–35) — tie the beauty to the product.**
- `app-identify` (lead with the head-to-head proof: we name species others can't)
- `app-track-care`, `app-learn`, `app-collect`

**Phase CONVERT (days 36–60) — drive to articles, site, installs.**
- `article-fieldguide`, `article-understory` ("read the full guide — link in bio")
- `app-cta` (7-day trial, $0.99/mo), `community-ugc` (share & tag, we reshare)

**Fallback rule:** if the leading branch in a phase starts cooling (latest post < 45% of that
branch's peak engagement), rotate the next open slots to the runner-up branch. If a branch is
untried, slot one in to keep exploring — a sleeper hit shouldn't be missed.

## The learning loop (multi-armed bandit, honest version)

This is heuristic optimization, not magic. Each day:

1. **Score** each posted day: `likes×1 + comments×4 + saves×6 + follows×10` (deeper intent
   weighted heavier — a save or follow matters more than a like).
2. **Rank branches** by average score (the leaderboard on the dashboard).
3. **Exploit:** bias the next open (skeleton) slots in the current phase toward the top branch —
   reuse the angle/format that worked.
4. **Explore:** always keep one untested branch in rotation so we don't over-fit early.
5. **Detect exhaustion:** if a branch's latest post is far below its peak, mark it cooling and
   rotate. (This is the "day 5 got 300, day 6 got 1 → walk further down the day-5 path" rule,
   surfaced as a recommendation.)

In **Phase 1** the scores come from numbers you type in after posting. In **Phase 2** they come
from the Instagram Graph API insights endpoint automatically.

## Hashtag taxonomy

Per post = **brand** (always) + **discovery** (broad reach) + **niche** (theme/species):
- Brand: `#leafpeople #leafpeopleapp` + "leafpeople.app" in caption
- Discovery: `#plantsofinstagram #rareplants #aroidaddicts #foliage #indoorjungle …`
- Niche: per branch — e.g. `#velvetanthurium #anthuriumwarocqueanum #rarearoids` …

## Fortnightly goals

| Window | Theme | Followers | Avg likes |
|---|---|---|---|
| Days 1–14 | Establish the look, find the winning intro branch | 150 | 40 |
| Days 15–28 | Bridge beauty → the app | 400 | 80 |
| Days 29–42 | Concept posts turn lookers into learners | 800 | 120 |
| Days 43–56 | Article tie-ins drive site & app | 1,500 | 180 |
| Days 57–60+ | Rolling funnel — exploit winners, keep exploring | 2,000 | 220 |

(Targets are editable in `FORTNIGHT_GOALS`. Treat as hypotheses to beat, not promises.)

## How you run it (Phase 1 — manual-assist)

1. Open `/instagram`, click the day.
2. Hit **Copy caption + tags**, post it on Instagram (don't like an image? **↻ refresh** cycles the pool).
3. Come back, type the **likes / comments / saves / follows** in. Dashboard + recommendations update live.
4. Read the recommendations; they tell you which branch to lean into next.

## Roadmap

- **Phase 1 (done):** calendar, 15 authored intro posts, 45-day branch skeleton, dashboard,
  branch leaderboard, recommendations, refresh-image, manual metrics.
- **Phase 2:** connect Instagram Graph API **insights** (read-only — no app review needed for your
  own Business/Creator account) → metrics auto-fill, learning loop runs on real data; persist image
  choices + generated skeleton posts back to the repo via the `/api/publish` pattern.
- **Phase 3:** auto-posting via the Graph API content-publishing endpoint (Business account, public
  image URLs we already have, ~25 posts/day cap, Meta app review for the publish permission); a daily
  cron posts the approved day and spawns a fresh skeleton to keep the funnel populated.

## Notes / honesty

- Images are real photos from the repo library (rights-cleared, on-brand) — not AI-generated.
- "Self-learning" is only as good as the metrics feed; without the Phase 2 API it runs on what you type.
- Auto-posting (Phase 3) depends on Meta's review queue — don't gate the content launch on it.
