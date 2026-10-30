"""Engine: ties the NLP pipeline to clustering, trends, search, storage and live fan-out."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from collections import deque

from app.config import ACTIONABLE, CATEGORY_COLORS, CATEGORY_LABELS, DB_PATH
from app.engine.clustering import IssueClusterer
from app.engine.search import BM25Index
from app.engine.trends import TrendEngine
from app.nlp.pipeline import Analyzer
from app.nlp.preprocess import normalize


class Engine:
    def __init__(self, fresh_db: bool = True):
        self.analyzer = Analyzer()
        self.clusterer = IssueClusterer()
        self.trends = TrendEngine()
        self.index = BM25Index()
        self.records: dict[int, dict] = {}
        self.recent = deque(maxlen=60)
        self.next_id = 1
        self.vtime = time.time()          # virtual "now" (advanced by the simulator)
        self.speed = 30.0
        self.running = True
        self.incidents: list[dict] = []
        self.subscribers: set[asyncio.Queue] = set()
        self.lock = threading.RLock()
        self.counters = {"total": 0, "actionable": 0, "started": time.time()}
        self.lat_ms: deque = deque(maxlen=200)
        if fresh_db and DB_PATH.exists():
            DB_PATH.unlink()
        self.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS complaints(
            id INTEGER PRIMARY KEY, ts REAL, source TEXT, raw TEXT, clean TEXT, category TEXT, confidence REAL,
            severity REAL, level TEXT, location TEXT, lat REAL, lng REAL, route TEXT, mode TEXT, cluster_id INTEGER)""")

    # ------------------------------------------------------------------ ingest
    def ingest(self, text: str, source: str = "Manual", ts: float | None = None, publish: bool = True) -> dict:
        text = (text or "").strip()
        if not text:
            raise ValueError("empty complaint")
        text = text[:1000]
        with self.lock:
            a = self.analyzer.analyze(text)
            a["id"], a["source"], a["ts"] = self.next_id, source, ts if ts is not None else self.vtime
            self.next_id += 1
            a["cluster_id"] = self.clusterer.assign(a) if a["actionable"] else None
            self.trends.add(a)
            self.index.add(a["id"], a["tokens"])
            emb = a.pop("_emb")
            rec = dict(a)
            rec["color"] = CATEGORY_COLORS[a["category"]]
            self.records[rec["id"]] = rec
            self.recent.appendleft(rec)
            self.counters["total"] += 1
            self.counters["actionable"] += int(a["actionable"])
            self.lat_ms.append(a["latency_ms"])
            self.db.execute("INSERT INTO complaints VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (rec["id"], rec["ts"], source, text, rec["clean"], rec["category"], rec["confidence"],
                             rec["severity"], rec["severity_level"], rec["location"], rec["lat"], rec["lng"],
                             rec["route"], rec["mode"], rec["cluster_id"]))
        if publish:
            self.publish("complaint", self.public(rec))
        return rec

    @staticmethod
    def public(rec: dict) -> dict:
        keep = ("id", "ts", "source", "raw", "clean", "category", "category_label", "confidence", "low_confidence",
                "actionable", "location", "lat", "lng", "route", "mode", "severity", "severity_level", "cluster_id",
                "phrases", "code_mixed", "color", "corrections")
        d = {k: rec[k] for k in keep if k in rec}
        d["corrections"] = [{"from": c["from"], "to": c["to"]} for c in rec.get("corrections", [])]
        return d

    # ------------------------------------------------------------------ pub/sub
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q):
        self.subscribers.discard(q)

    def publish(self, event: str, data: dict):
        msg = json.dumps({"event": event, "data": data})
        for q in list(self.subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    # ------------------------------------------------------------------ queries
    def snapshot(self) -> dict:
        with self.lock:
            now = self.vtime
            tot = self.trends.totals(now)
            tl = self.trends.timeline(now)
            emerging = self.trends.emerging(now)
            issues = self.clusterer.top(now, 12)
            hot = self.trends.hotspots(now)
            rate = tot["count"] / 60.0
            lat = sum(self.lat_ms) / len(self.lat_ms) if self.lat_ms else 0.0
            active_inc = [i for i in self.incidents if i["end"] > now]
            return {
                "now": now, "speed": self.speed, "running": self.running,
                "kpis": {"total": self.counters["total"], "actionable": self.counters["actionable"],
                         "last_hour": tot["count"], "rate_per_min": round(rate, 2), "avg_severity": tot["avg_sev"],
                         "critical": tot["critical"], "open_issues": len(issues),
                         "emerging": len(emerging["items"]), "latency_ms": round(lat, 1)},
                "categories": {c: tot["by_category"].get(c, 0) for c in ACTIONABLE},
                "sources": tot["by_source"], "modes": tot["by_mode"],
                "timeline": tl, "emerging": emerging, "issues": issues, "hotspots": hot,
                "incidents": [{"id": i["id"], "name": i["name"], "location": i["location"], "end": i["end"]} for i in active_inc],
                "meta": {"labels": CATEGORY_LABELS, "colors": CATEGORY_COLORS},
            }

    def recent_feed(self, n=40):
        with self.lock:
            return [self.public(r) for r in list(self.recent)[:n]]

    def cluster_detail(self, cid: int):
        with self.lock:
            cl = self.clusterer.clusters.get(cid)
            if not cl:
                return None
            ms = [self.public(self.records[i]) for i in cl.members[-60:][::-1] if i in self.records]
            s = cl.summary(self.vtime)
            s["complaints"] = ms
            tl = [0] * 12
            for t in cl.times:
                k = int((self.vtime - t) // 600)
                if 0 <= k < 12:
                    tl[11 - k] += 1
            s["spark"] = tl
            return s

    def clusters(self, category=None, q=None, limit=60):
        with self.lock:
            rows = self.clusterer.top(self.vtime, 400, only_active=False)
        if category:
            rows = [r for r in rows if r["category"] == category]
        if q:
            ql = q.lower()
            rows = [r for r in rows if ql in r["title"].lower() or any(ql in k for k in r["keywords"])]
        return rows[:limit]

    def search(self, q: str, k=20, category=None):
        toks = normalize(q).tokens
        toks = self.analyzer.speller.correct(toks)[0]
        with self.lock:
            hits = self.index.search(toks, k=k * 3)
            out = []
            for did, sc in hits:
                r = self.records.get(did)
                if r and (not category or r["category"] == category):
                    p = self.public(r)
                    p["score"] = round(sc, 2)
                    out.append(p)
        return out[:k]

    def export_rows(self):
        with self.lock:
            cur = self.db.execute("SELECT * FROM complaints ORDER BY id")
            cols = [c[0] for c in cur.description]
            return cols, cur.fetchall()
