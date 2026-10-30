"""End-to-end analysis pipeline: raw complaint text -> structured analysis."""
from __future__ import annotations

import time

import numpy as np

from app.config import ACTIONABLE, CATEGORIES, CATEGORY_LABELS
from app.nlp import pos_tagger, severity
from app.nlp.location import LocationExtractor
from app.nlp.models import SemanticSpace, load_bundle
from app.nlp.preprocess import normalize
from app.nlp.spell import SpellCorrector
from app.data.gazetteer import PLACES

LOW_CONF = 0.45


class Analyzer:
    def __init__(self):
        b = load_bundle()
        self.clf = b["classifier"]
        self.lm = b["lm"]
        self.sem = SemanticSpace(b["sem_vec"], b["svd"])
        gaz_words = {w for p in PLACES for a in p[4] for w in a.split()}
        self.speller = SpellCorrector(self.lm, set(b["vocab"]) | gaz_words, protected=gaz_words)
        self.loc = LocationExtractor()
        self.classes = list(self.clf.classes_)

    def analyze(self, text: str, trace: bool = False) -> dict:
        t0 = time.perf_counter()
        norm = normalize(text)
        tokens, fixes = self.speller.correct(norm.tokens)
        clean = " ".join(tokens)

        proba = self.clf.predict_proba([clean])[0]
        order = np.argsort(-proba)
        cat = str(self.classes[order[0]])
        conf = float(proba[order[0]])
        probs = {str(self.classes[i]): round(float(proba[i]), 4) for i in order}

        locs = self.loc.locations(tokens)
        primary = LocationExtractor.primary(locs)
        routes = LocationExtractor.routes(text)
        lines = LocationExtractor.lines(tokens)
        mode = LocationExtractor.mode(tokens, routes, lines)

        sev = severity.score(tokens, clean, cat, norm)
        tagged = pos_tagger.tag(tokens)
        phrases = pos_tagger.noun_phrases(tagged)
        emb = self.sem.embed(clean)

        out = {
            "raw": text, "clean": clean, "tokens": tokens,
            "category": cat, "category_label": CATEGORY_LABELS[cat], "confidence": round(conf, 3),
            "low_confidence": conf < LOW_CONF, "actionable": cat in ACTIONABLE, "probs": probs,
            "location": primary["name"] if primary else None,
            "lat": primary["lat"] if primary else None, "lng": primary["lng"] if primary else None,
            "locations": [{k: v for k, v in l.items() if k in {"name", "type", "lat", "lng", "surface", "fuzzy"}} for l in locs],
            "route": routes[0] if routes else (lines[0] if lines else None), "routes": routes, "lines": lines,
            "mode": mode,
            "severity": sev["score"], "severity_level": sev["level"], "severity_factors": sev["factors"],
            "phrases": phrases[:5],
            "code_mixed": sorted({l for _, _, l in norm.code_mixed}),
            "corrections": fixes,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
        if trace:
            out["trace"] = {
                "normalized": norm.text, "pos": [{"token": t, "tag": g, "by": s} for t, g, s in tagged],
                "hashtags": norm.hashtags, "mentions": norm.mentions,
                "code_mix_hits": [{"token": a, "gloss": b, "lang": c} for a, b, c in norm.code_mixed],
                "related_terms": self._related(tokens),
            }
        out["_emb"] = emb
        return out

    def _related(self, tokens):
        seen, res = set(), []
        for t in tokens:
            if t in seen or len(t) < 5 or t in self.loc.vocab_tokens or not t.isalpha():
                continue
            seen.add(t)
            nb = self.sem.neighbours(t, 3)
            if nb and t not in {"that", "this", "with", "from", "have", "were", "very"}:
                res.append({"term": t, "neighbours": nb})
            if len(res) >= 6:
                break
        return res
