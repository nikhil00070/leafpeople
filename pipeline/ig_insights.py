#!/usr/bin/env python3
"""Pull Instagram Graph API insights for the Leaf People account and print a report.

Read-only analytics for our OWN IG Business account (no Meta app review needed). Lists
recent media, pulls per-post + account insights, and prints a breakdown:
  - account: followers, post count, reach (last ~30d)
  - per post: reach, likes, comments, saves, shares, engagement rate; reels also get
    plays/views + average watch time
  - REELS vs STATIC summary (does the reel-reach thesis hold, in numbers?)
  - top movers by reach and by engagement rate
  - best-effort labels each post with our posts.json day/title + a 🪝 if it carried a hook

Run via .github/workflows/ig-insights.yml (uses the IG_TOKEN/IG_USER_ID secrets), or locally:
    IG_TOKEN=... IG_USER_ID=... python pipeline/ig_insights.py
    IG_LIMIT=50 ...   # how many recent media to scan (default 40)
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
UA = "leafpeople-insights/1.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = None


def graph(path, params):
    p = dict(params); p["access_token"] = TOKEN
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(p)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def _metric_group(mid, metrics):
    """Fetch a group of metrics; if the batch errors (a deprecated metric like 'plays'), retry
    EACH metric on its own so one bad metric can't take down the good ones. The old code dropped
    by substring-matching Meta's error text, which wrongly ate 'reach' (it appears in the error's
    list of VALID metrics) — that's why reach read 0 everywhere."""
    try:
        data = graph(f"{mid}/insights", {"metric": ",".join(metrics)})
        return {d["name"]: d["values"][0]["value"] for d in data.get("data", [])}
    except RuntimeError:
        out = {}
        for mt in metrics:
            try:
                data = graph(f"{mid}/insights", {"metric": mt})
                for d in data.get("data", []):
                    out[d["name"]] = d["values"][0]["value"]
            except RuntimeError:
                pass
        return out


def media_insights(m):
    """{metric: value} for one media. Reach + core metrics first (all valid → one call); reel
    watch-time/views in a second group so a deprecated reel metric never zeroes reach."""
    mid, ptype = m["id"], m.get("media_product_type", "")
    out = _metric_group(mid, ["reach", "saved", "shares", "total_interactions"])
    if ptype == "REELS":
        out.update(_metric_group(mid, ["ig_reels_avg_watch_time", "ig_reels_video_view_total_time", "views"]))
    return out


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()[:60]


def posts_index():
    """normalized first caption line -> {day,title,reel,hook}. Matches a real IG media to its
    authored post by CAPTION (robust) — NOT by guessing the date from a 1/day schedule, which
    broke when 3 posts went out on day 1 then 1/day."""
    out = {}
    try:
        posts = json.load(open(os.path.join(ROOT, "instagram", "posts.json")))
        for p in posts:
            key = _norm((p.get("caption") or "").split("\n")[0])
            if key:
                out[key] = {"day": p.get("day"), "title": p.get("title", ""),
                            "reel": bool(p.get("reel")), "hook": p.get("hook")}
    except Exception:
        pass
    return out


def rate(m):
    r = m.get("reach") or 0
    return (m.get("total_interactions", 0) / r) if r else 0.0


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else (f"{n:.1f}" if isinstance(n, float) else str(n))


def main():
    global TOKEN
    TOKEN = os.environ.get("IG_TOKEN")
    uid = os.environ.get("IG_USER_ID")
    if not TOKEN or not uid:
        sys.exit("IG_TOKEN / IG_USER_ID not set")
    limit = int(os.environ.get("IG_LIMIT", "40"))
    pidx = posts_index()

    acct = graph(uid, {"fields": "username,followers_count,media_count"})
    print("=" * 72)
    print(f"LEAF PEOPLE · INSTAGRAM  —  @{acct.get('username','?')}")
    print(f"  followers: {fmt(acct.get('followers_count',0))}   posts: {fmt(acct.get('media_count',0))}")
    try:
        since = (dt.date.today() - dt.timedelta(days=30)).isoformat()
        until = dt.date.today().isoformat()
        ar = graph(f"{uid}/insights", {"metric": "reach", "period": "day",
                                       "metric_type": "total_value", "since": since, "until": until})
        tv = ar["data"][0].get("total_value", {}).get("value")
        if tv is not None:
            print(f"  reach (last 30d): {fmt(tv)}")
    except Exception:
        pass

    fields = "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count"
    media = graph(f"{uid}/media", {"fields": fields, "limit": limit}).get("data", [])
    rows = []
    for m in media:
        ins = media_insights(m)
        date = (m.get("timestamp", "")[:10])
        meta = pidx.get(_norm((m.get("caption") or "").split("\n")[0]), {})
        rows.append({
            "date": date,
            "type": "REEL" if m.get("media_product_type") == "REELS" else m.get("media_type", "?"),
            "reach": ins.get("reach", 0),
            "likes": m.get("like_count", ins.get("likes", 0)),
            "comments": m.get("comments_count", ins.get("comments", 0)),
            "saved": ins.get("saved", 0),
            "shares": ins.get("shares", 0),
            "total_interactions": ins.get("total_interactions", 0),
            "watch_ms": ins.get("ig_reels_avg_watch_time", 0),
            "plays": ins.get("views", ins.get("plays", 0)),
            "label": (f"d{meta['day']} {meta['title']}" if meta else (m.get("caption", "")[:42]).replace("\n", " ")),
            "hook": meta.get("hook") if meta else None,
            "is_reel": m.get("media_product_type") == "REELS",
        })

    print("=" * 72)
    print(f"RECENT POSTS ({len(rows)})   reach · eng% · ♥likes · 💬cmts · 🔖saves · ↗shares   [reels: ▶plays · ⏱avg watch]")
    print("-" * 72)
    for r in rows:
        tag = "▶ REEL " if r["is_reel"] else "🖼 IMG  "
        hook = " 🪝" if r["hook"] else ""
        line = (f"{r['date']}  {tag} reach {fmt(r['reach']):>6} · {rate(r)*100:4.1f}% · "
                f"♥{fmt(r['likes'])} 💬{fmt(r['comments'])} 🔖{fmt(r['saved'])} ↗{fmt(r['shares'])}")
        if r["is_reel"]:
            line += f"  ▶{fmt(r['plays'])} ⏱{r['watch_ms']/1000:.1f}s"
        print(line + f"   {r['label']}{hook}")

    reels = [r for r in rows if r["is_reel"]]
    imgs = [r for r in rows if not r["is_reel"]]

    def avg(xs, k):
        xs = [x[k] for x in xs if x.get(k) is not None]
        return sum(xs) / len(xs) if xs else 0

    # Emit a JSON the /dashboard renders (committed by the ig-insights workflow).
    result = {
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "account": {"username": acct.get("username"), "followers": acct.get("followers_count"),
                    "posts": acct.get("media_count")},
        "summary": {
            "reels": {"count": len(reels), "avg_reach": round(avg(reels, "reach")),
                      "avg_eng_pct": round(sum(rate(r) for r in reels) / len(reels) * 100, 1) if reels else 0,
                      "avg_watch_s": round(avg(reels, "watch_ms") / 1000, 1), "avg_plays": round(avg(reels, "plays"))},
            "images": {"count": len(imgs), "avg_reach": round(avg(imgs, "reach")),
                       "avg_eng_pct": round(sum(rate(r) for r in imgs) / len(imgs) * 100, 1) if imgs else 0},
        },
        "posts": [{**r, "eng_pct": round(rate(r) * 100, 1)} for r in rows],
    }
    try:
        json.dump(result, open(os.path.join(ROOT, "instagram", "insights.json"), "w"), indent=2)
        print("[insights] wrote instagram/insights.json")
    except Exception as e:
        print(f"[insights] could not write insights.json: {e}")

    print("=" * 72)
    print("REELS vs STATIC")
    print(f"  reels  ({len(reels):>2}): avg reach {avg(reels,'reach'):>7.0f} · avg eng "
          f"{(sum(rate(r) for r in reels)/len(reels)*100 if reels else 0):4.1f}% · avg watch "
          f"{(avg(reels,'watch_ms')/1000):.1f}s · avg plays {avg(reels,'plays'):.0f}")
    print(f"  images ({len(imgs):>2}): avg reach {avg(imgs,'reach'):>7.0f} · avg eng "
          f"{(sum(rate(r) for r in imgs)/len(imgs)*100 if imgs else 0):4.1f}%")
    if reels and imgs and avg(imgs, 'reach'):
        print(f"  → reels reach {avg(reels,'reach')/max(avg(imgs,'reach'),1):.1f}× the static posts")

    print("-" * 72)
    print("TOP 5 BY REACH")
    for r in sorted(rows, key=lambda x: x["reach"], reverse=True)[:5]:
        print(f"  {fmt(r['reach']):>6}  {r['date']}  {'▶' if r['is_reel'] else '🖼'} {r['label']}{' 🪝' if r['hook'] else ''}")
    print("TOP 5 BY ENGAGEMENT RATE")
    for r in sorted(rows, key=rate, reverse=True)[:5]:
        print(f"  {rate(r)*100:4.1f}%  {r['date']}  {'▶' if r['is_reel'] else '🖼'} {r['label']}{' 🪝' if r['hook'] else ''}")
    if reels:
        print("REELS BY AVG WATCH TIME (retention proxy — higher = less skipping)")
        for r in sorted(reels, key=lambda x: x["watch_ms"], reverse=True):
            print(f"  {r['watch_ms']/1000:4.1f}s  {r['date']}  {r['label']}{' 🪝' if r['hook'] else ''}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
