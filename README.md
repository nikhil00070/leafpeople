# Leaf People — Website

Marketing site + AI-generated content sections for **Leaf People**, the rare-aroid field
guide, care tracker, and collector's marketplace. Static HTML, deployed on Vercel.
Modeled on the ForkFox site structure, recolored to a green→teal botanical palette.

App Store: https://apps.apple.com/us/app/leaf-people-rare-plant-guide/id6760627345

## Structure

```
.
├── index.html              # cinematic landing page
├── css/site.css            # design system (palette, type, components)
├── js/site.js              # nav, reveals, count-ups, care bars
├── images/app/             # app screenshots (shot-01 … shot-10)
├── the-leaf/               # Understory — long-form editorial (Dish equivalent)
│   ├── index.html          #   manifest-driven index
│   ├── manifest.json       #   article list (generated)
│   └── <slug>/index.html   #   article pages (generated)
├── field-guide/            # Field Guide — genus care guides (Carte equivalent)
│   ├── index.html          #   index with genus filter
│   ├── manifest.json
│   └── <slug>/index.html
├── privacy/  support/      # static pages
├── pipeline/               # daily article generator (Python + Claude + Jinja2)
├── .github/workflows/      # cron jobs that publish articles
└── vercel.json             # routing + cache headers
```

## Local preview

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```

## Deploy (Vercel)

The repo root is the deploy root. Connect the repo in Vercel, or:

```bash
vercel --prod
```

## Content pipeline

See [`pipeline/README.md`](pipeline/README.md). In short: topics live in
`pipeline/leaf_queue.json` / `guide_queue.json`; GitHub Actions run the generators on a
cron, which call Claude (Sonnet 4.6) with a cached editorial-voice system prompt + a JSON
schema, run an AI-"slop" quality gate, render Jinja2 templates to HTML, update the section
manifest, rebuild `sitemap.xml`, and commit. Requires the `ANTHROPIC_API_KEY` repo secret.

## Brand

| Token | Value |
|-------|-------|
| Background | `#0B0F0D` |
| Card | `#141A16` |
| Accent (green→teal) | `#57C77A → #25B5C9` |
| Display / body / serif | Geologica / Inter / Lora |
