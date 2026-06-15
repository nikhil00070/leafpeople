# 🎬 Reels Runbook — "let's make more reels like X"

Say a theme; I run this. The **only** things that need a decision are in **§0 The Brief**.
Everything else (format, overlay, music approach, calendar insert) is a fixed, reusable system.

---

## §0 The Brief — what we decide together (the rest is automatic)

| Decision | Last batch (the "model holding a plant" reels) |
|---|---|
| **Theme / voice** | "Plants as my quiet refuge from a chaotic world" — 7am plant check, 200 unread emails, green = the color of life |
| **On-screen concept** | A young woman holds & slowly turns a potted rare plant in a cozy modern room |
| **Count / budget** | 10 reels · ~$2.50 each (8s, 720p) ≈ $25 + ~$0.30 music |
| **Variation axes** | plant (different leaf forms) · model (brunette/blonde) · room |
| **Music vibe** | calm, slow, bright **morning**, soft (no drums) — copyright-safe original |
| **Caption rule** | lifestyle/generic, **no species claim** (AI plant); lead with the feeling, brand in the CTA |
| **Placement** | sprinkled mixed-parity days, ~2/wk, interspersed with existing reels |

**Before generating:** draft the hooks (overlay lines) + captions in the voice and get a thumbs-up.
The hooks are short (1–3 serif lines); captions carry the fuller feeling + soft CTA.

---

## §1 Fixed system (don't re-decide these)

- **Format:** vertical 9:16, 8s, `google/veo-3-fast`, `generate_audio:true`, with a hands/no-morph guardrail in every prompt.
- **Overlay:** ALWAYS `add_hook.py` house style — `LEAF PEOPLE` kicker (spaced caps) + green accent bar + Georgia serif headline, lower-left, soft scrim. Only the headline words change. This is what keeps every reel visually consistent.
- **Music:** `meta/musicgen` (`stereo-large`, mp3) — original, copyright-safe (the API can't add IG trending audio). Generate a few beds in the vibe and rotate. We CANNOT use real songs (e.g. Papaoutai) — match the *vibe* only.
- **Cost:** 8s 720p Veo ≈ $2.50/clip · musicgen bed ≈ $0.05. Check Replicate credit first.
- **Token:** `REPLICATE_API_TOKEN` (user supplies inline; never commit it).

---

## §2 Step-by-step

**1. Music beds** → `/tmp/music_beds/bed-*.mp3` (musicgen, N beds in the vibe; soften by lowering mix volume not just the prompt).

**2. Prompts** → edit `make_model_reels.py` `SPECS` (or a copy) with the N varied `(who, plant, room)` tuples. Keep `_GUARD` (natural hands, no morphing).

**3. Generate (background — ~2 min/clip):**
```
for i in $(seq 1 N); do REPLICATE_API_TOKEN=… python3 pipeline/make_model_reels.py $i; done
```
Persists `model-NN-raw.mp4` (no music) **and** mixes a rotated bed → `model-NN.mp4`.
→ The raw masters mean **re-mixing music is free** — never regenerate video to change a track.

**4. Review** → `open /tmp/model_reels`; user approves music/look. Re-mix freely if needed (rotate beds, tune `MUS`/`AMB` volumes in `mix_music`).

**5. Burn hooks** → for each reel, `add_hook.make_overlay(hook, png)` then overlay (preserves audio, `-c:a copy`). Output the finished reels.

**6. Place in repo:**
- `model-NN.mp4` → `videos/instagram/<batch>-NN.mp4`
- cover frame (ffmpeg `-ss 2.2`) → `images/instagram/<batch>-NN-cover.jpg`

**7. Insert into the calendar** → adapt & run `insert_model_reels.py` (see §3). Pins existing future posts' media, interleaves the new reels at `POSITIONS`, renumbers days, writes `posts.json` (+ `.bak`). Double-insert guarded.

**8. Verify (no posting):**
```
IG_DRY_RUN=1 LP_DATE=<a new date> python3 pipeline/post_to_instagram.py   # → resolves the new reel
IG_DRY_RUN=1 LP_DATE=<a shifted date> python3 pipeline/post_to_instagram.py # → shifted reel/article still correct
```
Check: JSON valid, days contiguous 1..N, +N count.

**9. Commit + push** (`git pull --rebase --autostash` then push). Vercel redeploys ~1–2 min; hard-refresh `/instagram` to review.

---

## §3 Per-batch edits to `insert_model_reels.py`

The script is one-shot and **guarded against re-running**. For a NEW batch, change:
- **`id` prefix** — `model-` is used. Use a new prefix (e.g. `b2-`) and update the guard `startswith(...)`.
- **`POSITIONS`** — the sprinkled new-day numbers (mixed parity). `date(day) = 2026-06-07 + (day-1)`.
- **`FREEZE`** — keep ≥ today's day so posted/imminent days are untouched.
- **`REELS`** — the `(title, hook, caption)` list; `HASHTAGS`/`CTA` as needed.
- **media paths** in `model_post()` — point `video`/`img_ready`/`image` at the new batch files.

---

## §4 Why the calendar survives inserts (the load-bearing design)

- **Poster (`post_to_instagram.py`):** a post is a reel when `reel:true` (NOT day parity); media resolves by explicit `video` / `img_ready` first, then the day-keyed `d{day}.mp4` / `ig_ready/d{day}.jpg` fallback.
- **Insert = pin then renumber:** every future post is pinned to its CURRENT asset by explicit field *before* days change, so renumbering never re-points a post at someone else's day-keyed file. **No renaming the 248 day-keyed assets.**
- **Queue (`instagram/index.html`)** mirrors the same resolution so previews are accurate.
- Reels can now post on **any** day.

---

## §5 File map

| File | Role |
|---|---|
| `make_reels_ai.py` | `token()`, `run(model,input,tok)`, `postprocess()` — Replicate plumbing |
| `make_model_reels.py` | the reel prompts + Veo generate + music mix (persists raws) |
| `add_hook.py` | the house overlay (kicker + serif headline) — the consistency guarantee |
| `insert_model_reels.py` | reflow-safe calendar insert (adapt per §3) |
| `post_to_instagram.py` | the daily auto-poster (reel-flag + explicit media) |
| `instagram/posts.json` | the calendar; `instagram/index.html` | the /instagram queue UI |
