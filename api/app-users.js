// /api/app-users — the /dashboard "App" tab data (per-user rows + aggregate insights).
//
// PostHog is the source (GA4 can't do per-user). Two layers:
//  1) Per-user (25-row sample): each recent user's 30-day activity → Claude one-line
//     summary + a per-user "Take Action" item.
//  2) Aggregate insights (ALL users — the scale path): funnel, retention, paywall-by-gate,
//     purchase failures, identify health, top searches/plants/screens → Claude turns them
//     into a RANKED, typed action list (BUILD/BUG/CONTENT/PRICING/MARKETING/DATA), so
//     customer behavior surfaces the next app-build changes to make.
// Merged into ONE endpoint (Vercel 12-function cap). Read-only PostHog personal key +
// Anthropic key, both server-side (Vercel env). Returns { connected:false } when unconfigured.
//
// Env: POSTHOG_PERSONAL_API_KEY, POSTHOG_PROJECT_ID, POSTHOG_HOST, ANTHROPIC_API_KEY

let cache = null, cacheAt = 0;
const CACHE_MS = 60 * 60 * 1000;   // 1h — Claude calls cost; data lags anyway
const MAX_USERS = 25;

async function hog(host, pid, key, query) {
  const r = await fetch(`${host}/api/projects/${pid}/query/`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ query: { kind: "HogQLQuery", query } }),
  });
  if (!r.ok) throw new Error(`hogql ${r.status}: ${(await r.text()).slice(0, 200)}`);
  const j = await r.json();
  return j.results || [];
}

// Aggregate insight queries across ALL users (not the 25-user sample) — the scale path.
// Every query is 30d + internal-excluded via the shared WHERE clause `W`. Defensive: any
// single query that fails resolves to [] so one bad query never sinks the whole panel.
async function aggregateInsights(host, pid, key, W) {
  const q = (sql) => hog(host, pid, key, sql).catch(() => []);
  const [funnel, retention, paywall, failures, identify, searches, plants, screens, shops, contentGaps] = await Promise.all([
    // Overall reach funnel — who does what, of everyone active.
    q(`SELECT count(DISTINCT person_id) AS users,
         count(DISTINCT if(event='identify_started', person_id, NULL)) AS identifiers,
         count(DISTINCT if(event='collection_add', person_id, NULL)) AS collectors,
         count(DISTINCT if(event='paywall_shown', person_id, NULL)) AS paywalled,
         count(DISTINCT if(event='purchase_completed', person_id, NULL)) AS buyers,
         count(DISTINCT if(event='outbound_shop_tap', person_id, NULL)) AS shoppers
       FROM events WHERE ${W}`),
    // Retention: returning (2+ distinct days) vs one-and-done.
    q(`SELECT countIf(d >= 2) AS returning, countIf(d = 1) AS one_time FROM
         (SELECT person_id, count(DISTINCT toDate(timestamp)) AS d FROM events WHERE ${W} GROUP BY person_id)`),
    // Paywall leak by gate: shown vs sub-taps vs purchases per source.
    q(`SELECT properties.source AS source,
         countIf(event='paywall_shown') AS shown,
         countIf(event='subscribe_tapped') AS sub_taps,
         countIf(event='purchase_completed') AS purchases,
         count(DISTINCT if(event='paywall_shown', person_id, NULL)) AS users_shown
       FROM events WHERE ${W} AND event IN ('paywall_shown','subscribe_tapped','purchase_completed')
         AND coalesce(toString(properties.source),'') != ''
       GROUP BY source ORDER BY shown DESC LIMIT 12`),
    // Purchase failures by reason (cancelled = user choice, excluded) → likely BUGs.
    q(`SELECT properties.reason AS reason, count() AS c, count(DISTINCT person_id) AS users
       FROM events WHERE ${W} AND event='purchase_failed' AND coalesce(toString(properties.reason),'') NOT IN ('','cancelled')
       GROUP BY reason ORDER BY c DESC LIMIT 8`),
    // Identify feature health: start → matched vs not-in-library vs declined vs error.
    // (completed = legacy value from builds before the richer outcomes shipped.)
    q(`SELECT countIf(event='identify_started') AS started,
         countIf(event='identify_result' AND properties.outcome='matched') AS matched,
         countIf(event='identify_result' AND properties.outcome='not_in_library') AS not_in_library,
         countIf(event='identify_result' AND properties.outcome='declined') AS declined,
         countIf(event='identify_result' AND properties.outcome='completed') AS completed_legacy,
         countIf(event='identify_result' AND properties.outcome='error') AS errored
       FROM events WHERE ${W} AND event IN ('identify_started','identify_result')`),
    // Search demand — what people look for (content signal).
    q(`SELECT lower(trim(properties.q)) AS q, count() AS c, count(DISTINCT person_id) AS users
       FROM events WHERE ${W} AND event='library_searched' AND trim(coalesce(toString(properties.q),'')) != ''
       GROUP BY q ORDER BY c DESC LIMIT 20`),
    // Most-viewed plants (interest / content-gap signal).
    q(`SELECT properties.plant AS plant, properties.genus AS genus, count() AS c, count(DISTINCT person_id) AS users
       FROM events WHERE ${W} AND event='plant_viewed' AND coalesce(toString(properties.plant),'') != ''
       GROUP BY plant, genus ORDER BY c DESC LIMIT 20`),
    // Screen attention (dead features surface as near-zero rows).
    q(`SELECT properties.$screen_name AS screen, count() AS c, count(DISTINCT person_id) AS users
       FROM events WHERE ${W} AND event='$screen' AND coalesce(toString(properties.$screen_name),'') != ''
       GROUP BY screen ORDER BY c DESC LIMIT 20`),
    // Outbound shop taps (marketplace intent).
    q(`SELECT properties.name AS seller, count() AS c, count(DISTINCT person_id) AS users
       FROM events WHERE ${W} AND event='outbound_shop_tap' AND coalesce(toString(properties.name),'') != ''
       GROUP BY seller ORDER BY c DESC LIMIT 10`),
    // CONTENT-GAP GOLD: plants people photographed that we identified but DON'T carry
    // (not_in_library) — each is a care guide / library entry worth adding, ranked by demand.
    q(`SELECT lower(concat(coalesce(toString(properties.genus),''), ' ', coalesce(toString(properties.species),''))) AS taxon,
         count() AS c, count(DISTINCT person_id) AS users
       FROM events WHERE ${W} AND event='identify_result' AND properties.outcome='not_in_library'
       GROUP BY taxon ORDER BY c DESC LIMIT 15`),
  ]);
  const f = funnel[0] || [], ret = retention[0] || [], idf = identify[0] || [];
  return {
    funnel: { users: +f[0]||0, identifiers: +f[1]||0, collectors: +f[2]||0, paywalled: +f[3]||0, buyers: +f[4]||0, shoppers: +f[5]||0 },
    retention: { returning: +ret[0]||0, one_time: +ret[1]||0 },
    identify: { started: +idf[0]||0, matched: +idf[1]||0, not_in_library: +idf[2]||0, declined: +idf[3]||0, completed_legacy: +idf[4]||0, errored: +idf[5]||0 },
    content_gaps: contentGaps.map((r) => ({ taxon: (r[0]||"").trim(), count: +r[1]||0, users: +r[2]||0 })).filter((x) => x.taxon),
    paywall_by_source: paywall.map((r) => ({ source: r[0], shown: +r[1]||0, sub_taps: +r[2]||0, purchases: +r[3]||0, users_shown: +r[4]||0 })),
    purchase_failures: failures.map((r) => ({ reason: r[0], count: +r[1]||0, users: +r[2]||0 })),
    top_searches: searches.map((r) => ({ q: r[0], count: +r[1]||0, users: +r[2]||0 })),
    top_plants: plants.map((r) => ({ plant: r[0], genus: r[1], count: +r[2]||0, users: +r[3]||0 })),
    screens: screens.map((r) => ({ screen: r[0], count: +r[1]||0, users: +r[2]||0 })),
    shop_taps: shops.map((r) => ({ seller: r[0], count: +r[1]||0, users: +r[2]||0 })),
  };
}

// Turn the aggregates into a RANKED, typed action list — the "what should we do next" engine.
// Explicitly asked to flag BUILD items (app changes) and BUGs (from purchase failures / high error rates).
async function claudeRecommendations(apiKey, agg) {
  const prompt = `You are the product lead for Leaf People, a rare-plant iOS app (identify, browse, per-plant care, marketplace; paywall at $0.99/mo gating the full experience). Below are 30-day usage aggregates from PostHog — REAL data, internal/admin sessions excluded.

Produce a RANKED list of the most important, concrete actions the team should take next, MOST IMPACTFUL FIRST. For each recommendation:
- "type": exactly one of BUILD (app code/feature/UX change to ship in the next build), CONTENT (add plant data / care guide / article), PRICING (paywall placement, price, plan), BUG (a likely defect to fix), MARKETING, DATA (instrumentation gap blocking a decision).
- "title": the action, imperative, <10 words.
- "evidence": the SPECIFIC numbers from the data that justify it (quote them).
- "detail": 1-2 sentences on exactly what to do.

Rules:
- Base EVERYTHING on the numbers. Quote them. Never invent a mechanic or a problem the data doesn't show.
- The team specifically wants BUILD updates called out — if user behavior implies an app change, tag it BUILD and be concrete about the change.
- purchase_failures with non-'cancelled' reasons are almost certainly BUGs — rank them near the top with the reason + count.
- A high identify error rate (errored vs started) is a BUILD/BUG signal.
- CRITICAL — you do NOT know what content already exists. top_plants are plants users VIEWED, and a view happens ON that plant's detail/care-guide screen — so every plant in top_plants ALREADY HAS a care guide. NEVER recommend "build/add a care guide" for a plant in top_plants, and NEVER claim a plant has "no content"/"zero content"/"missing care guide". A high view count means the EXISTING guide is popular (a CONTENT signal to EXPAND/improve it, or a MARKETING/interest signal), not that it's missing.
- The ONLY data-backed content-GAP signal is content_gaps (identify outcome 'not_in_library') — plants users photographed that we could NOT match to the library. Recommend adding those by name. If content_gaps is empty, do NOT invent content gaps from any other field.
- top_searches can suggest CONTENT/UX only if a term looks like it would return nothing; frame it as "verify search returns results for X", never as a confirmed gap.
- A paywall source with many shows but ~0 purchases is a PRICING/BUILD signal (gate placed wrong or wall too hard).
- If the whole dataset is thin (few users/events), say so via data_confidence and keep the list short and honest — do NOT pad it.

Return ONLY valid JSON, no prose: {"headline":"<one line on the single biggest takeaway>","data_confidence":"low|medium|high","recommendations":[{"type":"...","title":"...","evidence":"...","detail":"..."}]}

Aggregates JSON:
${JSON.stringify(agg)}`;
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": apiKey, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({ model: "claude-haiku-4-5-20251001", max_tokens: 2500, messages: [{ role: "user", content: prompt }] }),
  });
  if (!r.ok) throw new Error(`anthropic ${r.status}: ${(await r.text()).slice(0, 160)}`);
  const j = await r.json();
  let text = (j.content || []).map((c) => c.text || "").join("");
  text = text.replace(/^```json\s*/i, "").replace(/```\s*$/i, "").trim();
  return JSON.parse(text);
}

async function claudeSummaries(apiKey, users) {
  const compact = users.map((u) => ({
    id: u.pid.slice(0, 8),
    membership: u.membership || "free",
    events: u.events, sessions: u.sessions,
    paywalls: u.paywall_shown, subscribe_taps: u.subscribe_tapped, purchases: u.purchases,
    top_taps: u.top_taps, top_screens: u.top_screens,
    plants_viewed: u.top_plants.map((p) => p.plant), searches: u.searches,
    days_active: u.days_active,
  }));
  const prompt = `You are analyzing users of a rare-plant iOS app (identify, browse, care, marketplace, paywall at $0.99/mo).
For EACH user below:
1. "summary" — a punchy one-line behavioral read (max ~18 words), naming the SPECIFIC plants they viewed and terms they searched when notable, where they lingered, and (if they hit a paywall) why they likely didn't subscribe.
2. "action" — ONE concrete, product-focused action item WE (the team) could take to better serve THIS user / users like them, based on what the data shows (max ~16 words). Be specific and doable — e.g. "Add a care guide for Philodendron melanochrysum — 3 views, none exists", "Paywall hit on identify with high intent; test a free first-ID". If the user's behavior is healthy and reveals nothing to act on, return exactly "None". Do NOT invent problems just to fill it — "None" is a valid, common answer.
Also write a 2-sentence overall TREND summary across all users, and a top-level "actions" array of the 1-3 highest-leverage action items across the WHOLE cohort (patterns seen in multiple users). If nothing stands out, return an empty array.
Return ONLY valid JSON, no prose: {"trend":"...","actions":["..."],"users":[{"id":"<id>","summary":"...","action":"..."}]}
Users JSON:
${JSON.stringify(compact)}`;
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": apiKey, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({ model: "claude-haiku-4-5-20251001", max_tokens: 2000, messages: [{ role: "user", content: prompt }] }),
  });
  if (!r.ok) throw new Error(`anthropic ${r.status}: ${(await r.text()).slice(0, 160)}`);
  const j = await r.json();
  let text = (j.content || []).map((c) => c.text || "").join("");
  text = text.replace(/^```json\s*/i, "").replace(/```\s*$/i, "").trim();
  return JSON.parse(text);
}

export default async function handler(req, res) {
  const host = (process.env.POSTHOG_HOST || "https://us.i.posthog.com").replace(/\/$/, "");
  const pid = process.env.POSTHOG_PROJECT_ID, key = process.env.POSTHOG_PERSONAL_API_KEY;
  const anthropic = process.env.ANTHROPIC_API_KEY;
  if (!pid || !key) return res.status(200).json({ connected: false });

  const fresh = !!(req.query && req.query.fresh);
  if (cache && !fresh && Date.now() - cacheAt < CACHE_MS) { res.setHeader("cache-control", "no-store"); return res.status(200).json(cache); }

  // 30-day window, excluding the admin's own (internal-tagged) sessions.
  const W = "timestamp > now() - INTERVAL 30 DAY AND coalesce(toString(properties.internal), '') != 'true'";
  try {
    // Per-user aggregate (the table rows).
    const agg = await hog(host, pid, key, `
      SELECT toString(person_id) AS pid, argMax(properties.membership, timestamp) AS membership,
             count() AS events, count(DISTINCT properties.$session_id) AS sessions,
             count(DISTINCT toDate(timestamp)) AS days_active,
             min(timestamp) AS first_seen, max(timestamp) AS last_seen,
             countIf(event='paywall_shown') AS paywall_shown,
             countIf(event='subscribe_tapped') AS subscribe_tapped,
             countIf(event='purchase_completed') AS purchases
      FROM events WHERE ${W}
      GROUP BY pid ORDER BY last_seen DESC LIMIT ${MAX_USERS}`);

    const users = agg.map((r) => ({
      pid: r[0], membership: r[1], events: Number(r[2]) || 0, sessions: Number(r[3]) || 0,
      days_active: Number(r[4]) || 0, first_seen: r[5], last_seen: r[6],
      paywall_shown: Number(r[7]) || 0, subscribe_tapped: Number(r[8]) || 0, purchases: Number(r[9]) || 0,
      top_taps: [], top_screens: [], top_plants: [], searches: [], summary: "", action: "",
    }));
    const byId = Object.fromEntries(users.map((u) => [u.pid, u]));

    if (users.length) {
      const ids = "'" + users.map((u) => u.pid).join("','") + "'";
      // Per-user event (tap) breakdown.
      const taps = await hog(host, pid, key, `
        SELECT toString(person_id) AS pid, event, count() AS c FROM events
        WHERE ${W} AND toString(person_id) IN (${ids}) AND event != '$screen'
        GROUP BY pid, event ORDER BY c DESC`).catch(() => []);
      for (const r of taps) { const u = byId[r[0]]; if (u && u.top_taps.length < 6) u.top_taps.push({ event: r[1], n: Number(r[2]) || 0 }); }
      // Per-user screens (where they spent attention).
      const scr = await hog(host, pid, key, `
        SELECT toString(person_id) AS pid, properties.$screen_name AS screen, count() AS c FROM events
        WHERE ${W} AND event='$screen' AND toString(person_id) IN (${ids})
        GROUP BY pid, screen ORDER BY c DESC`).catch(() => []);
      for (const r of scr) { const u = byId[r[0]]; if (u && r[1] && u.top_screens.length < 5) u.top_screens.push({ screen: r[1], n: Number(r[2]) || 0 }); }
      // The actionable specifics — WHICH plants they viewed + WHAT they searched.
      const plants = await hog(host, pid, key, `
        SELECT toString(person_id) AS pid, properties.plant AS v, count() AS c FROM events
        WHERE ${W} AND event='plant_viewed' AND toString(person_id) IN (${ids})
        GROUP BY pid, v ORDER BY c DESC`).catch(() => []);
      for (const r of plants) { const u = byId[r[0]]; if (u && r[1] && u.top_plants.length < 6) u.top_plants.push({ plant: r[1], n: Number(r[2]) || 0 }); }
      const searches = await hog(host, pid, key, `
        SELECT toString(person_id) AS pid, properties.q AS v, count() AS c FROM events
        WHERE ${W} AND event='library_searched' AND toString(person_id) IN (${ids})
        GROUP BY pid, v ORDER BY c DESC`).catch(() => []);
      for (const r of searches) { const u = byId[r[0]]; if (u && r[1] && u.searches.length < 6) u.searches.push(r[1]); }
    }

    // Aggregate insights run across EVERYONE (not the 25-user sample) — the scale path.
    // NOTE: distinct name from the per-user `agg` above — same scope, must not collide.
    const insights = await aggregateInsights(host, pid, key, W).catch(() => null);

    let trend = "", actions = [], recs = null;
    if (anthropic && users.length) {
      try {
        // Per-user summaries and cohort recommendations in parallel — two cheap Haiku calls, 1h-cached.
        const [out, recOut] = await Promise.all([
          claudeSummaries(anthropic, users),
          insights ? claudeRecommendations(anthropic, insights).catch((e) => ({ _error: String(e.message).slice(0, 100) })) : Promise.resolve(null),
        ]);
        trend = out.trend || "";
        actions = Array.isArray(out.actions) ? out.actions.filter(Boolean).slice(0, 3) : [];
        const byShortId = Object.fromEntries((out.users || []).map((u) => [u.id, u]));
        for (const u of users) {
          const o = byShortId[u.pid.slice(0, 8)] || {};
          u.summary = o.summary || "";
          u.action = o.action || "None";   // default: nothing to do
        }
        recs = recOut;
      } catch (e) { trend = "(summary unavailable: " + String(e.message).slice(0, 80) + ")"; }
    }

    cache = { connected: true, updated: new Date().toISOString(), count: users.length,
              trend, actions, users, insights, recommendations: recs };
    cacheAt = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(cache);
  } catch (e) {
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 200) });
  }
}
