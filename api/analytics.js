// /api/analytics — App Store Connect ANALYTICS reports for the /dashboard.
//
// Different source from /api/asc (Sales reports). Uses the Analytics Reports API: request an
// ONGOING report → Apple generates instances asynchronously → download gzipped CSV segments.
// Reuses ASC_* creds; app id from ASC_APP_ID (default = Leaf People).
//
// Gives: impressions, product page views, conversion rate, first-time downloads vs redownloads.
// NOT here: Day-1/7/35 download-to-paid funnels (ASC-UI-only cohorts).
//
// LIFECYCLE: first call CREATES the request; Apple lists the report CATALOG quickly but the daily
// report INSTANCES (the data files) take up to ~48h to appear. Until an instance with segments
// exists, returns { pending:true }. Data also lags ~1-2 days. Response carries diag (report names,
// instance states, CSV header) so column parsing can be confirmed once data lands.

import crypto from "crypto";
import zlib from "zlib";

let cache = null, cacheAt = 0;
const CACHE_MS = 3 * 60 * 60 * 1000;
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

// Pull the newest usable instance's CSV for a report. Tries DAILY→WEEKLY→MONTHLY, newest first,
// only COMPLETED instances with downloadable segments. Returns { csv, date, header, diag }.
async function fetchData(jwt, reportId) {
  const inst = await api(jwt, `/v1/analyticsReports/${reportId}/instances?limit=200`);
  const all = (inst.data || []).map((i) => ({ id: i.id, ...(i.attributes || {}) }));
  const diag = { instances: all.length, sample: all.slice(0, 4).map((i) => ({ g: i.granularity, d: i.processingDate, s: i.state })) };
  const order = { DAILY: 0, WEEKLY: 1, MONTHLY: 2 };
  const usable = all
    .filter((i) => !i.state || i.state === "COMPLETED")
    .sort((a, b) => (order[a.granularity] ?? 9) - (order[b.granularity] ?? 9) || (a.processingDate < b.processingDate ? 1 : -1));
  for (const it of usable) {
    const seg = await api(jwt, `/v1/analyticsReportInstances/${it.id}/segments?limit=100`);
    let csv = "";
    for (const s of (seg.data || [])) {
      const u = s.attributes && s.attributes.url; if (!u) continue;
      const buf = Buffer.from(await (await fetch(u)).arrayBuffer());
      let t; try { t = zlib.gunzipSync(buf).toString("utf8"); } catch { t = buf.toString("utf8"); }
      csv += (csv ? "\n" : "") + t;
    }
    if (csv.trim()) {
      const header = csv.split(/\r?\n/, 1)[0];
      return { csv, date: it.processingDate, header, diag };
    }
  }
  return { csv: null, diag };
}

// Sum metric columns from an analytics CSV. Handles both WIDE (a column per metric) and TALL
// (an "Event"/dimension column + a "Counts" value column) layouts.
function sumMetrics(csv) {
  const lines = csv.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return {};
  const sep = lines[0].includes("\t") ? "\t" : ",";
  const head = lines[0].split(sep).map((h) => h.trim());
  const hl = head.map((h) => h.toLowerCase());
  const col = (re) => hl.findIndex((h) => re.test(h));
  const num = (c, i) => (i >= 0 ? Number((c[i] || "").replace(/[,\s"]/g, "")) || 0 : 0);
  const t = { impressions: 0, pageViews: 0, firstTime: 0, redownloads: 0, totalDownloads: 0 };
  // wide columns (if present)
  const wImp = col(/^impressions?(\s|$)/) >= 0 ? col(/^impressions?(\s|$)/) : col(/^impressions? total/);
  const wPV = col(/product page views?/);
  const wFT = col(/first.?time download/);
  const wRe = col(/redownload/);
  const wTot = col(/total download/);
  // tall layout: a counts column + an event/type column
  const counts = col(/^counts?$/) >= 0 ? col(/^counts?$/) : col(/\bcounts?\b/);
  const evCol = col(/^event$/) >= 0 ? col(/^event$/) : col(/engagement type|event type|page type|^type$/);
  for (let i = 1; i < lines.length; i++) {
    const c = lines[i].split(sep);
    if (wImp >= 0 || wPV >= 0 || wFT >= 0) {
      t.impressions += num(c, wImp); t.pageViews += num(c, wPV);
      t.firstTime += num(c, wFT); t.redownloads += num(c, wRe); t.totalDownloads += num(c, wTot);
    } else if (counts >= 0 && evCol >= 0) {
      const ev = (c[evCol] || "").toLowerCase(), v = num(c, counts);
      if (ev.includes("impression")) t.impressions += v;
      else if (ev.includes("page view")) t.pageViews += v;
      else if (ev.includes("first") && ev.includes("download")) t.firstTime += v;
      else if (ev.includes("redownload")) t.redownloads += v;
      else if (ev.includes("total") && ev.includes("download")) t.totalDownloads += v;
    }
  }
  return { ...t, header: head };
}

export default async function handler(req, res) {
  const issuer = process.env.ASC_ISSUER_ID, keyId = process.env.ASC_KEY_ID, p8 = process.env.ASC_P8;
  if (!issuer || !keyId || !p8) return res.status(200).json({ connected: false });
  const fresh = !!(req.query && req.query.fresh);
  if (cache && !fresh && Date.now() - cacheAt < CACHE_MS) { res.setHeader("cache-control", "no-store"); return res.status(200).json(cache); }

  const done = (obj) => { cache = obj; cacheAt = Date.now(); res.setHeader("cache-control", "no-store"); return res.status(200).json(obj); };
  try {
    const jwt = token(issuer, keyId, p8);
    const { id: reqId, created } = await ensureRequest(jwt);
    if (created) return done({ connected: true, pending: true, note: "Analytics report just requested — Apple generates the data within ~48h." });
    const reports = await reportsFor(jwt, reqId);
    if (!reports.length) return done({ connected: true, pending: true, note: "Report request exists; Apple hasn't produced reports yet (~48h)." });

    const pick = (re) => reports.find((r) => r.attributes && re.test((r.attributes.name || "").toLowerCase()));
    const engagement = pick(/discovery and engagement standard/) || pick(/discovery and engagement/);
    const downloads = pick(/^app downloads standard/) || pick(/^app downloads/);

    const out = { connected: true, updated: new Date().toISOString(), diag: {} };
    let gotAny = false;
    if (engagement) {
      const d = await fetchData(jwt, engagement.id);
      out.diag.engagement = { header: d.header, ...d.diag };
      if (d.csv) { const m = sumMetrics(d.csv); out.date = d.date; out.impressions = m.impressions; out.pageViews = m.pageViews; gotAny = true; }
    }
    if (downloads && (!engagement || downloads.id !== engagement.id)) {
      const d = await fetchData(jwt, downloads.id);
      out.diag.downloads = { header: d.header, ...d.diag };
      if (d.csv) { const m = sumMetrics(d.csv); out.firstTimeDownloads = m.firstTime; out.redownloads = m.redownloads; out.totalDownloads = m.totalDownloads || (m.firstTime + m.redownloads); gotAny = true; }
    }
    if (!gotAny) return done({ connected: true, pending: true, note: "Reports cataloged; daily data files not generated yet (Apple takes up to ~48h from setup). Filling in soon.", diag: out.diag });
    const dl = out.totalDownloads || out.firstTimeDownloads || 0;
    if (out.impressions && dl) out.conversionRate = Math.round((dl / out.impressions) * 10000) / 100;
    return done(out);
  } catch (e) {
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 300) });
  }
}
