# Content Pipeline

Generates the two article sections — **The Leaf** (editorial) and **Field Guide** (genus
care guides) — with Claude, and renders them to static HTML.

## How it works

1. Topics live in `leaf_queue.json` / `guide_queue.json`, each item `{slug, …, status}`.
2. A generator picks the next `status: "queued"` item.
3. It calls Claude **Sonnet 4.6** with:
   - a **cached** system prompt = `voice.md` (editorial voice + rules + forbidden phrases),
   - the per-topic instruction as the (uncached) user message,
   - `output_config.format` = a JSON schema, so the response is structured JSON.
4. `slop_repair.py` rejects any draft containing banned AI-"slop" phrases.
5. `render.py` fills a Jinja2 template (`templates/leaf-canonical.html` /
   `guide-canonical.html`) and writes `<section>/<slug>/index.html`.
6. `manifest_helpers.py` upserts the entry into the section `manifest.json` (drives the
   index page), and `generate_sitemap.py` rebuilds `sitemap.xml`.
7. The item is marked `published`.

Prompt caching: `voice.md` is the stable prefix sent with `cache_control: ephemeral`, so
repeated runs in a cache window pay full price for it only once. Each run prints token
usage including `cache_read` so you can confirm hits.

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
cd pipeline
python generate_leaf.py     # publishes next queued The Leaf article
python generate_guide.py    # publishes next queued Field Guide article
python generate_sitemap.py  # rebuild sitemap.xml
```

## Scheduling

GitHub Actions (`.github/workflows/`) run on cron and commit results:

| Workflow | Cadence |
|----------|---------|
| `leaf-publisher.yml`  | Mon/Wed/Fri 8:00 AM ET |
| `guide-generator.yml` | Weekdays 10:15 AM ET |

Set the `ANTHROPIC_API_KEY` secret in the repo. Both also support manual
`workflow_dispatch`.

## Adding topics

Append objects to the queue files. The Leaf items use `{slug, title_hint, category}`;
Field Guide items use `{slug, genus, title_hint}`. New items default to `status: "queued"`.
