"""FastAPI application: REST + Server-Sent-Events API and static UI."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import (ACTIONABLE, CATEGORIES, CATEGORY_COLORS, CATEGORY_LABELS, GOOGLE_MAPS_API_KEY, SOURCES,
                        STATIC_DIR)
from app.data.gazetteer import PLACES
from app.data.generator import add_noise
from app.engine.core import Engine
from app.engine.simulator import SCENARIOS, Simulator
from app.ingest.runner import poll_forever
from app.ingest.sources import configured_sources
from app.nlp.models import load_metrics

# 50 h of history means >= 2 whole days, which switches the trend detector to its time-of-day baseline
BACKFILL_HOURS = float(os.environ.get("TRANSAFE_BACKFILL_HOURS", "50"))
SIM_SEED = int(os.environ.get("TRANSAFE_SEED", "11"))             # random seed of the simulator
AUTOSTART_SIM = os.environ.get("TRANSAFE_SIM", "1") == "1"
LIVE_ALLOWED = os.environ.get("TRANSAFE_LIVE", "1") == "1"      # TRANSAFE_LIVE=0 forces simulator mode

engine: Engine
sim: Simulator
live = False                      # True when real feeds are polled instead of the simulator
source_status: list[dict] = []    # one entry per live source, filled by the pollers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Live mode (any X / Reddit credentials set): real-time clock, real posts only, no synthetic data.
    Otherwise: the simulator with a backfilled history."""
    global engine, sim, live
    engine = Engine()
    sim = Simulator(engine, seed=SIM_SEED)
    sources = configured_sources() if LIVE_ALLOWED else []
    live = bool(sources)
    source_status.clear()
    tasks = []
    if live:
        engine.speed = 1.0
        tasks.append(asyncio.create_task(sim.run_live()))
        for s in sources:
            source_status.append({})
            tasks.append(asyncio.create_task(poll_forever(engine, s, source_status[-1])))
    else:
        if BACKFILL_HOURS > 0:
            await asyncio.to_thread(sim.backfill, BACKFILL_HOURS)
        engine.running = AUTOSTART_SIM
        tasks.append(asyncio.create_task(sim.run()))
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Transafe - Real-Time Public Transport Complaint Analyzer", lifespan=lifespan)


class AnalyzeIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    noise: float = Field(0, ge=0, le=100)         # % of words that get a typo before analysis (0 = text unchanged)
    seed: int | None = None                       # same seed + same text + same noise = same typos


class ComplaintIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    source: str = "Complaint Portal"


class SimIn(BaseModel):
    running: bool | None = None
    speed: float | None = Field(None, ge=1, le=600)
    auto_incidents: bool | None = None


class IncidentIn(BaseModel):
    kind: str
    location: str | None = None


def _clean(a: dict) -> dict:
    a = dict(a)
    a.pop("_emb", None)
    return a


@app.get("/api/meta")
def meta():
    return {"categories": [{"key": c, "label": CATEGORY_LABELS[c], "color": CATEGORY_COLORS[c]} for c in CATEGORIES],
            "actionable": ACTIONABLE, "sources": SOURCES, "live": live, "maps_key": GOOGLE_MAPS_API_KEY,
            "places": {p[0]: {"lat": p[2], "lng": p[3]} for p in PLACES},
            "scenarios": [{"key": k, "name": v["name"], "locations": v["locs"]} for k, v in SCENARIOS.items()]}


@app.get("/api/state")
def state():
    return {"snapshot": engine.snapshot(), "feed": engine.recent_feed(40)}


@app.post("/api/analyze")
def analyze(body: AnalyzeIn):
    """Run the full NLP pipeline on a text with a detailed trace (nothing is stored).

    With noise > 0 the text first goes through the generator's add_noise() (typos, slang, odd case), so the
    spell-corrector can be shown working: `original` is what was sent, `noisy_text` is what was analysed.
    """
    noisy = body.text
    if body.noise > 0:
        # add_noise gives each word a typo with probability p_typo * 0.15, so noise 100 % -> p_typo 6.67 -> every word
        noisy = add_noise(body.text, random.Random(body.seed), p_typo=body.noise / 15)
    out = _clean(engine.analyzer.analyze(noisy, trace=True))
    out.update(original=body.text, noisy_text=noisy, noise=body.noise)
    return out


@app.post("/api/complaints")
def add_complaint(body: ComplaintIn):
    rec = engine.ingest(body.text, body.source)
    return Engine.public(rec)


@app.post("/api/complaints/batch")
async def upload_csv(file: UploadFile = File(...)):
    """CSV with a `text` column (optional `source`)."""
    raw = (await file.read()).decode("utf-8", errors="ignore")
    rows = list(csv.DictReader(io.StringIO(raw)))
    if not rows or "text" not in rows[0]:
        raise HTTPException(400, "CSV must have a 'text' column")
    n = 0
    for r in rows[:2000]:
        if (r.get("text") or "").strip():
            engine.ingest(r["text"], r.get("source") or "CSV Import")
            n += 1
    return {"ingested": n}


@app.get("/api/complaints")
def complaints(q: str | None = None, category: str | None = None, limit: int = Query(30, le=200)):
    if q:
        return engine.search(q, limit, category)
    feed = engine.recent_feed(200)
    if category:
        feed = [f for f in feed if f["category"] == category]
    return feed[:limit]


@app.get("/api/issues")
def issues(category: str | None = None, q: str | None = None):
    return engine.clusters(category, q)


@app.get("/api/issues/{cid}")
def issue(cid: int):
    d = engine.cluster_detail(cid)
    if not d:
        raise HTTPException(404, "issue not found")
    return d


@app.get("/api/model")
def model():
    return load_metrics()


@app.post("/api/simulator")
def simulator(body: SimIn):
    if body.running is not None:
        engine.running = body.running
    if body.speed is not None:
        engine.speed = body.speed
    if body.auto_incidents is not None:
        sim.auto_incidents = body.auto_incidents
    return {"running": engine.running, "speed": engine.speed, "auto_incidents": sim.auto_incidents}


@app.get("/api/sources")
def sources():
    """Health of the live feeds (empty in simulator mode)."""
    return {"live": live, "sources": source_status}


@app.post("/api/simulator/incident")
def incident(body: IncidentIn):
    if live:
        raise HTTPException(409, "incidents can only be injected in simulator mode")
    if body.kind not in SCENARIOS:
        raise HTTPException(400, f"unknown scenario; choose from {list(SCENARIOS)}")
    return sim.trigger(body.kind, body.location) | {"mix": None}


@app.get("/api/export.csv")
def export_csv():
    cols, rows = engine.export_rows()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    w.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=complaints.csv"})


@app.get("/api/stream")
async def stream():
    """Server-Sent Events: `complaint` / `incident` events as they happen + a `snapshot` every 2 s."""
    q = engine.subscribe()

    async def gen():
        try:
            yield "retry: 2000\n\n"
            last = 0.0
            loop = asyncio.get_event_loop()
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    pass
                if loop.time() - last > 2.0:
                    last = loop.time()
                    yield f"data: {json.dumps({'event': 'snapshot', 'data': engine.snapshot()})}\n\n"
        finally:
            engine.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
