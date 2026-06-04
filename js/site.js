/* Leaf People — landing interactions */
(function () {
  "use strict";

  // Sticky nav background on scroll
  const nav = document.getElementById("nav");
  if (nav) {
    const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 24);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // Mobile nav toggle
  const toggle = document.getElementById("navToggle");
  const links = document.getElementById("navLinks");
  if (toggle && links) {
    toggle.addEventListener("click", () => links.classList.toggle("open"));
    links.querySelectorAll("a").forEach((a) =>
      a.addEventListener("click", () => links.classList.remove("open"))
    );
  }

  // Reveal-on-scroll
  const revealEls = document.querySelectorAll(".reveal");
  const revealObs = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          revealObs.unobserve(e.target);
        }
      });
    },
    { threshold: 0.15 }
  );
  revealEls.forEach((el) => revealObs.observe(el));

  // Count-up metrics
  const counts = document.querySelectorAll("[data-count]");
  const countObs = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        const el = e.target;
        const target = parseInt(el.dataset.count, 10);
        const dur = 1100;
        const start = performance.now();
        const tick = (now) => {
          const p = Math.min((now - start) / dur, 1);
          const eased = 1 - Math.pow(1 - p, 3);
          el.textContent = Math.round(target * eased) + (target >= 60 ? "+" : "");
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
        countObs.unobserve(el);
      });
    },
    { threshold: 0.5 }
  );
  counts.forEach((el) => countObs.observe(el));

  // Care bars fill on view
  const bars = document.getElementById("careBars");
  if (bars) {
    const barObs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          bars.querySelectorAll(".bar-fill").forEach((f) => {
            f.style.width = f.dataset.val + "%";
          });
          barObs.unobserve(e.target);
        });
      },
      { threshold: 0.4 }
    );
    barObs.observe(bars);
  }

  // Reading-progress bar (article pages)
  const prog = document.getElementById("readProgress");
  if (prog) {
    const onProg = () => {
      const d = document.documentElement;
      const max = d.scrollHeight - d.clientHeight;
      prog.style.width = (max > 0 ? (d.scrollTop / max) * 100 : 0) + "%";
    };
    window.addEventListener("scroll", onProg, { passive: true });
    onProg();
  }

  // "More from…" related cards (article pages) — pulled from the section manifest
  const relGrid = document.getElementById("relatedGrid");
  if (relGrid) {
    const path = location.pathname.replace(/\/$/, "");
    const section = path.indexOf("/field-guide/") !== -1 ? "field-guide" : "the-leaf";
    const slug = path.split("/").pop();
    const fmtDate = (d) =>
      new Date(d).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
    const hideRelated = () => {
      const s = relGrid.closest(".related");
      if (s) s.style.display = "none";
    };
    fetch("/" + section + "/manifest.json")
      .then((r) => r.json())
      .then((items) => {
        // Hide pending (unreviewed) drafts from the related-cards rail too.
        items = items.filter((a) => (a.status || "published") === "published");
        const others = items.filter((a) => a.slug !== slug).slice(0, 4);
        if (!others.length) return hideRelated();
        relGrid.innerHTML = others
          .map(
            (a) => `
        <a class="related-card" href="${a.url}">
          <div class="rc-thumb" style="background-image:url('${a.thumb}')"></div>
          <div class="rc-body">
            <div class="rc-tag">${a.category || ""}</div>
            <div class="rc-title">${a.title}</div>
            <div class="rc-meta">${fmtDate(a.date)}</div>
          </div>
        </a>`
          )
          .join("");
      })
      .catch(hideRelated);
  }

  // Subscribe forms — AJAX submit, inline thanks, no page navigation.
  // Sends an email to hello@percentearth.co via FormSubmit; nothing else is stored.
  document.querySelectorAll("form[data-subscribe-form]").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = form.querySelector("button[type=submit]");
      if (btn) { btn.disabled = true; btn.textContent = "Sending…"; }
      const data = Object.fromEntries(new FormData(form).entries());
      try {
        await fetch(form.action, {
          method: "POST",
          headers: { "Content-Type": "application/json", "Accept": "application/json" },
          body: JSON.stringify(data),
        });
      } catch (_) { /* still show thanks — request was attempted */ }
      const thanks = document.createElement("p");
      thanks.className = "subscribe-thanks";
      thanks.textContent = "Thanks — we'll be in touch.";
      form.replaceWith(thanks);
    });
  });
})();

/* ===== Subscriber wall (Phase 1: visible only) =====
   Real enforcement comes from edge middleware in a later phase — this just renders the wall.
   OFF by default; preview any article with ?paywall=1. Flip PAYWALL_ON to true to show it live. */
(function () {
  "use strict";
  var PAYWALL_ON = true;
  var preview = location.search.indexOf("paywall=1") !== -1;
  if (!(PAYWALL_ON || preview)) return;
  if (!/^\/(the-leaf|field-guide)\//.test(location.pathname)) return;

  var box = document.querySelector("article.prose") || document.querySelector(".guide-wrap");
  if (!box) return;

  // Lazy-load Firebase Auth (a module) only now that the wall is actually showing — so the
  // ~100KB SDK never loads on non-gated pages. auth.js sets window.lpAuth + fires lp-auth-changed.
  if (!document.querySelector("script[data-lp-auth]")) {
    var authScript = document.createElement("script");
    authScript.type = "module";
    authScript.src = "/js/auth.js";
    authScript.setAttribute("data-lp-auth", "1");
    document.head.appendChild(authScript);
  }

  // WSJ-style: clamp the body to ~6 lines, then fade it out into the wall.
  box.style.position = "relative";
  box.style.maxHeight = "24em";
  box.style.overflow = "hidden";
  var fade = document.createElement("div");
  fade.style.cssText = "position:absolute;left:0;right:0;bottom:0;height:5em;pointer-events:none;background:linear-gradient(to bottom,rgba(255,255,255,0),var(--bg,#fff))";
  box.appendChild(fade);

  var css = document.createElement("style");
  css.textContent =
    ".lp-wall{max-width:520px;margin:.5rem auto 1.8rem;padding:2rem 1.7rem;text-align:center;background:#0b0f0d;color:#e8efe9;border:1px solid rgba(255,255,255,.12);border-radius:16px;box-shadow:0 16px 44px rgba(0,0,0,.32)}" +
    ".lp-wall h3{font-family:'Geologica',sans-serif;font-size:1.45rem;margin:0 0 .5rem;color:#f3f7f3}" +
    ".lp-wall p{color:#b8c8bb;max-width:44ch;margin:0 auto 1.3rem;line-height:1.55}" +
    ".lp-wall .btns{display:flex;gap:.7rem;justify-content:center;flex-wrap:wrap}" +
    ".lp-wall a,.lp-wall button{display:inline-block;padding:.72rem 1.35rem;border-radius:10px;font-weight:700;text-decoration:none;font-size:.92rem;font-family:inherit;cursor:pointer;border:0;line-height:1.2}" +
    ".lp-wall .primary{background:#FA2A52;color:#fff}" +
    ".lp-wall .ghost{background:transparent;color:#e8efe9;border:1px solid rgba(255,255,255,.28)}" +
    ".lp-signin{display:none;margin-top:1.1rem;padding-top:1.1rem;border-top:1px solid rgba(255,255,255,.12)}" +
    ".lp-signin.open{display:block}" +
    ".lp-signin .row{display:flex;gap:.6rem;justify-content:center;flex-wrap:wrap;margin-bottom:.7rem}" +
    ".lp-signin .prov{background:#fff;color:#111;min-width:200px}" +
    ".lp-signin .prov.google{background:#f1f3f4}" +
    ".lp-signin form{display:flex;gap:.5rem;justify-content:center;flex-wrap:wrap;margin-top:.2rem}" +
    ".lp-signin input{padding:.6rem .8rem;border-radius:9px;border:1px solid rgba(255,255,255,.22);background:#11161300;color:#e8efe9;font-size:.9rem;min-width:150px}" +
    ".lp-signin input::placeholder{color:#7e8d80}" +
    ".lp-signin .status{min-height:1.2em;margin:.6rem 0 0;font-size:.85rem;color:#b8c8bb}" +
    ".lp-signin .status.err{color:#ff8aa0}";
  document.head.appendChild(css);

  var wall = document.createElement("div");
  wall.className = "lp-wall";
  wall.innerHTML =
    "<h3>Keep reading with Leaf People</h3>" +
    "<p>The rest of this story is for subscribers. One Leaf People subscription unlocks every Understory feature and Field Guide — in the app and here on the web.</p>" +
    "<div class='btns'>" +
      "<a class='primary' href='https://apps.apple.com/us/app/leaf-people-rare-plant-guide/id6760627345' target='_blank' rel='noopener'>Subscribe in the app</a>" +
      "<button type='button' class='ghost' data-lp-signin-toggle>Already a subscriber? Sign in</button>" +
    "</div>" +
    "<div class='lp-signin' data-lp-signin>" +
      "<div class='row'>" +
        "<button type='button' class='prov' data-prov='apple'>Continue with Apple</button>" +
        "<button type='button' class='prov google' data-prov='google'>Continue with Google</button>" +
      "</div>" +
      "<form data-lp-email-form>" +
        "<input type='email' name='email' placeholder='Email' autocomplete='email' required>" +
        "<input type='password' name='password' placeholder='Password' autocomplete='current-password' required>" +
        "<button type='submit' class='ghost'>Sign in</button>" +
      "</form>" +
      "<p class='status' data-lp-status></p>" +
    "</div>";
  box.parentNode.insertBefore(wall, box.nextSibling);

  var panel = wall.querySelector("[data-lp-signin]");
  var status = wall.querySelector("[data-lp-status]");
  var setStatus = function (msg, isErr) {
    status.textContent = msg || "";
    status.classList.toggle("err", !!isErr);
  };
  var busy = function (on) {
    wall.querySelectorAll("button,input").forEach(function (el) { el.disabled = on; });
  };
  var run = function (promise) {
    if (!window.lpAuth) { setStatus("Still loading — try again in a second.", true); return; }
    setStatus("Signing in…");
    busy(true);
    promise()
      .catch(function (e) {
        var m = window.lpAuth.readableError(e);
        if (m) setStatus(m, true); else setStatus(""); // null = user cancelled
      })
      .finally(function () { busy(false); });
  };

  wall.querySelector("[data-lp-signin-toggle]").addEventListener("click", function () {
    panel.classList.toggle("open");
  });
  wall.querySelector("[data-prov='apple']").addEventListener("click", function () {
    run(function () { return window.lpAuth.signInApple(); });
  });
  wall.querySelector("[data-prov='google']").addEventListener("click", function () {
    run(function () { return window.lpAuth.signInGoogle(); });
  });
  wall.querySelector("[data-lp-email-form]").addEventListener("submit", function (e) {
    e.preventDefault();
    var f = e.target;
    run(function () { return window.lpAuth.signInEmail(f.email.value, f.password.value); });
  });

  // When auth state arrives (sign-in completes, or returning signed-in visitor), reflect it.
  // NOTE: this only confirms IDENTITY. The actual content unlock is Phase 3 (server-side
  // entitlement check via edge middleware) — for now we just acknowledge the signed-in user.
  window.addEventListener("lp-auth-changed", function (ev) {
    var user = ev.detail && ev.detail.user;
    if (!user) return;
    var who = user.email || user.displayName || "your account";
    wall.innerHTML =
      "<h3>You're signed in</h3>" +
      "<p>Signed in as <strong style='color:#e8efe9'>" + who + "</strong>. " +
      "Subscriber access unlocks here once we finish connecting your subscription — coming shortly.</p>" +
      "<div class='btns'><button type='button' class='ghost' data-lp-signout>Sign out</button></div>";
    var so = wall.querySelector("[data-lp-signout]");
    if (so) so.addEventListener("click", function () { window.lpAuth && window.lpAuth.signOut(); location.reload(); });
  });
})();
