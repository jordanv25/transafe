# Transafe

Real-Time Public Transport Complaint Analyzer. College NLP project (AI53, MSRIT, Bengaluru), Problem 5.
Goal: process incoming passenger complaints (BMTC bus + Namma Metro) and produce live categories,
locations, severity levels and emerging trends. Must be a fully working, polished project that earns
full internal marks and looks strong on a resume. Owner: Jordan.

## Run / test
- `pip install -r requirements.txt`
- `python run.py` (trains models on first run, ~10 s; serves http://127.0.0.1:8000; `--retrain` forces retraining)
- `python -m pytest -q tests` (22 tests, must stay green; stop any running server first, tests reset data_store.sqlite3)
- `python scripts/benchmark.py` (latency + incident detection delay), `python scripts/import_csv.py file.csv` (real labelled data),
  `python scripts/capture_demo.py` (docs/ screenshots + GIF; needs `pip install playwright pillow`, not in requirements)
- Docker: `docker build -t transafe .` in `transafe/`; CI is `.github/workflows/ci.yml` (pytest on push). Neither has been run on GitHub / Docker yet.
- Env vars: `TRANSAFE_BACKFILL_HOURS` (default 50; 3 = fast start but fallback trend baseline), `TRANSAFE_SEED` (simulator seed, default 11),
  `TRANSAFE_SIM` (1 = simulator on), `TRANSAFE_LIVE=0` forces simulator mode
- Optional keys in git-ignored `transafe/.env` (see `.env.example`): `GOOGLE_MAPS_API_KEY`, `X_BEARER_TOKEN`, `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`
- Live mode = any X/Reddit credentials set: real-time clock, real posts only, no simulator. Adapters are in `app/ingest/`
  (official APIs only, no scraping); tests mock HTTP and never touch the network. Map code is `static/js/map.js` (Google, Leaflet fallback).

## Architecture
raw text -> normalise -> spell-correct -> classify -> places/routes -> severity -> POS/phrases
-> cluster + trend engine + BM25 + SQLite -> FastAPI (REST + SSE) -> dashboard.
- `app/main.py` routes and SSE; `app/engine/` core.py, clustering.py, trends.py, search.py, simulator.py
- `app/nlp/` preprocess, edit_distance, language_model (MLE/add-1/add-k/Kneser-Ney), spell (noisy channel),
  pos_tagger (lexicon + suffix + Brill rules), location (gazetteer + fuzzy), severity, models (training/eval), pipeline
- `app/data/` generator.py (template grammar for synthetic training text), gold_test.py (GOLD = 108 hand-written test
  complaints + GOLD_NEW = 117 more written by the AI assistant, NEVER train on either), gazetteer.py (~50 Bengaluru places,
  approximate coordinates), real_data.py (optional git-ignored real_labeled.csv; drops any text found in the test sets)
- `static/` index.html, css/app.css (design tokens at top), js/ (one module per page); Chart.js and Leaflet are vendored
- `app/ingest/` sources.py (X, Reddit adapters), runner.py (polling into `Engine.ingest`)
- `docs/EXPLAINER.md` explains every component, formulas, likely viva questions

## Current results (python run.py --retrain)
- 88.0% accuracy / 87.7% macro-F1 on the 108 hand-written test set; Naive Bayes baseline 86.1%
- 85.5% / 85.4% on the second batch (117, templates not tuned on it); 86.7% on both (225)
- 74.4% on held-out synthetic templates (random split is 100% and optimistic; do not quote it)
- scripts/benchmark.py on Jordan's laptop: incident flagged after 3.4 min on average (median 3.0, 24/24 detected, simulated
  minutes, 50 h history; 2.8 min with 3 h history); pipeline latency about 8 ms per complaint (7.5-10.1 ms across runs).
  Jordan's earlier figures of 2.5 min / 3.9 ms did not reproduce

## Rules for working on this repo
- Be honest in docs and UI: training data is synthetic, the feed is simulated unless live mode is on (then it is public social posts, not BMTC-filed complaints), gazetteer coordinates are approximate.
- Never commit API keys; never scrape sites that have no API or whose terms forbid it.
- Never add gold_test.py examples to training data. New real labelled complaints go into gold_test.py only.
- After changing NLP code or templates: retrain, run tests, update numbers in README and the Model page text.
- Keep the 8 category colours in app/config.py (validated palette, fixed order, never cycled).
- Do not commit models/, *.sqlite3*, __pycache__ (see .gitignore).
- The second test batch (GOLD_NEW) was written by the AI assistant, not collected from passengers; never call it "real".
  Real complaints go into real_labeled.csv (training, via scripts/import_csv.py) or gold_test.py (testing), never both.
- Syllabus mapping (README) must stay accurate: units I, II, III, V are covered; CYK parsing (III) and machine translation (IV) are not.

## Known limitations
- Synthetic training data; real-world accuracy unverified. Safety is the weakest class (about 76% F1).
- Severity is rule-based (no labelled severity data). Small gazetteer. Romanised Hindi/Kannada only, no native scripts.
- Spell corrector skips words shorter than 4 letters and may mis-correct unseen romanised Hindi/Kannada words.
- Trend detector: baseline is the same 30-minute slot on earlier days once the log has >= 2 days, else the previous 3 hours.
  The demo backfills 50 h by default so the better baseline is on; `TRANSAFE_BACKFILL_HOURS=3` gives the fallback.
  Random false alarms remain (many entities tested, mean of few days); weekdays and weekends are not separated.
- Kneser-Ney perplexity is worse than add-1 on the out-of-domain hand-written set (explained in docs).

## Roadmap (priority order)
1. UI restyle per Jordan's instructions (tokens in static/css/app.css; layout is plain CSS grid).
2. Collect 200+ real complaints (public tweets / grievance posts), label, add to gold_test.py (testing) and/or
   scripts/import_csv.py (training), report new accuracy. The importer and training hook exist; no real data yet.
3. Adapters to ingest real feeds into POST /api/complaints (X, WhatsApp webhook, portal export).
4. Optional syllabus extras: CYK parser for complaint structure (Unit III), Kannada/Hindi translation (Unit IV).
5. (Done, untested remotely: Dockerfile, CI, screenshots, GIF.) Confirm CI is green on GitHub and the Docker build works.
6. Final presentation: live demo flow is Inject incident -> Emerging trends -> NLP Analyzer -> Model page.

## Preferences
- Jordan is a student; explain choices simply and keep code readable (it must be explainable in a viva).
- Prefer small, tested changes; show the diff summary and test results after each change.