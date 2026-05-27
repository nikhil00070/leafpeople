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
