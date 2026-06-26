// /api/seo — SEO + AEO data for the /dashboard, in ONE function (Vercel Hobby caps
// serverless functions at 12, so gsc + aeo are merged here). Returns { gsc, aeo }.
//
//  gsc — Google Search Console search analytics (clicks, impressions, CTR, avg position,
//        top queries, top pages). Reuses GA4_SA_JSON; grant that service-account email
//        access on the Search Console property + enable the Search Console API.
//        GSC_SITE_URL default "sc-domain:leafpeople.app" (set to "https://leafpeople.app/"
//        for a URL-prefix property).
//  aeo — Reads our live robots.txt / llms.txt / sitemap and reports AI-readiness.

import crypto from "crypto";

let cache = null, cacheAt = 0, tok = null, tokExp = 0, SITE_RESOLVED = null;
const CACHE_MS = 3 * 60 * 60 * 1000;
const SITE = () => process.env.GSC_SITE_URL || "sc-domain:leafpeople.app";
const BASE = "https://leafpeople.app";
const AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "ClaudeBot", "Claude-Web", "Anthropic-AI", "Google-Extended", "Applebot-Extended", "Amazonbot", "CCBot", "Bytespider"];

const b64url = (b) => Buffer.from(b).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const r2 = (n) => Math.round(n * 100) / 100;
const ymd = (off) => { const d = new Date(); d.setUTCDate(d.getUTCDate() - off); return d.toISOString().slice(0, 10); };

// ---- Search Console ----
async function gscToken(sa) {
  const now = Math.floor(Date.now() / 1000);
  if (tok && tokExp > now + 60) return tok;
  const head = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claim = b64url(JSON.stringify({
    iss: sa.client_email, scope: "https://www.googleapis.com/auth/webmasters.readonly",
    aud: "https://oauth2.googleapis.com/token", iat: now, exp: now + 3600,
  }));
  const sig = b64url(crypto.createSign("RSA-SHA256").update(`${head}.${claim}`).sign(sa.private_key));
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: `${head}.${claim}.${sig}` }),
  });
  const j = await r.json();
  if (!j.access_token) throw new Error("oauth: " + JSON.stringify(j).slice(0, 140));
  tok = j.access_token; tokExp = now + (j.expires_in || 3600);
  return tok;
}
async function gscQuery(token, body) {
  const r = await fetch(`https://searchconsole.googleapis.com/webmasters/v3/sites/${encodeURIComponent(SITE_RESOLVED || SITE())}/searchAnalytics/query`, {
    method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`gsc ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.json();
}
// Discover which Search Console property the service account actually has access to,
// so it works whether the property is a Domain (sc-domain:…) or URL-prefix (https://…)
// one — no env guessing. Prefers an explicit GSC_SITE_URL, else the first leafpeople match.
async function resolveSite(token) {
  if (process.env.GSC_SITE_URL) return { site: process.env.GSC_SITE_URL, available: [process.env.GSC_SITE_URL] };
  try {
    const r = await fetch("https://searchconsole.googleapis.com/webmasters/v3/sites", { headers: { Authorization: `Bearer ${token}` } });
    const j = await r.json();
    const sites = (j.siteEntry || []).map((s) => s.siteUrl);
    const lp = sites.find((s) => /leafpeople\.app/i.test(s)) || null;
    return { site: lp, available: sites };
  } catch { return { site: null, available: [] }; }
}

async function getGSC() {
  const saRaw = process.env.GA4_SA_JSON;
  if (!saRaw) return { connected: false };
  let sa; try { sa = JSON.parse(saRaw); } catch { return { connected: false, error: "GA4_SA_JSON invalid" }; }
  const startDate = ymd(31), endDate = ymd(3);
  try {
    const token = await gscToken(sa);
    const { site, available } = await resolveSite(token);
    if (!site) {
      return { connected: false, error: "Service account has access to no Search Console property yet (grant may still be propagating, or was added to a different property). Visible: " + (available.length ? available.join(", ") : "none"), available };
    }
    SITE_RESOLVED = site;
    const [totals, queries, pages, byDate] = await Promise.all([
      gscQuery(token, { startDate, endDate, dimensions: [] }),
      gscQuery(token, { startDate, endDate, dimensions: ["query"], rowLimit: 15, orderBy: [{ field: "clicks", descending: true }] }).catch(() => ({ rows: [] })),
      gscQuery(token, { startDate, endDate, dimensions: ["page"], rowLimit: 12, orderBy: [{ field: "clicks", descending: true }] }).catch(() => ({ rows: [] })),
      gscQuery(token, { startDate, endDate, dimensions: ["date"] }).catch(() => ({ rows: [] })),
    ]);
    const t = (totals.rows && totals.rows[0]) || { clicks: 0, impressions: 0, ctr: 0, position: 0 };
    const path = (u) => { try { return new URL(u).pathname || u; } catch { return u; } };
    return {
      connected: true, site: site, from: startDate, to: endDate,
      totals: { clicks: t.clicks || 0, impressions: t.impressions || 0, ctr_pct: r2((t.ctr || 0) * 100), position: r2(t.position || 0) },
      top_queries: (queries.rows || []).map((r) => ({ key: r.keys[0], clicks: r.clicks, impressions: r.impressions, ctr_pct: r2((r.ctr || 0) * 100), position: r2(r.position) })),
      top_pages: (pages.rows || []).map((r) => ({ key: path(r.keys[0]), clicks: r.clicks, impressions: r.impressions, position: r2(r.position) })),
      series: (byDate.rows || []).map((r) => ({ date: r.keys[0], clicks: r.clicks, impressions: r.impressions })),
    };
  } catch (e) { return { connected: false, error: String(e.message || e).slice(0, 220) }; }
}

// ---- AEO readiness ----
async function siteText(path) {
  try { const r = await fetch(BASE + path, { headers: { "user-agent": "LeafPeople-Dashboard" } }); return r.ok ? await r.text() : null; } catch { return null; }
}
// Read AI-crawler hit counters the middleware writes to Vercel KV (Upstash REST).
const AEO_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "ClaudeBot", "Claude-Web", "Anthropic-AI", "Google-Extended", "Applebot-Extended", "Amazonbot", "CCBot", "Bytespider"];
async function crawlerHits() {
  const url = process.env.KV_REST_API_URL, tok = process.env.KV_REST_API_TOKEN;
  if (!url || !tok) return null;
  try {
    const keys = AEO_BOTS.map((b) => `aeo:hit:${b}`);
    const r = await fetch(`${url}/mget/${keys.map(encodeURIComponent).join("/")}`, { headers: { Authorization: `Bearer ${tok}` } });
    const j = await r.json();
    const vals = j.result || [];
    const hits = {};
    AEO_BOTS.forEach((b, i) => { const n = Number(vals[i]) || 0; if (n > 0) hits[b] = n; });
    return hits;
  } catch { return null; }
}
async function getAEO() {
  const [robots, llms, sitemap, hits] = await Promise.all([siteText("/robots.txt"), siteText("/llms.txt"), siteText("/sitemap.xml"), crawlerHits()]);
  const robotsLc = (robots || "").toLowerCase();
  const aiAllowed = AI_BOTS.filter((b) => {
    const i = robotsLc.indexOf(b.toLowerCase()); if (i < 0) return false;
    const block = robotsLc.slice(i, i + 220);
    return /allow:\s*\//.test(block) && !/disallow:\s*\/\s*(\n|$)/.test(block);
  });
  const llmsOK = !!llms && llms.length > 50;
  const llmsRefs = llms ? (llms.match(/^\s*-\s*\[/gm) || []).length : 0;
  const sitemapUrls = sitemap ? (sitemap.match(/<loc>/g) || []).length : 0;
  const checks = [
    { id: "robots", label: "robots.txt welcomes AI crawlers", ok: aiAllowed.length >= 3, detail: aiAllowed.length ? aiAllowed.join(", ") : "no AI bots explicitly allowed" },
    { id: "llms", label: "llms.txt published (AI-readable index)", ok: llmsOK, detail: llmsOK ? `${llmsRefs} references listed` : "missing or empty" },
    { id: "sitemap", label: "sitemap.xml submitted", ok: sitemapUrls > 0, detail: sitemapUrls ? `${sitemapUrls} URLs` : "missing" },
    { id: "fulltext", label: "Full article text served to crawlers", ok: true, detail: "middleware serves full content to search + AI bots (sanctioned sampling)" },
  ];
  return {
    connected: true, ready: checks.filter((c) => c.ok).length, total: checks.length, checks,
    ai_bots_allowed: aiAllowed, llms_refs: llmsRefs, sitemap_urls: sitemapUrls,
    crawler_hits: (hits && Object.keys(hits).length) ? hits : null,
    note: hits == null
      ? "Connect a Vercel KV store (KV_REST_API_URL/TOKEN) so the middleware can log AI-crawler hits."
      : "No AI-crawler hits recorded yet — they'll appear here as bots fetch your articles.",
  };
}

export default async function handler(req, res) {
  const fresh = !!(req.query && req.query.fresh);
  if (cache && !fresh && Date.now() - cacheAt < CACHE_MS) { res.setHeader("cache-control", "no-store"); return res.status(200).json(cache); }
  const [gsc, aeo] = await Promise.all([getGSC(), getAEO()]);
  const out = { updated: new Date().toISOString(), gsc, aeo };
  cache = out; cacheAt = Date.now();
  res.setHeader("cache-control", "no-store");
  return res.status(200).json(out);
}
