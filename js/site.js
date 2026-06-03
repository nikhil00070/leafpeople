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
  var PAYWALL_ON = false;
  var preview = location.search.indexOf("paywall=1") !== -1;
  if (!(PAYWALL_ON || preview)) return;
  if (!/^\/(the-leaf|field-guide)\//.test(location.pathname)) return;

  var box = document.querySelector("article.prose") || document.querySelector(".guide-wrap");
  if (!box) return;

  // WSJ-style: clamp the body to ~6 lines, then fade it out into the wall.
  box.style.position = "relative";
  box.style.maxHeight = "16em";
  box.style.overflow = "hidden";
  var fade = document.createElement("div");
  fade.style.cssText = "position:absolute;left:0;right:0;bottom:0;height:7em;pointer-events:none;background:linear-gradient(to bottom,rgba(255,255,255,0),var(--bg,#fff))";
  box.appendChild(fade);

  var css = document.createElement("style");
  css.textContent =
    ".lp-wall{margin:0 0 1.2rem;padding:.4rem 1.4rem 1.4rem;text-align:center}" +
    ".lp-wall h3{font-family:'Geologica',sans-serif;font-size:1.45rem;margin:0 0 .5rem}" +
    ".lp-wall p{color:#5a6b5e;max-width:44ch;margin:0 auto 1.3rem;line-height:1.5}" +
    ".lp-wall .btns{display:flex;gap:.7rem;justify-content:center;flex-wrap:wrap}" +
    ".lp-wall a{display:inline-block;padding:.72rem 1.35rem;border-radius:10px;font-weight:700;text-decoration:none;font-size:.92rem}" +
    ".lp-wall .primary{background:#FA2A52;color:#fff}" +
    ".lp-wall .ghost{background:transparent;color:#2b3a2f;border:1px solid rgba(0,0,0,.2)}";
  document.head.appendChild(css);

  var wall = document.createElement("div");
  wall.className = "lp-wall";
  wall.innerHTML =
    "<h3>Keep reading with Leaf People</h3>" +
    "<p>The rest of this story is for subscribers. One Leaf People subscription unlocks every Understory feature and Field Guide — in the app and here on the web.</p>" +
    "<div class='btns'>" +
      "<a class='primary' href='https://apps.apple.com/us/app/leaf-people-rare-plant-guide/id6760627345' target='_blank' rel='noopener'>Subscribe in the app</a>" +
      "<a class='ghost' href='#' data-lp-signin>Already a subscriber? Sign in</a>" +
    "</div>";
  box.parentNode.insertBefore(wall, box.nextSibling);

  // Phase 2 will wire this to Firebase Auth (Sign in with Apple); placeholder for now.
  var si = wall.querySelector("[data-lp-signin]");
  if (si) si.addEventListener("click", function (e) { e.preventDefault(); alert("Web sign-in is coming soon — for now, subscribe in the app."); });
})();
