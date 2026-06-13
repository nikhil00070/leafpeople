// /api/run-insights — the /dashboard "Refresh Instagram numbers" button.
//
// Dispatches the ig-insights.yml workflow, which pulls Graph API insights and commits
// instagram/insights.json (the dashboard then renders it). Mirrors /api/publish posture
// (GITHUB_TOKEN; /dashboard is noindex but otherwise unguarded).

const REPO_OWNER = "nikhil00070";
const REPO_NAME = "leafpeople";
const WORKFLOW = "ig-insights.yml";
const REF = "main";

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const token = process.env.GITHUB_TOKEN;
  if (!token) return res.status(500).json({ error: "GITHUB_TOKEN not configured on the server." });

  const body = typeof req.body === "string" ? safeJson(req.body) : (req.body || {});
  let limit = parseInt(body.limit, 10);
  if (!Number.isFinite(limit) || limit < 1 || limit > 200) limit = 40;

  const url = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW}/dispatches`;
  const gh = await fetch(url, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "leafpeople-dashboard",
    },
    body: JSON.stringify({ ref: REF, inputs: { limit: String(limit) } }),
  });

  if (gh.status === 204) return res.status(200).json({ ok: true, limit });
  const text = await gh.text();
  return res.status(gh.status).json({ error: "GitHub dispatch failed", status: gh.status, body: text.slice(0, 500) });
}

function safeJson(s) { try { return JSON.parse(s); } catch { return {}; } }
