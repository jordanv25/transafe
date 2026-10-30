# How TransitPulse works - explainer and viva notes

Read this before presenting. Each section: what it does, the idea, where the code is, and a question you may get.

## 1. Normalisation (`nlp/preprocess.py`)
Complaints are messy: "bus tumba late aagide #SilkBoardJam 45mins pls!!!". We unescape HTML, strip URLs and @mentions,
split hashtags by camel case, squeeze elongations ("sooo"), expand slang (pls→please, bcoz→because), map romanised
Hindi/Kannada words to English glosses (bheed→crowd, tumba→very), separate numbers and units, and tokenise.
Code-mixing is recorded so the UI can show "Hinglish" / "Kanglish".
*Q: Why not a Kannada/Hindi script model?* Most social-media complaints in India are written in Roman script; a lexicon
is a transparent, cheap first step. A transliteration + translation model would be the next one (Unit IV).

## 2. Minimum edit distance and spelling correction (`nlp/edit_distance.py`, `nlp/spell.py`)
Edit distance D(i,j) = min( D(i-1,j)+1, D(i,j-1)+1, D(i-1,j-1)+[a_i≠b_j] ), plus adjacent transposition
(Damerau). For an unknown word x we generate vocabulary words within distance 1-2 and choose the best by the noisy
channel model:  ŵ = argmax_w P(w | context) · P(x | w), with P(x|w) ∝ exp(-α·d(x,w)) and P(w|context) from the bigram
language model. Common English words (30k list) and place names are protected so they are never "corrected".
*Q: why use the LM at all?* "buss" is distance 1 from both "bus" and "buns"; the context ("the buss was late") decides.

## 3. N-gram language model and smoothing (`nlp/language_model.py`)
P(w_i | w_{i-1}) = c(w_{i-1} w_i) / c(w_{i-1}) gives zero to unseen pairs, so perplexity is infinite. We implement
Laplace (add-1), add-k and interpolated **Kneser-Ney**:
P_KN(w|v) = max(c(vw) − d, 0)/c(v) + λ(v)·P_cont(w), λ(v) = d·|{w: c(vw)>0}| / c(v), where P_cont(w) counts in how many
*different contexts* w appears (so "Francisco" is rare as a continuation even if frequent). Perplexity PP = 2^H =
exp(−(1/N) Σ log P). The Model page compares all methods.
*Q: why does add-1 beat KN on the hand-written set?* That set is out of domain with many unseen words; add-1 hands out
more mass to unseen events. In-domain KN is clearly best. This is an honest observation, not a bug.

## 4. POS tagging (`nlp/pos_tagger.py`)
A rule-based tagger: closed-class lexicon, domain lexicon, suffix rules (-ing, -ed, -ly…), then Brill-style
**transformation rules** that rewrite tags from context (e.g. VERB→NOUN after a determiner). We use the tags to extract
noun-phrase "issue phrases" (rude conductor, broken seats) for cluster labels.
*Q: why not a stochastic/HMM tagger?* It needs a tagged corpus; we have none for this domain. The architecture allows
dropping one in.

## 5. Classification (`nlp/models.py`)
Features: TF-IDF of word 1-2-grams and character 2-5-grams (characters make it robust to typos and code-mixing).
Model: multinomial logistic regression, softmax P(c|x) = exp(w_c·x)/Σ exp(w_k·x). Naive Bayes is trained as a baseline.
Evaluation: (a) random split - optimistic, (b) held-out templates, (c) 108 hand-written complaints. Report (c).
*Q: your data is synthetic - is the accuracy real?* Say plainly: it is an estimate on hand-written text; the next step is
real labelled data. The generator is a template grammar (Unit III) with injected noise.

## 6. Entities (`nlp/location.py`)
A gazetteer of ~50 Bengaluru places with aliases. Longest-match over token n-grams, then fuzzy match using edit distance
(≤1 for short names, ≤2 for long ones) so "silk bord" and "marthahalli" still resolve. Routes come from regexes
("route 335E", "500D", "G4"); mode (bus / metro) from cue words. The primary location is chosen with prepositional cues
("near", "at", "stuck at").

## 7. Severity (`nlp/severity.py`)
Score = category prior + safety-critical terms (injured, fire, harassed…) + intensity words (worst, packed…) +
duration (parsed from "45 mins", "half an hour", "2 hrs") + recurrence ("again", "daily") + vulnerable groups
(women, children, elderly) + emphasis (caps, "!!", angry emoji). Intensifiers ("very") multiply, hedges ("slightly")
reduce, negation within 3 tokens cancels a term ("no accident"). Levels: low <30, medium <55, high <78, critical.
Every point is explained in the UI. *Q: why rules instead of ML?* No labelled severity data exists, and authorities need
to see *why* something is critical. Rules are transparent; they can be calibrated later against officer labels.

## 8. Clustering - recurring issues (`engine/clustering.py`)
Each complaint gets an LSA vector (TF-IDF → truncated SVD, 64 dims) - a distributional semantic space where "packed" and
"crowded" end up close. A complaint joins the best active cluster of the same category when
0.60·cosine + 0.38·[same place] + 0.20·[same route] (+0.12 if it is the cluster's main place) ≥ 0.45, else it starts a new
issue. Clusters close after 6 hours of silence. Priority = severity-weighted volume in the last hour, boosted by growth.

## 9. Trend / burst detection (`engine/trends.py`)
For an entity (category, place, route, category@place) compare the count in the last 30 min (observed O) with the rate
expected from the previous 3 hours: E = baseline_count · 30 / baseline_span. z = (O − E)/√(E + 0.5) (Poisson
approximation). Emerging when O ≥ 4 and z ≥ 2.5. A cold-start flag shows "calibrating" until 30 min of history exist.
*Q: why not a threshold on counts?* Rush hour makes counts high every day; comparing with expected volume avoids false alarms.

## 10. Search (`engine/search.py`)
Okapi BM25: score(q,d) = Σ_t IDF(t) · tf·(k1+1) / (tf + k1(1 − b + b·|d|/avgdl)), k1=1.5, b=0.75. The query goes through the
same normaliser and spell corrector as complaints.

## 11. Streaming (`app/main.py`, `engine/core.py`, `engine/simulator.py`)
Every complaint passes through `Engine.ingest`, which runs the pipeline (~5 ms), clusters, updates trend counters, indexes
for search, writes to SQLite and pushes the result to all browsers over Server-Sent Events. A snapshot of aggregates is
pushed every 2 s. The simulator is a Poisson process whose rate follows morning/evening peaks and which injects
incidents; time is virtual (1×-300×) so you can demo a day in minutes.

## Likely questions - short answers
* **What is novel?** Combining noisy-text NLP (spelling, code-mixing), explainable severity and statistical burst detection
  in one streaming pipeline, evaluated on a separate hand-written set.
* **How would it scale?** Pipeline is stateless per complaint; move clustering/trends to Redis or Kafka consumers.
* **What about real data?** Adapters for X / portal webhooks post to `/api/complaints`; the rest is unchanged.
* **Weaknesses?** Synthetic training data, rule-based severity, small gazetteer, no Kannada script, no coreference.
