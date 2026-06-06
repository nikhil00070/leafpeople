// /api/apply-ig-images — "Save image choices" handler for the /instagram planner.
//
// The page POSTs { selections: { "<post_id>": "/images/...", ... } } (the curated
// image picks held in localStorage). We validate and forward to GitHub's
// workflow_dispatch for apply-instagram-images.yml, which writes each post's
// `image` in instagram/posts.json and commits — so auto-posting uses the picks,
// not the seeded defaults. Mirrors /api/apply-images.

const REPO_OWNER = "nikhil00070";
const REPO_NAME = "leafpeople";
const WORKFLOW = "apply-instagram-images.yml";
const REF = "main";

const ID_RE = /^[a-z0-9][a-z0-9._-]{1,80}$/i;        // post ids like "d01" … "d213"
const SRC_LOCAL = /^\/images\/[A-Za-z0-9._\/-]{3,200}\.(jpg|jpeg|png|webp)$/i;
const SRC_INAT = /^https:\/\/(inaturalist-open-data\.s3\.amazonaws\.com|static\.inaturalist\.org)\/photos\/\d+\/(large|original|medium)\.(jpe?g|png)(\?.*)?$/i;
const validSrc = (v) => SRC_LOCAL.test(v) || SRC_INAT.test(v);

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
    const id = String(k);
    if (!ID_RE.test(id)) return res.status(400).json({ error: `invalid post id: ${k}` });
    if (typeof v !== "string" || !validSrc(v)) {
      return res.status(400).json({ error: `invalid image for ${id}: ${v}` });
    }
    clean[id] = v;
  }
  const n = Object.keys(clean).length;
  if (!n) return res.status(400).json({ error: "no valid selections" });
  if (n > 250) return res.status(400).json({ error: "too many selections" });

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
