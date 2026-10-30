"""Gazetteer-based location / route / mode extraction (named-entity recognition
for a closed domain) with fuzzy matching via edit distance."""
from __future__ import annotations

import re

from app.data.gazetteer import METRO_LINES, PLACES, ROUTES
from app.nlp.edit_distance import distance

CUES = {"at", "near", "opp", "opposite", "outside", "inside", "around", "stuck", "from", "in", "by"}
METRO_WORDS = {"metro", "train", "trains", "station", "coach", "platform", "token", "line", "namma", "bmrcl", "tunnel"}
BUS_WORDS = {"bus", "buses", "driver", "conductor", "bmtc", "stop", "footboard", "depot", "route", "vajra"}

ROUTE_CTX = re.compile(r"\b(?:route|bus|no|number|#)\s*[:#.-]?\s*((?:v-?)?\d{2,3}[a-z]{0,3})\b", re.I)
ROUTE_BARE = re.compile(r"\b((?:v-?)?\d{3}[a-z]{1,3}|(?:v-?)?\d{3}(?=\s+(?:bus|route|stop)\b)|[gk]-?\d{1,3}[a-z]?(?=\b)|kia-?\d+)\b", re.I)
KNOWN_ROUTES = {r.lower() for r in ROUTES}


class LocationExtractor:
    def __init__(self):
        self.index: dict[tuple, dict] = {}
        self.compact: dict[str, dict] = {}
        self.max_len = 1
        for name, typ, lat, lng, aliases, w in PLACES:
            rec = {"name": name, "type": typ, "lat": lat, "lng": lng}
            for a in aliases + [name.lower()]:
                toks = tuple(a.split())
                self.index[toks] = rec
                self.compact[a.replace(" ", "")] = rec
                self.max_len = max(self.max_len, len(toks))
        self.compact_keys = list(self.compact)
        self.vocab_tokens = {t for k in self.index for t in k}

    # ------------------------------------------------------------------
    def _fuzzy(self, s: str):
        if len(s) < 6:
            return None
        maxd = 1 if len(s) < 9 else 2
        best, bd = None, maxd + 1
        for k in self.compact_keys:
            if abs(len(k) - len(s)) > maxd or k[0] != s[0]:
                continue
            d = distance(s, k, max_d=maxd)
            if d < bd:
                best, bd = k, d
        return self.compact[best] if best else None

    def locations(self, tokens: list[str]):
        found, i = [], 0
        while i < len(tokens):
            hit = None
            for n in range(min(self.max_len, len(tokens) - i), 0, -1):
                win = tuple(tokens[i:i + n])
                if win in self.index:
                    hit = (n, self.index[win], False)
                    break
            if not hit:
                for n in range(min(3, len(tokens) - i), 0, -1):
                    s = "".join(tokens[i:i + n])
                    if not s.isalpha():
                        continue
                    rec = self.compact.get(s) or self._fuzzy(s)
                    if rec:
                        hit = (n, rec, s not in self.compact)
                        break
            if hit:
                n, rec, fuzzy = hit
                cue = tokens[i - 1] if i > 0 and tokens[i - 1] in CUES else None
                found.append({**rec, "start": i, "end": i + n, "surface": " ".join(tokens[i:i + n]),
                              "fuzzy": fuzzy, "cue": cue})
                i += n
            else:
                i += 1
        # de-duplicate by canonical name, keep first
        seen, uniq = set(), []
        for f in found:
            if f["name"] not in seen:
                seen.add(f["name"])
                uniq.append(f)
        return uniq

    @staticmethod
    def primary(locs):
        if not locs:
            return None
        for cue in ("at", "near", "stuck", "outside", "opp", "opposite", "around", "inside", "in", "by"):
            for l in locs:
                if l["cue"] == cue:
                    return l
        return locs[0]

    # ------------------------------------------------------------------
    @staticmethod
    def routes(raw: str):
        out = []
        for rx in (ROUTE_CTX, ROUTE_BARE):
            for m in rx.finditer(raw):
                r = m.group(1).upper().replace("--", "-")
                if r.startswith("V") and not r.startswith("V-"):
                    r = "V-" + r[1:]
                if re.fullmatch(r"\d{2,3}", r) and r.lower() not in KNOWN_ROUTES and rx is ROUTE_CTX \
                        and int(r) < 100 and r.lower() not in KNOWN_ROUTES:
                    # "bus 50 people" style false positives: require known route or 3 digits
                    continue
                if r not in out:
                    out.append(r)
        return out

    @staticmethod
    def lines(tokens: list[str]):
        txt = " ".join(tokens)
        return [v for k, v in METRO_LINES.items() if k in txt]

    @staticmethod
    def mode(tokens: list[str], routes: list[str], lines: list[str]) -> str:
        t = set(tokens)
        m = len(t & METRO_WORDS) + 2 * len(lines)
        b = len(t & BUS_WORDS) + 2 * len(routes)
        if m == 0 and b == 0:
            return "unknown"
        return "metro" if m > b else "bus"
