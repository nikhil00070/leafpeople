"""Jinja2 renderer for article templates."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from common import inline_md, sci_name

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent / "templates")),
    autoescape=select_autoescape(["html"]),
)
_env.filters["sci_name"] = sci_name
# `md` converts our limited inline markdown to HTML. inline_md already escapes
# &, <, > before adding <strong>/<em>, so its output is safe to emit verbatim —
# wrap in Markup so Jinja's autoescape doesn't re-escape the tags.
_env.filters["md"] = lambda s: Markup(inline_md(s))


def render(template_name: str, **context) -> str:
    return _env.get_template(template_name).render(**context)
