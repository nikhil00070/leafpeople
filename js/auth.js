/* Leaf People — web authentication (Phase 2)
   Firebase Auth (Sign in with Apple / Google / Email), shared identity with the iOS app.
   Loaded as a module on article pages alongside site.js. Exposes window.lpAuth + fires a
   "lp-auth-changed" CustomEvent on window so the (classic-script) paywall in site.js can react.

   This file only establishes IDENTITY. Whether a signed-in user is a paying subscriber is
   decided server-side in Phase 3 (RevenueCat -> Cloud Function -> Firestore -> edge middleware).
   The config below is public Firebase client config — safe to ship in the browser. */
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getAuth, setPersistence, browserLocalPersistence,
  OAuthProvider, GoogleAuthProvider, signInWithPopup,
  signInWithEmailAndPassword, onAuthStateChanged, signOut,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyChqdwH7WJgZGyC4sE5WYktsXwXC1IEVFU",
  authDomain: "leafpeople-1c8d1.firebaseapp.com",
  projectId: "leafpeople-1c8d1",
  storageBucket: "leafpeople-1c8d1.firebasestorage.app",
  messagingSenderId: "689459008483",
  appId: "1:689459008483:web:1c0a212140bf33841706d6",
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
auth.useDeviceLanguage();
setPersistence(auth, browserLocalPersistence).catch(() => {});

const emit = (user) =>
  window.dispatchEvent(new CustomEvent("lp-auth-changed", { detail: { user } }));

// Friendlier copy for the handful of errors users actually hit.
function readableError(e) {
  const code = (e && e.code) || "";
  if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") return null; // user backed out
  if (code === "auth/unauthorized-domain") return "This domain isn't authorized for sign-in yet.";
  if (code === "auth/invalid-credential" || code === "auth/wrong-password") return "Wrong email or password.";
  if (code === "auth/user-not-found") return "No account found for that email.";
  if (code === "auth/too-many-requests") return "Too many attempts — try again in a bit.";
  return "Sign-in failed. Please try again.";
}

window.lpAuth = {
  user: null,
  ready: false,        // true once Firebase has reported initial auth state
  readableError,
  signInApple() {
    const p = new OAuthProvider("apple.com");
    p.addScope("email");
    p.addScope("name");
    return signInWithPopup(auth, p);
  },
  signInGoogle() {
    return signInWithPopup(auth, new GoogleAuthProvider());
  },
  signInEmail(email, password) {
    return signInWithEmailAndPassword(auth, email, password);
  },
  signOut() {
    return signOut(auth);
  },
};

onAuthStateChanged(auth, (user) => {
  window.lpAuth.user = user;
  window.lpAuth.ready = true;
  emit(user);
});
