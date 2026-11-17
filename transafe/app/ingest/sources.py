"""Adapters that pull real public posts about Bengaluru public transport.

Each source has a `fetch()` that returns only items it has not returned before, as
`Item(ext_id, text, ts)`. They use the platforms' official APIs (no scraping), so each needs
credentials from the platform's developer console; see `.env.example`.
An `httpx.Client` can be injected so tests run without the network.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_POLL_SECONDS, REDDIT_SUBREDDITS,
                        X_BEARER_TOKEN, X_POLL_SECONDS)

USER_AGENT = "transafe/1.0 (student NLP project; read-only)"
TRANSPORT_TERMS = 'BMTC OR "Namma Metro" OR BMRCL OR "bmtc bus"'


class SourceError(Exception):
    """A source could not be read (bad credentials, rate limit, unpaid plan...). The message is shown in /api/sources."""


@dataclass
class Item:
    ext_id: str
    text: str
    ts: float          # when the post was written (unix seconds)


class XSource:
    """X (Twitter) API v2 recent search, newest posts about BMTC / Namma Metro (last 7 days only)."""
    label = "X / Twitter (live)"
    interval = X_POLL_SECONDS

    def __init__(self, bearer: str = X_BEARER_TOKEN, max_results: int = 10, client: httpx.Client | None = None):
        self.bearer, self.max_results = bearer, max_results
        self.client = client or httpx.Client(timeout=20)
        self.since_id: str | None = None     # makes X return (and bill) only posts newer than the last one seen

    def fetch(self) -> list[Item]:
        params = {"query": f"({TRANSPORT_TERMS}) -is:retweet -is:reply lang:en", "max_results": self.max_results,
                  "tweet.fields": "created_at"}
        if self.since_id:
            params["since_id"] = self.since_id
        r = self.client.get("https://api.x.com/2/tweets/search/recent", params=params,
                            headers={"Authorization": f"Bearer {self.bearer}", "User-Agent": USER_AGENT})
        if r.status_code in (401, 403):
            raise SourceError("X rejected the bearer token")
        if r.status_code == 402:
            raise SourceError("X API credits exhausted (pay-per-use plan)")
        if r.status_code == 429:
            raise SourceError("X rate limit reached")
        r.raise_for_status()
        body = r.json()
        posts = body.get("data", [])
        if posts:
            self.since_id = body.get("meta", {}).get("newest_id") or max(p["id"] for p in posts)
        return [Item(p["id"], p["text"], _iso_to_ts(p.get("created_at"))) for p in reversed(posts)]


class RedditSource:
    """Newest posts mentioning BMTC / metro in the Bengaluru subreddits, via Reddit's OAuth API (app-only login)."""
    label = "Reddit (live)"
    interval = REDDIT_POLL_SECONDS

    def __init__(self, client_id: str = REDDIT_CLIENT_ID, secret: str = REDDIT_CLIENT_SECRET,
                 subreddits: list[str] | None = None, client: httpx.Client | None = None):
        self.auth = (client_id, secret)
        self.subreddits = subreddits or REDDIT_SUBREDDITS
        self.client = client or httpx.Client(timeout=20)
        self.token: str | None = None
        self.seen: set[str] = set()

    def _login(self):
        r = self.client.post("https://www.reddit.com/api/v1/access_token", auth=self.auth,
                             data={"grant_type": "client_credentials"}, headers={"User-Agent": USER_AGENT})
        if r.status_code != 200 or "access_token" not in r.json():
            raise SourceError("Reddit login failed (check REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET)")
        self.token = r.json()["access_token"]

    def fetch(self) -> list[Item]:
        if not self.token:
            self._login()
        out: list[Item] = []
        for sub in self.subreddits:
            r = self.client.get(f"https://oauth.reddit.com/r/{sub}/search",
                                params={"q": "BMTC OR metro OR BMRCL", "restrict_sr": 1, "sort": "new", "t": "week",
                                        "limit": 25},
                                headers={"Authorization": f"bearer {self.token}", "User-Agent": USER_AGENT})
            if r.status_code == 401:       # token expired (they last ~1 h): log in again on the next poll
                self.token = None
                raise SourceError("Reddit token expired")
            if r.status_code == 429:
                raise SourceError("Reddit rate limit reached")
            r.raise_for_status()
            for child in r.json().get("data", {}).get("children", []):
                d = child["data"]
                if d["name"] in self.seen:
                    continue
                self.seen.add(d["name"])
                text = f"{d.get('title', '')}. {d.get('selftext', '')}".strip(". ")
                out.append(Item(d["name"], text, float(d.get("created_utc", 0))))
        return sorted(out, key=lambda i: i.ts)


def _iso_to_ts(value: str | None) -> float:
    from datetime import datetime, timezone
    if not value:
        return 0.0
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()


def configured_sources() -> list:
    """Sources whose credentials are present."""
    src = []
    if X_BEARER_TOKEN:
        src.append(XSource())
    if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
        src.append(RedditSource())
    return src
