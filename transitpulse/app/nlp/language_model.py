"""N-gram language models with several smoothing methods (Units I-III).

methods: 'mle' (no smoothing), 'laplace' (add-1), 'addk' (add-k),
         'kn' (interpolated Kneser-Ney, recursive, any order)
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

BOS, EOS, UNK = "<s>", "</s>", "<unk>"


class NGramLM:
    def __init__(self, order: int = 2, method: str = "kn", k: float = 0.05, discount: float = 0.75):
        self.order, self.method, self.k, self.D = order, method, k, discount
        self.vocab: set[str] = set()
        self.raw: dict[tuple, Counter] = defaultdict(Counter)       # highest order counts
        self.cont: list[dict[tuple, Counter]] = []                   # continuation counts per order
        self.ctx_total: list[dict[tuple, int]] = []
        self.ctx_types: list[dict[tuple, int]] = []
        self.n_tokens = 0

    # ---------------------------------------------------------------- training
    def _pad(self, sent):
        return [BOS] * (self.order - 1) + list(sent) + [EOS]

    def fit(self, sentences, unk_min_count: int | None = None):
        o = self.order
        if unk_min_count:  # replace rare words by <unk> so the model learns to expect unseen words
            cnt = Counter(w for s_ in sentences for w in s_)
            sentences = [[w if cnt[w] >= unk_min_count else UNK for w in s_] for s_ in sentences]
        types = [set() for _ in range(o + 2)]
        for sent in sentences:
            t = self._pad(sent)
            self.vocab.update(sent)
            self.n_tokens += len(sent) + 1
            for i in range(o - 1, len(t)):
                for n in range(1, o + 1):
                    types[n].add(tuple(t[i - n + 1:i + 1]))
                self.raw[tuple(t[i - o + 1:i])][t[i]] += 1
        self.vocab.update([EOS, UNK])
        # continuation counts for lower orders (Kneser-Ney)
        self.cont = [defaultdict(Counter) for _ in range(o + 1)]
        for n in range(1, o):
            for g in types[n + 1]:
                self.cont[n][g[1:-1]][g[-1]] += 1
        for ctx, c in self.raw.items():
            self.cont[o][ctx] = c
        # lower-order raw counts (for add-k / mle on lower orders we only use highest order)
        self.ctx_total = [{} for _ in range(o + 1)]
        self.ctx_types = [{} for _ in range(o + 1)]
        for n in range(1, o + 1):
            for ctx, c in self.cont[n].items():
                self.ctx_total[n][ctx] = sum(c.values())
                self.ctx_types[n][ctx] = len(c)
        return self

    # ------------------------------------------------------------- probability
    def prob(self, w: str, ctx: tuple = ()) -> float:
        o = self.order
        ctx = tuple(ctx)[-(o - 1):] if o > 1 else ()
        ctx = (BOS,) * (o - 1 - len(ctx)) + ctx
        V = len(self.vocab)
        if self.method == "kn":
            return self._kn(w, ctx, o, V)
        c = self.raw.get(ctx, {})
        tot = sum(c.values())
        cw = c.get(w, 0)
        if self.method == "mle":
            return cw / tot if tot else 0.0
        k = 1.0 if self.method == "laplace" else self.k
        return (cw + k) / (tot + k * V)

    def _kn(self, w, ctx, n, V):
        if n == 0:
            return 1.0 / V
        sub = ctx[len(ctx) - (n - 1):] if n > 1 else ()
        lower = self._kn(w, ctx, n - 1, V)
        tot = self.ctx_total[n].get(sub, 0)
        if tot == 0:
            return lower
        cw = self.cont[n][sub].get(w, 0)
        lam = self.D * self.ctx_types[n][sub] / tot
        return max(cw - self.D, 0) / tot + lam * lower

    def logprob(self, w: str, ctx: tuple = ()) -> float:
        p = self.prob(w if w in self.vocab else UNK, ctx)
        return math.log(p) if p > 0 else float("-inf")

    # ------------------------------------------------------------- evaluation
    def perplexity(self, sentences) -> float:
        lp, n = 0.0, 0
        for sent in sentences:
            ctx = [BOS] * (self.order - 1)
            for w in list(sent) + [EOS]:
                p = self.prob(w if w in self.vocab else UNK, tuple(ctx))
                if p <= 0:
                    return float("inf")
                lp += math.log(p)
                n += 1
                ctx.append(w)
                ctx = ctx[1:] if self.order > 1 else []
        return math.exp(-lp / max(n, 1))

    def sentence_logprob(self, sent) -> float:
        ctx = [BOS] * (self.order - 1)
        total = 0.0
        for w in list(sent) + [EOS]:
            total += self.logprob(w, tuple(ctx))
            ctx.append(w)
            ctx = ctx[1:] if self.order > 1 else []
        return total
