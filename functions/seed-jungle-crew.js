/* One-off seed for the Jungle Rhythm (build spec §3–4, §14). Idempotent — safe to re-run;
 * every write is a fixed-id set(merge). Creates the crew doc, the 6 channels, Kimi's host
 * member doc, her pinned intro post in Main, and the kimiState guard doc.
 *
 * Run once (Admin SDK bypasses security rules):
 *   cd leafpeople-website/functions
 *   # auth: either `gcloud auth application-default login`, or set
 *   #   GOOGLE_APPLICATION_CREDENTIALS=/path/to/serviceAccount.json
 *   node seed-jungle-crew.js
 */
const admin = require("firebase-admin");
admin.initializeApp({ projectId: "leafpeople-1c8d1" });
const db = admin.firestore();
const now = admin.firestore.FieldValue.serverTimestamp();

const CREW = "jungle-crew";
const KIMI = "kimi";

const CHANNELS = [
  { id: "main",         name: "Main",          order: 0, blurb: "Everything crew",       photoFirst: false },
  { id: "new-leaves",   name: "New Leaves",    order: 1, blurb: "New growth & arrivals", photoFirst: true  },
  { id: "wins",         name: "Wins",          order: 2, blurb: "Positive posts only",   photoFirst: true  },
  { id: "questions",    name: "Questions",     order: 3, blurb: "Ask the crew",           photoFirst: false },
  { id: "sourcing",     name: "Sourcing",      order: 4, blurb: "Trusted sellers",       photoFirst: false },
  { id: "kimis-corner", name: "Kimi's Corner", order: 5, blurb: "Kimi's posts",          photoFirst: false },
];

const KIMI_INTRO =
  "Hey, I'm Kimi. Seven years collecting aroids — mostly velvet anthuriums and a few philodendrons I probably paid too much for. I grow in PON, mostly self-watering setups. This is the Jungle Rhythm. Show me what you're growing. 🌿";

async function main() {
  const crew = db.collection("crews").doc(CREW);

  await crew.set({
    name: "Leaf People",
    community: "Jungle Rhythm",
    host: "Kimi",
    mission: "Create massive jungles together. Learn from each other's wins and losses. Grow — the plants and the knowledge.",
    vibes: "From debating PON vs LECA to hunting down a dark-form warocqueanum nobody can find, this is where serious collectors actually talk. Share your wins, your losses, your rarest finds, and the plant you probably paid too much for. No gatekeeping. No beginner-shaming. Just people who grow rare plants and love every obsessive minute of it. The jungle grows faster together.",
    coverImage: "CrewCover",
    foundedAt: now,
    memberCount: 1,
  }, { merge: true });

  for (const ch of CHANNELS) {
    await crew.collection("channels").doc(ch.id).set(ch, { merge: true });
  }

  // Kimi's host member doc (spec §14).
  await crew.collection("members").doc(KIMI).set({
    displayName: "Kimi",
    isKimi: true,
    isHost: true,
    verified: true,
    roots: 0,
    joinedAt: now,
    bio: "Seven years growing velvet aroids. PON in self-watering pots. I drop a question every few days — answer if you want, lurk if you don't. No pressure.",
    region: "sf_bay_area",
  }, { merge: true });

  // Kimi's pinned intro in Main (spec §14). Fixed id so re-runs don't duplicate.
  await crew.collection("channels").doc("main").collection("messages").doc("kimi-intro").set({
    authorId: KIMI,
    authorName: "Kimi",
    text: KIMI_INTRO,
    photoURLs: [],
    createdAt: now,
    editedAt: null,
    deleted: false,
    replyToId: null,
    reactions: {},
    readBy: [],
    mentions: [],
    type: "message",
    isKimiGenerated: true,
    pinned: true,
  }, { merge: true });

  await db.collection("kimiState").doc(CREW).set({
    pinnedIntroPosted: true,
    lastPostAt: now,
    recentCheckIns: [],
  }, { merge: true });

  console.log("✓ Seeded Jungle Rhythm: crew + 6 channels + Kimi + pinned intro.");
}

main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
