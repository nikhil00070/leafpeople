"""Zero-tolerance AI-slop gate. Scans generated prose for banned phrases and
flags any article that contains them so it can be regenerated rather than shipped."""

BANNED = [
    "delve into", "in today's fast-paced world", "navigating the landscape",
    "vibrant tapestry", "hidden gem", "nestled in", "a testament to",
    "when it comes to", "it's worth noting", "in conclusion", "unlock the secrets",
    "elevate your", "game-changer", "look no further", "dive in", "treasure trove",
    "the world of", "embark on a journey", "rich history", "stunning beauty",
    "must-have", "takes center stage", "at the end of the day", "low-maintenance",
]


def find_slop(text: str) -> list[str]:
    low = text.lower()
    return [p for p in BANNED if p in low]


def check_article(strings: list[str]) -> list[str]:
    """Return the list of banned phrases found across all provided text strings."""
    hits: list[str] = []
    for s in strings:
        hits.extend(find_slop(s))
    return sorted(set(hits))
