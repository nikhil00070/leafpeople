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

// ASC snapshot to anchor to. Apple's Analytics Reports API can't backfill before it was enabled
// (~Jun 19), so these lifetime values are seeded from App Store Connect and the API adds the days
// AFTER `asOf` on top — ties to ASC today and stays in sync as new days stream in.
// To re-snapshot: read the lifetime totals in ASC → Analytics and update these four + asOf.
// Snapshot of App Store Connect → Analytics LIFETIME numbers, displayed verbatim so the
// dashboard always TIES to ASC (Apple's API double-counts impressions if summed live, and
// lags ~2 days anyway, so a dated snapshot is more trustworthy than a fragile live add).
// To refresh: read ASC → Analytics lifetime + update these + asOf.
const ASC_BASELINE = { asOf: "2026-06-25", impressions: 652, pageViews: 93, firstTime: 12, redownloads: 1, conversionRate: 2.76 };

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

async function instanceCsv(jwt, instanceId) {
  const seg = await api(jwt, `/v1/analyticsReportInstances/${instanceId}/segments?limit=100`);
  let csv = "";
  for (const s of (seg.data || [])) {
    const u = s.attributes && s.attributes.url; if (!u) continue;
    const buf = Buffer.from(await (await fetch(u)).arrayBuffer());
    let t; try { t = zlib.gunzipSync(buf).toString("utf8"); } catch { t = buf.toString("utf8"); }
    csv += (csv ? "\n" : "") + t;
  }
  return csv;
}

// Sum a report's metrics across the most-recent `days` DAILY instances — so totals match ASC's
// "Last 30 Days" view rather than a single day. Returns { totals, header, from, to, days, diag }.
async function fetchWindow(jwt, reportId, after) {
  const inst = await api(jwt, `/v1/analyticsReports/${reportId}/instances?limit=200`);
  const all = (inst.data || []).map((i) => ({ id: i.id, ...(i.attributes || {}) }));
  const diag = { instances: all.length, sample: all.slice(0, 4).map((i) => ({ g: i.granularity, d: i.processingDate, s: i.state })) };
  // Sum only DAILY instances AFTER the ASC baseline date — those are the days the API can see
  // that the hardcoded baseline doesn't already include, so the two add up without double-counting.
  const daily = all.filter((i) => i.granularity === "DAILY" && (!i.state || i.state === "COMPLETED") && (!after || i.processingDate > after))
    .sort((a, b) => (a.processingDate < b.processingDate ? 1 : -1));
  const totals = { impressions: 0, pageViews: 0, firstTime: 0, redownloads: 0, totalDownloads: 0 };
  let header = null; const dates = [];
  for (const it of daily) {
    const csv = await instanceCsv(jwt, it.id);
    if (!csv.trim()) continue;
    const m = sumMetrics(csv);
    if (!header) header = m.header;
    for (const k of ["impressions", "pageViews", "firstTime", "redownloads", "totalDownloads"]) totals[k] += m[k] || 0;
    dates.push(it.processingDate);
  }
  return { totals, header, from: dates[dates.length - 1], to: dates[0], days: dates.length, diag };
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

// DIAG: per-day, group every row by its Event value and sum Counts + Unique Counts, so we can
// see exactly which event(s) to add (and whether Counts or Unique matches ASC). Inspect-only.
async function eventDump(jwt, reportId, n) {
  const inst = await api(jwt, `/v1/analyticsReports/${reportId}/instances?limit=200`);
  const daily = (inst.data || []).map((i) => ({ id: i.id, ...(i.attributes || {}) }))
    .filter((i) => i.granularity === "DAILY" && (!i.state || i.state === "COMPLETED"))
    .sort((a, b) => (a.processingDate < b.processingDate ? 1 : -1)).slice(0, n);
  const out = [];
  for (const it of daily) {
    let csv;
    try { csv = await instanceCsv(jwt, it.id); }
    catch (e) { out.push({ date: it.processingDate, error: String(e.message || e).slice(0, 60) }); continue; }
    const lines = csv.split(/\r?\n/).filter(Boolean);
    if (lines.length < 2) { out.push({ date: it.processingDate, empty: true }); continue; }
    const sep = lines[0].includes("\t") ? "\t" : ",";
    const head = lines[0].split(sep).map((h) => h.trim());
    const evi = head.findIndex((h) => /^event$/i.test(h));
    const ci = head.findIndex((h) => /^counts?$/i.test(h));
    const ui = head.findIndex((h) => /unique count/i.test(h));
    const num = (x) => Number((x || "").replace(/[,\s"]/g, "")) || 0;
    const byEvent = {};
    for (let i = 1; i < lines.length; i++) {
      const c = lines[i].split(sep);
      const ev = (c[evi] || "").trim() || "(blank)";
      if (!byEvent[ev]) byEvent[ev] = { counts: 0, unique: 0, rows: 0 };
      byEvent[ev].counts += num(c[ci]); byEvent[ev].unique += num(c[ui]); byEvent[ev].rows++;
    }
    out.push({ date: it.processingDate, header: evi < 0 ? head : undefined, events: byEvent });
  }
  return out;
}

// Sum the live Apple Analytics daily instances (rolling ~30d). Skips days Apple 500s on.
// engagement → Impression + Page view counts; downloads → all rows (total app downloads).
async function sumDaily(jwt, reportId, kind) {
  const inst = await api(jwt, `/v1/analyticsReports/${reportId}/instances?limit=200`);
  const daily = (inst.data || []).map((i) => ({ id: i.id, ...(i.attributes || {}) }))
    .filter((i) => i.granularity === "DAILY" && (!i.state || i.state === "COMPLETED"))
    .sort((a, b) => (a.processingDate < b.processingDate ? 1 : -1)).slice(0, 32);
  let impressions = 0, pageViews = 0, downloads = 0, days = 0, skipped = 0, from = null, to = null;
  for (const it of daily) {
    let csv; try { csv = await instanceCsv(jwt, it.id); } catch { skipped++; continue; }
    const lines = csv.split(/\r?\n/).filter(Boolean); if (lines.length < 2) continue;
    const sep = lines[0].includes("\t") ? "\t" : ",";
    const head = lines[0].split(sep).map((h) => h.trim().toLowerCase());
    const evi = head.findIndex((h) => /^event$/.test(h));
    const ci = head.findIndex((h) => /^counts?$/.test(h));
    const num = (x) => Number((x || "").replace(/[,\s"]/g, "")) || 0;
    for (let i = 1; i < lines.length; i++) {
      const c = lines[i].split(sep); const v = num(c[ci]);
      if (kind === "downloads") downloads += v;
      else { const ev = (c[evi] || "").toLowerCase(); if (ev === "impression") impressions += v; else if (ev === "page view") pageViews += v; }
    }
    days++; to = to || it.processingDate; from = it.processingDate;
  }
  return { impressions, pageViews, downloads, days, skipped, from, to };
}

export default async function handler(req, res) {
  const issuer = process.env.ASC_ISSUER_ID, keyId = process.env.ASC_KEY_ID, p8 = process.env.ASC_P8;
  if (!issuer || !keyId || !p8) return res.status(200).json({ connected: false });
  const fresh = !!(req.query && req.query.fresh);

  if (req.query && req.query.diag) {
    try {
      const jwt = token(issuer, keyId, p8);
      const { id: reqId } = await ensureRequest(jwt);
      const reports = await reportsFor(jwt, reqId);
      const pick = (re) => reports.find((r) => r.attributes && re.test((r.attributes.name || "").toLowerCase()));
      const eng = pick(/discovery and engagement/), dl = pick(/app downloads/);
      return res.status(200).json({
        reports: reports.map((r) => r.attributes && r.attributes.name),
        engagement: eng ? await eventDump(jwt, eng.id, 9) : null,
        downloads: dl ? await eventDump(jwt, dl.id, 9) : null,
      });
    } catch (e) { return res.status(200).json({ diagError: String(e.message || e).slice(0, 300) }); }
  }

  if (cache && !fresh && Date.now() - cacheAt < CACHE_MS) { res.setHeader("cache-control", "no-store"); return res.status(200).json(cache); }

  // AUTO / LIVE: pull Apple's Analytics API directly (rolling ~30d) so nothing is pasted by hand.
  // These are Apple's own engagement counts — they won't pixel-match the deduplicated ASC website
  // totals, but they update daily on their own. Installs/revenue come from the Sales API (/api/asc).
  const r2 = (n) => Math.round(n * 100) / 100;
  try {
    const jwt = token(issuer, keyId, p8);
    const { id: reqId, created } = await ensureRequest(jwt);
    if (created) throw new Error("analytics report just requested");
    const reports = await reportsFor(jwt, reqId);
    const pick = (re) => reports.find((r) => r.attributes && re.test((r.attributes.name || "").toLowerCase()));
    const eng = pick(/discovery and engagement standard/) || pick(/discovery and engagement/);
    const dl = pick(/^app downloads standard/) || pick(/^app downloads/);
    const e = eng ? await sumDaily(jwt, eng.id, "engagement") : { impressions: 0, pageViews: 0, days: 0 };
    const d = dl ? await sumDaily(jwt, dl.id, "downloads") : { downloads: 0, days: 0 };
    const impressions = e.impressions, pageViews = e.pageViews, downloads = d.downloads;
    const out = {
      connected: true, source: "live", updated: new Date().toISOString(),
      window: "rolling ~30d (Apple Analytics API)", from: e.from || d.from, to: e.to || d.to,
      impressions, pageViews, downloads30: downloads,
      conversionRate: impressions ? r2((downloads / impressions) * 100) : 0,
      daysEngagement: e.days, daysDownloads: d.days, skipped: (e.skipped || 0) + (d.skipped || 0),
    };
    // Sanity: if Apple returned essentially nothing (all instances 500'd / not generated), fall back
    // to the last known snapshot so the tab never goes blank.
    if (!impressions && !downloads) throw new Error("no live data this fetch");
    cache = out; cacheAt = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(out);
  } catch (e) {
    const out = {
      connected: true, source: "snapshot", note: "Apple Analytics API unavailable this fetch — showing last snapshot. " + String(e.message || e).slice(0, 80),
      updated: new Date().toISOString(), baselineAsOf: ASC_BASELINE.asOf,
      impressions: ASC_BASELINE.impressions, pageViews: ASC_BASELINE.pageViews,
      conversionRate: ASC_BASELINE.conversionRate,
    };
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(out);
  }
}
