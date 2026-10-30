"""Training + loading of every learned component.

* NGramLM (Kneser-Ney) on clean complaint text      -> spelling prior, perplexity report
* TF-IDF (word + char n-grams) + Logistic Regression -> complaint category (NB baseline kept for comparison)
* TF-IDF + truncated SVD (LSA)                       -> distributional semantic space for clustering
Evaluation: random split, template-held-out split, hand-written gold set.
"""
from __future__ import annotations

import json
import random
import time

import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline

from app.config import CATEGORIES, MODEL_DIR
from app.data.generator import build_dataset
from app.data.gold_test import GOLD
from app.nlp.language_model import NGramLM
from app.nlp.preprocess import normalize

BUNDLE_PATH = MODEL_DIR / "bundle.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"


def make_classifier(kind="lr"):
    feats = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2)),
    ])
    clf = LogisticRegression(C=12, max_iter=3000) if kind == "lr" else MultinomialNB(alpha=0.05)
    return Pipeline([("f", feats), ("c", clf)])


def _norm_text(t):
    return normalize(t).text


def _prf(y_true, y_pred):
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=CATEGORIES, zero_division=0)
    return {c: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
            for i, c in enumerate(CATEGORIES)}


def _report(y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred, labels=CATEGORIES)
    macro = precision_recall_fscore_support(y_true, y_pred, labels=CATEGORIES, average="macro", zero_division=0)
    return {"accuracy": float(accuracy_score(y_true, y_pred)), "macro_f1": float(macro[2]), "n": len(y_true),
            "per_class": _prf(y_true, y_pred), "confusion": cm.tolist()}


def train_all(n_per_class=700, seed=7, verbose=True):
    t0 = time.time()
    rows = build_dataset(n_per_class, seed)
    X = [_norm_text(r["text"]) for r in rows]
    y = [r["category"] for r in rows]
    clean_tokens = [normalize(r["clean"]).tokens for r in rows]
    gold_X = [_norm_text(t) for _, t in GOLD]
    gold_y = [l for l, _ in GOLD]
    metrics = {"dataset": {"train_examples": len(rows), "per_class": {c: y.count(c) for c in CATEGORIES},
                           "gold_examples": len(GOLD), "classes": CATEGORIES,
                           "templates": sum(len(set(r["template_id"] for r in rows if r["category"] == c)) for c in CATEGORIES)}}

    # --- 1. random split (optimistic: shares templates between train & test)
    rng = random.Random(seed)
    idx = list(range(len(rows)))
    rng.shuffle(idx)
    cut = int(0.8 * len(idx))
    tr, te = idx[:cut], idx[cut:]
    m = make_classifier("lr").fit([X[i] for i in tr], [y[i] for i in tr])
    metrics["random_split"] = _report([y[i] for i in te], list(m.predict([X[i] for i in te])))

    # --- 2. template-held-out split (harder: unseen sentence templates)
    held = set()
    for c in CATEGORIES:
        tids = sorted(set(r["template_id"] for r in rows if r["category"] == c))
        rng.shuffle(tids)
        held.update((c, t) for t in tids[: max(2, len(tids) // 5)])
    tr = [i for i, r in enumerate(rows) if (r["category"], r["template_id"]) not in held]
    te = [i for i, r in enumerate(rows) if (r["category"], r["template_id"]) in held]
    m = make_classifier("lr").fit([X[i] for i in tr], [y[i] for i in tr])
    metrics["template_holdout"] = _report([y[i] for i in te], list(m.predict([X[i] for i in te])))

    # --- 3. final model on all data, evaluated on the hand-written gold set
    lr = make_classifier("lr").fit(X, y)
    nb = make_classifier("nb").fit(X, y)
    metrics["gold_lr"] = _report(gold_y, list(lr.predict(gold_X)))
    metrics["gold_nb"] = _report(gold_y, list(nb.predict(gold_X)))

    # --- language model + smoothing comparison (Units I-III)
    n_tr = int(0.85 * len(clean_tokens))
    lm_train, lm_test = clean_tokens[:n_tr], clean_tokens[n_tr:]
    gold_tok = [normalize(t).tokens for _, t in GOLD]
    lm_rows = []
    for name, order, method in [("Bigram - MLE (no smoothing)", 2, "mle"), ("Bigram - Laplace (add-1)", 2, "laplace"),
                                ("Bigram - Add-k (k=0.05)", 2, "addk"), ("Bigram - Kneser-Ney", 2, "kn"),
                                ("Trigram - Kneser-Ney", 3, "kn")]:
        lm_ = NGramLM(order, method).fit(lm_train, unk_min_count=2)
        pt, pg = lm_.perplexity(lm_test), lm_.perplexity(gold_tok)
        lm_rows.append({"model": name, "ppl_heldout": None if pt == float("inf") else round(pt, 1),
                        "ppl_gold": None if pg == float("inf") else round(pg, 1)})
    metrics["language_model"] = lm_rows

    # --- final LM (bigram KN) trained on everything, speller vocab
    all_tok = clean_tokens
    lm = NGramLM(2, "kn").fit(all_tok)
    vocab = {w for s in all_tok for w in s}

    # --- LSA semantic space
    sem_vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2)
    Xs = sem_vec.fit_transform([normalize(r["clean"]).text for r in rows])
    svd = TruncatedSVD(n_components=64, random_state=seed).fit(Xs)
    metrics["semantic"] = {"dims": 64, "explained_variance": float(svd.explained_variance_ratio_.sum())}

    bundle = {"classifier": lr, "lm": lm, "vocab": vocab, "sem_vec": sem_vec, "svd": svd}
    joblib.dump(bundle, BUNDLE_PATH)
    metrics["train_seconds"] = round(time.time() - t0, 1)
    METRICS_PATH.write_text(json.dumps(metrics, indent=1))
    if verbose:
        print(f"[train] {len(rows)} examples | gold acc LR {metrics['gold_lr']['accuracy']:.3f} "
              f"NB {metrics['gold_nb']['accuracy']:.3f} | template-holdout {metrics['template_holdout']['accuracy']:.3f} "
              f"| random {metrics['random_split']['accuracy']:.3f} | {metrics['train_seconds']}s")
    return bundle, metrics


def load_bundle():
    if not BUNDLE_PATH.exists():
        return train_all()[0]
    return joblib.load(BUNDLE_PATH)


def load_metrics():
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text())
    return {}


class SemanticSpace:
    """LSA embeddings: TF-IDF -> SVD -> L2 normalise. Also nearest-neighbour terms."""

    def __init__(self, vec, svd):
        self.vec, self.svd = vec, svd
        terms = vec.get_feature_names_out()
        self.terms = terms
        self.term_idx = {t: i for i, t in enumerate(terms)}
        T = svd.components_.T
        T = T / (np.linalg.norm(T, axis=1, keepdims=True) + 1e-9)
        self.term_vecs = T

    def embed(self, text: str):
        v = self.svd.transform(self.vec.transform([text]))[0]
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def neighbours(self, word: str, k=5):
        i = self.term_idx.get(word)
        if i is None:
            return []
        sims = self.term_vecs @ self.term_vecs[i]
        order = np.argsort(-sims)
        out = []
        for j in order:
            t = self.terms[j]
            if t == word or " " in t or t.startswith(word) or word.startswith(t):
                continue
            out.append({"term": t, "sim": round(float(sims[j]), 2)})
            if len(out) >= k:
                break
        return out
