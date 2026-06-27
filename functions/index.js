/* Leaf People — RevenueCat webhook → Firebase `subscriber` custom claim.
 *
 * RevenueCat calls this on every subscription event. We set RevenueCat's App User ID = the
 * Firebase UID (done in the iOS app), so event.app_user_id IS the Firebase UID. We grant/revoke
 * the `subscriber` custom claim, which rides inside the user's ID token and is what the website's
 * edge middleware checks. Also mirrors to Firestore users/{uid} for visibility.
 *
 * Deploy: see DEPLOY.md. Auth: RevenueCat sends the configured Authorization header value, which
 * must equal the RC_WEBHOOK_AUTH secret.
 */
const { onRequest } = require("firebase-functions/v2/https");
const { defineSecret } = require("firebase-functions/params");
const admin = require("firebase-admin");

admin.initializeApp();
const RC_WEBHOOK_AUTH = defineSecret("RC_WEBHOOK_AUTH");

// Event types that mean the user currently HAS access vs has LOST it.
// CANCELLATION is intentionally ignored — access continues until EXPIRATION fires.
const GRANTS = new Set([
  "INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION", "PRODUCT_CHANGE",
  "NON_RENEWING_PURCHASE", "SUBSCRIPTION_EXTENDED", "TEMPORARY_ENTITLEMENT_GRANT",
]);
const REVOKES = new Set(["EXPIRATION", "REFUND"]);

exports.revenuecatWebhook = onRequest({ secrets: [RC_WEBHOOK_AUTH], invoker: "public" }, async (req, res) => {
  if (req.method !== "POST") return res.status(405).send("POST only");
  if ((req.get("authorization") || "") !== RC_WEBHOOK_AUTH.value()) {
    return res.status(401).send("unauthorized");
  }

  const event = (req.body && req.body.event) || {};
  const uid = event.app_user_id;
  const type = event.type;
  if (!uid || !type) return res.status(200).send("ignored: missing uid/type");
  if (uid.startsWith("$RCAnonymousID:")) return res.status(200).send("ignored: anonymous id");

  let subscriber;
  if (GRANTS.has(type)) subscriber = true;
  else if (REVOKES.has(type)) subscriber = false;
  else return res.status(200).send("ignored: " + type); // CANCELLATION, BILLING_ISSUE, TEST…

  try {
    const user = await admin.auth().getUser(uid);
    const claims = Object.assign({}, user.customClaims || {});
    if (claims.subscriber !== subscriber) {
      claims.subscriber = subscriber;
      await admin.auth().setCustomUserClaims(uid, claims);
    }
    await admin.firestore().doc("users/" + uid).set(
      { subscriber, subscriberUpdatedAt: admin.firestore.FieldValue.serverTimestamp() },
      { merge: true }
    ).catch(() => {});
    return res.status(200).send("ok: " + uid + " subscriber=" + subscriber);
  } catch (e) {
    if (e.code === "auth/user-not-found") {
      // The purchase happened before the user signed into Firebase Auth, or under a different id.
      return res.status(200).send("no firebase user: " + uid);
    }
    console.error("revenuecatWebhook", e);
    return res.status(500).send("error");
  }
});

/* Leaf People — plant-ID proxy. Holds the Anthropic key SERVER-SIDE so it never ships in the
 * app binary. The app builds the full Anthropic /v1/messages body (prompt + reference/query
 * images) and POSTs it here with a Firebase ID token. We verify the token, PIN the model and
 * CAP max_tokens (so a leaked client can't run arbitrary large Claude jobs on our key), then
 * forward to Anthropic with the secret key and pass the JSON straight back.
 *
 * Secret:  firebase functions:secrets:set ANTHROPIC_API_KEY
 * Gate:    any valid Firebase ID token (anonymous or signed-in). The app signs in anonymously
 *          if there's no user yet, so ID still works without an explicit account.
 * To tune the model/prompt later: change CLAUDE_MODEL here and redeploy — no app build needed.
 */
const ANTHROPIC_API_KEY = defineSecret("ANTHROPIC_API_KEY");
const CLAUDE_MODEL = "claude-sonnet-4-6";   // mirrors APIConfig.claudeModel; pinned server-side
const CLAUDE_MAX_TOKENS = 1024;

exports.identifyPlant = onRequest(
  { secrets: [ANTHROPIC_API_KEY], invoker: "public", memory: "512MiB", timeoutSeconds: 120 },
  async (req, res) => {
    if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

    // Gate: a valid Firebase ID token (anonymous counts). Without this the proxy would be an
    // open Claude faucet on our account.
    const m = (req.get("authorization") || "").match(/^Bearer (.+)$/i);
    if (!m) return res.status(401).json({ error: "missing auth token" });
    try {
      await admin.auth().verifyIdToken(m[1]);
    } catch {
      return res.status(401).json({ error: "invalid auth token" });
    }

    // Keep the app's messages/system, but pin model + cap tokens server-side.
    const body = (req.body && typeof req.body === "object") ? req.body : {};
    if (!Array.isArray(body.messages)) return res.status(400).json({ error: "missing messages" });
    body.model = CLAUDE_MODEL;
    body.max_tokens = Math.min(Number(body.max_tokens) || CLAUDE_MAX_TOKENS, CLAUDE_MAX_TOKENS);

    try {
      const r = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "x-api-key": ANTHROPIC_API_KEY.value(),
          "anthropic-version": "2023-06-01",
          "content-type": "application/json",
        },
        body: JSON.stringify(body),
      });
      const text = await r.text();   // pass Anthropic's JSON straight through; the app parses it
      return res.status(r.status).set("content-type", "application/json").send(text);
    } catch (e) {
      console.error("identifyPlant upstream", e);
      return res.status(502).json({ error: "upstream error" });
    }
  }
);
