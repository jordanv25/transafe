"""Noisy-channel spelling correction (Unit II).

For an out-of-vocabulary token x we pick the candidate w maximising
    log P_LM(w | left context) + log P_LM(next | w)  -  alpha * edit_distance(x, w)
i.e. a language-model prior (Kneser-Ney bigram) times a channel model
P(x|w) ~ exp(-alpha * d).  Candidates come from the domain vocabulary within
a bounded Damerau-Levenshtein distance.
"""
from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache

from app.nlp.edit_distance import align, distance
from app.nlp.language_model import NGramLM

try:  # optional: protects ordinary English words from being "corrected"
    from wordfreq import top_n_list
    COMMON = set(top_n_list("en", 30000))
except Exception:  # pragma: no cover
    COMMON = set()

ROUTE_LIKE = re.compile(r"^(\d{1,3}[a-z]{0,3}|[a-z]{1,3}-?\d+[a-z]*)$")
ALPHA = 2.3  # channel penalty per edit (~ln 10)


class SpellCorrector:
    def __init__(self, lm: NGramLM, vocab: set[str], protected: set[str] | None = None):
        self.lm = lm
        self.vocab = {w for w in vocab if w.isalpha() and len(w) > 2}
        self.protected = set(protected or set()) | set(vocab)
        self.by_len = defaultdict(list)
        for w in self.vocab:
            self.by_len[len(w)].append(w)
        self._cands = lru_cache(maxsize=20000)(self._candidates)

    def _candidates(self, tok: str):
        maxd = 1 if len(tok) <= 5 else 2
        out = []
        for L in range(len(tok) - maxd, len(tok) + maxd + 1):
            for w in self.by_len.get(L, ()):
                if w[0] != tok[0] and len(tok) < 7 and w[1:2] != tok[1:2]:
                    continue
                d = distance(tok, w, max_d=maxd)
                if d <= maxd:
                    out.append((w, d))
        return out

    def is_oov(self, tok: str) -> bool:
        return (tok.isalpha() and len(tok) >= 4 and tok not in self.protected and tok not in COMMON
                and not ROUTE_LIKE.match(tok))

    def correct(self, tokens: list[str]):
        out, fixes = list(tokens), []
        for i, tok in enumerate(tokens):
            if not self.is_oov(tok):
                continue
            cands = self._cands(tok)
            if not cands:
                continue
            prev = tuple(out[max(0, i - 1):i])
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            best, best_s = None, float("-inf")
            for w, d in cands:
                s = self.lm.logprob(w, prev) - ALPHA * d
                if nxt:
                    s += self.lm.logprob(nxt, (w,))
                if s > best_s:
                    best, best_s = (w, d), s
            if best:
                w, d = best
                out[i] = w
                _, ops = align(tok, w)
                fixes.append({"index": i, "from": tok, "to": w, "distance": d,
                              "ops": [{"op": o, "a": a, "b": b} for o, a, b in ops]})
        return out, fixes
