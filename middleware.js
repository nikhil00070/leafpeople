/* Leaf People — Edge Middleware (Phase 3 enforcement)
 *
 * Gates Understory + Field Guide ARTICLE pages. Subscribers get the full index.html;
 * everyone else is rewritten to the article's preview.html (free section + wall). The full
 * text lives only in index.html, so non-subscribers never receive it — real server-side
 * withholding, not CSS hiding.
 *
 * Entitlement = the `subscriber` custom claim inside the Firebase ID token (cookie __lpAuth),
 * which js/auth.js keeps fresh. We verify the token's RS256 signature against Google's public
 * keys (Web Crypto, no deps), then read the claim. A comma-separated LP_SUBSCRIBER_UIDS env
 * var is an additional allowlist (for comps / testing before the app bridge exists).
 *
 * SAFETY:
 *   - Dormant unless LP_PAYWALL === "on" (default: pass everything through unchanged).
 *   - Fail-OPEN: any unexpected error serves the normal page (never blocks a real reader).
 *   - Only ever rewrites bare article paths (/the-leaf/<slug>, /field-guide/<slug>); never
 *     files (manifest.json, _data.json), section indexes, or the preview itself (no loops).
 */

export const config = {
  matcher: ["/the-leaf/:slug", "/field-guide/:slug"],
};

const ARTICLE = /^\/(the-leaf|field-guide)\/[^/.]+$/; // one slug segment, no dot (so not *.json)
// Verified search + AI crawlers get the FULL article (Google flexible sampling, paired with the
// isAccessibleForFree:false paywall schema in the page — sanctioned, not cloaking). This is what
// makes the 179 articles indexable + citable by search engines and AI answer engines.
const CRAWLER_UA = /(googlebot|google-inspectiontool|storebot-google|google-extended|bingbot|slurp|duckduckbot|baiduspider|yandex|applebot|gptbot|oai-searchbot|chatgpt-user|perplexitybot|claudebot|claude-web|anthropic-ai|amazonbot|bytespider|ccbot|facebookexternalhit|twitterbot|linkedinbot)/i;
const JWK_URL =
  "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com";
const PROJECT_ID = "leafpeople-1c8d1";

let jwksCache = null;
let jwksAt = 0;

// AEO crawler logging — which AI answer engines actually fetch our content. Map a
// user-agent to a clean bot name; /api/seo reads the KV counters for the dashboard.
const AI_BOT_NAMES = [
  ["gptbot", "GPTBot"], ["oai-searchbot", "OAI-SearchBot"], ["chatgpt-user", "ChatGPT-User"],
  ["perplexitybot", "PerplexityBot"], ["claudebot", "ClaudeBot"], ["claude-web", "Claude-Web"],
  ["anthropic-ai", "Anthropic-AI"], ["google-extended", "Google-Extended"], ["applebot-extended", "Applebot-Extended"],
  ["amazonbot", "Amazonbot"], ["ccbot", "CCBot"], ["bytespider", "Bytespider"],
];
function aiBotName(ua) {
  const s = (ua || "").toLowerCase();
  for (const [needle, name] of AI_BOT_NAMES) if (s.includes(needle)) return name;
  return null;
}
// Fire-and-forget INCR via the Vercel KV (Upstash) REST API — no package needed.
function kvIncr(key) {
  const url = process.env.KV_REST_API_URL, tok = process.env.KV_REST_API_TOKEN;
  if (!url || !tok) return Promise.resolve();
  return fetch(`${url}/incr/${encodeURIComponent(key)}`, { headers: { Authorization: `Bearer ${tok}` } }).catch(() => {});
}

export default async function middleware(request, context) {
  // AEO: log AI-crawler fetches regardless of paywall state (runs before the dormant check).
  try {
    const bot = aiBotName(request.headers.get("user-agent"));
    if (bot) {
      const day = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      const p = Promise.all([kvIncr(`aeo:hit:${bot}`), kvIncr(`aeo:hit:${bot}:${day}`)]);
      if (context && context.waitUntil) context.waitUntil(p);
    }
  } catch { /* never let logging affect the response */ }

  try {
    const flag = (process.env.LP_PAYWALL || "").trim().toLowerCase();
    if (flag !== "on") return; // dormant -> serve normally

    const url = new URL(request.url);
    if (!ARTICLE.test(url.pathname)) return; // not a gated article page

    // Crawlers (search + AI) get the full page so it can be indexed and cited; humans still gated.
    if (CRAWLER_UA.test(request.headers.get("user-agent") || "")) return;

    const token = readCookie(request, "__lpAuth");
    if (await isSubscriber(token)) return; // verified subscriber -> full page

    // Non-subscriber -> serve the preview file's HTML at the same URL. We FETCH it (a different
    // path, not matched by the matcher, so no loop) rather than relying on a rewrite header.
    const previewURL = new URL(url.pathname.replace(/\/$/, "") + "/preview", url.origin);
    const res = await fetch(previewURL.toString(), { headers: { "x-lp-internal": "1" } });
    const html = await res.text();
    return new Response(html, {
      status: 200,
      headers: {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "private, no-store",
        "x-lp-gated": "1", // debug marker so we can confirm the gate fired
      },
    });
  } catch (_) {
    return; // fail open — serve the normal page on any error
  }
}

function readCookie(request, name) {
  const raw = request.headers.get("cookie") || "";
  const m = raw.match(new RegExp("(?:^|;\\s*)" + name + "=([^;]+)"));
  return m ? decodeURIComponent(m[1]) : null;
}

async function isSubscriber(token) {
  const payload = token ? await verifyFirebaseIdToken(token) : null;
  if (!payload) return false;
  if (payload.subscriber === true) return true;
  const allow = (process.env.LP_SUBSCRIBER_UIDS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const uid = payload.user_id || payload.sub;
  return allow.includes(uid);
}

async function verifyFirebaseIdToken(token) {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const header = JSON.parse(b64urlToText(parts[0]));
  const payload = JSON.parse(b64urlToText(parts[1]));
  if (header.alg !== "RS256" || !header.kid) return null;

  // Standard Firebase ID-token claim checks.
  const now = Math.floor(Date.now() / 1000);
  if (payload.aud !== PROJECT_ID) return null;
  if (payload.iss !== "https://securetoken.google.com/" + PROJECT_ID) return null;
  if (!payload.sub || payload.exp <= now || payload.iat > now + 300) return null;

  const jwk = await getJwk(header.kid);
  if (!jwk) return null;
  const key = await crypto.subtle.importKey(
    "jwk",
    { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"]
  );
  const ok = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    b64urlToBytes(parts[2]),
    new TextEncoder().encode(parts[0] + "." + parts[1])
  );
  return ok ? payload : null;
}

async function getJwk(kid) {
  const now = Date.now();
  if (!jwksCache || now - jwksAt > 3600_000) {
    const res = await fetch(JWK_URL);
    jwksCache = (await res.json()).keys || [];
    jwksAt = now;
  }
  return jwksCache.find((k) => k.kid === kid) || null;
}

function b64urlToBytes(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  const pad = s.length % 4;
  if (pad) s += "=".repeat(4 - pad);
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function b64urlToText(s) {
  return new TextDecoder().decode(b64urlToBytes(s));
}
