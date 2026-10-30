# TransitPulse - Real-Time Public Transport Complaint Analyzer

NLP course project (AI53) · Problem 5: *continuously process incoming passenger complaints and generate live issue
categories, locations, severity levels and emerging trends.*

Built for Bengaluru (BMTC buses + Namma Metro). Complaints arrive as noisy social-media / portal text, sometimes
code-mixed with Hindi or Kannada, and the system turns the stream into something an operations team can act on.

## What it does

| Requirement | How it is solved |
|---|---|
| **Live issue categories** | TF-IDF (word + char n-grams) → logistic regression, 8 complaint classes + "other" (praise / queries) |
| **Locations** | Gazetteer NER with fuzzy matching (edit distance), BMTC route numbers, metro lines, bus/metro mode |
| **Severity levels** | Explainable 0-100 score: category prior + safety terms + intensity + duration + recurrence + vulnerable groups, with negation and intensifier handling |
| **Recurring issues** | Incremental clustering in an LSA semantic space + place + route |
| **Emerging trends** | Poisson z-score burst detection on category / place / route / category@place |
| **Live** | Streaming engine, Server-Sent Events, simulator with incident injection, REST API for real feeds |

Plus: noisy-channel spell correction, Hinglish/Kanglish normalisation, POS tagging and issue phrases, BM25 search, CSV
import/export, SQLite log, an NLP "pipeline inspector" page and a model-evaluation page.

## Run it

```bash
pip install -r requirements.txt
python run.py            # trains models on first run (~10 s), opens http://127.0.0.1:8000
python -m pytest -q tests
```

In the UI: press **Inject** (top right) to start an incident such as a bus breakdown at Silk Board; within seconds the
*Emerging trends* panel flags it, the map hotspot grows and a recurring issue appears. Use **NLP Analyzer** to paste
any complaint and see every stage. Change the speed (1×-300×) to compress time.

## Architecture

```
 sources (X, portal, WhatsApp, app, CSV, POST /api/complaints)   simulator (rush hours + incidents)
                         \                                      /
                          v                                    v
   raw text -> normalise -> spell-correct -> classify -> extract places/routes -> severity -> POS/phrases
                                                  |
                                                  v
                      cluster (recurring issues) + trend engine (bursts) + BM25 index + SQLite
                                                  |
                                   FastAPI  --SSE-->  dashboard (map, charts, feed, issues)
```

## Syllabus coverage

| Unit | Topic | Where |
|---|---|---|
| I | Challenges of NLP, Indian-language processing | `nlp/preprocess.py` (Hinglish/Kanglish lexicon, noisy text) |
| I | Statistical language model | `nlp/language_model.py` |
| I, V | Information retrieval | `engine/search.py` (BM25), TF-IDF everywhere |
| II | Spelling error detection and correction, min edit distance | `nlp/edit_distance.py`, `nlp/spell.py` |
| II | Rule-based / transformation-based POS tagging | `nlp/pos_tagger.py` |
| II, III | Smoothing, N-grams, entropy / perplexity | `nlp/language_model.py` (MLE, add-1, add-k, Kneser-Ney), Model page |
| III | Context-free grammar | `data/generator.py` (template grammar that generates the training text) |
| V | Distributional semantics | `nlp/models.py` `SemanticSpace` (TF-IDF → SVD / LSA) used for clustering and related terms |

Syntactic parsing (CYK, Unit III) and machine translation (Unit IV) are not used because this problem does not need
them; they could be added (a CYK parser for complaint structure, translation of Kannada/Hindi complaints).

## Results (and how to read them)

Numbers are produced by `python run.py --retrain` and shown on the **Model & Evaluation** page.

* **~88% accuracy / ~88% macro-F1** on 108 hand-written complaints (12 per class) that were never trained on.
* **~74% accuracy** on synthetic complaints from phrase templates held out of training.
* Naive Bayes baseline: ~86% on the hand-written set.

Please be upfront about the limits when presenting:

* The training data is **synthetic** (generated from templates with injected noise). The hand-written set is a fairer
  test, but it was written by one person, and template coverage was adjusted after looking at its errors, so treat the
  88% as an estimate, not a guarantee on real complaints.
* The live feed is a **simulation** (it reuses the same generator plus the hand-written sentences). The pipeline itself
  is source-agnostic; real data goes in through `POST /api/complaints` or CSV upload.
* Coordinates in the gazetteer are approximate, and BMTC route numbers are illustrative.
* To strengthen the project: collect 200+ real complaints (tweets, public grievance posts), label them, add them to
  `app/data/gold_test.py` and report the numbers on those.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | dashboard snapshot + recent feed |
| GET | `/api/stream` | SSE: `complaint`, `incident`, `snapshot` events |
| POST | `/api/analyze` | full pipeline trace for one text (not stored) |
| POST | `/api/complaints` | ingest one complaint `{text, source}` |
| POST | `/api/complaints/batch` | ingest a CSV with a `text` column |
| GET | `/api/complaints?q=...` | BM25 search; or latest complaints |
| GET | `/api/issues`, `/api/issues/{id}` | recurring issues and their complaints |
| GET | `/api/model` | evaluation metrics |
| POST | `/api/simulator`, `/api/simulator/incident` | pause, speed, inject incident |
| GET | `/api/export.csv` | all processed complaints |

Interactive docs: `http://127.0.0.1:8000/docs`.

```bash
curl -X POST localhost:8000/api/complaints -H 'content-type: application/json' \
  -d '{"text":"Bus 335E broke down near Silk Board, stuck 45 mins","source":"X / Twitter"}'
```

## Project layout

```
run.py                     start server (trains models if needed)
app/main.py                FastAPI routes + SSE
app/engine/                core.py (ingest, snapshot), clustering.py, trends.py, search.py, simulator.py
app/nlp/                   preprocess, edit_distance, language_model, spell, pos_tagger, location, severity, models, pipeline
app/data/                  generator.py (training text), gold_test.py (hand-written test set), gazetteer.py
static/                    index.html, css/app.css (design tokens at top), js/*.js (one module per page)
tests/test_nlp.py          unit + API tests
docs/EXPLAINER.md          how every component works, formulas, likely viva questions
```

## Restyling the UI

All colours, spacing and fonts are CSS variables at the top of `static/css/app.css`; category colours live in
`app/config.py`. Each page is one JS module in `static/js/`, so layout changes stay local.
