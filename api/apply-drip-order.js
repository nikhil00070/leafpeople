// /api/apply-drip-order — Save handler for the /articledrip page.
//
// The page POSTs { order: [{ slug, section }, ...] } — the curated drip sequence. We
// validate and forward to GitHub's workflow_dispatch for apply-drip-order.yml, which
// writes the order into articledrip/drip.json, rebuilds feed.json in that order (the
// phone's Stories drip), and commits. Mirrors /api/publish + /api/apply-images posture
// (uses GITHUB_TOKEN; /articledrip is noindex but otherwise unguarded).

const REPO_OWNER = "nikhil00070";
const REPO_NAME = "leafpeople";
const WORKFLOW = "apply-drip-order.yml";
const REF = "main";

const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,80}$/;
const SECTIONS = new Set(["the-leaf", "field-guide"]);

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const token = process.env.GITHUB_TOKEN;
  if (!token) return res.status(500).json({ error: "GITHUB_TOKEN not configured on the server." });

  const body = typeof req.body === "string" ? safeJson(req.body) : (req.body || {});
  const order = body.order;
  if (!Array.isArray(order) || !order.length) {
    return res.status(400).json({ error: "order array required" });
  }
  if (order.length > 1000) return res.status(400).json({ error: "order too long" });

  const clean = [];
  const seen = new Set();
  for (const x of order) {
    const slug = String((x && typeof x === "object") ? x.slug : x || "").trim();
    if (!SLUG_RE.test(slug)) return res.status(400).json({ error: `invalid slug: ${slug}` });
    if (seen.has(slug)) continue;                 // de-dupe defensively
    seen.add(slug);
    const section = (x && typeof x === "object" && x.section) ? String(x.section) : undefined;
    if (section && !SECTIONS.has(section)) return res.status(400).json({ error: `invalid section: ${section}` });
    clean.push(section ? { slug, section } : { slug });
  }
  if (!clean.length) return res.status(400).json({ error: "no valid slugs in order" });

  const url = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW}/dispatches`;
  const gh = await fetch(url, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "leafpeople-drip",
    },
    body: JSON.stringify({ ref: REF, inputs: { order: JSON.stringify(clean) } }),
  });

  if (gh.status === 204) return res.status(200).json({ ok: true, count: clean.length });
  const text = await gh.text();
  return res.status(gh.status).json({ error: "GitHub dispatch failed", status: gh.status, body: text.slice(0, 500) });
}

function safeJson(s) { try { return JSON.parse(s); } catch { return {}; } }
