// /api/app-analytics — in-app (iOS) behavior for the /dashboard "App Analytics" tab.
//
// Same GA4 Data API + service account as /api/ga4, but reads the APP side: screens,
// the paywall funnel, key actions, and free-vs-premium splits — the events the app
// logs via Track.swift (Firebase Analytics → GA4).
//
// Property: GA4_APP_PROPERTY_ID if set (the Firebase-linked app property), else falls
// back to GA4_PROPERTY_ID (works when the iOS app stream lives in the same property as
// the web stream). The funnel/screen events are app-only, so they isolate app data even
// in a combined property. Breakdowns by source/plan/membership need those registered as
// GA4 custom dimensions; until then those sections come back empty (handled gracefully).
//
// Returns { connected:false } (200) when GA4 isn't configured, so the dashboard degrades.

import crypto from "crypto";

let tok = null, tokExp = 0;
let cache = null, cacheAt = 0;
const CACHE_MS = 5 * 60 * 1000;

const b64url = (b) => Buffer.from(b).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const num = (v) => (v == null ? 0 : Number(v));

async function accessToken(sa) {
  const now = Math.floor(Date.now() / 1000);
  if (tok && tokExp > now + 60) return tok;
  const head = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claim = b64url(JSON.stringify({
    iss: sa.client_email,
    scope: "https://www.googleapis.com/auth/analytics.readonly",
    aud: "https://oauth2.googleapis.com/token",
    iat: now, exp: now + 3600,
  }));
  const sig = b64url(crypto.createSign("RSA-SHA256").update(`${head}.${claim}`).sign(sa.private_key));
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: `${head}.${claim}.${sig}` }),
  });
  const j = await r.json();
  if (!j.access_token) throw new Error("oauth: " + JSON.stringify(j).slice(0, 160));
  tok = j.access_token; tokExp = now + (j.expires_in || 3600);
  return tok;
}

async function report(pid, token, body) {
  const r = await fetch(`https://analyticsdata.googleapis.com/v1beta/properties/${pid}:runReport`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`runReport ${r.status}: ${(await r.text()).slice(0, 160)}`);
  return r.json();
}

// iOS-only filter so a combined web+app property still isolates the app.
const IOS = { filter: { fieldName: "platform", stringFilter: { value: "iOS" } } };
// The events Track.swift logs.
const FUNNEL = ["paywall_shown", "subscribe_tapped", "purchase_completed", "purchase_failed", "paywall_dismissed", "purchase_restored"];
const ACTIONS = ["identify_started", "identify_result", "plant_viewed", "story_opened", "listing_viewed", "collection_add", "custom_plant_added", "library_searched"];

export default async function handler(req, res) {
  const pid = process.env.GA4_APP_PROPERTY_ID || process.env.GA4_PROPERTY_ID;
  const saRaw = process.env.GA4_SA_JSON;
  if (!pid || !saRaw) return res.status(200).json({ connected: false });

  const skipCache = !!(req.query && req.query.fresh);
  if (!skipCache && cache && Date.now() - cacheAt < CACHE_MS) {
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(cache);
  }

  let sa;
  try { sa = JSON.parse(saRaw); } catch { return res.status(200).json({ connected: false, error: "GA4_SA_JSON is not valid JSON" }); }

  const win = [{ startDate: "30daysAgo", endDate: "today" }];
  const all = [{ startDate: "2020-01-01", endDate: "today" }];
  const evFilter = (names) => ({ filter: { fieldName: "eventName", inListFilter: { values: names } } });
  const andFilter = (...f) => ({ andGroup: { expressions: f } });

  try {
    const token = await accessToken(sa);

    // Optional breakdowns (need GA4 custom dimensions registered) — never fail the whole route.
    const tryReport = async (body) => { try { return await report(pid, token, body); } catch { return { rows: [] }; } };

    const [totalsR, allR, screensR, eventsR, bySourceR, byPlanR, membershipR] = await Promise.all([
      // iOS engagement totals (30d)
      report(pid, token, { dateRanges: win, dimensionFilter: IOS, metrics: [{ name: "activeUsers" }, { name: "newUsers" }, { name: "sessions" }, { name: "engagedSessions" }, { name: "userEngagementDuration" }, { name: "screenPageViews" }] }),
      // total app users since launch
      report(pid, token, { dateRanges: all, dimensionFilter: IOS, metrics: [{ name: "totalUsers" }] }),
      // top screens by views + users + avg engagement
      report(pid, token, { dateRanges: win, dimensionFilter: IOS, dimensions: [{ name: "unifiedScreenName" }], metrics: [{ name: "screenPageViews" }, { name: "activeUsers" }, { name: "userEngagementDuration" }], orderBys: [{ metric: { metricName: "screenPageViews" }, desc: true }], limit: 15 }),
      // counts for the funnel + key actions
      report(pid, token, { dateRanges: win, dimensions: [{ name: "eventName" }], metrics: [{ name: "eventCount" }, { name: "totalUsers" }], dimensionFilter: evFilter([...FUNNEL, ...ACTIONS]), limit: 50 }),
      // paywall_shown by source gate (needs custom dim "source")
      tryReport({ dateRanges: win, dimensions: [{ name: "customEvent:source" }], metrics: [{ name: "eventCount" }, { name: "totalUsers" }], dimensionFilter: andFilter(evFilter(["paywall_shown"])), orderBys: [{ metric: { metricName: "eventCount" }, desc: true }], limit: 20 }),
      // subscribe_tapped by plan (needs custom dim "plan")
      tryReport({ dateRanges: win, dimensions: [{ name: "customEvent:plan" }], metrics: [{ name: "eventCount" }], dimensionFilter: andFilter(evFilter(["subscribe_tapped"])), limit: 10 }),
      // active users split by membership (needs user-scoped custom dim "membership")
      tryReport({ dateRanges: win, dimensions: [{ name: "customUser:membership" }], metrics: [{ name: "activeUsers" }, { name: "userEngagementDuration" }], limit: 10 }),
    ]);

    const t = totalsR.rows?.[0]?.metricValues || [];
    const activeUsers = num(t[0]?.value), newUsers = num(t[1]?.value), sessions = num(t[2]?.value),
      engagedSessions = num(t[3]?.value), engDur = num(t[4]?.value), screenViews = num(t[5]?.value);
    const r1 = (n) => Math.round(n * 10) / 10;

    // event counts → map
    const ev = {};
    (eventsR.rows || []).forEach((r) => { ev[r.dimensionValues[0].value] = { count: num(r.metricValues[0].value), users: num(r.metricValues[1].value) }; });
    const evc = (n) => ev[n]?.count || 0;
    const evu = (n) => ev[n]?.users || 0;

    const shown = evc("paywall_shown"), tapped = evc("subscribe_tapped"), bought = evc("purchase_completed");
    const out = {
      connected: true,
      updated: new Date().toISOString(),
      property: pid,
      window: 30,
      totals: {
        active_users: activeUsers,
        total_users: num(allR.rows?.[0]?.metricValues?.[0]?.value),
        new_users: newUsers,
        sessions,
        screen_views: screenViews,
        avg_sec_per_user: activeUsers ? Math.round(engDur / activeUsers) : 0,
        engaged_rate_pct: sessions ? r1((engagedSessions / sessions) * 100) : 0,
      },
      // The paywall funnel — your core "who hit a gate, why no subscribe".
      funnel: {
        paywall_shown: shown,
        paywall_shown_users: evu("paywall_shown"),
        subscribe_tapped: tapped,
        purchase_completed: bought,
        purchase_failed: evc("purchase_failed"),
        paywall_dismissed: evc("paywall_dismissed"),
        purchase_restored: evc("purchase_restored"),
        shown_to_tapped_pct: shown ? r1((tapped / shown) * 100) : 0,
        tapped_to_bought_pct: tapped ? r1((bought / tapped) * 100) : 0,
        shown_to_bought_pct: shown ? r1((bought / shown) * 100) : 0,
      },
      by_source: (bySourceR.rows || []).map((r) => ({ source: r.dimensionValues[0].value, shown: num(r.metricValues[0].value), users: num(r.metricValues[1].value) })),
      by_plan: (byPlanR.rows || []).map((r) => ({ plan: r.dimensionValues[0].value, taps: num(r.metricValues[0].value) })),
      membership: (membershipR.rows || []).map((r) => ({ membership: r.dimensionValues[0].value || "(not set)", users: num(r.metricValues[0].value), avg_sec: num(r.metricValues[0].value) ? Math.round(num(r.metricValues[1].value) / num(r.metricValues[0].value)) : 0 })),
      top_screens: (screensR.rows || []).map((r) => ({ screen: r.dimensionValues[0].value, views: num(r.metricValues[0].value), users: num(r.metricValues[1].value), avg_sec: num(r.metricValues[1].value) ? Math.round(num(r.metricValues[2].value) / num(r.metricValues[1].value)) : 0 })),
      actions: ACTIONS.map((n) => ({ name: n, count: evc(n), users: evu(n) })).filter((a) => a.count > 0),
    };
    cache = out; cacheAt = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(out);
  } catch (e) {
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 200) });
  }
}
