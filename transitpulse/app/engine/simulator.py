"""Live complaint-stream simulator.

Produces a realistic, time-varying stream (rush-hour peaks, night lull) and
injects *incidents* (bus breakdown, metro snag, rain, safety spree...) that
create genuine bursts for the trend detector to find.  The pipeline itself is
source-agnostic: real feeds can be pushed into POST /api/complaints.
"""
from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

from app.config import SOURCES, SOURCE_WEIGHTS, TIMEZONE
from app.data.generator import generate
from app.data.gold_test import GOLD
from app.data.gazetteer import ROUTES

TZ = ZoneInfo(TIMEZONE)

SCENARIOS = {
    "bus_breakdown": {"name": "Bus breakdown", "mix": {"breakdown": 0.5, "delay": 0.3, "overcrowding": 0.2},
                      "rate": 5.0, "minutes": 40, "locs": ["Silk Board", "Hebbal", "Marathahalli", "KR Puram", "Majestic"]},
    "metro_snag": {"name": "Metro technical snag", "mix": {"breakdown": 0.45, "delay": 0.3, "overcrowding": 0.25},
                   "rate": 6.0, "minutes": 35, "locs": ["MG Road", "Majestic", "Indiranagar", "Yeshwanthpur", "Trinity"]},
    "heavy_rain": {"name": "Heavy rain / waterlogging", "mix": {"delay": 0.55, "breakdown": 0.2, "safety": 0.15, "accessibility": 0.1},
                   "rate": 4.5, "minutes": 50, "locs": ["Bellandur", "Hosur Road", "Sarjapur Road", "Koramangala"]},
    "safety_spree": {"name": "Safety incidents on a corridor", "mix": {"safety": 0.7, "driver_behavior": 0.3},
                     "rate": 3.5, "minutes": 45, "locs": ["Peenya", "Kengeri", "Yelahanka", "Nayandahalli"]},
    "event_crowd": {"name": "Event crowd (match / concert)", "mix": {"overcrowding": 0.7, "delay": 0.2, "safety": 0.1},
                    "rate": 6.0, "minutes": 40, "locs": ["MG Road", "Cubbon Park", "Trinity", "Shivajinagar"]},
    "ac_failure": {"name": "AC failures on a route", "mix": {"vehicle_condition": 0.8, "overcrowding": 0.2},
                   "rate": 3.5, "minutes": 45, "locs": ["Electronic City", "Whitefield", "Banashankari", "Hebbal"]},
}

BASE_MIX = {"overcrowding": 0.21, "delay": 0.25, "safety": 0.06, "driver_behavior": 0.11, "vehicle_condition": 0.09,
            "fare_ticketing": 0.09, "breakdown": 0.06, "accessibility": 0.05, "other": 0.08}


def base_rate(vt: float) -> float:
    """complaints per virtual minute at virtual time vt"""
    h = datetime.fromtimestamp(vt, TZ)
    x = h.hour + h.minute / 60
    r = 1.1
    for centre, amp in ((9.0, 1.6), (18.5, 1.9)):
        r += amp * np.exp(-((x - centre) ** 2) / 2.2)
    if x < 5.5 or x > 22.5:
        r *= 0.35
    return float(r)


def peak_mix(vt: float) -> dict:
    h = datetime.fromtimestamp(vt, TZ)
    x = h.hour + h.minute / 60
    mix = dict(BASE_MIX)
    if 7.5 <= x <= 10.5 or 17 <= x <= 20.5:
        mix["overcrowding"] *= 1.8
        mix["delay"] *= 1.4
    return mix


class Simulator:
    def __init__(self, engine, seed=11):
        self.e = engine
        self.rng = random.Random(seed)
        self.np = np.random.default_rng(seed)
        self.next_incident = 1
        self.auto_incidents = True
        self._next_auto = self.e.vtime + self.rng.uniform(20, 45) * 60
        self.task = None

    # -------------------------------------------------------------------
    def _complaint(self, vt, mix, loc=None, route=None):
        cats, w = zip(*mix.items())
        cat = self.rng.choices(cats, w)[0]
        src = self.rng.choices(SOURCES, SOURCE_WEIGHTS)[0]
        if loc is None and self.rng.random() < 0.2 and cat != "other":
            text = self.rng.choice([t for l, t in GOLD if l == cat])
        else:
            text = generate(self.rng, cat, loc=loc, route=route)["text"]
        return text, src

    def trigger(self, kind: str, location: str | None = None):
        sc = SCENARIOS[kind]
        loc = location or self.rng.choice(sc["locs"])
        route = self.rng.choice(ROUTES[:10]) if kind in ("bus_breakdown", "safety_spree", "ac_failure") else None
        inc = {"id": self.next_incident, "kind": kind, "name": sc["name"], "location": loc, "route": route,
               "mix": sc["mix"], "rate": sc["rate"], "start": self.e.vtime, "end": self.e.vtime + sc["minutes"] * 60}
        self.next_incident += 1
        self.e.incidents.append(inc)
        self.e.incidents = self.e.incidents[-20:]
        self.e.publish("incident", {"id": inc["id"], "name": inc["name"], "location": loc})
        return inc

    # -------------------------------------------------------------------
    def step(self, vt_from: float, vt_to: float, publish=True, auto=True):
        dv = vt_to - vt_from
        n = self.np.poisson(base_rate(vt_from) * dv / 60.0)
        mix = peak_mix(vt_from)
        for _ in range(n):
            ts = vt_from + self.rng.random() * dv
            text, src = self._complaint(ts, mix)
            self.e.ingest(text, src, ts=ts, publish=publish)
        for inc in self.e.incidents:
            lo, hi = max(vt_from, inc["start"]), min(vt_to, inc["end"])
            if hi <= lo:
                continue
            # ramp up / down over the incident lifetime for a natural-looking burst
            mid = (inc["start"] + inc["end"]) / 2
            shape = 1.0 - abs((lo + hi) / 2 - mid) / ((inc["end"] - inc["start"]) / 2) * 0.6
            k = self.np.poisson(inc["rate"] * shape * (hi - lo) / 60.0)
            for _ in range(k):
                ts = lo + self.rng.random() * (hi - lo)
                text, src = self._complaint(ts, inc["mix"], loc=inc["location"], route=inc["route"])
                self.e.ingest(text, src, ts=ts, publish=publish)
        if auto and self.auto_incidents and vt_to >= self._next_auto:
            self.trigger(self.rng.choice(list(SCENARIOS)))
            self._next_auto = vt_to + self.rng.uniform(35, 70) * 60

    def backfill(self, hours=3.0, log=print):
        end = self.e.vtime
        start = end - hours * 3600
        t, step = start, 120.0
        total = 0
        while t < end:
            self.step(t, min(t + step, end), publish=False, auto=False)
            t += step
        self._next_auto = end + self.rng.uniform(8, 15) * 60
        log(f"[sim] backfilled {self.e.counters['total']} complaints ({hours}h of history)")

    async def run(self):
        last = time.time()
        while True:
            await asyncio.sleep(0.25)
            now = time.time()
            dt = now - last
            last = now
            if not self.e.running:
                continue
            with self.e.lock:
                v0 = self.e.vtime
                self.e.vtime = v0 + dt * self.e.speed
                self.step(v0, self.e.vtime)
