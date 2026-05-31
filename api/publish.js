// /api/publish — one-tap publish/reject for the /review page.
//
// The /review JS posts { slug, action } here; we forward it to GitHub's
// workflow_dispatch API with the slug baked in, so the user never has to
// type it into the Actions form. The publish.yml workflow then runs
// publish.py, which flips the manifest status and commits + pushes — and
// Vercel redeploys from the new main automatically.
//
// Env vars (set in Vercel project settings):
//   GITHUB_TOKEN  – fine-grained personal access token with Actions: Read+Write
//                   on nikhil00070/leafpeople. Never exposed client-side.
//
// Security: /review itself is noindex but otherwise unguarded; this matches
// that posture (any traffic that reaches /review can hit /api/publish).
// If we ever expose /review more broadly, gate this with a shared secret.

const REPO_OWNER = "nikhil00070";
const REPO_NAME  = "leafpeople";
const WORKFLOW   = "publish.yml";
const REF        = "main";

// Allow only <section>/<slug> with conservative chars — prevents anyone from
// shoving arbitrary strings into the workflow input.
const SLUG_RE = /^(the-leaf|field-guide)\/[a-z0-9][a-z0-9-]{1,80}$/;
const ALLOWED_ACTIONS = new Set(["publish", "reject"]);

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "POST only" });
  }
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return res.status(500).json({ error: "GITHUB_TOKEN not configured on the server." });
  }

  // Vercel parses JSON bodies automatically when content-type is application/json.
  const body = typeof req.body === "string" ? safeJson(req.body) : (req.body || {});
  const slug = (body.slug || "").trim();
  const action = (body.action || "publish").trim();

  if (!SLUG_RE.test(slug)) {
    return res.status(400).json({ error: `Invalid slug: ${slug}` });
  }
  if (!ALLOWED_ACTIONS.has(action)) {
    return res.status(400).json({ error: `Invalid action: ${action}` });
  }

  const url = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW}/dispatches`;
  const gh = await fetch(url, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "leafpeople-review",
    },
    body: JSON.stringify({
      ref: REF,
      inputs: { slug, action },
    }),
  });

  if (gh.status === 204) {
    // GitHub returns 204 No Content on a successful dispatch.
    return res.status(200).json({ ok: true, slug, action });
  }

  const text = await gh.text();
  return res.status(gh.status).json({
    error: "GitHub dispatch failed",
    status: gh.status,
    body: text.slice(0, 500),
  });
}

function safeJson(s) {
  try { return JSON.parse(s); } catch { return {}; }
}
