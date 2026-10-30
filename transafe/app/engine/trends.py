"""Streaming trend / burst detection.

For an entity (category, location, route, or category@location) we compare the
number of complaints in the recent window W with the rate expected from a
longer baseline window B:
        expected = baseline_count * W / B
        z        = (observed - expected) / sqrt(expected + 0.5)      (Poisson z-score)
An entity is "emerging" when observed >= MIN_OBS and z >= Z_THRESHOLD.
"""
from __future__ import annotations

import math
from collections import Counter, deque

from app.config import ACTIONABLE, CATEGORY_LABELS

RECENT = 30 * 60.0
BASELINE = 3 * 3600.0
MIN_OBS = 4
Z_THRESHOLD = 2.5


class TrendEngine:
    def __init__(self, maxlen=50000):
        self.events = deque(maxlen=maxlen)   # (ts, category, location, route, severity, source, mode)
        self.t_first = None

    def add(self, c: dict):
        if not c["actionable"]:
            return
        if self.t_first is None:
            self.t_first = c["ts"]
        self.events.append((c["ts"], c["category"], c["location"], c["route"], c["severity"], c["source"], c["mode"]))

    # ---------------------------------------------------------------- helpers
    def _window(self, lo, hi):
        return [e for e in self.events if lo < e[0] <= hi]

    def timeline(self, now: float, bucket=600.0, n=18):
        start = now - bucket * n
        series = {c: [0] * n for c in ACTIONABLE}
        for ts, cat, *_ in reversed(self.events):
            if ts <= start:
                break
            i = min(n - 1, int((ts - start) // bucket))
            if ts <= now:
                series[cat][i] += 1
        labels = [start + bucket * (i + 1) for i in range(n)]
        return {"labels": labels, "series": series, "bucket": bucket}

    def _keys(self, e):
        _, cat, loc, rt, *_ = e
        ks = [("category", cat, CATEGORY_LABELS[cat])]
        if loc:
            ks.append(("location", loc, loc))
            ks.append(("issue", f"{cat}@{loc}", f"{CATEGORY_LABELS[cat]} at {loc}"))
        if rt:
            ks.append(("route", rt, f"Route {rt}" if not rt.endswith("Line") else rt))
        return ks

    def emerging(self, now: float, limit=8):
        recent = self._window(now - RECENT, now)
        base = self._window(now - RECENT - BASELINE, now - RECENT)
        warm = (self.t_first is not None) and (now - self.t_first >= 1800)
        base_span = min(BASELINE, max(now - RECENT - (self.t_first or now), 1.0))
        rc, bc, sev, meta = Counter(), Counter(), Counter(), {}
        for e in recent:
            for k in self._keys(e):
                rc[k[:2]] += 1
                sev[k[:2]] += e[4]
                meta[k[:2]] = k[2]
        for e in base:
            for k in self._keys(e):
                bc[k[:2]] += 1
        out = []
        for key, obs in rc.items():
            if obs < MIN_OBS:
                continue
            expected = bc.get(key, 0) * RECENT / base_span
            z = (obs - expected) / math.sqrt(expected + 0.5)
            if z >= Z_THRESHOLD:
                kind, name = key
                out.append({"kind": kind, "key": name, "label": meta[key], "recent": obs,
                            "expected": round(expected, 1), "z": round(z, 1),
                            "growth_pct": round(100 * (obs - expected) / max(expected, 1.0)),
                            "avg_severity": round(sev[key] / obs, 1),
                            "spark": self._spark(kind, name, now)})
        # prefer specific entities: issue > location > route > category when scores are comparable
        rank = {"issue": 3, "location": 2, "route": 2, "category": 1}
        out.sort(key=lambda r: (r["z"] * (1 + 0.15 * rank[r["kind"]])), reverse=True)
        # drop category-level rows if a more specific one explains the same burst
        dedup, kinds = [], set()
        for r in out:
            if r["kind"] == "category" and ("issue" in kinds or "location" in kinds) and len(out) > 3:
                continue
            kinds.add(r["kind"])
            dedup.append(r)
        return {"items": dedup[:limit], "calibrating": not warm}

    def _spark(self, kind, name, now, n=12, bucket=300.0):
        start = now - n * bucket
        arr = [0] * n
        for e in reversed(self.events):
            if e[0] <= start:
                break
            if any(k[:2] == (kind, name) for k in self._keys(e)):
                arr[min(n - 1, int((e[0] - start) // bucket))] += 1
        return arr

    def hotspots(self, now: float, window=3600.0, limit=40):
        agg = {}
        for ts, cat, loc, rt, sev, *_ in self._window(now - window, now):
            if not loc:
                continue
            a = agg.setdefault(loc, {"count": 0, "sev": 0.0, "cats": Counter()})
            a["count"] += 1
            a["sev"] += sev
            a["cats"][cat] += 1
        rows = [{"name": k, "count": v["count"], "avg_severity": round(v["sev"] / v["count"], 1),
                 "top_category": v["cats"].most_common(1)[0][0], "categories": dict(v["cats"])} for k, v in agg.items()]
        rows.sort(key=lambda r: r["count"] * r["avg_severity"], reverse=True)
        return rows[:limit]

    def totals(self, now: float, window=3600.0):
        w = self._window(now - window, now)
        return {"count": len(w), "avg_sev": round(sum(e[4] for e in w) / len(w), 1) if w else 0.0,
                "by_category": dict(Counter(e[1] for e in w)), "by_source": dict(Counter(e[5] for e in w)),
                "by_mode": dict(Counter(e[6] for e in w)),
                "critical": sum(1 for e in w if e[4] >= 78)}
