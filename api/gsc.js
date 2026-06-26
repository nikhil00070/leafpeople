// /api/gsc — Google Search Console (the SEO scorecard) for the /dashboard SEO tab.
//
// Reuses the SAME service account as /api/ga4 (GA4_SA_JSON) — no new creds. Once that
// service-account email is added as a user on the Search Console property, this returns
// real organic-search numbers: clicks, impressions, CTR, average position, top queries,
// and top landing pages over the last 28 days.
//
// Setup (one-time): Search Console → Settings → Users and permissions → Add user →
// the GA4_SA_JSON client_email → Full/Restricted. Also enable the Search Console API in
// the GCP project. Until then this returns { connected:false } and the tab degrades.
//
// Env: GA4_SA_JSON (whole service-account JSON), GSC_SITE_URL (default sc-domain:leafpeople.app).

import crypto from "crypto";

let tok = null, tokExp = 0;
let cache = null, cacheAt = 0;
const CACHE_MS = 3 * 60 * 60 * 1000;
const SITE = () => process.env.GSC_SITE_URL || "sc-domain:leafpeople.app";

const b64url = (b) => Buffer.from(b).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const r2 = (n) => Math.round(n * 100) / 100;

async function accessToken(sa) {
  const now = Math.floor(Date.now() / 1000);
  if (tok && tokExp > now + 60) return tok;
  const head = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claim = b64url(JSON.stringify({
    iss: sa.client_email,
    scope: "https://www.googleapis.com/auth/webmasters.readonly",
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

async function query(token, body) {
  const r = await fetch(`https://searchconsole.googleapis.com/webmasters/v3/sites/${encodeURIComponent(SITE())}/searchAnalytics/query`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`gsc ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

const ymd = (off) => { const d = new Date(); d.setUTCDate(d.getUTCDate() - off); return d.toISOString().slice(0, 10); };

export default async function handler(req, res) {
  const saRaw = process.env.GA4_SA_JSON;
  if (!saRaw) return res.status(200).json({ connected: false });
  const fresh = !!(req.query && req.query.fresh);
  if (cache && !fresh && Date.now() - cacheAt < CACHE_MS) { res.setHeader("cache-control", "no-store"); return res.status(200).json(cache); }

  let sa;
  try { sa = JSON.parse(saRaw); } catch { return res.status(200).json({ connected: false, error: "GA4_SA_JSON is not valid JSON" }); }

  // GSC data lags ~2-3 days, so look back 3 → 31 days for a clean 28-day window.
  const startDate = ymd(31), endDate = ymd(3);
  try {
    const token = await accessToken(sa);
    const [totals, queries, pages, byDate] = await Promise.all([
      query(token, { startDate, endDate, dimensions: [] }),
      query(token, { startDate, endDate, dimensions: ["query"], rowLimit: 15, orderBy: [{ field: "clicks", descending: true }] }).catch(() => ({ rows: [] })),
      query(token, { startDate, endDate, dimensions: ["page"], rowLimit: 12, orderBy: [{ field: "clicks", descending: true }] }).catch(() => ({ rows: [] })),
      query(token, { startDate, endDate, dimensions: ["date"] }).catch(() => ({ rows: [] })),
    ]);
    const t = (totals.rows && totals.rows[0]) || { clicks: 0, impressions: 0, ctr: 0, position: 0 };
    const path = (u) => { try { return new URL(u).pathname || u; } catch { return u; } };

    const out = {
      connected: true, updated: new Date().toISOString(), site: SITE(), from: startDate, to: endDate,
      totals: { clicks: t.clicks || 0, impressions: t.impressions || 0, ctr_pct: r2((t.ctr || 0) * 100), position: r2(t.position || 0) },
      top_queries: (queries.rows || []).map((r) => ({ key: r.keys[0], clicks: r.clicks, impressions: r.impressions, ctr_pct: r2((r.ctr || 0) * 100), position: r2(r.position) })),
      top_pages: (pages.rows || []).map((r) => ({ key: path(r.keys[0]), clicks: r.clicks, impressions: r.impressions, position: r2(r.position) })),
      series: (byDate.rows || []).map((r) => ({ date: r.keys[0], clicks: r.clicks, impressions: r.impressions })),
    };
    cache = out; cacheAt = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(out);
  } catch (e) {
    // Most common: the SA isn't a user on the property yet, or the API isn't enabled.
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 220) });
  }
}
