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

/* ===== Subscriber wall (Phase 3: server-rendered) =====
   The wall (.lp-wall) is baked into preview.html by the render pipeline; the edge middleware
   serves preview.html to non-subscribers and the full index.html to subscribers. This script
   only WIRES the wall that's already in the DOM — it never decides access (the server does).
   On a full page there is no .lp-wall, so this is a no-op. */
(function () {
  "use strict";
  var wall = document.querySelector("[data-lp-wall]");
  if (!wall) return;

  // Lazy-load Firebase Auth (a module) only on a walled page — the ~100KB SDK never loads
  // on full articles. auth.js sets window.lpAuth + fires lp-auth-changed (with isSubscriber).
  if (!document.querySelector("script[data-lp-auth]")) {
    var authScript = document.createElement("script");
    authScript.type = "module";
    authScript.src = "/js/auth.js";
    authScript.setAttribute("data-lp-auth", "1");
    document.head.appendChild(authScript);
  }

  var panel = wall.querySelector("[data-lp-signin]");
  var status = wall.querySelector("[data-lp-status]");
  var setStatus = function (msg, isErr) {
    if (!status) return;
    status.textContent = msg || "";
    status.classList.toggle("err", !!isErr);
  };
  var busy = function (on) {
    wall.querySelectorAll("button,input").forEach(function (el) { el.disabled = on; });
  };
  var run = function (fn) {
    if (!window.lpAuth) { setStatus("Still loading — try again in a second.", true); return; }
    setStatus("Signing in…");
    busy(true);
    fn()
      .catch(function (e) {
        var m = window.lpAuth.readableError(e);
        if (m) setStatus(m, true); else setStatus(""); // null = user cancelled
      })
      .finally(function () { busy(false); });
  };

  var toggle = wall.querySelector("[data-lp-signin-toggle]");
  if (toggle && panel) toggle.addEventListener("click", function () { panel.classList.toggle("open"); });
  var apple = wall.querySelector("[data-prov='apple']");
  if (apple) apple.addEventListener("click", function () { run(function () { return window.lpAuth.signInApple(); }); });
  var google = wall.querySelector("[data-prov='google']");
  if (google) google.addEventListener("click", function () { run(function () { return window.lpAuth.signInGoogle(); }); });
  var emailForm = wall.querySelector("[data-lp-email-form]");
  if (emailForm) emailForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var f = e.target;
    run(function () { return window.lpAuth.signInEmail(f.email.value, f.password.value); });
  });

  // Auth state arrived (sign-in completed, or a returning signed-in visitor).
  // SUBSCRIBER -> reload; the edge middleware now sees the token cookie + claim and serves the full page.
  // SIGNED IN, NOT SUBSCRIBED -> say so, point them to the app.
  window.addEventListener("lp-auth-changed", function (ev) {
    var d = ev.detail || {};
    if (!d.user) return;
    if (d.isSubscriber) {
      setStatus("Subscription found — unlocking…");
      location.reload();
      return;
    }
    var who = d.user.email || d.user.displayName || "your account";
    wall.innerHTML =
      "<h3>You're signed in</h3>" +
      "<p>Signed in as <strong style='color:#e8efe9'>" + who + "</strong>, but we don't see an active subscription on this account. " +
      "Subscribe in the app to unlock every story here on the web.</p>" +
      "<div class='btns'>" +
        "<a class='primary' href='https://apps.apple.com/us/app/leaf-people-rare-plant-guide/id6760627345' target='_blank' rel='noopener'>Subscribe in the app</a>" +
        "<button type='button' class='ghost' data-lp-signout>Sign out</button>" +
      "</div>";
    var so = wall.querySelector("[data-lp-signout]");
    if (so) so.addEventListener("click", function () { window.lpAuth && window.lpAuth.signOut(); location.reload(); });
  });
})();
