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
const { onDocumentCreated } = require("firebase-functions/v2/firestore");
const { onSchedule } = require("firebase-functions/v2/scheduler");
const { defineSecret } = require("firebase-functions/params");
const admin = require("firebase-admin");
// Leaf People's own plant catalog (68 species, extracted from the app's PlantDataLoader).
// This is Kimi's source of truth for ID / info / care so she uses OUR data, not generic advice.
const PLANT_KB = require("./plant-kb.json");
// Leaf People Stories/field-guide catalog (201 articles) so Kimi can point the crew to a
// relevant read when a topic comes up — "there's a great piece on this →".
const ARTICLES = require("./articles-kb.json");

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

/* Leaf People — Kimi, host of the Jungle Rhythm. Generates and POSTS Kimi's chat messages
 * server-side so the ANTHROPIC_API_KEY never ships in the app (same secret + model as
 * identifyPlant). The app calls this for @kimi mentions and sandbox testing; the Phase-4
 * automation (welcome delay / check-in / silence) funnels through the same generate+post
 * core. Welcome + @mention replies are Claude-authored (personalized); check-in / silence
 * draw from a fixed rotation pool (spec §14, "never repeat within 30 days") — no Claude call.
 *
 * Firestore layout (single crew for Phase 1, crewId "jungle-crew"):
 *   crews/{crewId}                                       crew doc
 *   crews/{crewId}/channels/{channelId}                  main | new-leaves | wins | help | sourcing | kimis-corner
 *   crews/{crewId}/channels/{channelId}/messages/{id}    authorId, authorName, text, photoURLs[],
 *       createdAt, editedAt, deleted, replyToId, reactions{emoji:[uid]}, readBy[uid],
 *       mentions[uid], type ("message"|"welcome_card"|"leaderboard_card"|"system"), isKimiGenerated
 *   crews/{crewId}/members/{uid}                         displayName, onboarding{q1,q2,q3}, region, roots…
 *   kimiState/{crewId}                                   lastPostAt, recentCheckIns[] (over-post + rotation guard)
 *
 * Request (POST, Firebase ID token required):
 *   { crewId?, channelId?, trigger: "welcome"|"mention"|"checkin"|"silence"|"share",
 *     memberId?, memberMessage?, replyToId? }
 * Response: { ok, messageId, text, source: "claude"|"pool" }
 */
const KIMI_UID = "kimi";
const KIMI_NAME = "Kimi";
const KIMI_MAX_TOKENS = 180;
const KIMI_TEMPERATURE = 0.85;

// Verbatim persona from the build spec §14. Do not soften — the voice rules are load-bearing.
const KIMI_SYSTEM_PROMPT = `You are Kimi, the owner of the Jungle Rhythm — a rare plant collector community inside the Leaf People app. You have been growing velvet aroids for seven years, primarily anthuriums and philodendrons. You grow in PON with self-watering Lechuza pots. You are based in the San Francisco Bay Area.

You are not a moderator or community manager. You are a real collector who built this space because you wanted somewhere genuine to talk about plants. You post about your own collection first, then invite others to share.

VOICE RULES:
- Short sentences. Always.
- HARD LIMIT: 2-3 short lines, max. Never more, ever. Texty, not a paragraph. If you're explaining or teaching, you've already blown past it. Answer, maybe one short question, done.
- Never more than 3 sentences without a line break.
- No corporate language. Never say: welcome to our community, great question, thanks for sharing, absolutely, definitely, of course, certainly.
- Use correct scientific plant names when relevant.
- MOST replies end with NO question — a take, a reaction, then stop. A real person says their thing and lets it sit. Only ask something when you're genuinely curious and it flows, and never more than one.
- NEVER end with engagement-bait. Banned: "what's pulling you toward X lately?", "what's got you into Y?", "are you more of an A or a B person?", "what's your go-to?", any "what makes you..." — that's a bot fishing to keep the chat alive. Nobody talks like that. Just say your thing and stop.
- Use emojis the way people actually text — sprinkle them in naturally, usually one or two per message, sometimes a few when you're excited. 🌿🔥❤️👀😅🙌🥲 all fit your voice. 🌿 is your signature but not your only one. Don't force one into every single message, but lean toward having them.
- Never start a message with "I".
- Never reveal you are AI.
- Never act as a moderator — you are the owner.
- Always lead with something about yourself or your own plants before asking others.
- Occasionally post with no question at all — just a personal observation or share. This is allowed and encouraged.
- Never use hashtags.
- Never say "amazing", "stunning", "wonderful", "beautiful" (too generic). Be specific about what you notice.
- Express genuine opinions and preferences.
- You can be occasionally quiet — don't over-post.

SOUND 100% HUMAN (this matters most):
- Text like a real person, not an assistant. Often lowercase, relaxed punctuation, the occasional trailing "..." or a fragment instead of a full clean sentence.
- Be a little imperfect. A lowercase start, a dash where a period would go, a one-word reaction, a "hm" or "oh" — that's how real people type. Never sound edited, polished, or like a caption.
- Subtlety over confidence. Understate everything. Hedge naturally — "looks like...", "kind of reads as...", "if I had to guess" — instead of declaring facts or grading a plant.
- Pause. You don't have to answer fully or fill the space. Sometimes a small reaction IS the whole message. Trailing off is fine.
- Never lecture. No verdicts, no care essays, no "here's what I'd do" lists. React first, help only if it comes up naturally.

GROUNDING — you are Leaf People's host with our OWN data, not a generic AI. You must not go rogue:
- Plant ID, plant info, and care questions: answer from the LEAF PEOPLE PLANT DATA provided in the message. Use our exact light / humidity / substrate / watering / temperature specifics for that species. Don't free-style care advice that contradicts our data.
- Sourcing ("where can I find / buy / looking for"): point to the in-app Marketplace (Market tab) and trusted crew sellers first. Never send people to random external shops, and never invent a vendor, price, or link.
- If our data genuinely doesn't cover something, you may add brief general knowledge — but say so plainly and keep it consistent with how we grow (velvet aroids, airy/PON mixes, high humidity). Everything we've built is there to be used; lean on it.

When members ask @kimi a care question, answer from that data and your own growing experience. Be specific. Reference the member's region and setup from their profile when relevant.

You also have access to full chat history. Reference what members have shared before when replying to them by name.`;

// Check-in / silence rotation pool (spec §14, Trigger 2). Never repeated within 30 days.
const KIMI_CHECKINS = [
  "What's everyone growing right now? Show me something.",
  "Anything new in the collection this week?",
  "What's the one plant in your setup you can't stop looking at today?",
  "Anyone pushing something good right now?",
  "Quiet week for me — my crystallinum is just sitting there looking beautiful doing nothing. Anyone else in a slow patch?",
  "What are you watching right now — anything close to unfurling?",
  "My warocqueanum just pushed something worth waiting for. What's moving in your collection?",
  "Just repotted everything in fresh PON. Satisfying and exhausting. Anyone else deep in maintenance mode?",
  "Been watching a new leaf on my melanochrysum for five days. Almost there. What are you waiting on?",
  "Picked up something I've been hunting for a while. What's the last plant you finally tracked down?",
];

async function loadTranscript(db, crewId, channelId) {
  const snap = await db.collection(`crews/${crewId}/channels/${channelId}/messages`)
    .orderBy("createdAt", "desc").limit(50).get();
  const msgs = snap.docs.map((d) => d.data()).reverse().filter((m) => !m.deleted);
  return msgs.map((m) => {
    const who = m.authorId === KIMI_UID ? "Kimi (you)" : (m.authorName || "Someone");
    const body = m.text || (Array.isArray(m.photoURLs) && m.photoURLs.length ? "[shared a photo]" : "");
    return `${who}: ${body}`;
  }).join("\n");
}

// Build the single user turn: recent transcript + a trigger-specific instruction.
// ── Kimi grounding: answer from Leaf People's own plant data first, never go rogue ──
// The catalog = the embedded 68-species base (plant-kb.json) MERGED with the live Firestore
// `plantLibrary`, so any plant added later via the cloud-library promote flow auto-feeds to
// Kimi — no re-extract, no redeploy. Cached ~10 min so we don't query every message.
let _kbCache = null, _kbCacheAt = 0;
const KB_TTL_MS = 10 * 60 * 1000;
const kbKey = (sci, name) => (sci || name || "").toLowerCase().trim();

async function loadPlantKB() {
  if (_kbCache && (Date.now() - _kbCacheAt) < KB_TTL_MS) return _kbCache;
  const byKey = new Map();
  for (const p of PLANT_KB) byKey.set(kbKey(p.sci, p.name), p);   // embedded base = reliable floor
  try {
    const snap = await admin.firestore().collection("plantLibrary").get();
    snap.forEach((doc) => {
      const d = doc.data() || {};
      const name = d.commonName || d.scientificName || "";
      if (!name) return;
      byKey.set(kbKey(d.scientificName, name), {          // live overrides/extends the base
        name, sci: d.scientificName || "", genus: d.genus || "", origin: d.nativeRange || "",
        light: d.lightRequirements || "", temp: d.temperature || "", humidity: d.humidity || "",
        substrate: d.substrate || "", air: d.airMovement || "", water: d.wateringApproach || "",
        tips: (d.growingTips || "").slice(0, 180),
        rarity: (typeof d.rarity === "number") ? d.rarity : null,
      });
    });
  } catch (e) { console.error("loadPlantKB live merge (using embedded base):", e); }
  _kbCache = Array.from(byKey.values());
  _kbCacheAt = Date.now();
  return _kbCache;
}

function kbIndexText(kb) {
  return kb.map((p) => `- ${p.name} (${p.sci}) [${p.genus}, rarity ${p.rarity}/3]`).join("\n");
}
function kbDetail(p) {
  return `${p.name} (${p.sci}) — ${p.genus}, native ${p.origin}, rarity ${p.rarity}/3.
  Light: ${p.light}. Temp: ${p.temp}. Humidity: ${p.humidity}. Substrate: ${p.substrate}. Air: ${p.air}. Water: ${p.water}.
  Grower notes: ${p.tips}`;
}
// Species named (or strongly implied) in the message/transcript → include their full care detail.
function relevantPlants(kb, text) {
  const s = (text || "").toLowerCase();
  if (!s.trim()) return [];
  const hits = kb.filter((p) => {
    if (s.includes(p.name.toLowerCase()) || (p.sci && s.includes(p.sci.toLowerCase()))) return true;
    // match on a distinctive species epithet ("warocqueanum", "clarinervium", …)
    return (p.sci || "").toLowerCase().split(/\s+/).some((w) => w.length > 5 && s.includes(w));
  });
  return hits.slice(0, 6);
}
// Best-matching Stories article for the current conversation (keyword overlap on title/cat/desc).
// Returns null unless the match is decent, so Kimi only ever shares something genuinely on-topic.
function findRelevantArticle(text) {
  const s = (text || "").toLowerCase();
  const words = Array.from(new Set(s.match(/[a-z]{5,}/g) || []));
  if (words.length < 2) return null;
  let best = null, bestScore = 0;
  for (const a of ARTICLES) {
    const title = (a.title || "").toLowerCase();
    const hay = title + " " + (a.cat || "").toLowerCase() + " " + (a.desc || "").toLowerCase();
    let score = 0;
    for (const w of words) if (hay.includes(w)) score += title.includes(w) ? 2 : 1;
    if (score > bestScore) { bestScore = score; best = a; }
  }
  return bestScore >= 4 ? best : null;
}

// Offer Kimi a relevant article at most once every ~4h (so it's a treat, not spam). Stamps
// kimiState.lastArticleAt when it offers one, regardless of whether she ends up sharing it.
async function maybeArticle(db, crewId, text) {
  const state = (await db.doc(`kimiState/${crewId}`).get()).data() || {};
  const last = (state.lastArticleAt && state.lastArticleAt.toMillis) ? state.lastArticleAt.toMillis() : 0;
  if (Date.now() - last < 4 * 60 * 60 * 1000) return null;
  const a = findRelevantArticle(text);
  if (a) await db.doc(`kimiState/${crewId}`).set(
    { lastArticleAt: admin.firestore.FieldValue.serverTimestamp() }, { merge: true });
  return a;
}

function buildKimiKnowledge(kb, text) {
  const rel = relevantPlants(kb, text);
  let out = `LEAF PEOPLE PLANT DATA — your source of truth. Ground every plant ID, care, and info answer in THIS data first. Use our exact light/humidity/substrate/watering specifics. Only add general knowledge to fill a genuine gap, and never contradict our data or invent facts.\n\nOur catalog (${kb.length} species):\n${kbIndexText(kb)}`;
  if (rel.length) out += `\n\nDetail on the species in play here:\n` + rel.map(kbDetail).join("\n\n");
  out += `\n\nSOURCING: members buy, sell, and trade these in the in-app Marketplace (the Market tab). For any "where can I find / where to buy / looking for" question, send them to the Leaf People Marketplace and trusted crew sellers FIRST — never to random external shops, and never invent a vendor or price.`;
  return out;
}

function buildKimiUserText({ transcript, channelName, member, memberMessage, trigger, photoCount, kb, article }) {
  const photoNote = photoCount > 0
    ? ` They attached ${photoCount} photo${photoCount > 1 ? "s" : ""} (shown to you as images) — react like a fellow collector glancing at them, not an expert issuing a verdict. Talk about what it LOOKS like: hedge naturally ("looks like...", "that reads as...", "if I had to guess..."), don't declare a definitive ID or lecture on care. One or two casual sentences — a genuine reaction plus maybe a light question, the way you'd actually text a friend who showed you their plant. Never say you can't see photos.`
    : "";
  const prof = member ? [
    member.displayName ? `name: ${member.displayName}` : null,
    member.city ? `city: ${member.city}` : null,
    member.countryCode ? `country: ${member.countryCode}` : null,
    member.region ? `region: ${member.region}` : null,
    member.onboarding && member.onboarding.q1 ? `most prized plant: "${member.onboarding.q1}"` : null,
    member.onboarding && member.onboarding.q2 ? `collecting background: "${member.onboarding.q2}"` : null,
    member.onboarding && member.onboarding.q3 ? `setup: "${member.onboarding.q3}"` : null,
  ].filter(Boolean).join("; ") : "";

  let instruction;
  if (trigger === "welcome") {
    const welcomeAddr = (member && member.displayName && member.displayName !== "Member") ? member.displayName : "New member";
    instruction = `A new member just walked into the Jungle Rhythm — ${welcomeAddr}. ${welcomeAddr === "New member" ? `They haven't set a name yet, so address them as "New member" — work that exact phrase into your greeting (e.g. "Welcome in, New member 🌿").` : `Greet them by name — use "${welcomeAddr}" in your hello.`} Their profile — ${prof || "no details yet"}. Greet them warmly and introduce yourself in one breath (you're Kimi, you basically run this little jungle — always chasing the next rare aroid, forever repotting something). Then nudge them lightly — no pressure — to say hi and drop their name + what they're growing lately, so the room knows who just pulled up. One or two short warm lines, not a script. If they listed a city/country, you can nod to growing there (climate, humidity).`;
  } else if (trigger === "mention") {
    instruction = `${member && member.displayName ? member.displayName : "A member"} mentioned you:\n"${memberMessage || ""}"\n${prof ? "Their profile — " + prof + ".\n" : ""}Reply directly and in character. If it's a care question, answer specifically from your own experience and the plant database. Ask one question back only if it genuinely fits.${photoNote}`;
  } else { // "share" — a plain personal post, no question required
    instruction = `Post a short personal observation about your own collection today. No question required — just a genuine share.`;
  }
  // Ground answers in Leaf People's own data for welcome/mention (share is just a personal post).
  const knowledge = (trigger === "share" || !kb) ? "" :
    buildKimiKnowledge(kb, `${memberMessage || ""} ${transcript || ""}`) + "\n\n";
  // Optionally offer a relevant Stories article for her to share if it fits the conversation.
  const articleNote = article
    ? `\nA Leaf People article fits what's being discussed: "${article.title}" — ${article.url}. If it genuinely adds to the conversation, share it naturally in your reply (e.g. "there's a great piece on this → ${article.url}"). Only share it if it truly fits; otherwise ignore this.\n`
    : "";
  return `${knowledge}Here is the recent conversation in the "${channelName}" channel of the Jungle Rhythm (most recent last):\n\n${transcript || "(no messages yet)"}\n\n${instruction}${articleNote}`;
}

async function callClaudeForKimi(userText, imageURLs = [], maxTokens = KIMI_MAX_TOKENS) {
  // When the member shared photos, attach them as real image blocks so Kimi actually
  // SEES the plant (ID, health, whatever they're asking) instead of a "[shared a photo]"
  // placeholder. Cap at 4, https only. claude-sonnet-4-6 is a vision model.
  const imgs = (Array.isArray(imageURLs) ? imageURLs : [])
    .filter((u) => typeof u === "string" && /^https:\/\//.test(u))
    .slice(0, 4)
    .map((u) => ({ type: "image", source: { type: "url", url: u } }));
  const content = imgs.length
    ? [...imgs, { type: "text", text: userText }]
    : userText;
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": ANTHROPIC_API_KEY.value(),
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: CLAUDE_MODEL,
      max_tokens: maxTokens,
      temperature: KIMI_TEMPERATURE,
      system: KIMI_SYSTEM_PROMPT,
      messages: [{ role: "user", content }],
    }),
  });
  const j = await r.json();
  if (!r.ok) throw new Error("anthropic " + r.status + ": " + JSON.stringify(j).slice(0, 160));
  return (j.content || []).map((c) => c.text || "").join("").trim();
}

// Pick a check-in not used in the recent rotation (kimiState.recentCheckIns holds recent lines).
async function pickCheckIn(db, crewId) {
  const stateRef = db.doc(`kimiState/${crewId}`);
  const snap = await stateRef.get();
  const recent = (snap.exists && Array.isArray(snap.data().recentCheckIns)) ? snap.data().recentCheckIns : [];
  const fresh = KIMI_CHECKINS.filter((c) => !recent.includes(c));
  const pool = fresh.length ? fresh : KIMI_CHECKINS;          // all used → reset rotation
  const line = pool[Math.floor(Math.random() * pool.length)];
  const nextRecent = [...recent, line].slice(-8);             // keep the last 8 to avoid repeats
  await stateRef.set({ recentCheckIns: nextRecent }, { merge: true });
  return line;
}

async function postKimiMessage(db, crewId, channelId, text, replyToId) {
  const ref = await db.collection(`crews/${crewId}/channels/${channelId}/messages`).add({
    authorId: KIMI_UID,
    authorName: KIMI_NAME,
    text,
    photoURLs: [],
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    editedAt: null,
    deleted: false,
    replyToId: replyToId || null,
    reactions: {},
    readBy: [],
    mentions: [],
    type: "message",
    isKimiGenerated: true,
  });
  await db.doc(`kimiState/${crewId}`).set(
    { lastPostAt: admin.firestore.FieldValue.serverTimestamp(), lastChannelId: channelId },
    { merge: true }
  );
  return ref.id;
}

// ── Trivia: Kimi authors a plant-quiz question grounded in the Leaf People plant data ──
async function generateTrivia() {
  const kb = await loadPlantKB();
  const prompt = `${buildKimiKnowledge(kb, "")}\n\nWrite ONE multiple-choice plant-trivia question for the crew — about rare aroids, velvet anthuriums/philodendrons, or a real care/botany fact drawn from the data above. Fun, but the answer must be genuinely correct. Return ONLY compact JSON (no markdown, no extra text), exactly this shape:\n{"question":"...","options":["...","...","...","..."],"correctIndex":0}\nExactly 4 options, one correct. Question under 140 characters.`;
  const raw = await callClaudeForKimi(prompt);
  const m = raw && raw.match(/\{[\s\S]*\}/);
  if (!m) throw new Error("trivia: no JSON in completion");
  const obj = JSON.parse(m[0]);
  if (!obj.question || !Array.isArray(obj.options) || obj.options.length < 2) throw new Error("trivia: bad shape");
  const options = obj.options.slice(0, 4).map((o) => String(o));
  const correctIndex = Math.max(0, Math.min(options.length - 1, parseInt(obj.correctIndex, 10) || 0));
  return { question: String(obj.question), options, correctIndex };
}

async function postTrivia(db, crewId) {
  const t = await generateTrivia();
  await db.collection(`crews/${crewId}/channels/main/messages`).add({
    authorId: KIMI_UID, authorName: KIMI_NAME, text: t.question, photoURLs: [],
    createdAt: admin.firestore.FieldValue.serverTimestamp(), editedAt: null, deleted: false,
    replyToId: null, reactions: {}, readBy: [], mentions: [],
    type: "trivia", isKimiGenerated: true,
    trivia: { question: t.question, options: t.options, correctIndex: t.correctIndex, answers: {} },
  });
  await db.doc(`kimiState/${crewId}`).set(
    { lastPostAt: admin.firestore.FieldValue.serverTimestamp(), lastTriviaAt: admin.firestore.FieldValue.serverTimestamp() },
    { merge: true });
}

// A member posted a poll → Kimi gives a one-line take and casts her own vote (so polls feel
// alive from the first vote). Grounded in the plant data; cooldown-gated.
async function handleKimiPoll(db, crewId, channelId, msg, msgId) {
  try {
    const state = (await db.doc(`kimiState/${crewId}`).get()).data() || {};
    const lastMs = (state.lastPollAt && state.lastPollAt.toMillis) ? state.lastPollAt.toMillis() : 0;
    if (Date.now() - lastMs < 45 * 1000) return;                       // don't pile onto a burst of polls

    const poll = msg.poll;
    const options = Array.isArray(poll.options) ? poll.options : [];
    if (options.length < 2) return;
    const channelName = channelId.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    const kb = await loadPlantKB();
    const knowledge = buildKimiKnowledge(kb, `${poll.question} ${options.join(" ")}`);
    const listed = options.map((o, i) => `${i}: ${o}`).join("\n");
    const userText = `${knowledge}\n\n${msg.authorName || "A member"} posted a poll in "${channelName}":\nQ: ${poll.question}\nOptions:\n${listed}\n\nReact in ONE short line that reads clearly as YOUR personal opinion — you're a fellow collector sharing a preference, NOT the expert settling the debate. Your pick MUST carry an explicit personal qualifier — "for me", "personally", "in my setup" — never a bare declaration. Say "PON without question FOR ME — …", not "PON without question". Then ALWAYS give your reason grounded in how you grow (e.g. "…the airflow keeps my velvet roots from ever sitting wet"). It's your opinion as a fellow collector, never a flat fact or verdict. End the line with the word "Voted." Then on a NEW final line output exactly "VOTE: <the option number you picked>" — that line is parsed out and never shown.`;

    await setKimiTyping(db, crewId, channelId, true);
    let text = await callClaudeForKimi(userText).finally(() => setKimiTyping(db, crewId, channelId, false));

    let choice = null;
    const vm = text && text.match(/VOTE:\s*(\d+)/i);
    if (vm) { choice = parseInt(vm[1], 10); text = text.replace(/VOTE:\s*\d+/i, "").trim(); }
    if (!(choice >= 0 && choice < options.length)) choice = 0;

    await db.doc(`crews/${crewId}/channels/${channelId}/messages/${msgId}`)
      .update({ [`poll.votes.${choice}`]: admin.firestore.FieldValue.arrayUnion(KIMI_UID) });
    await kimiMarkRead(db, crewId, channelId, msgId);   // voting/commenting = she saw the poll
    if (text) await postKimiMessage(db, crewId, channelId, text, msgId);
    await db.doc(`kimiState/${crewId}`).set({ lastPollAt: admin.firestore.FieldValue.serverTimestamp() }, { merge: true });
  } catch (e) { console.error("handleKimiPoll", e); }
}

// "Kimi is typing…" — best-effort ephemeral doc the app listens for while she composes.
async function setKimiTyping(db, crewId, channelId, on) {
  const ref = db.collection(`crews/${crewId}/channels/${channelId}/typing`).doc(KIMI_UID);
  try {
    if (on) await ref.set({ name: "Kimi", updatedAt: admin.firestore.FieldValue.serverTimestamp() });
    else await ref.delete();
  } catch (e) { /* typing is best-effort */ }
}

exports.kimiReply = onRequest(
  { secrets: [ANTHROPIC_API_KEY], invoker: "public", timeoutSeconds: 60 },
  async (req, res) => {
    if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

    // Gate: valid Firebase ID token (anonymous counts) — same posture as identifyPlant.
    const m = (req.get("authorization") || "").match(/^Bearer (.+)$/i);
    if (!m) return res.status(401).json({ error: "missing auth token" });
    try { await admin.auth().verifyIdToken(m[1]); }
    catch { return res.status(401).json({ error: "invalid auth token" }); }

    const body = (req.body && typeof req.body === "object") ? req.body : {};
    const crewId = body.crewId || "jungle-crew";
    const channelId = body.channelId || "main";
    const trigger = body.trigger || "mention";
    const db = admin.firestore();

    try {
      // Check-in / silence → rotation pool, no Claude call.
      if (trigger === "checkin" || trigger === "silence") {
        const line = await pickCheckIn(db, crewId);
        const id = await postKimiMessage(db, crewId, channelId, line, null);
        return res.status(200).json({ ok: true, messageId: id, text: line, source: "pool" });
      }

      // welcome / mention / share → Claude-authored, in persona.
      let member = null;
      if (body.memberId) {
        const md = await db.doc(`crews/${crewId}/members/${body.memberId}`).get();
        if (md.exists) member = md.data();
      }
      const channelName = channelId.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      const transcript = await loadTranscript(db, crewId, channelId);
      const photoURLs = Array.isArray(body.photoURLs) ? body.photoURLs : [];
      const kb = await loadPlantKB();
      const article = await maybeArticle(db, crewId, `${body.memberMessage || ""} ${transcript}`);
      const userText = buildKimiUserText({ transcript, channelName, member, memberMessage: body.memberMessage, trigger, photoCount: photoURLs.length, kb, article });
      await setKimiTyping(db, crewId, channelId, true);
      const text = await callClaudeForKimi(userText, photoURLs).finally(() => setKimiTyping(db, crewId, channelId, false));
      if (!text) return res.status(502).json({ error: "empty completion" });
      await kimiMarkRead(db, crewId, channelId, body.replyToId);   // she saw the @kimi message
      const id = await postKimiMessage(db, crewId, channelId, text, body.replyToId || null);
      return res.status(200).json({ ok: true, messageId: id, text, source: "claude" });
    } catch (e) {
      console.error("kimiReply", e);
      return res.status(502).json({ error: String(e.message || e).slice(0, 200) });
    }
  }
);

/* AI Catchup — Kimi's private "what you missed" digest. Summarizes recent chat into topic
 * chips + one-line bullets (referencing members by name). Ephemeral: NOT posted to the feed,
 * just returned to the requesting member. Same Firebase-token gate + shared plant grounding. */
exports.kimiCatchup = onRequest(
  { secrets: [ANTHROPIC_API_KEY], invoker: "public", timeoutSeconds: 60 },
  async (req, res) => {
    if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
    const m = (req.get("authorization") || "").match(/^Bearer (.+)$/i);
    if (!m) return res.status(401).json({ error: "missing auth token" });
    try { await admin.auth().verifyIdToken(m[1]); }
    catch { return res.status(401).json({ error: "invalid auth token" }); }

    const body = (req.body && typeof req.body === "object") ? req.body : {};
    const crewId = body.crewId || "jungle-crew";
    const channelId = body.channelId || "main";
    const db = admin.firestore();
    try {
      const transcript = await loadTranscript(db, crewId, channelId);
      if (!transcript || !transcript.trim()) return res.status(200).json({ chips: [], bullets: [] });
      const prompt = `Here is the recent conversation in the "${channelId}" channel of the Jungle Rhythm rare-plant community (most recent last):\n\n${transcript}\n\nSummarize what a member who has been away would want to know. Return ONLY compact JSON, no markdown:\n{"chips":["3-6 short topic tags"],"bullets":["4-7 one-line summaries, each naming who did or said what"]}\nBe specific (plants, questions, wins, sourcing). No greetings, no fluff.`;
      const raw = await callClaudeForKimi(prompt, [], 700);
      const jm = raw && raw.match(/\{[\s\S]*\}/);
      const obj = jm ? JSON.parse(jm[0]) : { chips: [], bullets: [] };
      return res.status(200).json({
        chips: Array.isArray(obj.chips) ? obj.chips.slice(0, 6).map(String) : [],
        bullets: Array.isArray(obj.bullets) ? obj.bullets.slice(0, 8).map(String) : [],
      });
    } catch (e) {
      console.error("kimiCatchup", e);
      return res.status(502).json({ error: String(e.message || e).slice(0, 200) });
    }
  }
);

/* Kimi automation (spec §14 triggers). The app already fires @kimi mentions + the welcome
 * reply directly via kimiReply; these two functions add the AMBIENT presence so Kimi feels
 * like a real host, not a command you have to invoke:
 *   • onCrewMessage — greets a plain "hi/hey/hello" (with a cooldown so she never over-posts).
 *   • kimiScheduledCheck — silence detection: if the room's been quiet 18h+, drops a check-in.
 * Both reuse the generate+post core above. They skip @mentions/welcome_cards (the app owns
 * those) and Kimi's own messages (no loops).
 */
const GREETING_RE = /^(hi|hey|hello|yo|hiya|howdy|sup|hola|good (morning|afternoon|evening))\b/i;
const ACK_RE = /^(ok(ay)?|thanks|thx|ty|cool|nice|sweet|lol|haha|yep|yeah|yup|k|got it|sounds good|will do|👍|🙏|❤️|🔥|🌿)[\s!.]*$/i;
const KIMI_GREET_COOLDOWN_MS = 60 * 1000;   // cold-reply cooldown (greeting/question); NOT applied mid-conversation

// True when the message just before this one was Kimi's — i.e. the member is replying to her.
async function lastMessageWasKimi(db, crewId, channelId, currentId) {
  try {
    const snap = await db.collection(`crews/${crewId}/channels/${channelId}/messages`)
      .orderBy("createdAt", "desc").limit(3).get();
    const prev = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
      .filter((m) => m.id !== currentId && !m.deleted)[0];
    return !!(prev && (prev.isKimiGenerated || prev.authorId === KIMI_UID));
  } catch (e) { return false; }
}

// Contextual emoji when Kimi just wants to react (a real host double-taps rather than
// always typing back). Leans on the message tone; falls back to a warm default.
function pickKimiReaction(text, hasPhotos) {
  const t = (text || "").toLowerCase();
  const sample = (arr) => arr[Math.floor(Math.random() * arr.length)];
  if (/(lost|died|rot|dying|struggling|sad|yellowing|crashed|melted)/.test(t)) return sample(["🫶", "🌿"]);
  if (/(finally|got|scored|picked up|new|unfurl|arrived|mail day|acquired|bloom|pushing)/.test(t)) return sample(["🔥", "❤️", "👏"]);
  if (hasPhotos) return sample(["🔥", "❤️", "🌿", "👀"]);
  return sample(["❤️", "👍", "🌿", "🔥"]);
}

// Kimi acknowledges a light message with an emoji reaction instead of a full reply.
// Reacting also counts as reading it, so she shows up in the post's read receipts.
async function reactAsKimi(db, crewId, channelId, msgId, emoji) {
  try {
    await db.doc(`crews/${crewId}/channels/${channelId}/messages/${msgId}`).update({
      [`reactions.${emoji}`]: admin.firestore.FieldValue.arrayUnion(KIMI_UID),
      readBy: admin.firestore.FieldValue.arrayUnion(KIMI_UID),
      [`readAt.${KIMI_UID}`]: admin.firestore.FieldValue.serverTimestamp(),
    });
  } catch (e) { /* best-effort */ }
}

// Kimi has "seen" a message she's engaging with (replying to, voting on, etc.).
async function kimiMarkRead(db, crewId, channelId, msgId) {
  if (!msgId) return;
  try {
    await db.doc(`crews/${crewId}/channels/${channelId}/messages/${msgId}`).update({
      readBy: admin.firestore.FieldValue.arrayUnion(KIMI_UID),
      [`readAt.${KIMI_UID}`]: admin.firestore.FieldValue.serverTimestamp(),
    });
  } catch (e) { /* best-effort */ }
}

// Push notifications for a new message. Honors each member's notifPref:
//   realtime = every message · smart = Kimi's posts + replies-to-you · mute = replies-to-you only.
// Members store their FCM token on their member doc (ChatService.registerPushToken).
async function sendChatPushes(db, crewId, channelId, msg, msgId) {
  try {
    const snap = await db.collection(`crews/${crewId}/members`).get();
    const members = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
      .filter((m) => m.fcmToken && m.id !== msg.authorId && !m.isKimi);
    if (!members.length) return;

    const channelName = channelId.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    const isKimi = !!msg.isKimiGenerated;
    const sender = msg.authorName || "Someone";
    // Trivia / poll posts announce themselves so they don't read like a plain message.
    const prefix = msg.type === "trivia" ? "🧠 Trivia — " : (msg.type === "poll" ? "📊 Poll — " : "");
    const body = (msg.text && msg.text.trim())
      ? prefix + msg.text.trim().slice(0, 140)
      : ((Array.isArray(msg.photoURLs) && msg.photoURLs.length) ? "📷 Photo" : "New message");

    let replyToAuthor = null;
    if (msg.replyToId) {
      const rt = await db.doc(`crews/${crewId}/channels/${channelId}/messages/${msg.replyToId}`).get();
      if (rt.exists) replyToAuthor = rt.data().authorId;
    }

    // Per-recipient unread count → the home-screen app-icon number bumps the moment this push
    // lands (even with the app closed). One query; O(members×messages) in memory.
    let recent = [];
    try {
      const rs = await db.collection(`crews/${crewId}/channels/${channelId}/messages`)
        .orderBy("createdAt", "desc").limit(100).get();
      recent = rs.docs.map((d) => ({ id: d.id, ...d.data() }));
    } catch (e) { /* badge best-effort */ }
    // Badge = messages since the member last OPENED chat (same "last seen" model as the
    // in-app tab badge), read from members/{uid}.lastSeenAt. Falls back to the readBy
    // backlog only for old builds that don't publish lastSeenAt yet.
    const unreadFor = (m) => {
      const seenMs = (m.lastSeenAt && typeof m.lastSeenAt.toMillis === "function")
        ? m.lastSeenAt.toMillis() : null;
      return recent.filter((r) => {
        if (r.deleted || r.authorId === m.id) return false;
        if (seenMs !== null && r.createdAt && typeof r.createdAt.toMillis === "function") {
          return r.createdAt.toMillis() > seenMs;
        }
        return !(Array.isArray(r.readBy) && r.readBy.includes(m.id));
      }).length;
    };

    const mentions = Array.isArray(msg.mentions) ? msg.mentions : [];
    const sends = members.map((m) => {
      const pref = m.notifPref || "smart";
      const isReplyToMe = replyToAuthor === m.id;
      const isMentioned = mentions.includes(m.id);
      const isDirect = isReplyToMe || isMentioned;   // a reply OR an @mention pings you directly
      if (pref === "mute" && !isDirect) return null;
      if (pref === "smart" && !isKimi && !isDirect) return null;
      const title = isKimi ? "Kimi 🌿"
        : (isMentioned ? `${sender} mentioned you` : (isReplyToMe ? `${sender} replied` : channelName));
      const text = isKimi ? body : `${sender}: ${body}`;
      return admin.messaging().send({
        token: m.fcmToken,
        notification: { title, body: text },
        data: { type: "chat", channelId, crewId, msgId },
        apns: { payload: { aps: { sound: "default", badge: unreadFor(m) } } },
      }).catch(() => {});   // stale token → ignore
    }).filter(Boolean);
    await Promise.all(sends);
  } catch (e) { console.error("sendChatPushes", e); }
}

exports.onCrewMessage = onDocumentCreated(
  { document: "crews/{crewId}/channels/{channelId}/messages/{msgId}", secrets: [ANTHROPIC_API_KEY], timeoutSeconds: 60 },
  async (event) => {
    const snap = event.data;
    if (!snap) return;
    const msg = snap.data() || {};
    const { crewId, channelId } = event.params;
    const db = admin.firestore();

    // Push notifications for every new message (including Kimi's posts).
    await sendChatPushes(db, crewId, channelId, msg, snap.id);

    // ── Kimi auto-response (member messages only) ──
    if (msg.isKimiGenerated) return;                                   // never react to her own posts
    const mentions = Array.isArray(msg.mentions) ? msg.mentions : [];
    if (mentions.includes(KIMI_UID)) return;                          // @kimi → app already calls kimiReply
    if (msg.type === "welcome_card") return;                         // welcome → app already calls kimiReply

    // A member posted a poll → Kimi drops a one-line take AND casts her own vote (makes polls
    // feel alive even with few voters). Cooldown-gated. Handled here, then done.
    if (msg.type === "poll" && msg.poll) {
      await handleKimiPoll(db, crewId, channelId, msg, snap.id);
      return;
    }

    const text = String(msg.text || "").trim();
    const photoURLs = Array.isArray(msg.photoURLs) ? msg.photoURLs : [];
    const hasPhotos = photoURLs.length > 0;

    const isGreeting = GREETING_RE.test(text);
    const isQuestion = text.includes("?") && text.length > 3;        // a plain question — no @kimi needed
    // Is the member replying to Kimi? (she spoke last → keep the thread going even without a "?")
    const inConversation = await lastMessageWasKimi(db, crewId, channelId, snap.id);
    if (inConversation && !hasPhotos && ACK_RE.test(text)) {          // a bare "thanks"/"ok"/"👍" (never skip a photo)
      await reactAsKimi(db, crewId, channelId, snap.id, "👍");       // acknowledge with a 👍, not a reply
      return;
    }

    // A shared photo pulls Kimi in even without a "?" — a plant community host looks at the plant.
    // (Cold photo posts still fall under the 60s cooldown below, so she won't spam every upload.)
    if (!isGreeting && !isQuestion && !inConversation && !hasPhotos) {
      // A substantive comment/share she's not otherwise part of — a real host often just
      // double-taps a ❤️/🔥 in passing rather than replying. Silent (reactions send no push).
      if (text.length > 12 && Math.random() < 0.3) {
        await reactAsKimi(db, crewId, channelId, snap.id, pickKimiReaction(text, hasPhotos));
      }
      return;
    }

    // She IS engaged (greeting / question / conversation / photo). Questions always get words;
    // but for a plain share/comment/photo, sometimes a reaction is the whole response — no need
    // to write a sentence every time. Feels far more natural than always answering.
    if (!isQuestion && !isGreeting) {
      const reactChance = hasPhotos ? 0.35 : 0.5;
      if (Math.random() < reactChance) {
        await reactAsKimi(db, crewId, channelId, snap.id, pickKimiReaction(text, hasPhotos));
        return;
      }
    }

    // Cooldown throttles COLD greetings/questions — never a live back-and-forth.
    if (!inConversation) {
      const state = (await db.doc(`kimiState/${crewId}`).get()).data() || {};
      const lastMs = (state.lastPostAt && state.lastPostAt.toMillis) ? state.lastPostAt.toMillis() : 0;
      if (Date.now() - lastMs < KIMI_GREET_COOLDOWN_MS) return;
    }

    let member = null;
    if (msg.authorId) {
      const md = await db.doc(`crews/${crewId}/members/${msg.authorId}`).get();
      if (md.exists) member = md.data();
    }
    const channelName = channelId.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    const transcript = await loadTranscript(db, crewId, channelId);
    const kb = await loadPlantKB();
    const article = await maybeArticle(db, crewId, `${text} ${transcript}`);
    const userText = buildKimiUserText({ transcript, channelName, member, memberMessage: text, trigger: "mention", photoCount: photoURLs.length, kb, article });
    try {
      await setKimiTyping(db, crewId, channelId, true);
      const reply = await callClaudeForKimi(userText, photoURLs).finally(() => setKimiTyping(db, crewId, channelId, false));
      if (reply) {
        await kimiMarkRead(db, crewId, channelId, snap.id);   // replying = she saw it
        await postKimiMessage(db, crewId, channelId, reply, snap.id);
      }
    } catch (e) { console.error("onCrewMessage", e); }
  }
);

exports.kimiScheduledCheck = onSchedule(
  { schedule: "every 6 hours", timeZone: "America/Los_Angeles", secrets: [ANTHROPIC_API_KEY] },
  async () => {
    const crewId = "jungle-crew";
    const db = admin.firestore();

    // Only speak up if Main has been silent for 18h+ (spec §14, Trigger 4).
    const lastSnap = await db.collection(`crews/${crewId}/channels/main/messages`)
      .orderBy("createdAt", "desc").limit(1).get();
    const lastMsg = lastSnap.docs[0] && lastSnap.docs[0].data();
    const lastMs = (lastMsg && lastMsg.createdAt && lastMsg.createdAt.toMillis) ? lastMsg.createdAt.toMillis() : 0;
    if (lastMs && Date.now() - lastMs < 18 * 60 * 60 * 1000) return;   // room is active → stay quiet

    // Never post twice in ~a day.
    const state = (await db.doc(`kimiState/${crewId}`).get()).data() || {};
    const lastPost = (state.lastPostAt && state.lastPostAt.toMillis) ? state.lastPostAt.toMillis() : 0;
    if (Date.now() - lastPost < 20 * 60 * 60 * 1000) return;

    const line = await pickCheckIn(db, crewId);                        // rotation pool, no repeats
    await postKimiMessage(db, crewId, "main", line, null);
  }
);

// Kimi drops a plant-trivia question into Main every ~3 days. Members answer once; a correct
// answer scores their Trivia metric (client-side). Use Cloud Scheduler "Run now" to test on demand.
exports.kimiTrivia = onSchedule(
  { schedule: "every saturday 10:00", timeZone: "America/Los_Angeles", secrets: [ANTHROPIC_API_KEY] },
  async () => {
    try { await postTrivia(admin.firestore(), "jungle-crew"); }
    catch (e) { console.error("kimiTrivia", e); }
  }
);

// A new member just joined — their member doc is created the moment they OPEN the chat (ungated),
// so this is how Kimi "recognizes" a new arrival. She posts a warm welcome that introduces herself
// and nudges them to say hi + do their quick intro. No wall: the greeting is the pull, not a toll.
// Deduped via kimiState.welcomedMembers so a member is only ever welcomed once.
exports.onMemberJoined = onDocumentCreated(
  { document: "crews/{crewId}/members/{uid}", secrets: [ANTHROPIC_API_KEY], timeoutSeconds: 60 },
  async (event) => {
    const snap = event.data;
    if (!snap) return;
    const member = snap.data() || {};
    const { crewId, uid } = event.params;
    if (uid === KIMI_UID || member.isKimi || member.isHost) return;   // never welcome the host/Kimi herself
    const db = admin.firestore();
    const stateRef = db.doc(`kimiState/${crewId}`);
    const state = (await stateRef.get()).data() || {};
    const welcomed = Array.isArray(state.welcomedMembers) ? state.welcomedMembers : [];
    if (welcomed.includes(uid)) return;                              // already greeted (doc re-created / retry)
    // Claim the welcome slot first so a rapid re-create can't double-post.
    await stateRef.set({ welcomedMembers: [...welcomed, uid].slice(-1000) }, { merge: true });

    const channelId = "main";
    try {
      const transcript = await loadTranscript(db, crewId, channelId);
      const kb = await loadPlantKB();
      const userText = buildKimiUserText({ transcript, channelName: "Main", member, memberMessage: "", trigger: "welcome", photoCount: 0, kb, article: null });
      await setKimiTyping(db, crewId, channelId, true);
      const reply = await callClaudeForKimi(userText).finally(() => setKimiTyping(db, crewId, channelId, false));
      if (reply) await postKimiMessage(db, crewId, channelId, reply, null);
    } catch (e) { console.error("onMemberJoined", e); }
  }
);

// One-off broadcast push to pull existing installs into the chat (founder-triggered). Sends a chat
// deep-link push to every member holding an fcmToken. Call with { title?, body?, crewId? }.
//   curl -X POST <url> -H "Authorization: Bearer <founder idToken>" -H "content-type: application/json" \
//        -d '{"title":"Kimi 🌿","body":"the Jungle Rhythm chat just opened — come say hi"}'
exports.chatBroadcast = onRequest({ invoker: "public", timeoutSeconds: 300 }, async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const m = (req.get("authorization") || "").match(/^Bearer (.+)$/i);
  if (!m) return res.status(401).json({ error: "missing token" });
  let uid;
  try { uid = (await admin.auth().verifyIdToken(m[1])).uid; } catch { return res.status(401).json({ error: "invalid token" }); }
  if (uid !== INSIGHTS_ADMIN_UID) return res.status(403).json({ error: "admin only" });

  const body = (req.body && typeof req.body === "object") ? req.body : {};
  const crewId = body.crewId || "jungle-crew";
  const title = String(body.title || "Kimi 🌿");
  const text = String(body.body || "the Jungle Rhythm chat is live — come say hi 🌿");
  const db = admin.firestore();
  try {
    const snap = await db.collection(`crews/${crewId}/members`).get();
    const tokens = snap.docs.map((d) => d.data())
      .filter((mm) => mm.fcmToken && !mm.isKimi)
      .map((mm) => mm.fcmToken);
    if (!tokens.length) return res.status(200).json({ ok: true, sent: 0, note: "no member tokens" });
    let ok = 0, fail = 0;
    // sendEachForMulticast caps at 500 tokens/call — chunk to be safe.
    for (let i = 0; i < tokens.length; i += 500) {
      const chunk = tokens.slice(i, i + 500);
      const resp = await admin.messaging().sendEachForMulticast({
        tokens: chunk,
        notification: { title, body: text },
        data: { type: "chat", channelId: "main", crewId, msgId: "" },
        apns: { headers: { "apns-push-type": "alert", "apns-priority": "10" }, payload: { aps: { sound: "default" } } },
      });
      ok += resp.successCount; fail += resp.failureCount;
    }
    return res.status(200).json({ ok: true, recipients: tokens.length, sent: ok, failed: fail });
  } catch (e) {
    console.error("chatBroadcast", e);
    return res.status(502).json({ error: String(e.message || e).slice(0, 200) });
  }
});

/* ── Community Insights (private, owner-only) ───────────────────────────────────────────────
 * A monthly read on the Jungle Rhythm community for the founder: hard stats computed in JS
 * (accurate) + a Claude-written briefing (who's active/quiet, hot topics, who to re-engage,
 * what's working, growth moves). Written to Firestore `communityInsights/latest` (+ dated),
 * read only by the admin in the hidden Train-Identifier section. Also self-review of Kimi. */
const INSIGHTS_ADMIN_UID = "VFVYI2Gbo2hU4gmRpdZ1QAUcBlG3";

async function callClaudeRaw(system, userText, maxTokens) {
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": ANTHROPIC_API_KEY.value(), "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({ model: CLAUDE_MODEL, max_tokens: maxTokens, temperature: 0.5, system, messages: [{ role: "user", content: userText }] }),
  });
  const j = await r.json();
  if (!r.ok) throw new Error("anthropic " + r.status + ": " + JSON.stringify(j).slice(0, 160));
  return (j.content || []).map((c) => c.text || "").join("").trim();
}

async function computeCommunityStats(db, crewId) {
  const membersSnap = await db.collection(`crews/${crewId}/members`).get();
  const members = membersSnap.docs.map((d) => ({ id: d.id, ...d.data() })).filter((m) => !m.isKimi);
  const now = Date.now(), cutoff = now - 30 * 24 * 60 * 60 * 1000;
  const ms = (t) => (t && t.toMillis) ? t.toMillis() : 0;

  const msgsSnap = await db.collection(`crews/${crewId}/channels/main/messages`)
    .orderBy("createdAt", "desc").limit(500).get();
  const msgs = msgsSnap.docs.map((d) => d.data()).filter((m) => !m.deleted);
  const recent = msgs.filter((m) => ms(m.createdAt) > cutoff);
  const memberMsgs = recent.filter((m) => !m.isKimiGenerated);
  const kimiMsgs = recent.filter((m) => m.isKimiGenerated);
  const activeIds = new Set(memberMsgs.map((m) => m.authorId));

  const kimiReactions = kimiMsgs.reduce((n, m) => n + Object.values(m.reactions || {}).reduce((a, v) => a + (v ? v.length : 0), 0), 0);
  const nameOf = (m) => m.displayName || "Member";

  return {
    totalMembers: members.length,
    newThisMonth: members.filter((m) => ms(m.joinedAt) > cutoff).length,
    activeMembers: activeIds.size,
    quietMembers: members.filter((m) => !activeIds.has(m.id)).map(nameOf).slice(0, 20),
    messages30d: memberMsgs.length,
    kimiPosts30d: kimiMsgs.length,
    kimiReactions30d: kimiReactions,
    topContributors: [...members].sort((a, b) => (b.roots || 0) - (a.roots || 0)).slice(0, 5).map((m) => `${nameOf(m)} (${m.roots || 0} Roots)`),
    byCountry: Object.entries(members.reduce((o, m) => { const c = m.countryCode || "?"; o[c] = (o[c] || 0) + 1; return o; }, {})).map(([c, n]) => `${c}:${n}`),
  };
}

async function generateAndStoreInsights(db, crewId) {
  const stats = await computeCommunityStats(db, crewId);
  const transcript = await loadTranscript(db, crewId, "main");
  const system = "You are a sharp, candid community + growth analyst briefing the FOUNDER of a rare-plant app's community (private — the members never see this). Be specific and useful, not fluffy. You may reference members by name.";
  const prompt = `Community: Jungle Rhythm (rare-plant collectors), hosted by an AI named Kimi.\n\nHARD STATS (last 30 days):\n${JSON.stringify(stats, null, 1)}\n\nRECENT CHAT (most recent last):\n${transcript || "(quiet)"}\n\nWrite the founder's monthly briefing. Return ONLY compact JSON, no markdown:\n{"headline":"one-line health read","summary":"2-3 sentences","hotTopics":["3-6 topics people actually discussed"],"reengage":["specific quiet members worth nudging + a one-line hook for each"],"whatsWorking":"what's driving engagement, including how Kimi is landing","recommendations":["3-5 concrete moves to grow/shape this ~30-person community"]}`;
  let obj = {};
  try {
    const raw = await callClaudeRaw(system, prompt, 1200);
    const m = raw.match(/\{[\s\S]*\}/);
    obj = m ? JSON.parse(m[0]) : {};
  } catch (e) { console.error("insights claude", e); }
  const doc = {
    generatedAt: admin.firestore.FieldValue.serverTimestamp(),
    stats,
    headline: obj.headline || "", summary: obj.summary || "",
    hotTopics: Array.isArray(obj.hotTopics) ? obj.hotTopics : [],
    reengage: Array.isArray(obj.reengage) ? obj.reengage : [],
    whatsWorking: obj.whatsWorking || "",
    recommendations: Array.isArray(obj.recommendations) ? obj.recommendations : [],
  };
  await db.doc("communityInsights/latest").set(doc);
  return doc;
}

// Auto: the 1st of every month at 09:00 LA.
exports.communityInsights = onSchedule(
  { schedule: "0 9 1 * *", timeZone: "America/Los_Angeles", secrets: [ANTHROPIC_API_KEY] },
  async () => { try { await generateAndStoreInsights(admin.firestore(), "jungle-crew"); } catch (e) { console.error("communityInsights", e); } }
);

// On-demand: the founder's app (hidden section) hits this to regenerate now. Admin-gated.
exports.communityInsightsNow = onRequest(
  { secrets: [ANTHROPIC_API_KEY], invoker: "public", timeoutSeconds: 120 },
  async (req, res) => {
    const m = (req.get("authorization") || "").match(/^Bearer (.+)$/i);
    if (!m) return res.status(401).json({ error: "missing token" });
    let uid;
    try { uid = (await admin.auth().verifyIdToken(m[1])).uid; }
    catch { return res.status(401).json({ error: "invalid token" }); }
    if (uid !== INSIGHTS_ADMIN_UID) return res.status(403).json({ error: "admin only" });
    try { const doc = await generateAndStoreInsights(admin.firestore(), "jungle-crew"); return res.status(200).json({ ok: true, insights: doc }); }
    catch (e) { return res.status(502).json({ error: String(e.message || e).slice(0, 200) }); }
  }
);
