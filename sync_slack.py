#!/usr/bin/env python3
"""
sync_slack.py — Fetches new info requests from #commercial-global and #aes-global
and writes them into data/requests.json.

Usage:
    pip install slack-sdk
    export SLACK_BOT_TOKEN=xoxb-your-token-here
    python scripts/sync_slack.py

GitHub Actions: set SLACK_BOT_TOKEN as a repository secret.
"""

import os
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    raise SystemExit("Install slack-sdk first:  pip install slack-sdk")


# ── Config ────────────────────────────────────────────────────────────────────
CHANNELS = {
    "C04P01H413R": "commercial-global",
    "C081H6A0CVC": "aes-global",
    "CD2EU60KA": "success",
}

# Keywords that indicate an information request
REQUEST_PATTERNS = [
    r"\bdoes anyone\b",
    r"\bcan anyone\b",
    r"\banyone have\b",
    r"\banyone know\b",
    r"\banyone got\b",
    r"\blooking for\b",
    r"\bsomeone have\b",
    r"\bdo we have\b",
    r"\bcan someone\b",
]
REQUEST_RE = re.compile("|".join(REQUEST_PATTERNS), re.IGNORECASE)

# Category keyword rules — order matters (first match wins)
CATEGORIES = [
    {
        "id": "risk",
        "name": "Risk product",
        "color": "#993C1D",
        "keywords": ["risk", "vendor risk", "due diligence", "risk dashboard", "risk deck", "risk intel"],
    },
    {
        "id": "samples",
        "name": "Sample reports & examples",
        "color": "#0F6E56",
        "keywords": ["report", "example", "newsletter", "insight", "earnings", "campaign", "social report", "pharma"],
    },
    {
        "id": "sales",
        "name": "Sales collateral & decks",
        "color": "#185FA5",
        "keywords": ["deck", "slide", "buyer pack", "proposal", "template", "pitch", "rfp", "roadmap", "one pager", "one-pager", "brief"],
    },
    {
        "id": "refs",
        "name": "Client references & contacts",
        "color": "#534AB7",
        "keywords": ["reference", "contact", "connection", "intro", "client who", "customer who", "speak to", "ambassador"],
    },
    {
        "id": "comp",
        "name": "Competitive intelligence",
        "color": "#854F0B",
        "keywords": ["competitor", "alphasense", "alpha sense", "valona", "bloomberg", "m-brain", "memo", "everbridge", "dataminr", "public relay", "competitive"],
    },
    {
        "id": "ops",
        "name": "Operational & admin",
        "color": "#5F5E5A",
        "keywords": ["login", "password", "w9", "banking", "gong", "salesforce", "api", "link", "contract", "clause", "ungm", "tableau"],
    },
]


def classify(text: str) -> str:
    """Return the category id for a message text."""
    t = text.lower()
    for cat in CATEGORIES:
        if any(kw in t for kw in cat["keywords"]):
            return cat["id"]
    return "ops"  # fallback


def is_request(text: str) -> bool:
    return bool(REQUEST_RE.search(text))


def load_existing(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "last_synced": "2024-01-01T00:00:00Z",
        "categories": [
            {**{k: v for k, v in cat.items() if k != "keywords"}, "requests": []}
            for cat in CATEGORIES
        ],
    }


def save(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {path}")


def fetch_channel(client: WebClient, channel_id: str, channel_name: str, oldest_ts: str) -> list[dict]:
    """Fetch all messages newer than oldest_ts that match request patterns."""
    found = []
    cursor = None

    while True:
        kwargs = dict(channel=channel_id, oldest=oldest_ts, limit=200)
        if cursor:
            kwargs["cursor"] = cursor

        try:
            resp = client.conversations_history(**kwargs)
        except SlackApiError as e:
            print(f"  Error fetching {channel_name}: {e.response['error']}")
            break

        for msg in resp["messages"]:
            text = msg.get("text", "")
            if not text or msg.get("subtype"):
                continue
            if not is_request(text):
                continue

            ts = float(msg["ts"])
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            date_str = dt.strftime("%Y-%m-%d")

            # Get display name
            user_id = msg.get("user", "")
            try:
                user_info = client.users_info(user=user_id)
                author = user_info["user"]["profile"].get("real_name", user_id)
            except Exception:
                author = user_id

            permalink = f"https://signalhq.slack.com/archives/{channel_id}/p{msg['ts'].replace('.', '')}"

            found.append({
                "date": date_str,
                "author": author,
                "channel": channel_name,
                "text": text[:400],  # truncate very long messages
                "url": permalink,
                "_ts": msg["ts"],
            })

        if not resp.get("has_more"):
            break
        cursor = resp["response_metadata"].get("next_cursor")
        time.sleep(0.5)  # rate limit

    print(f"  {channel_name}: found {len(found)} new requests")
    return found


def merge(data: dict, new_messages: list[dict]) -> int:
    """Merge new messages into data, deduplicating by URL. Returns count added."""
    # Build set of existing URLs
    existing_urls = {
        r["url"]
        for cat in data["categories"]
        for r in cat["requests"]
    }

    cat_map = {cat["id"]: cat for cat in data["categories"]}
    added = 0

    for msg in new_messages:
        if msg["url"] in existing_urls:
            continue
        cat_id = classify(msg["text"])
        entry = {k: v for k, v in msg.items() if k != "_ts"}
        cat_map[cat_id]["requests"].append(entry)
        existing_urls.add(msg["url"])
        added += 1

    return added


def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise SystemExit("Set the SLACK_BOT_TOKEN environment variable.")

    client = WebClient(token=token)
    data_path = Path(__file__).parent.parent / "data" / "requests.json"
    data = load_existing(data_path)

    # Fetch from last synced timestamp
    last_sync_dt = datetime.fromisoformat(data["last_synced"].replace("Z", "+00:00"))
    oldest_ts = str(last_sync_dt.timestamp())

    print(f"Fetching messages since {data['last_synced']}...")
    all_new = []
    for channel_id, channel_name in CHANNELS.items():
        msgs = fetch_channel(client, channel_id, channel_name, oldest_ts)
        all_new.extend(msgs)

    added = merge(data, all_new)
    data["last_synced"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    save(data_path, data)
    print(f"\nDone — added {added} new requests. Total: {sum(len(c['requests']) for c in data['categories'])}")


if __name__ == "__main__":
    main()
