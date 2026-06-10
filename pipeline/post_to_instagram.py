#!/usr/bin/env python3
"""Publish the day's scheduled Instagram post via the Instagram Graph API.

Finds the calendar post due today (relative to start_date in instagram/publish_config.json),
assembles the caption (body + CTA + hashtags + photo credit for stock images), and publishes
the image to your Instagram Business/Creator account using the Graph API content-publishing
flow (create media container -> publish). Marks the post 'posted' in instagram/posts.json.

SAFE BY DEFAULT — it only publishes when ALL of these are true:
  * instagram/publish_config.json has {"enabled": true} and a past/today start_date
  * IG_TOKEN and IG_USER_ID env vars are present (GitHub secrets)
  * IG_DRY_RUN != "1"
Otherwise it just logs exactly what it WOULD post and publishes nothing.

Env:
  IG_TOKEN     long-lived / system-user access token (GitHub secret)
  IG_USER_ID   Instagram Business account id (the IG user id, not the FB Page id)
  IG_DRY_RUN   "1" forces a dry run even when enabled (for safe manual test runs)
  LP_DATE      override "today" (YYYY-MM-DD) for testing
  SITE_BASE    public base for image URLs (default https://leafpeople.app)

NOTE: the posted image is `post["image"]` from posts.json. Your /instagram picker choices
currently live in the browser (localStorage); persist them to posts.json (the planned
"Save" step) so auto-posts use your curated picks rather than the defaults.
"""

import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "instagram" / "posts.json"
LIBRARY = ROOT / "instagram" / "library.json"
CONFIG = ROOT / "instagram" / "publish_config.json"
GRAPH = "https://graph.facebook.com/v21.0"   # bump as Meta deprecates versions


def log(m):
    print(f"[ig-post] {m}")


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


# Hashtag strategy (mirror of the /instagram web picker): keep ONLY the brand tag in
# the caption (clean caption) and push every other hashtag into the first comment.
# Caption vs first-comment placement is cosmetic to the algorithm — both are indexed —
# but the clean caption reads better. Tags are value-ranked so the comment leads with
# the species-specific tags, then the proven broad rare-aroid tags, then filler.
BRAND_PIN = "#leafpeopleapp"
TAG_RANK = ["#velvetanthurium", "#darkleafanthurium", "#anthurium", "#anthuriumlove",
            "#rarearoids", "#aroidsofinstagram", "#rareplants", "#aroids", "#houseplant"]


def tag_rank(t):
    k = t.lower()
    if k == BRAND_PIN:
        return -1
    try:
        return TAG_RANK.index(k)
    except ValueError:
        return 999


def split_tags(tags):
    """Return (caption_tags, comment_tags): brand pin in the caption, the rest (ranked) in the first comment."""
    seen, uniq = set(), []
    for t in tags or []:
        k = (t or "").lower()
        if t and k not in seen:
            seen.add(k)
            uniq.append(t)
    ordered = sorted(range(len(uniq)), key=lambda i: (tag_rank(uniq[i]), i))
    ordered = [uniq[i] for i in ordered]
    return ordered[:1], ordered[1:]


def assemble(post, credit_by_src):
    """Build (caption, first_comment) for a post."""
    parts = [post.get("caption", "").strip()]
    if post.get("cta"):
        parts.append(post["cta"].strip())
    cap_tags, com_tags = split_tags(post.get("hashtags"))
    if cap_tags:
        parts.append(" ".join(cap_tags))
    credit = credit_by_src.get(post.get("image", ""))
    if credit:  # licensing: stock/iNat images must carry attribution when posted
        parts.append("\U0001F4F7 " + credit)
    caption = "\n\n".join(p for p in parts if p)
    first_comment = " ".join(com_tags)
    return caption, first_comment


def graph_post(path, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def publish(ig_user_id, token, image_url, caption):
    container = graph_post(f"{ig_user_id}/media",
                           {"image_url": image_url, "caption": caption, "access_token": token})
    cid = container["id"]
    log(f"created media container {cid}")
    last = None
    for _ in range(12):  # container may need a moment to finish processing
        try:
            out = graph_post(f"{ig_user_id}/media_publish",
                             {"creation_id": cid, "access_token": token})
            if out.get("id"):
                return out["id"]
        except Exception as e:
            last = e
        time.sleep(5)
    raise RuntimeError(f"publish did not return a media id (last error: {last})")


def add_comment(media_id, token, message):
    """Post the overflow hashtags as the first comment on the freshly published media."""
    if not (message or "").strip():
        return None
    out = graph_post(f"{media_id}/comments", {"message": message, "access_token": token})
    return out.get("id")


def main():
    cfg = load(CONFIG, {})
    if not cfg.get("start_date"):
        log("no start_date set in instagram/publish_config.json — nothing scheduled yet.")
        return 0

    start = dt.date.fromisoformat(cfg["start_date"])
    today = dt.date.fromisoformat(os.environ.get("LP_DATE") or dt.date.today().isoformat())
    idx = (today - start).days
    if idx < 0:
        log(f"start_date {start} is {-idx} day(s) away — nothing to post yet.")
        return 0

    day = idx + 1
    posts = load(POSTS, [])
    post = next((p for p in posts if p.get("day") == day), None)
    if not post:
        log(f"day {day} is beyond the {len(posts)}-day calendar — nothing to post.")
        return 0
    if post.get("status") == "posted":
        log(f"day {day} ({post['id']}) already marked posted — skipping.")
        return 0
    if not post.get("image") or not post.get("caption"):
        log(f"day {day} ({post['id']}) has no image/caption — skipping.")
        return 0

    credit_by_src = {}
    for e in load(LIBRARY, []):
        if e.get("kind") == "stock" and e.get("credit"):
            credit_by_src[e["src"]] = e["credit"]

    base = os.environ.get("SITE_BASE", "https://leafpeople.app").rstrip("/")
    image_url = base + post["image"]
    caption, first_comment = assemble(post, credit_by_src)

    log(f"DUE: day {day} · {post.get('title', '')} · branch={post.get('branch')}")
    log(f"image: {image_url}")
    log("caption:\n" + caption + "\n")
    log("first comment (hashtags):\n" + (first_comment or "(none)") + "\n")

    token = os.environ.get("IG_TOKEN")
    uid = os.environ.get("IG_USER_ID")
    force_dry = os.environ.get("IG_DRY_RUN") == "1"
    live = bool(cfg.get("enabled")) and bool(token) and bool(uid) and not force_dry

    if not live:
        if force_dry:
            why = "IG_DRY_RUN=1"
        elif not cfg.get("enabled"):
            why = "publish_config.enabled is false"
        elif not (token and uid):
            why = "IG_TOKEN / IG_USER_ID not set"
        else:
            why = "unknown"
        log(f"DRY RUN ({why}) — would post the above; publishing nothing.")
        return 0

    media_id = publish(uid, token, image_url, caption)
    log(f"PUBLISHED media {media_id}")

    if first_comment:
        try:
            cmt = add_comment(media_id, token, first_comment)
            log(f"first comment posted ({cmt}): {first_comment}")
        except Exception as e:  # a missing comment must not undo a successful post
            log(f"WARNING: post published but first comment failed: {e}")

    post["status"] = "posted"
    post["posted_at"] = today.isoformat()
    post["ig_media_id"] = media_id
    POSTS.write_text(json.dumps(posts, indent=2) + "\n", encoding="utf-8")
    log(f"marked day {day} ({post['id']}) posted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
