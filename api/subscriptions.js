// /api/subscriptions — App Store subscription numbers for the /dashboard funnel.
//
// Reuses the App Store Connect creds already wired for downloads (ASC_*). Pulls:
//   - SUBSCRIPTION / SUMMARY (snapshot)        -> active paid subs + active trials
//   - SUBSCRIPTION_EVENT / SUMMARY (last 30d)  -> new subscribes, trial conversions, cancels
// ES256 JWT (Node crypto, no SDK), gzipped TSV. Best-effort: surfaces Apple's error so we can
// fix the report version if needed. Returns { connected:false } when ASC env isn't set.
//
// All subs originate on the App Store (web is unlock-only), so this is complete coverage today.

import crypto from "crypto";
import zlib from "zlib";

let cache = null, cacheAt = 0;
const CACHE_MS = 2 * 60 * 60 * 1000;

function token(issuer, keyId, p8) {
  const key = p8.includes("\\n") ? p8.replace(/\\n/g, "\n") : p8;
  const now = Math.floor(Date.now() / 1000);
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
  const input = `${b64({ alg: "ES256", kid: keyId, typ: "JWT" })}.${b64({ iss: issuer, iat: now, exp: now + 19 * 60, aud: "appstoreconnect-v1" })}`;
  const sig = crypto.createSign("SHA256").update(input).sign({ key, dsaEncoding: "ieee-p1363" });
  return `${input}.${sig.toString("base64url")}`;
}

async function fetchReport(jwt, params) {
  const r = await fetch(`https://api.appstoreconnect.apple.com/v1/salesReports?${new URLSearchParams(params)}`, {
    headers: { Authorization: `Bearer ${jwt}`, Accept: "application/a-gzip" },
  });
  if (r.status === 404) return null;                                            // no report that day
  if (!r.ok) throw new Error(`${params["filter[reportType]"]} ${r.status}: ${(await r.text()).replace(/\s+/g, " ").slice(0, 600)}`);
  return zlib.gunzipSync(Buffer.from(await r.arrayBuffer())).toString("utf8");
}

function parse(raw) {
  const lines = raw.split("\n").filter(Boolean);
  const head = lines[0].split("\t").map((h) => h.trim());
  return { head, rows: lines.slice(1).map((l) => l.split("\t")), col: (n) => head.indexOf(n) };
}

const ymd = (base, off) => { const d = new Date(base); d.setUTCDate(d.getUTCDate() - off); return d.toISOString().slice(0, 10); };

export default async function handler(req, res) {
  const issuer = process.env.ASC_ISSUER_ID, keyId = process.env.ASC_KEY_ID, p8 = process.env.ASC_P8, vendor = process.env.ASC_VENDOR_NUMBER;
  if (!issuer || !keyId || !p8 || !vendor) return res.status(200).json({ connected: false });
  if (cache && Date.now() - cacheAt < CACHE_MS) { res.setHeader("cache-control", "no-store"); return res.status(200).json(cache); }

  const common = { "filter[frequency]": "DAILY", "filter[reportSubType]": "SUMMARY", "filter[vendorNumber]": vendor, "filter[version]": "1_4" };
  try {
    const jwt = token(issuer, keyId, p8);
    const base = new Date();

    // Snapshot: most recent SUBSCRIPTION report with data (active subs + trials)
    let active = 0, trials = 0, snapDate = null;
    const TRIAL_COLS = ["Active Free Trial Introductory Offer Subscriptions", "Active Pay As You Go Introductory Offer Subscriptions", "Active Pay Up Front Introductory Offer Subscriptions"];
    for (let i = 1; i <= 12; i++) {
      const raw = await fetchReport(jwt, { ...common, "filter[reportType]": "SUBSCRIPTION", "filter[reportDate]": ymd(base, i) });
      if (!raw) continue;
      const { rows, col } = parse(raw);
      const std = col("Active Standard Price Subscriptions");
      const tc = TRIAL_COLS.map(col);
      for (const r of rows) {
        if (std >= 0) active += Number(r[std] || 0) || 0;
        for (const c of tc) if (c >= 0) trials += Number(r[c] || 0) || 0;
      }
      snapDate = ymd(base, i);
      break;
    }

    // Events (last 30d): new subscribes, trial conversions, cancels
    const ev = { subscribe: 0, conversion: 0, cancel: 0 };
    const evRaw = await Promise.all(Array.from({ length: 30 }, (_, i) =>
      fetchReport(jwt, { ...common, "filter[reportType]": "SUBSCRIPTION_EVENT", "filter[reportDate]": ymd(base, i + 1) }).catch(() => null)));
    for (const raw of evRaw) {
      if (!raw) continue;
      const { rows, col } = parse(raw);
      const ei = col("Event"), qi = col("Quantity");
      if (ei < 0 || qi < 0) continue;
      for (const r of rows) {
        const e = (r[ei] || "").toLowerCase(), q = Number(r[qi] || 0) || 0;
        if (e.includes("cancel")) ev.cancel += q;
        else if (e.includes("conver")) ev.conversion += q;
        else if (e.includes("subscribe") || e.includes("introductory")) ev.subscribe += q;
      }
    }

    cache = { connected: true, updated: new Date().toISOString(), active, trials, snapDate, events30: ev };
    cacheAt = Date.now();
    res.setHeader("cache-control", "no-store");
    return res.status(200).json(cache);
  } catch (e) {
    return res.status(200).json({ connected: false, error: String(e.message || e).slice(0, 600) });
  }
}
