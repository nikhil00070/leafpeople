# Instagram Auto-Posting Setup — Full Playbook

How we wired **automated daily Instagram posting** for Leaf People, start to finish, so it can be
repeated for **ForkFox** (or any app). Captures every step, every Meta screen + the exact choice to
make, the token dance, and the gotchas that tripped us up.

> **What this builds:** a GitHub Action (daily cron) that publishes one queued post per day to a
> **Business** Instagram account via the Meta Graph API — fully hands-off. Plus a manual planner page.
> No paid ads, no third-party tools.

> **Reusable vs. per-app:** Parts 0–4 (accounts + Meta app + tokens + secrets) must be done **once per
> app** (each app = its own IG account, its own token/secrets). Part 5 (the repo code) is mostly
> reusable — the poster script + workflow are generic; only the content queue + `SITE_BASE` change.

---

## Key facts learned (read first)

- **The IG account MUST be a Business (or Creator) account.** A *personal* IG account **cannot** use
  the publishing API at all.
- **You do NOT need Meta App Review or Business Verification** to post to *your own* account — as long
  as the app stays in **Development mode** and your account is an **Admin** on it. (App Review is only
  for posting on behalf of *other* people.)
- **Meta's new flow has no "Add Product" button** — everything goes through **"Use cases."**
- **Use the permanent Page access token, not the 60-day user token** (details in Part 3) — then there's
  no token-refresh chore.

---

## Part 0 — Create the two accounts (use a company email)

Use one company email for both, e.g. `hello@percentearth.co` (it was also our support email). IG and
Facebook are separate systems, so the same email is fine for both.

1. **Facebook account** — sign up at **facebook.com** in a desktop browser. This is a normal *personal*
   profile (Meta requires one to own a Page + dev app). Add a name, photo, and **phone number** (helps
   pass new-account checks).
2. **Instagram account** — sign up in the **Instagram phone app**. Pick the handle (e.g.
   `leafpeople.app` — periods are allowed). Add profile photo + bio + bio link.

⚠️ **New accounts get scrutinized.** Expect a possible phone/ID verification. Don't auto-post from a
day-old account — warm it up with manual posts first (see Part 7).

---

## Part 1 — Make IG a Business account + link a Facebook Page

The publishing API reaches the IG account *through* a Facebook Page, so this link is mandatory.

3. **IG app** → Settings → **Account type → Switch to professional → Business**.
4. **facebook.com** (logged in as the company FB account) → **Pages → Create new Page** (e.g. "Leaf
   People").
5. **IG app** → Settings → **Business → Connect or create** → connect the Page from step 4.

> The chain that makes everything work: **FB account → manages the Page → Page linked to the IG account
> → owns the Meta dev app.** Same FB account at every link.

---

## Part 2 — Meta Developer App (developers.facebook.com)

All in a desktop browser, logged in as the **company FB account**.

6. Register as a developer (verify phone/email) → **Create App**.
7. When asked for a **use case**, choose **"Create an app without a use case"** → app type **Business**
   → name it (e.g. "Leaf People Poster"). (The ads / Threads use cases are NOT what you want.)
8. **Business portfolio** prompt → **"I don't want to connect a business portfolio yet."** (Not needed
   for Development-mode own-account posting; you can add later.)
9. The app dashboard has **no "Add Product"** — only **"Use cases."** Click **Add use cases**.
10. Filter to **Content management** → select **"Manage messaging & content on Instagram"**
    (*"Publish posts, share stories, respond to comments…"*). Add it.
    - You'll get a banner about "extra steps before publishing" — that's the **go-Live** path; ignore
      it for own-account Dev-mode posting.
11. Open the use case → **"Customize."** It defaults to the **Instagram-login** setup. **⚠️ Switch to
    "API setup with Facebook login"** (there's a link saying *"If you want hashtags and insights,
    switch to the API setup with Facebook login"*).
    - **Why:** our poster script reaches IG via the **Page** (`graph.facebook.com`), which is the
      Facebook-login path. The Instagram-login path uses a different host/token shape our script isn't
      built for. The Facebook-login path also gives insights (for later auto-metrics).
12. Under **Add required permissions → "Manage content on Instagram"**, the needed permissions are:
    `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`, `pages_show_list`,
    `business_management`. On the **Permissions and features** page these should already show
    **"Ready for testing"** — that means they work in Development mode **without App Review**. ✅
    - **Use `instagram_content_publish`** (the publish one), NOT `instagram_business_content_publish`
      (that's the Instagram-login variant).
13. **SKIP:** "Send messages on Instagram", "Complete app review", "Configure webhooks", "Become a Tech
    Provider." None are needed for own-account posting.
14. Confirm under **App roles → Roles** that you're **Admin**, and the app stays in **Development mode**.
15. **App settings → Basic** → note your **App ID** and **App Secret** (click "Show") — needed for the
    long-lived token exchange.

---

## Part 3 — Get the credentials (this is the fiddly part)

### 3a. Generate a token (Graph API Explorer)
16. **Tools → Graph API Explorer** → top-right, select your app.
17. **Permissions** → add `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
    `pages_read_engagement`, `business_management`.
18. **Generate Access Token** → authorize. You'll hit grant screens:
    - **"Choose the Pages…"** → select your Page (e.g. Leafpeople.app)
    - **"Choose the Businesses…"** → select the business (or skip)
    - It may say **"Switch to [Your Name]"** — that's just your company FB profile's display name;
      switch/continue.
    - ⚠️ **Make sure the Page (and IG, if shown) are checked** — a token without Page access can't post.
19. Copy the token. This one is **short-lived (~1 hr)**.

### 3b. Exchange for a long-lived (~60-day) token
20. Paste this in the browser, filling in your values:
    ```
    https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN
    ```
    The returned `access_token` is your long-lived **user** token (`expires_in` ≈ 5,184,000 sec = 60d).

### 3c. Get the Page id + IG_USER_ID
21. Paste (using the long-lived token):
    ```
    https://graph.facebook.com/v21.0/me/accounts?access_token=LONG_TOKEN
    ```
    Find your Page entry → note its **`id`**. (Also note its **`access_token`** — used in 3d.)
22. Paste (swap in the Page id — keep `instagram_business_account` and `access_token=` exactly as-is):
    ```
    https://graph.facebook.com/v21.0/PAGE_ID?fields=instagram_business_account&access_token=LONG_TOKEN
    ```
    The `instagram_business_account.id` = your **`IG_USER_ID`**. *(This never changes regardless of
    which token you use.)*

### 3d. ⭐ Use the PERMANENT Page token (skip the 60-day refresh)
The user token from 3b expires in 60 days. But the **Page access token** — returned in the
`me/accounts` response (3c) when called with a long-lived user token — **does not expire on a timer.**

23. From the **`me/accounts`** response, copy the **`access_token`** on your Page's entry. **That is your
    `IG_TOKEN`** (permanent).
24. Verify: paste it into **developers.facebook.com/tools/debug/accesstoken** → it should say
    **"Expires: Never."** ✅
    - Caveat: a Page token can still break if you change the FB password, revoke the app, or Meta forces
      a reset — rare, one-time fixes, not a recurring chore.

**You now have the two values:** `IG_TOKEN` (permanent Page token) + `IG_USER_ID`.

---

## Part 4 — Add the GitHub secrets

25. Repo → **Settings → Secrets and variables → Actions → New repository secret**:
    - `IG_TOKEN` = the permanent Page token
    - `IG_USER_ID` = the `instagram_business_account.id`
    - Names must be **exact** (uppercase) — that's what the workflow reads.

---

## Prerequisite — Build the Instagram content queue (do this first / in parallel)

The plumbing (Parts 0–4) is useless without a **queue of posts** for the cron to publish. This is the
most app-specific part — it's the actual content, and it must exist before go-live.

**What the queue is:** `instagram/posts.json` — an ordered list, one entry per day. Each entry:
```
{ "id": "d01", "day": 1, "date": "2026-06-02", "phase": "welcome",
  "branch": "welcome-leafpeople", "title": "...", "image": "/images/source/inat/x.jpg",
  "caption": "...", "hashtags": ["#leafpeople", ...], "cta": "...", "status": "draft" }
```

**How Leaf People's queue was built (213 days, Jun 2 → Dec 31):**
- `pipeline/instagram_seed.py` generates it from: authored launch posts + a story-a-day wave (each post
  spotlights a published article, caption from the article's deck), using its own curated photo.
- `instagram/library.json` — the image pool, each image tagged with the branches it suits.
- `instagram/branches.json` — the strategy/branch map (funnel phases, the handle).
- Re-running the seed preserves existing days and appends any new ones (never disturbs a curated order).

**Images must live in the repo and be publicly reachable.** The poster builds the URL as
`SITE_BASE + post.image` (e.g. `https://leafpeople.app/images/source/inat/x.jpg`). The Graph API
**requires a public image URL** to publish — local/private paths won't work. Leaf People keeps them in
`/images/instagram/`, `/images/source/inat/`, `/images/source/stock/`.

**Curation → publish:** the `/instagram` planner lets you pick a per-post image. Those picks live in the
**browser (localStorage)** until you click **"Save image choices to repo,"** which writes them into
`posts.json` so the **auto-poster uses your picks, not the seeded defaults.** Always do this before
go-live. (Planner also tracks Queue vs. Past and has a one-tap "Save image + caption" for manual posts.)

**For ForkFox — the content work to do first:**
- [ ] Build a `posts.json` queue (captions, hashtags, schedule, image paths) — authored or generated
- [ ] Put **all** post images in the ForkFox repo at **public** paths; confirm each resolves at
      `https://<forkfox-domain>/<path>`
- [ ] (Optional) a `library.json` + the planner page for curating images
- [ ] Curate, then **Save image choices to repo** so the queue's images are final

> Without this queue, the cron runs fine but has **nothing to post** — it'll just log "nothing scheduled."

---

## Part 5 — The automation code (in the repo) — adapt per app

Leaf People's pieces (ForkFox needs its own equivalents):
- **`instagram/posts.json`** — the content queue (one entry per day: caption, image path, hashtags).
- **`instagram/publish_config.json`** — `{ "start_date": "YYYY-MM-DD", "enabled": true/false }`. Dormant
  until `enabled:true`.
- **`pipeline/post_to_instagram.py`** — computes the day-due post, builds the caption (+ photo credit),
  publishes via Graph API (create media container → publish), marks it posted. Reads `IG_TOKEN` /
  `IG_USER_ID` from env. **`dry_run=1` logs what it would post and publishes nothing.**
- **`.github/workflows/instagram-publish.yml`** — daily cron (`workflow_dispatch` for manual dry-runs).
  Dormant/dry until `publish_config` is enabled + secrets present.
- **`instagram/index.html`** — optional manual planner (calendar, image picker, Queue/Past tracking,
  one-tap "Save image + caption" for posting by hand).

> For ForkFox: reuse `post_to_instagram.py` + the workflow nearly as-is; point `SITE_BASE` at ForkFox's
> domain, build ForkFox's `posts.json` queue, and use ForkFox's own IG_TOKEN/IG_USER_ID secrets.

---

## Part 6 — Test with a dry-run (posts nothing)

26. Temporarily set `publish_config.json` → `"start_date"` to **today**, keep `"enabled": false`. Commit.
27. GitHub → **Actions → "Publish to Instagram (daily)" → Run workflow → dry_run = 1**.
28. Open the run log — you should see:
    ```
    DUE: day 1 · <title> · branch=...
    image: https://.../...jpg
    caption: ...
    DRY RUN — would post the above; publishing nothing.
    Nothing to commit.
    ```
    This confirms: workflow runs, secrets readable, post selected, caption built — **nothing posted.**
29. Set `start_date` back to your real launch date (or null) and keep `enabled:false` until go-live.

---

## Part 7 — Go live

30. **Warm up first** if the account is new — post manually for ~1–2 weeks before automating (new
    accounts firing daily API posts get flagged).
31. When ready: `publish_config.json` → set **`start_date`** = the day you want **day 1** to post +
    **`enabled: true`**. The daily cron then posts automatically.
32. Point the IG **bio link** at the live App Store listing.

---

## Gotchas / decisions log (what tripped us up)

- **No "Add Product" anymore** → use **Use cases** (create app "without a use case", then add the
  Instagram use case under **Content management**).
- **Instagram use case defaults to Instagram-login** → **switch to Facebook-login** (matches the
  Page-based script + gives insights).
- **Business portfolio**: skip it for Dev mode.
- **App Review / "Become a Tech Provider"**: NOT needed for own-account posting in Dev mode.
- **Permissions "Ready for testing"** = good to go in Development mode (no review).
- **Page token > user token**: the Page token from `me/accounts` is permanent ("Expires: Never"); use it
  as `IG_TOKEN` to avoid the 60-day refresh.
- **In the `me/accounts` URL**, you replace `PAGE_ID`; keep the field name `instagram_business_account`
  and the param `access_token=` exactly as written.
- **`IG_USER_ID` is constant** — it doesn't change when you swap tokens.
- **Manual planner picks are per-browser (localStorage)** — they only become shared/used by the
  auto-poster after clicking **"Save image choices to repo."**
- **"Network error" on save** = flaky connection; just retry on stable Wi-Fi (the endpoint is fine).
- **Don't post from a brand-new account immediately** — warm it up manually first.

---

## For ForkFox — checklist

- [ ] Create/confirm a **Business** IG account for ForkFox (+ profile, handle, bio link)
- [ ] Create a **Facebook Page** for ForkFox, link the IG account to it
- [ ] Meta dev app for ForkFox (or reuse the same FB account) — Dev mode, Facebook-login Instagram use
      case, the 5 content permissions
- [ ] Generate the **permanent Page token** + **IG_USER_ID** (Part 3)
- [ ] Add `IG_TOKEN` + `IG_USER_ID` as **GitHub secrets in the ForkFox repo**
- [ ] Drop in `post_to_instagram.py` + `instagram-publish.yml` (adapt `SITE_BASE` + paths) and build
      ForkFox's `posts.json` content queue
- [ ] Dry-run test (Part 6), then go live (Part 7)
