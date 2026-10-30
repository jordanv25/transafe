# Transafe

Real-Time Public Transport Complaint Analyzer. College NLP project (AI53, MSRIT, Bengaluru), Problem 5.
Goal: process incoming passenger complaints (BMTC bus + Namma Metro) and produce live categories,
locations, severity levels and emerging trends. Must be a fully working, polished project that earns
full internal marks and looks strong on a resume. Owner: Jordan.

## Run / test
- `pip install -r requirements.txt`
- `python run.py` (trains models on first run, ~10 s; serves http://127.0.0.1:8000; `--retrain` forces retraining)
- `python -m pytest -q tests` (11 tests, must stay green)
- Env vars: `TRANSAFE_BACKFILL_HOURS` (default 3), `TRANSAFE_SIM` (1 = simulator on)

## Architecture
raw text -> normalise -> spell-correct -> classify -> places/routes -> severity -> POS/phrases
-> cluster + trend engine + BM25 + SQLite -> FastAPI (REST + SSE) -> dashboard.
- `app/main.py` routes and SSE; `app/engine/` core.py, clustering.py, trends.py, search.py, simulator.py
- `app/nlp/` preprocess, edit_distance, language_model (MLE/add-1/add-k/Kneser-Ney), spell (noisy channel),
  pos_tagger (lexicon + suffix + Brill rules), location (gazetteer + fuzzy), severity, models (training/eval), pipeline
- `app/data/` generator.py (template grammar for synthetic training text), gold_test.py (108 hand-written test
  complaints, NEVER train on it), gazetteer.py (~50 Bengaluru places, approximate coordinates)
- `static/` index.html, css/app.css (design tokens at top), js/ (one module per page); Chart.js and Leaflet are vendored
- `docs/EXPLAINER.md` explains every component, formulas, likely viva questions

## Current results (python run.py --retrain)
- 88.0% accuracy / 87.7% macro-F1 on the hand-written test set; Naive Bayes baseline 86.1%
- 74.4% on held-out synthetic templates (random split is 100% and optimistic; do not quote it)

## Rules for working on this repo
- Be honest in docs and UI: training data is synthetic, the live feed is simulated, gazetteer coordinates are approximate.
- Never add gold_test.py examples to training data. New real labelled complaints go into gold_test.py only.
- After changing NLP code or templates: retrain, run tests, update numbers in README and the Model page text.
- Keep the 8 category colours in app/config.py (validated palette, fixed order, never cycled).
- Do not commit models/, *.sqlite3*, __pycache__ (see .gitignore).
- Syllabus mapping (README) must stay accurate: units I, II, III, V are covered; CYK parsing (III) and machine translation (IV) are not.

## Known limitations
- Synthetic training data; real-world accuracy unverified. Safety is the weakest class (about 76% F1).
- Severity is rule-based (no labelled severity data). Small gazetteer. Romanised Hindi/Kannada only, no native scripts.
- Spell corrector skips words shorter than 4 letters and may mis-correct unseen romanised Hindi/Kannada words.
- Kneser-Ney perplexity is worse than add-1 on the out-of-domain hand-written set (explained in docs).

## Roadmap (priority order)
1. UI restyle per Jordan's instructions (tokens in static/css/app.css; layout is plain CSS grid).
2. Collect 200+ real complaints (public tweets / grievance posts), label, add to gold_test.py, report new accuracy.
3. Adapters to ingest real feeds into POST /api/complaints (X, WhatsApp webhook, portal export).
4. Optional syllabus extras: CYK parser for complaint structure (Unit III), Kannada/Hindi translation (Unit IV).
5. Docker file, CI running pytest, screenshots and a demo GIF in the README for the resume.
6. Final presentation: live demo flow is Inject incident -> Emerging trends -> NLP Analyzer -> Model page.

## Preferences
- Jordan is a student; explain choices simply and keep code readable (it must be explainable in a viva).
- Prefer small, tested changes; show the diff summary and test results after each change.