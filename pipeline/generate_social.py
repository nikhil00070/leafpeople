#!/usr/bin/env python3
"""Build the daily Instagram asset for an article: a branded 1080x1350 card
(plant photo + headline + logo) and an on-brand caption.

Outputs to social/<slug>.jpg + social/<slug>.json ({image_path, caption, url,
title, section}). The IG-post step reads the sidecar JSON.

    python generate_social.py the-leaf petiole-tells-the-truth   # specific
    python generate_social.py                                    # newest in feed.json

Caption generation needs ANTHROPIC_API_KEY; without it the card still renders
(caption left blank) so the visual can be developed/tested offline.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import common

ASSETS = common.ROOT / "assets"
GEO = str(ASSETS / "Geologica.ttf")
INTER = str(ASSETS / "Inter.ttf")
LOGO = common.SITE_ROOT / "images" / "icon-512.png"

W, H = 1080, 1350
PAD = 72
ACCENT = (91, 209, 122)          # --green
INK = (244, 247, 244)
DIM = (244, 247, 244, 205)

SECTIONS = {"the-leaf": "Understory", "field-guide": "Field Guide"}


def _font(path, size, variation=None):
    f = ImageFont.truetype(path, size)
    if variation:
        try:
            f.set_variation_by_name(variation)
        except Exception:
            pass
    return f


def _wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _cover(img, w, h):
    """Resize+center-crop to exactly w x h."""
    src_r, dst_r = img.width / img.height, w / h
    if src_r > dst_r:
        nh = h; nw = round(h * src_r)
    else:
        nw = w; nh = round(w / src_r)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def render_card(data: dict, section_label: str, hero_path: Path, out_path: Path):
    base = _cover(Image.open(hero_path).convert("RGB"), W, H).convert("RGBA")

    # global darken + bottom gradient for legibility
    overlay = Image.new("RGBA", (W, H), (6, 9, 7, 70))
    base = Image.alpha_composite(base, overlay)
    grad = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        grad.putpixel((0, y), int(255 * (max(0.0, (t - 0.12) / 0.88) ** 1.5) * 0.95))
    shade = Image.new("RGBA", (W, H), (5, 8, 7, 0))
    shade.putalpha(grad.resize((W, H)))
    base = Image.alpha_composite(base, shade)

    d = ImageDraw.Draw(base)

    # eyebrow (top-left): section label, accent, tracked caps
    eb = _font(GEO, 30, "Bold")
    label = section_label.upper()
    tracked = "  ".join(list(label))
    d.text((PAD, PAD), tracked, font=eb, fill=ACCENT)

    # headline (bottom), Geologica Black, wrapped
    title = data["title"]
    hl = _font(GEO, 92, "Black")
    lines = _wrap(d, title, hl, W - 2 * PAD)
    if len(lines) > 4:                      # shrink to fit
        hl = _font(GEO, 72, "Black")
        lines = _wrap(d, title, hl, W - 2 * PAD)
    asc, desc = hl.getmetrics()
    lh = asc + desc + 8

    # footer row geometry
    foot_h = 64
    foot_y = H - PAD - foot_h
    # deck (one line, above headline-to-footer)
    deck = (data.get("deck") or "").strip()
    deck_font = _font(INTER, 34, "Medium")
    deck_all = _wrap(d, deck, deck_font, W - 2 * PAD) if deck else []
    deck_lines = deck_all[:2]
    if len(deck_all) > 2 and deck_lines:
        deck_lines[-1] = deck_lines[-1].rstrip(" ,;:—-") + "…"
    dl_h = (deck_font.getmetrics()[0] + deck_font.getmetrics()[1] + 6)

    block_h = len(lines) * lh + (len(deck_lines) * dl_h + 22 if deck_lines else 0)
    y = foot_y - 40 - block_h
    for ln in lines:
        d.text((PAD, y), ln, font=hl, fill=INK)
        y += lh
    if deck_lines:
        y += 22
        for ln in deck_lines:
            d.text((PAD, y), ln, font=deck_font, fill=(223, 230, 223))
            y += dl_h

    # accent rule above footer
    d.line([(PAD, foot_y - 18), (PAD + 64, foot_y - 18)], fill=ACCENT, width=4)

    # footer: logo + wordmark (left), CTA (right)
    logo = Image.open(LOGO).convert("RGBA").resize((foot_h, foot_h), Image.LANCZOS)
    mask = Image.new("L", (foot_h, foot_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, foot_h, foot_h], radius=16, fill=255)
    base.paste(logo, (PAD, foot_y), mask)
    wm = _font(GEO, 38, "ExtraBold")
    d.text((PAD + foot_h + 20, foot_y + 6), "Leaf People", font=wm, fill=INK)
    cta = _font(GEO, 26, "Bold")
    cta_txt = "Read it in the app →"
    cw = d.textlength(cta_txt, font=cta)
    d.text((W - PAD - cw, foot_y + 18), cta_txt, font=cta, fill=ACCENT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out_path, "JPEG", quality=90)
    print(f"[social] card -> {out_path}")


CAPTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["caption", "hashtags"],
}


def build_caption(data: dict, url: str, section_label: str) -> str:
    prompt = (
        f"Write an Instagram caption for this {section_label} article.\n"
        f"Title: {data['title']}\nDeck: {data.get('deck','')}\n"
        "1 strong hook line, then 2-3 sentences of genuine value/teaser (no spoilers of "
        "everything), then a call to action to read the full piece in the Leaf People app "
        "or at the link in bio. Confident, literate, never hypey. Then 8-12 specific "
        "hashtags (rare aroids, the genus/topic, plant collecting). Return JSON."
    )
    out = common.generate(common.voice(), prompt, CAPTION_SCHEMA, max_tokens=1200)
    tags = " ".join(t if t.startswith("#") else "#" + t.lstrip("#") for t in out["hashtags"])
    return out["caption"].strip() + "\n\n" + tags + f"\n\n{url}"


def main() -> int:
    if len(sys.argv) >= 3:
        section, slug = sys.argv[1], sys.argv[2]
    else:  # newest article in the feed
        feed = json.loads((common.SITE_ROOT / "feed.json").read_text(encoding="utf-8"))
        if not feed["items"]:
            print("[social] no articles"); return 0
        section, slug = feed["items"][0]["section"], feed["items"][0]["slug"]

    post = common.SITE_ROOT / section / slug
    data = json.loads((post / "_data.json").read_text(encoding="utf-8"))
    section_label = SECTIONS.get(section, "Stories")
    hero = common.SITE_ROOT / data["hero"].lstrip("/")
    url = f"https://leafpeople.app/{section}/{slug}"

    out_img = common.SITE_ROOT / "social" / f"{slug}.jpg"
    render_card(data, section_label, hero, out_img)

    caption = ""
    try:
        caption = build_caption(data, url, section_label)
        print("[social] caption generated")
    except Exception as e:
        print(f"[social] caption skipped ({e.__class__.__name__}: {e})")

    sidecar = {
        "section": section, "slug": slug, "title": data["title"],
        "url": url, "image_path": f"social/{slug}.jpg", "caption": caption,
    }
    (common.SITE_ROOT / "social" / f"{slug}.json").write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[social] sidecar -> social/{slug}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
