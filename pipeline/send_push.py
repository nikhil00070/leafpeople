#!/usr/bin/env python3
"""Send one FCM push to the 'stories' topic for a published article.

Usage:
    python send_push.py <section>/<slug>

Reads the Firebase service account from the FCM_SERVICE_ACCOUNT env var (the whole
JSON, set as a GitHub repo secret). The project_id is read FROM that JSON, so
there's nothing else to configure.

Without FCM_SERVICE_ACCOUNT set, runs in DRY-RUN mode: prints the exact message
it would send and exits 0. This lets the publish workflow call it unconditionally
and lets you test locally before the secret exists.

Called by .github/workflows/publish.yml after an article is published.
"""

import json
import os
import sys
import urllib.error
import urllib.request

import common

SECTIONS = {"the-leaf": "Understory", "field-guide": "Field Guide"}
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


def access_token(sa_info: dict) -> str:
    """OAuth2 access token from the service account (FCM v1 needs Bearer auth)."""
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request

    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=[FCM_SCOPE])
    creds.refresh(Request())
    return creds.token


def build_message(section: str, slug: str) -> dict:
    data = json.loads((common.SITE_ROOT / section / slug / "_data.json").read_text(encoding="utf-8"))
    label = SECTIONS.get(section, "Stories")
    title = data["title"]
    url = f"https://leafpeople.app/{section}/{slug}"
    hero = data.get("hero") or ""
    image_url = f"https://leafpeople.app{hero}" if hero else ""

    apns = {"payload": {"aps": {"sound": "default", "mutable-content": 1}}}
    if image_url:
        apns["fcm_options"] = {"image": image_url}

    return {
        "message": {
            "topic": "stories",
            "notification": {"title": f"New in {label}", "body": title},
            # data travels to the app so it can deep-link into the native reader
            "data": {
                "section": section,
                "slug": slug,
                "url": url,
                "title": title,
                "deck": data.get("deck", ""),
                "image": image_url,
                "data_url": f"{url}/_data.json",
            },
            "apns": apns,
        }
    }


def main() -> int:
    if len(sys.argv) < 2 or "/" not in sys.argv[1]:
        print("usage: send_push.py <section>/<slug>", file=sys.stderr)
        return 2
    section, slug = sys.argv[1].split("/", 1)
    if not (common.SITE_ROOT / section / slug / "_data.json").exists():
        print(f"[push] no _data.json for {section}/{slug}", file=sys.stderr)
        return 2

    message = build_message(section, slug)

    sa_raw = os.environ.get("FCM_SERVICE_ACCOUNT")
    if not sa_raw:
        print("[push] DRY RUN — FCM_SERVICE_ACCOUNT not set. Would send:")
        print(json.dumps(message, indent=2))
        return 0

    sa_info = json.loads(sa_raw)
    project_id = sa_info["project_id"]
    token = access_token(sa_info)

    req = urllib.request.Request(
        f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
        data=json.dumps(message).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.load(r)
        print(f"[push] sent to topic 'stories': {resp.get('name')}")
        return 0
    except urllib.error.HTTPError as e:
        print(f"[push] FAILED {e.code}: {e.read().decode()[:400]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
