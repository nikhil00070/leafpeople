// /api/ga4 — read-only GA4 Data API for the /dashboard Traffic + attribution panels.
//
// Auth: service-account JWT (RS256, Node built-in crypto — no SDK) → OAuth token →
// GA4 Data API runReport/runRealtimeReport. Returns 30-day sessions/users/pageviews,
// live active users, top articles, channels, and app_store_click counts per article
// ("articles that landed customers"). Reads GA4_PROPERTY_ID + GA4_SA_JSON from Vercel env.
//
// Returns { connected:false } (200) when not configured, so the dashboard degrades cleanly.

import crypto from "crypto";

let tok = null, tokExp = 0;          // OAuth token cache (per warm instance)
const cache = {}, cacheAt = {};      // result cache (5 min) per window (days) to spare GA4 quota
const CACHE_MS = 5 * 60 * 1000;

const b64url = (b) => Buffer.from(b).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const num = (v) => (v == null ? 0 : Number(v));
const rows = (rep) => (rep.rows || []).map((r) => ({ key: r.dimensionValues?.[0]?.value, value: num(r.metricValues?.[0]?.value) }));

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

async function report(pid, token, body, realtime = false) {
  const verb = realtime ? "runRealtimeReport" : "runReport";
  const r = await fetch(`https://analyticsdata.googleapis.com/v1beta/properties/${pid}:${verb}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${verb} ${r.status}: ${(await r.text()).slice(0, 160)}`);
  return r.json();
}

export default async function handler(req, res) {
  const pid = process.env.GA4_PROPERTY_ID;
  const saRaw = process.env.GA4_SA_JSON;
  if (!pid || !saRaw) return res.status(200).json({ connected: false });

  // date = a specific "YYYY-MM-DD" (single day) or "total" (all time, default)
  const dateParam = (req.query && req.query.date) || "total";
  const isDay = /^\d{4}-\d{2}-\d{2}$/.test(dateParam);
  const ck = isDay ? dateParam : "total";

  const skipCache = !!(req.query && req.query.fresh);
  if (!skipCache && cache[ck] && Date.now() - cacheAt[ck] < CACHE_MS) {
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(cache[ck]);
  }

  let sa;
  try { sa = JSON.parse(saRaw); } catch { return res.status(200).json({ connected: false, error: "GA4_SA_JSON is not valid JSON" }); }

  try {
    const token = await accessToken(sa);
    const rWin = isDay ? [{ startDate: dateParam, endDate: dateParam }] : [{ startDate: "2020-01-01", endDate: "today" }];
    const rAll = [{ startDate: "2020-01-01", endDate: "today" }];   // "since launch" — GA returns from first data
    const clickFilter = { filter: { fieldName: "eventName", inListFilter: { values: ["app_store_click"] } } };

    const [totalsR, allR, seriesR, pages, channels, clicksByPage, clicksTotalR] = await Promise.all([
      report(pid, token, { dateRanges: rWin, metrics: [{ name: "activeUsers" }, { name: "newUsers" }, { name: "sessions" }, { name: "screenPageViews" }, { name: "engagedSessions" }, { name: "userEngagementDuration" }] }),
      report(pid, token, { dateRanges: rAll, metrics: [{ name: "totalUsers" }] }),
      report(pid, token, { dateRanges: rWin, dimensions: [{ name: "date" }], metrics: [{ name: "activeUsers" }], orderBys: [{ dimension: { dimensionName: "date" } }], limit: 90 }),
      report(pid, token, { dateRanges: rWin, dimensions: [{ name: "pagePath" }], metrics: [{ name: "screenPageViews" }, { name: "totalUsers" }], orderBys: [{ metric: { metricName: "screenPageViews" }, desc: true }], limit: 10 }),  // views + unique readers per page
      report(pid, token, { dateRanges: rWin, dimensions: [{ name: "sessionDefaultChannelGroup" }], metrics: [{ name: "totalUsers" }], orderBys: [{ metric: { metricName: "totalUsers" }, desc: true }], limit: 8 }),  // unique users per channel
      report(pid, token, { dateRanges: rWin, dimensions: [{ name: "pagePath" }], metrics: [{ name: "totalUsers" }], dimensionFilter: clickFilter, orderBys: [{ metric: { metricName: "totalUsers" }, desc: true }], limit: 8 }),  // unique install-tappers per article
      report(pid, token, { dateRanges: rWin, metrics: [{ name: "totalUsers" }], dimensionFilter: clickFilter }),   // unique users who tapped Install
    ]);

    let realtime = null, realtime_detail = [];
    try { const rt = await report(pid, token, { metrics: [{ name: "activeUsers" }] }, true); realtime = num(rt.rows?.[0]?.metricValues?.[0]?.value); } catch { /* realtime optional */ }
    try {
      const rd = await report(pid, token, { dimensions: [{ name: "city" }, { name: "deviceCategory" }], metrics: [{ name: "activeUsers" }] }, true);
      realtime_detail = (rd.rows || []).map((r) => ({ city: r.dimensionValues?.[0]?.value, device: r.dimensionValues?.[1]?.value, users: num(r.metricValues?.[0]?.value) }));
    } catch { /* detail optional */ }

    const t = totalsR.rows?.[0]?.metricValues || [];
    const activeUsers = num(t[0]?.value), newUsers = num(t[1]?.value), sessions = num(t[2]?.value),
      pageviews = num(t[3]?.value), engagedSessions = num(t[4]?.value), engDur = num(t[5]?.value);
    const series = (seriesR.rows || []).map((r) => ({ date: r.dimensionValues[0].value, users: num(r.metricValues[0].value) }));
    const mean = (arr) => (arr.length ? arr.reduce((s, x) => s + x.users, 0) / arr.length : 0);
    const r1 = (n) => Math.round(n * 10) / 10;
    const total_users = num(allR.rows?.[0]?.metricValues?.[0]?.value);
    const clicks_total = num(clicksTotalR.rows?.[0]?.metricValues?.[0]?.value);

    cache[ck] = {
      connected: true,
      window: ck,
      updated: new Date().toISOString(),
      totals: { sessions, users: activeUsers, pageviews, newUsers },
      total_users,
      dau: { avg7: r1(mean(series.slice(-7))), avg30: r1(mean(series)), today: series.length ? series[series.length - 1].users : 0 },
      dau_series: series,
      engagement: { avg_sec_per_user: activeUsers ? Math.round(engDur / activeUsers) : 0, rate_pct: sessions ? r1((engagedSessions / sessions) * 100) : 0 },
      new_pct: activeUsers ? r1((newUsers / activeUsers) * 100) : 0,
      realtime,
      realtime_detail,
      conversion: { app_store_clicks: clicks_total, click_rate_pct: activeUsers ? r1((clicks_total / activeUsers) * 100) : 0 },
      top_pages: (pages.rows || []).map((r) => ({ key: r.dimensionValues?.[0]?.value, views: num(r.metricValues?.[0]?.value), users: num(r.metricValues?.[1]?.value) })),
      channels: rows(channels),
      app_store_clicks: rows(clicksByPage),
    };
    cacheAt[ck] = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(cache[ck]);
  } catch (e) {
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 200) });
  }
}
