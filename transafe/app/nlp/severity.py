"""Explainable severity scoring (0-100) from lexical, numeric and context cues.

score = category prior + critical-term evidence + intensity terms
        + duration + recurrence + vulnerable groups + emphasis signals
Negation ("no accident") cancels a term; intensifiers / hedges scale it.
"""
from __future__ import annotations

import re

from app.config import SEVERITY_LEVELS

CATEGORY_PRIOR = {"safety": 38, "breakdown": 32, "overcrowding": 28, "accessibility": 24, "driver_behavior": 26,
                  "delay": 20, "vehicle_condition": 16, "fare_ticketing": 12, "other": 0}

CRITICAL = {"accident": 34, "injured": 36, "injury": 36, "hurt": 22, "died": 45, "death": 45, "dead": 40, "fire": 36,
            "smoke": 26, "sparks": 30, "burning": 30, "assault": 38, "molest": 42, "touched": 24, "harassing": 28,
            "harassed": 28, "harassment": 28, "stolen": 18, "theft": 18, "pickpocketing": 18, "snatched": 20,
            "drunk": 22, "stampede": 40, "collapsed": 30, "fainted": 30, "unsafe": 20, "dangerous": 22,
            "danger": 22, "dangerously": 22, "fell": 20, "fall": 16, "knock": 22, "stalker": 26, "stabbed": 50,
            "stranded": 18, "trapped": 26, "panicking": 20, "suffocating": 22, "breathe": 18, "tunnel": 12,
            "fight": 16, "abusing": 18, "abused": 16, "eve": 10, "stalking": 26, "khatarnak": 22}
INTENSE = {"worst": 10, "horrible": 10, "terrible": 10, "pathetic": 8, "nightmare": 10, "unbearable": 12,
           "jam": 6, "packed": 10, "overcrowded": 12, "overflowing": 10, "stuck": 8, "chaos": 10, "disgusting": 8,
           "filthy": 6, "unacceptable": 8, "scary": 12, "rash": 12, "overspeeding": 12, "suspended": 8, "halted": 8,
           "power": 4, "failure": 8, "cancelled": 8, "broke": 6, "broken": 6, "rude": 6, "refused": 6, "shouted": 6,
           "crushed": 14, "pushing": 8, "cannot": 4}
INTENSIFIERS = {"very": 1.25, "extremely": 1.5, "super": 1.3, "too": 1.2, "really": 1.2, "totally": 1.3,
                "completely": 1.4, "absolutely": 1.4, "highly": 1.25, "seriously": 1.2, "badly": 1.3,
                "dangerously": 1.4, "always": 1.1, "so": 1.15}
HEDGES = {"slightly": 0.6, "bit": 0.7, "little": 0.7, "somewhat": 0.7, "mildly": 0.6, "minor": 0.6}
NEGATORS = {"no", "not", "never", "without", "nothing", "didnt", "isnt", "dont"}
RECUR = {"again", "daily", "everyday", "always", "regularly", "repeatedly", "weeks", "week", "months",
         "every", "third", "second", "once"}
VULN = {"women", "woman", "ladies", "girl", "girls", "children", "kids", "child", "school", "students", "student",
        "senior", "seniors", "elderly", "old", "disabled", "pregnant", "wheelchair", "blind", "baby", "infant"}
NUMWORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10}
DUR_RE = re.compile(r"(\d+(?:\.\d+)?|half an|half a|an|a|one|two|three|four|five|six|ten)\s*(minutes?|hours?|days?)")


def parse_minutes(text: str) -> float:
    best = 0.0
    for m in DUR_RE.finditer(text):
        q, unit = m.group(1), m.group(2)
        if q.startswith("half"):
            val = 0.5
        elif q.replace(".", "").isdigit():
            val = float(q)
        else:
            val = NUMWORDS.get(q, 1)
        mins = val * (1 if unit.startswith("min") else 60 if unit.startswith("hour") else 1440)
        best = max(best, mins)
    if "almost an hour" in text or "over an hour" in text:
        best = max(best, 55 if "almost" in text else 70)
    if re.search(r"\bhalf an hour\b", text):
        best = max(best, 30)
    return best


def level_for(score: float) -> str:
    for thr, name in SEVERITY_LEVELS:
        if score >= thr:
            return name
    return "low"


def score(tokens: list[str], text: str, category: str, norm=None):
    factors = []
    total = float(CATEGORY_PRIOR.get(category, 0))
    if category == "other":
        return {"score": 0.0, "level": "low", "factors": [{"label": "Not a complaint", "points": 0.0}]}
    factors.append({"label": f"Category prior ({category.replace('_', ' ')})", "points": total})

    def mod(i):
        m = 1.0
        for j in range(max(0, i - 2), i):
            m *= INTENSIFIERS.get(tokens[j], 1.0) * HEDGES.get(tokens[j], 1.0)
        return m

    def negated(i):
        return any(tokens[j] in NEGATORS for j in range(max(0, i - 3), i)) and tokens[i] not in {"cannot"}

    crit, seen = [], set()
    for i, t in enumerate(tokens):
        if t in CRITICAL and t not in seen and not negated(i):
            seen.add(t)
            crit.append((CRITICAL[t] * mod(i), t))
    if crit:
        crit.sort(reverse=True)
        pts = crit[0][0] + 0.25 * sum(p for p, _ in crit[1:3])
        pts = min(pts, 48)
        total += pts
        factors.append({"label": "Safety-critical terms: " + ", ".join(t for _, t in crit[:3]), "points": round(pts, 1)})

    inten, seen = [], set()
    for i, t in enumerate(tokens):
        if t in INTENSE and t not in seen and not negated(i):
            seen.add(t)
            inten.append((INTENSE[t] * mod(i), t))
    if inten:
        inten.sort(reverse=True)
        pts = min(sum(p for p, _ in inten[:3]), 22)
        total += pts
        factors.append({"label": "Intensity words: " + ", ".join(t for _, t in inten[:3]), "points": round(pts, 1)})

    mins = parse_minutes(text)
    if mins >= 10:
        pts = min(mins / 4.0, 24)
        total += pts
        label = f"Duration ~{int(mins)} min" if mins < 120 else f"Duration ~{mins / 60:.1f} h"
        factors.append({"label": label, "points": round(pts, 1)})

    rec = [t for t in tokens if t in RECUR]
    if rec:
        total += 7
        factors.append({"label": "Recurring problem (" + rec[0] + ")", "points": 7.0})

    vul = [t for t in tokens if t in VULN]
    if vul:
        pts = 8 if category in {"safety", "overcrowding", "accessibility", "driver_behavior"} else 4
        total += pts
        factors.append({"label": "Vulnerable group (" + vul[0] + ")", "points": float(pts)})

    emph = 0.0
    if norm is not None:
        if norm.exclaims >= 2:
            emph += 3
        if norm.caps_ratio > 0.6:
            emph += 3
        if norm.angry:
            emph += 3
    if emph:
        total += emph
        factors.append({"label": "Emphasis (caps / ! / emoji)", "points": emph})

    total = max(0.0, min(100.0, total))
    # floor: genuine safety-critical evidence must never be rated low
    if crit and crit[0][0] >= 30 and category in {"safety", "breakdown", "overcrowding"}:
        total = max(total, 62.0)
    return {"score": round(total, 1), "level": level_for(total), "factors": factors}
