#!/usr/bin/env python3
"""Send one FCM push announcing newly-featured plants in Leaf People.

Lands exactly like the Stories push (same FCM v1 path, same 'stories' topic that
every installed app is already subscribed to) — so it reaches all customers with
NO app build. Unlike the Stories push it carries NO article keys, so tapping it
just opens the app; the launch sync (PlantLibrarySync) then pulls the new plants
in. Run it every time new plants get featured (right after the promote bumps the
library version).

    python send_plant_push.py                      # DRY RUN — preview only (default, safe)
    python send_plant_push.py --send               # actually broadcast to all customers
    python send_plant_push.py --send --image <url> # include a hero image in the banner
    python send_plant_push.py --title "..." --body "..." --send   # override copy

Safety: defaults to DRY RUN. It NEVER delivers without --send, so you always
preview the exact broadcast first.

Auth (for --send), in order: (1) FCM_SERVICE_ACCOUNT env (the whole JSON, the
same secret the CI Stories pusher uses), else (2) the local firebase-tools login
token (~/.config/configstore/firebase-tools.json) — the same credential the
promote scripts use for Firestore, which also carries FCM scope. So this fires
straight from the Mac with nothing extra to configure.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT_ID = "leafpeople-1c8d1"
TOPIC = "stories"   # every install subscribes to this topic (NotificationManager)
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FB_CLI = ("563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com",
          "j9iVZfS8kkCEFUPaAeJV0sAi")

# The locked, evergreen copy (count-less so it fits every drop).
DEFAULT_TITLE = "Woohoo — new rare plants added! 🌱"
DEFAULT_BODY = "New featured plants + care guides just landed. Keep collecting."


def access_token() -> tuple:
    """(bearer_token, project_id). Prefer the CI service account; fall back to the
    local firebase-tools login token (which carries FCM scope)."""
    sa_raw = os.environ.get("FCM_SERVICE_ACCOUNT")
    if sa_raw:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        sa_info = json.loads(sa_raw)
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=[FCM_SCOPE])
        creds.refresh(Request())
        return creds.token, sa_info["project_id"]
    cfg = os.path.expanduser("~/.config/configstore/firebase-tools.json")
    rt = json.load(open(cfg))["tokens"]["refresh_token"]
    data = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": rt,
                                   "client_id": FB_CLI[0], "client_secret": FB_CLI[1]}).encode()
    tok = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data))["access_token"]
    return tok, PROJECT_ID


def build_message(title: str, body: str, image_url: str = "") -> dict:
    apns = {"payload": {"aps": {"sound": "default", "mutable-content": 1}}}
    if image_url:
        apns["fcm_options"] = {"image": image_url}
    msg = {
        "message": {
            "topic": TOPIC,
            "notification": {"title": title, "body": body},
            # A marker so the app (and our own logs) can tell a plant drop from a
            # story push. No article keys → OpenArticle.from() returns nil → tapping
            # just opens the app, which syncs the new plants on launch.
            "data": {"kind": "plant_drop"},
            "apns": apns,
        }
    }
    if image_url:
        msg["message"]["notification"]["image"] = image_url
    return msg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default=DEFAULT_TITLE)
    ap.add_argument("--body", default=DEFAULT_BODY)
    ap.add_argument("--image", default="", help="optional hero image URL for the banner")
    ap.add_argument("--send", action="store_true", help="actually deliver (default is dry-run preview)")
    args = ap.parse_args()

    message = build_message(args.title, args.body, args.image)

    if not args.send:
        print("[push] DRY RUN (no --send) — would broadcast to ALL customers on topic '%s':" % TOPIC)
        print(json.dumps(message, ensure_ascii=False, indent=2))
        return 0

    token, project_id = access_token()
    req = urllib.request.Request(
        f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
        data=json.dumps(message).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.load(r)
        print(f"[push] sent plant drop to topic '{TOPIC}': {resp.get('name')}")
        return 0
    except urllib.error.HTTPError as e:
        print(f"[push] FAILED {e.code}: {e.read().decode()[:400]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
