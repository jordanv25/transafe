"""Incremental clustering of complaints into recurring "issues".

A new complaint joins the best-matching *active* cluster of the same category if
    score = 0.60 * cosine(LSA vectors) + 0.38 * same-location + 0.20 * same-route
exceeds a threshold, otherwise it starts a new cluster.  (Information-retrieval
style similarity in a distributional semantic space - Unit V.)
"""
from __future__ import annotations

import itertools
from collections import Counter

import numpy as np

from app.config import CATEGORY_LABELS

THRESHOLD = 0.45
ACTIVE_WINDOW = 6 * 3600  # seconds of (virtual) inactivity after which a cluster is closed


class Cluster:
    def __init__(self, cid: int, category: str, ts: float):
        self.id, self.category = cid, category
        self.first_seen = self.last_seen = ts
        self.centroid = None
        self.members: list[int] = []
        self.times: list[float] = []
        self.sevs: list[float] = []
        self.locations, self.routes, self.phrases, self.sources, self.modes = (Counter() for _ in range(5))

    def add(self, c: dict):
        self.members.append(c["id"])
        self.times.append(c["ts"])
        self.sevs.append(c["severity"])
        self.last_seen = max(self.last_seen, c["ts"])
        if c.get("location"):
            self.locations[c["location"]] += 1
        if c.get("route"):
            self.routes[c["route"]] += 1
        self.phrases.update(c.get("phrases", []))
        self.sources[c["source"]] += 1
        self.modes[c["mode"]] += 1
        v = c["_emb"]
        self.centroid = v.copy() if self.centroid is None else self.centroid + v

    @property
    def unit_centroid(self):
        n = np.linalg.norm(self.centroid)
        return self.centroid / n if n else self.centroid

    def title(self):
        lab = CATEGORY_LABELS[self.category]
        loc = self.locations.most_common(1)
        rt = self.routes.most_common(1)
        if loc and rt:
            return f"{lab} at {loc[0][0]} (route {rt[0][0]})"
        if loc:
            return f"{lab} at {loc[0][0]}"
        if rt:
            return f"{lab} on {rt[0][0]}"
        return f"{lab} - citywide"

    def summary(self, now: float, recent_window=3600.0):
        recent = [(t, s) for t, s in zip(self.times, self.sevs) if now - t <= recent_window]
        prior = sum(1 for t in self.times if recent_window < now - t <= 2 * recent_window)
        avg = float(np.mean(self.sevs)) if self.sevs else 0.0
        weighted = sum(s for _, s in recent) / 100.0
        return {
            "id": self.id, "title": self.title(), "category": self.category,
            "count": len(self.members), "recent": len(recent), "previous": prior,
            "avg_severity": round(avg, 1), "max_severity": round(max(self.sevs), 1) if self.sevs else 0,
            "first_seen": self.first_seen, "last_seen": self.last_seen,
            "locations": [k for k, _ in self.locations.most_common(3)],
            "routes": [k for k, _ in self.routes.most_common(3)],
            "keywords": [k for k, _ in self.phrases.most_common(4)],
            "sources": dict(self.sources), "mode": (self.modes.most_common(1)[0][0] if self.modes else "unknown"),
            "priority": round(weighted * (1 + min(1.5, max(0, len(recent) - prior) / 6)), 2),
            "active": now - self.last_seen <= ACTIVE_WINDOW,
        }


class IssueClusterer:
    def __init__(self):
        self.clusters: dict[int, Cluster] = {}
        self._ids = itertools.count(1)

    def assign(self, c: dict) -> int:
        best, best_s = None, 0.0
        for cl in self.clusters.values():
            if cl.category != c["category"] or c["ts"] - cl.last_seen > ACTIVE_WINDOW:
                continue
            cos = float(np.dot(cl.unit_centroid, c["_emb"]))
            s = 0.60 * max(cos, 0) + (0.38 if c.get("location") and c["location"] in cl.locations else 0) \
                + (0.20 if c.get("route") and c["route"] in cl.routes else 0)
            # same category + same dominant location is the same recurring issue even with different wording
            if c.get("location") and cl.locations and c["location"] == cl.locations.most_common(1)[0][0]:
                s += 0.12
            if s > best_s:
                best, best_s = cl, s
        if best is None or best_s < THRESHOLD:
            best = Cluster(next(self._ids), c["category"], c["ts"])
            self.clusters[best.id] = best
        best.add(c)
        return best.id

    def top(self, now: float, n=12, only_active=True):
        rows = [cl.summary(now) for cl in self.clusters.values() if cl.members]
        if only_active:
            rows = [r for r in rows if r["active"]]
        rows.sort(key=lambda r: (r["priority"], r["count"]), reverse=True)
        return rows[:n]
