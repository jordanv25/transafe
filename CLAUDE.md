# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Transafe is a real-time public-transport complaint analyzer (NLP course project, Bengaluru BMTC/Metro). All code lives in the `transafe/` subdirectory; the repo root only holds a stub `README.md`. The full README is `transafe/README.md`, and `transafe/docs/EXPLAINER.md` explains each component's formulas.

## Commands

Run everything from `transafe/`:

```bash
pip install -r requirements.txt
python run.py                      # trains models if models/bundle.joblib is missing, then serves on :8000
python run.py --retrain            # force retraining (~10 s); also rewrites models/metrics.json
python run.py --no-browser --port 8001
python -m pytest -q tests          # full suite (~35 s, includes API tests via TestClient)
python -m pytest -q tests/test_nlp.py::test_severity_ordering_and_negation   # single test
```

There is no linter or build step. The frontend is static files served as-is (no bundler).

Environment variables (read in `app/main.py`): `TRANSAFE_SIM=0` stops the simulator autostarting; `TRANSAFE_BACKFILL_HOURS=<n>` sets how much simulated history is generated at startup (default 3, `0` disables). Tests set these to `0.5` / `0`.

## Architecture

One `Engine` instance (`app/engine/core.py`) is created in the FastAPI lifespan (`app/main.py`) and holds all state in memory. `Engine.ingest()` is the single entry point for every complaint, whether from the simulator, `POST /api/complaints`, or CSV upload. Under a lock it runs the NLP `Analyzer` (`app/nlp/pipeline.py`: normalise, spell-correct, classify, extract places and routes, severity, POS and phrases), assigns an incremental cluster (`engine/clustering.py`), feeds the burst detector (`engine/trends.py`), indexes for BM25 (`engine/search.py`), writes to SQLite, and publishes to SSE subscribers. `/api/stream` pushes `complaint` and `incident` events plus a `snapshot` every 2 s; the dashboard JS (`static/js/`, one module per page) consumes these.

Things that span files and are easy to miss:

- **Virtual time.** `Engine.vtime` is the clock used by trends, clustering and snapshots, not wall-clock time. The simulator (`engine/simulator.py`) advances it at `engine.speed` (1x-600x), and `ingest(..., ts=)` accepts explicit timestamps for backfill. Use `vtime` for anything time-windowed.
- **Models are trained, not checked in.** `app/nlp/models.py::train_all` builds `models/bundle.joblib` (TF-IDF + logistic regression, naive Bayes baseline, n-gram language model, LSA `SemanticSpace`) and `models/metrics.json` from synthetic text produced by `app/data/generator.py` (a template grammar with noise injection). `models/` is gitignored; the bundle loader in `models.py` trains it automatically if it is missing, so a fresh clone works for both `run.py` and the tests (the first run is slower).
- **Evaluation data.** `app/data/gold_test.py::GOLD` is the hand-written test set that is never trained on. The accuracy numbers shown in the UI and README come from it. Changing generator templates after inspecting gold errors inflates the numbers, so be upfront about that.
- **Fresh DB per start.** `Engine(fresh_db=True)` deletes `data_store.sqlite3` on startup. The SQLite log is write-only; queries are served from in-memory structures.
- **Shared constants.** Categories, labels, colours, severity thresholds and sources are defined once in `app/config.py` and are exposed to the frontend through `/api/meta`. A new category also needs training templates in `app/data/generator.py` and a prior in `app/nlp/severity.py`.
- **Internal fields.** Analyzer output carries an `_emb` vector that must be popped before returning or serialising (`Engine.ingest` and `main._clean` do this); `Engine.public()` whitelists the fields sent to clients.
- **Location data** (`app/data/gazetteer.py`) drives both fuzzy place extraction and the map coordinates returned by `/api/meta`.
