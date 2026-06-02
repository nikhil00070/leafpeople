// /api/apply-images — Finalize handler for the /review-images curation page.
//
// The page POSTs { selections: { "<slug>": "/images/...", ... } }. We validate and forward
// to GitHub's workflow_dispatch for apply-article-images.yml, which sets each article's body
// image, re-renders, and commits. Mirrors /api/publish's posture (uses GITHUB_TOKEN; /review*
// pages are noindex but otherwise unguarded).

const REPO_OWNER = "nikhil00070";
const REPO_NAME = "leafpeople";
const WORKFLOW = "apply-article-images.yml";
const REF = "main";

const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,80}$/;
const SRC_RE = /^\/images\/[A-Za-z0-9._\/-]{3,200}\.(jpg|jpeg|png|webp)$/;

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const token = process.env.GITHUB_TOKEN;
  if (!token) return res.status(500).json({ error: "GITHUB_TOKEN not configured on the server." });

  const body = typeof req.body === "string" ? safeJson(req.body) : (req.body || {});
  const sel = body.selections;
  if (!sel || typeof sel !== "object" || Array.isArray(sel)) {
    return res.status(400).json({ error: "selections object required" });
  }

  const clean = {};
  for (const [k, v] of Object.entries(sel)) {
    const slug = String(k).split("/").pop();
    if (!SLUG_RE.test(slug) || typeof v !== "string" || !SRC_RE.test(v)) {
      return res.status(400).json({ error: `invalid selection: ${k} -> ${v}` });
    }
    clean[slug] = v;
  }
  const n = Object.keys(clean).length;
  if (!n) return res.status(400).json({ error: "no valid selections" });
  if (n > 200) return res.status(400).json({ error: "too many selections" });

  const url = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW}/dispatches`;
  const gh = await fetch(url, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "leafpeople-curate",
    },
    body: JSON.stringify({ ref: REF, inputs: { selections: JSON.stringify(clean) } }),
  });

  if (gh.status === 204) return res.status(200).json({ ok: true, count: n });
  const text = await gh.text();
  return res.status(gh.status).json({ error: "GitHub dispatch failed", status: gh.status, body: text.slice(0, 500) });
}

function safeJson(s) { try { return JSON.parse(s); } catch { return {}; } }
