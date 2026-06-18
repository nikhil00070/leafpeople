// /api/asc — read-only App Store numbers for the /dashboard Downloads panel.
//
// Auth: ES256 JWT signed with the .p8 key (Node crypto, no SDK). Pulls the App Store
// Connect Sales Reports API (DAILY / SALES / SUMMARY) for the last ~16 days — each report
// is a gzipped TSV. From each day we read Units + Developer Proceeds by Product Type
// Identifier: 1x = first-time download, 7x = update, IA* = in-app purchase. Returns
// since-launch + last-7d totals for downloads, updates, IAPs, and proceeds, plus a daily
// download series. (First-time-vs-redownload split + impressions live in /api/analytics.)
//
// Env (Vercel): ASC_ISSUER_ID, ASC_KEY_ID, ASC_P8 (whole .p8), ASC_VENDOR_NUMBER.
// Returns { connected:false } (200) when not configured, so the dashboard degrades cleanly.
// Note: Apple's data lags ~24-48h, so "latest" is yesterday/day-before, not live.

import crypto from "crypto";
import zlib from "zlib";

let cache = null, cacheAt = 0;
const CACHE_MS = 2 * 60 * 60 * 1000;   // 2h — the underlying data only changes daily

function token(issuer, keyId, p8) {
  const key = p8.includes("\\n") ? p8.replace(/\\n/g, "\n") : p8;   // tolerate escaped newlines
  const now = Math.floor(Date.now() / 1000);
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
  const input = `${b64({ alg: "ES256", kid: keyId, typ: "JWT" })}.${b64({ iss: issuer, iat: now, exp: now + 19 * 60, aud: "appstoreconnect-v1" })}`;
  const sig = crypto.createSign("SHA256").update(input).sign({ key, dsaEncoding: "ieee-p1363" });
  return `${input}.${sig.toString("base64url")}`;
}

// Parse one day's SALES/SUMMARY TSV into { downloads, updates, iap, proceeds }.
function parseDay(tsv) {
  const out = { downloads: 0, updates: 0, iap: 0, proceeds: 0 };
  const lines = tsv.split("\n").filter(Boolean);
  if (lines.length < 2) return out;
  const head = lines[0].split("\t");
  const ui = head.indexOf("Units");
  const pi = head.indexOf("Product Type Identifier");
  const dp = head.indexOf("Developer Proceeds");
  const cc = head.indexOf("Currency of Proceeds");
  if (ui < 0) return out;
  for (let i = 1; i < lines.length; i++) {
    const c = lines[i].split("\t");
    const pti = (pi >= 0 ? c[pi] : "") || "";
    const u = Number(c[ui] || 0) || 0;
    if (pti.charAt(0) === "1") out.downloads += u;        // 1x = app first-time download
    else if (pti.charAt(0) === "7") out.updates += u;     // 7x = update
    if (pti.startsWith("IA")) out.iap += u;               // IA* = in-app purchase
    // Developer Proceeds is per-unit in the row's local currency; sum the USD rows for a clean
    // number (a brand-new app is overwhelmingly USD — non-USD rows are negligible here).
    if (dp >= 0 && (cc < 0 || (c[cc] || "USD") === "USD")) out.proceeds += (Number(c[dp] || 0) || 0) * u;
  }
  out.proceeds = Math.round(out.proceeds * 100) / 100;
  return out;
}

async function dayStats(jwt, vendor, date) {
  const qs = new URLSearchParams({
    "filter[frequency]": "DAILY", "filter[reportType]": "SALES", "filter[reportSubType]": "SUMMARY",
    "filter[vendorNumber]": vendor, "filter[version]": "1_1", "filter[reportDate]": date,
  });
  const r = await fetch(`https://api.appstoreconnect.apple.com/v1/salesReports?${qs}`, {
    headers: { Authorization: `Bearer ${jwt}`, Accept: "application/a-gzip" },
  });
  if (r.status === 404) return null;                                // no report for that day yet
  if (!r.ok) throw new Error(`salesReports ${r.status}: ${(await r.text()).slice(0, 140)}`);
  const tsv = zlib.gunzipSync(Buffer.from(await r.arrayBuffer())).toString("utf8");
  return parseDay(tsv);
}

export default async function handler(req, res) {
  const issuer = process.env.ASC_ISSUER_ID, keyId = process.env.ASC_KEY_ID, p8 = process.env.ASC_P8;
  const vendor = process.env.ASC_VENDOR_NUMBER;
  if (!issuer || !keyId || !p8) return res.status(200).json({ connected: false });
  if (!vendor) return res.status(200).json({ connected: false, error: "ASC_VENDOR_NUMBER not set (App Store Connect → Payments and Financial Reports → Vendor #)" });

  if (cache && Date.now() - cacheAt < CACHE_MS) { res.setHeader("cache-control", "no-store"); return res.status(200).json(cache); }

  try {
    const jwt = token(issuer, keyId, p8);
    const dates = [];
    const base = new Date();
    for (let i = 1; i <= 16; i++) { const d = new Date(base); d.setUTCDate(d.getUTCDate() - i); dates.push(d.toISOString().slice(0, 10)); }

    const got = await Promise.all(dates.map(async (date) => {
      try { const s = await dayStats(jwt, vendor, date); return s == null ? null : { date, ...s }; }
      catch { return null; }
    }));
    const days = got.filter(Boolean).sort((a, b) => (a.date < b.date ? -1 : 1));
    const sum = (arr, k) => arr.reduce((s, x) => s + (x[k] || 0), 0);
    const last7days = days.slice(-7);
    const r2 = (n) => Math.round(n * 100) / 100;
    const series = days.map((d) => ({ date: d.date, units: d.downloads }));   // downloads/day (chart)

    cache = {
      connected: true, updated: new Date().toISOString(),
      latest: series[series.length - 1] || null,
      last7: sum(last7days, "downloads"),
      total: sum(days, "downloads"),
      series,
      updates: { total: sum(days, "updates"), last7: sum(last7days, "updates") },
      iap: { total: sum(days, "iap"), last7: sum(last7days, "iap") },
      proceeds: { total: r2(sum(days, "proceeds")), last7: r2(sum(last7days, "proceeds")) },
    };
    cacheAt = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(cache);
  } catch (e) {
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 200) });
  }
}
