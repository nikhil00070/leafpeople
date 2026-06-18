// /api/analytics — App Store Connect ANALYTICS reports for the /dashboard.
//
// Different source from /api/asc (which uses Sales reports). This uses the Analytics Reports
// API: you request an ONGOING report, Apple GENERATES it asynchronously, then you download
// gzipped CSV segments. Reuses the ASC_* creds; app id from ASC_APP_ID (default = Leaf People).
//
// Gives: impressions, product page views, first-time downloads vs redownloads, conversion rate.
// NOT available here: Day-1/7/35 download-to-paid funnels (those are ASC-UI-computed cohorts).
//
// LIFECYCLE: the first call CREATES the report request; Apple needs up to ~48h to produce the
// first instances, so until then this returns { pending:true }. Data also lags ~1-2 days. The
// response includes diag fields (report names + CSV headers) so column parsing can be refined.

import crypto from "crypto";
import zlib from "zlib";

let cache = null, cacheAt = 0;
const CACHE_MS = 6 * 60 * 60 * 1000;
const BASE = "https://api.appstoreconnect.apple.com";
const appId = () => process.env.ASC_APP_ID || "6760627345";

function token(issuer, keyId, p8) {
  const key = p8.includes("\\n") ? p8.replace(/\\n/g, "\n") : p8;
  const now = Math.floor(Date.now() / 1000);
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
  const input = `${b64({ alg: "ES256", kid: keyId, typ: "JWT" })}.${b64({ iss: issuer, iat: now, exp: now + 19 * 60, aud: "appstoreconnect-v1" })}`;
  const sig = crypto.createSign("SHA256").update(input).sign({ key, dsaEncoding: "ieee-p1363" });
  return `${input}.${sig.toString("base64url")}`;
}

async function api(jwt, path, opts = {}) {
  const r = await fetch(path.startsWith("http") ? path : BASE + path, {
    ...opts,
    headers: { Authorization: `Bearer ${jwt}`, Accept: "application/json", "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  const txt = await r.text();
  if (!r.ok) throw new Error(`${r.status} ${path.split("?")[0].replace(BASE, "")}: ${txt.replace(/\s+/g, " ").slice(0, 200)}`);
  try { return JSON.parse(txt); } catch { return {}; }
}

// Find the app's ONGOING analytics report request, creating one if none exists.
async function ensureRequest(jwt) {
  const list = await api(jwt, `/v1/apps/${appId()}/analyticsReportRequests?filter[accessType]=ONGOING&limit=50`);
  const ok = (list.data || []).find((r) => r.attributes && r.attributes.accessType === "ONGOING" && !r.attributes.stoppedDueToInactivity);
  if (ok) return { id: ok.id, created: false };
  const made = await api(jwt, `/v1/analyticsReportRequests`, {
    method: "POST",
    body: JSON.stringify({ data: { type: "analyticsReportRequests", attributes: { accessType: "ONGOING" }, relationships: { app: { data: { type: "apps", id: appId() } } } } }),
  });
  return { id: made.data.id, created: true };
}

async function reportsFor(jwt, reqId) {
  let url = `/v1/analyticsReportRequests/${reqId}/reports?limit=200`, out = [];
  while (url) { const p = await api(jwt, url); out.push(...(p.data || [])); url = p.links && p.links.next ? p.links.next : null; }
  return out;
}

// Newest DAILY instance's segments, downloaded + concatenated into one CSV string.
async function latestCsv(jwt, reportId) {
  const inst = await api(jwt, `/v1/analyticsReports/${reportId}/instances?filter[granularity]=DAILY&limit=100`);
  const instances = (inst.data || []).filter((i) => i.attributes)
    .sort((a, b) => (a.attributes.processingDate < b.attributes.processingDate ? 1 : -1));
  for (const it of instances) {
    const seg = await api(jwt, `/v1/analyticsReportInstances/${it.id}/segments?limit=100`);
    let csv = "";
    for (const s of (seg.data || [])) {
      const u = s.attributes && s.attributes.url;
      if (!u) continue;
      const buf = Buffer.from(await (await fetch(u)).arrayBuffer());
      let t; try { t = zlib.gunzipSync(buf).toString("utf8"); } catch { t = buf.toString("utf8"); }
      csv += (csv ? "\n" : "") + t;
    }
    if (csv.trim()) return { date: it.attributes.processingDate, csv };
  }
  return null;
}

// Sum metric columns out of an analytics CSV (best-effort fuzzy column match; returns header for diag).
function sumMetrics(csv) {
  const lines = csv.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return { header: [], rows: 0 };
  const sep = lines[0].includes("\t") ? "\t" : ",";
  const head = lines[0].split(sep).map((h) => h.trim());
  const idx = (re) => head.findIndex((h) => re.test(h.toLowerCase()));
  const ci = {
    impressions: idx(/^impressions?(\s|$)/) >= 0 ? idx(/^impressions?(\s|$)/) : idx(/impression/),
    pageViews: idx(/product page view/),
    firstTime: idx(/first.?time download/),
    redownloads: idx(/redownload/),
    totalDl: idx(/total download/),
  };
  const t = { impressions: 0, pageViews: 0, firstTime: 0, redownloads: 0, totalDownloads: 0 };
  const num = (c, i) => (i >= 0 ? Number((c[i] || "").replace(/[,\s]/g, "")) || 0 : 0);
  for (let i = 1; i < lines.length; i++) {
    const c = lines[i].split(sep);
    t.impressions += num(c, ci.impressions);
    t.pageViews += num(c, ci.pageViews);
    t.firstTime += num(c, ci.firstTime);
    t.redownloads += num(c, ci.redownloads);
    t.totalDownloads += num(c, ci.totalDl);
  }
  return { header: head, rows: lines.length - 1, ...t };
}

export default async function handler(req, res) {
  const issuer = process.env.ASC_ISSUER_ID, keyId = process.env.ASC_KEY_ID, p8 = process.env.ASC_P8;
  if (!issuer || !keyId || !p8) return res.status(200).json({ connected: false });
  const fresh = !!(req.query && req.query.fresh);
  if (cache && !fresh && Date.now() - cacheAt < CACHE_MS) { res.setHeader("cache-control", "no-store"); return res.status(200).json(cache); }

  try {
    const jwt = token(issuer, keyId, p8);
    const { id: reqId, created } = await ensureRequest(jwt);
    if (created) {
      cache = { connected: true, pending: true, note: "Analytics report just requested — Apple generates it within ~48h. The dashboard will fill in then." };
      cacheAt = Date.now(); res.setHeader("cache-control", "no-store"); return res.status(200).json(cache);
    }
    const reports = await reportsFor(jwt, reqId);
    if (!reports.length) {
      cache = { connected: true, pending: true, note: "Report request exists; Apple hasn't produced instances yet (up to ~48h)." };
      cacheAt = Date.now(); res.setHeader("cache-control", "no-store"); return res.status(200).json(cache);
    }
    const names = reports.map((r) => r.attributes && r.attributes.name).filter(Boolean);
    const pick = (re) => reports.find((r) => r.attributes && re.test((r.attributes.name || "").toLowerCase()));
    const engagement = pick(/discovery and engagement/) || pick(/engagement/) || pick(/impression/);
    const downloads = pick(/^app downloads/) || pick(/download/);

    const out = { connected: true, updated: new Date().toISOString(), reports: names };
    if (engagement) {
      const cv = await latestCsv(jwt, engagement.id);
      if (cv) { const m = sumMetrics(cv.csv); out.date = cv.date; out.impressions = m.impressions; out.pageViews = m.pageViews; out.diag_engagement = m.header; }
    }
    if (downloads && (!engagement || downloads.id !== engagement.id)) {
      const cv = await latestCsv(jwt, downloads.id);
      if (cv) { const m = sumMetrics(cv.csv); out.firstTimeDownloads = m.firstTime; out.redownloads = m.redownloads; out.totalDownloads = m.totalDownloads || (m.firstTime + m.redownloads); out.diag_downloads = m.header; }
    }
    const dl = out.totalDownloads || out.firstTimeDownloads || 0;
    if (out.impressions && dl) out.conversionRate = Math.round((dl / out.impressions) * 10000) / 100;
    cache = out; cacheAt = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(out);
  } catch (e) {
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 300) });
  }
}
