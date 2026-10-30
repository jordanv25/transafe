"""Okapi BM25 inverted index for searching the complaint archive (Unit V - IR)."""
from __future__ import annotations

import math
from collections import Counter, defaultdict

STOP = set("a an the is are was were be of at in on to for and or but it its this that with from by as i we you my "
           "me our they them their so very just not no do does did has have had please bus".split())


def stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def terms(tokens):
    return [stem(t) for t in tokens if t not in STOP and len(t) > 1]


class BM25Index:
    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.post: dict[str, dict[int, int]] = defaultdict(dict)
        self.dl: dict[int, int] = {}
        self.total_len = 0

    def add(self, doc_id: int, tokens):
        ts = terms(tokens)
        self.dl[doc_id] = len(ts)
        self.total_len += len(ts)
        for t, c in Counter(ts).items():
            self.post[t][doc_id] = c

    def search(self, query_tokens, k=20, allow=None):
        N = len(self.dl)
        if not N:
            return []
        avg = self.total_len / N
        scores = defaultdict(float)
        for t in set(terms(query_tokens)):
            plist = self.post.get(t)
            if not plist:
                continue
            idf = math.log(1 + (N - len(plist) + 0.5) / (len(plist) + 0.5))
            for d, tf in plist.items():
                if allow is not None and d not in allow:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * self.dl[d] / avg)
                scores[d] += idf * tf * (self.k1 + 1) / denom
        return sorted(scores.items(), key=lambda x: -x[1])[:k]
