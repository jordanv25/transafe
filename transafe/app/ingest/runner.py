"""Background polling of the live sources into the Engine."""
from __future__ import annotations

import asyncio
import time

from app.ingest.sources import SourceError

MAX_BACKOFF = 3600


async def poll_forever(engine, source, status: dict):
    """Poll one source forever. `status` is a dict shown by GET /api/sources."""
    status.update(source=source.label, ok=None, error=None, ingested=0, last_poll=None)
    wait = 0.0
    while True:
        await asyncio.sleep(wait)
        try:
            items = await asyncio.to_thread(source.fetch)
            status["ingested"] += ingest_items(engine, source.label, items)
            status.update(ok=True, error=None)
            wait = source.interval
        except SourceError as e:
            status.update(ok=False, error=str(e))
            wait = min(MAX_BACKOFF, max(wait * 2, source.interval))
        except Exception as e:                      # network hiccup etc.: keep the app alive, retry later
            status.update(ok=False, error=f"{type(e).__name__}: {e}")
            wait = min(MAX_BACKOFF, max(wait * 2, source.interval))
        status["last_poll"] = time.time()


def ingest_items(engine, label: str, items) -> int:
    n = 0
    for it in items:
        if not it.text.strip():
            continue
        # keep the post's own time when it is sane, so a first poll that returns older posts lands in the past
        ts = it.ts if 0 < it.ts <= engine.vtime else None
        engine.ingest(it.text, label, ts=ts)
        n += 1
    return n
