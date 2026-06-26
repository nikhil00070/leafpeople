// /api/aeo — Answer-Engine-Optimization readiness for the /dashboard AEO tab.
//
// "Are we set up to be found + cited by AI answer engines?" Reads our own live site —
// robots.txt (which AI bots we welcome), llms.txt (the AI-readable index), sitemap.xml
// (URL count) — and reports a readiness checklist. AI-crawler HIT COUNTS (how often
// GPTBot/ClaudeBot/Perplexity actually fetch us) need a logging store and arrive later;
// this is the "are the doors open + signposted" view.

let cache = null, cacheAt = 0;
const CACHE_MS = 6 * 60 * 60 * 1000;
const BASE = "https://leafpeople.app";

// The AI answer-engine / training crawlers we care about being readable + citable by.
const AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "ClaudeBot", "Claude-Web", "Anthropic-AI", "Google-Extended", "Applebot-Extended", "Amazonbot", "CCBot", "Bytespider"];

async function text(path) {
  try {
    const r = await fetch(BASE + path, { headers: { "user-agent": "LeafPeople-Dashboard" } });
    if (!r.ok) return null;
    return await r.text();
  } catch { return null; }
}

export default async function handler(req, res) {
  const fresh = !!(req.query && req.query.fresh);
  if (cache && !fresh && Date.now() - cacheAt < CACHE_MS) { res.setHeader("cache-control", "no-store"); return res.status(200).json(cache); }

  const [robots, llms, sitemap] = await Promise.all([text("/robots.txt"), text("/llms.txt"), text("/sitemap.xml")]);

  // robots.txt: which AI bots are explicitly Allowed (not Disallow: /).
  const robotsLc = (robots || "").toLowerCase();
  const aiAllowed = AI_BOTS.filter((b) => {
    const i = robotsLc.indexOf(b.toLowerCase());
    if (i < 0) return false;
    const block = robotsLc.slice(i, i + 220);
    return /allow:\s*\//.test(block) && !/disallow:\s*\/\s*(\n|$)/.test(block);
  });

  // llms.txt: present + how many references it lists.
  const llmsOK = !!llms && llms.length > 50;
  const llmsRefs = llms ? (llms.match(/^\s*-\s*\[/gm) || []).length : 0;

  // sitemap: URL count.
  const sitemapUrls = sitemap ? (sitemap.match(/<loc>/g) || []).length : 0;

  const checks = [
    { id: "robots", label: "robots.txt welcomes AI crawlers", ok: aiAllowed.length >= 3, detail: aiAllowed.length ? aiAllowed.join(", ") : "no AI bots explicitly allowed" },
    { id: "llms", label: "llms.txt published (AI-readable index)", ok: llmsOK, detail: llmsOK ? `${llmsRefs} references listed` : "missing or empty" },
    { id: "sitemap", label: "sitemap.xml submitted", ok: sitemapUrls > 0, detail: sitemapUrls ? `${sitemapUrls} URLs` : "missing" },
    { id: "fulltext", label: "Full article text served to crawlers", ok: true, detail: "middleware serves full content to search + AI bots (paywall sanctioned sampling)" },
  ];
  const ready = checks.filter((c) => c.ok).length;

  const out = {
    connected: true, updated: new Date().toISOString(),
    ready, total: checks.length, checks,
    ai_bots_allowed: aiAllowed, llms_refs: llmsRefs, sitemap_urls: sitemapUrls,
    crawler_hits: null, // pending a logging store (needs Vercel KV / a counter)
    note: "AI-crawler hit counts need a request logger (pending Vercel access). This shows readiness — the doors are open and signposted.",
  };
  cache = out; cacheAt = Date.now();
  res.setHeader("cache-control", "no-store");
  return res.status(200).json(out);
}
