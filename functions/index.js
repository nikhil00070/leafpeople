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
