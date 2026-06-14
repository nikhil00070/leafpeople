// /api/asc — read-only App Store download numbers for the /dashboard Downloads panel.
//
// Auth: ES256 JWT signed with the .p8 key (Node crypto, no SDK). Pulls the App Store
// Connect Sales Reports API (DAILY / SALES / SUMMARY) for the last ~16 days — each report
// is a gzipped TSV; we sum "Units" for app-download rows (Product Type Identifier 1x =
// first-time installs). Returns since-launch total, last 7d, latest day, and a daily series.
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

function sumDownloads(tsv) {
  const lines = tsv.split("\n").filter(Boolean);
  if (lines.length < 2) return 0;
  const head = lines[0].split("\t");
  const ui = head.indexOf("Units");
  const pi = head.indexOf("Product Type Identifier");
  if (ui < 0) return 0;
  let units = 0;
  for (let i = 1; i < lines.length; i++) {
    const c = lines[i].split("\t");
    const pti = (pi >= 0 ? c[pi] : "") || "";
    if (pti.charAt(0) === "1") units += Number(c[ui] || 0) || 0;   // PTI 1x = app first-time download
  }
  return units;
}

async function dayUnits(jwt, vendor, date) {
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
  return sumDownloads(tsv);
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
      try { const u = await dayUnits(jwt, vendor, date); return u == null ? null : { date, units: u }; }
      catch { return null; }
    }));
    const series = got.filter(Boolean).sort((a, b) => (a.date < b.date ? -1 : 1));
    const total = series.reduce((s, x) => s + x.units, 0);
    const last7 = series.slice(-7).reduce((s, x) => s + x.units, 0);

    cache = { connected: true, updated: new Date().toISOString(), latest: series[series.length - 1] || null, last7, total, series };
    cacheAt = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(cache);
  } catch (e) {
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 200) });
  }
}
