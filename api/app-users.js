// /api/app-users — per-user view for the /dashboard "Users" tab.
//
// PostHog is the source (GA4 can't do per-user). Pulls each recent user's 30-day
// activity via the HogQL Query API, then asks Claude for a one-line summary per user
// + an overall trend summary. Read-only PostHog personal key + Anthropic key, both
// server-side (Vercel env). Returns { connected:false } when unconfigured.
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
For EACH user below, write a punchy one-line behavioral summary (max ~18 words) — naming the SPECIFIC plants they viewed and terms they searched when notable, where they lingered, and (if they hit a paywall) why they likely didn't subscribe.
Also write a 2-sentence overall TREND summary across all users.
Return ONLY valid JSON, no prose: {"trend":"...","users":[{"id":"<id>","summary":"..."}]}
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

  const W = "timestamp > now() - INTERVAL 30 DAY";
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
      top_taps: [], top_screens: [], top_plants: [], searches: [], summary: "",
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

    let trend = "";
    if (anthropic && users.length) {
      try {
        const out = await claudeSummaries(anthropic, users);
        trend = out.trend || "";
        const sm = Object.fromEntries((out.users || []).map((u) => [u.id, u.summary]));
        for (const u of users) u.summary = sm[u.pid.slice(0, 8)] || "";
      } catch (e) { trend = "(summary unavailable: " + String(e.message).slice(0, 80) + ")"; }
    }

    cache = { connected: true, updated: new Date().toISOString(), count: users.length, trend, users };
    cacheAt = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(cache);
  } catch (e) {
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 200) });
  }
}
