"""Real labelled complaints that are added to the synthetic training data.

The file `app/data/real_labeled.csv` (columns: text,label) is optional. It is created by
`python scripts/import_csv.py your_file.csv`; `models.train_all` uses it when it exists.

Two safety rules are enforced here, for both the importer and the trainer:
  * labels must be one of the known categories;
  * a text that also appears in the hand-written test set (gold_test.py) is dropped, so a test
    complaint can never leak into training.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.config import CATEGORIES
from app.data.gold_test import GOLD, GOLD_NEW

REAL_CSV = Path(__file__).with_name("real_labeled.csv")
MIN_CHARS = 8


def key(text: str) -> str:
    """Comparison key for duplicates: lower-case, single spaces."""
    return " ".join((text or "").lower().split())


def norm_label(label: str) -> str:
    """'Driver Behavior', 'driver-behavior ' -> 'driver_behavior'."""
    return (label or "").strip().lower().replace("-", "_").replace(" ", "_")


def gold_keys() -> set[str]:
    return {key(t) for _, t in GOLD} | {key(t) for _, t in GOLD_NEW}


def clean_rows(rows, existing=()):
    """Validate (text, label) pairs. Returns (kept, rejected) where rejected maps a reason to a list of texts.

    `existing` are rows already stored; they count as duplicates but are not returned again.
    """
    seen = {key(r["text"]) for r in existing}
    blocked = gold_keys()
    kept, rejected = [], {"bad label": [], "too short": [], "duplicate": [], "same text as test set": []}
    for text, label in rows:
        text, lab = " ".join((text or "").split()), norm_label(label)
        if lab not in CATEGORIES:
            rejected["bad label"].append(f"{label!r}: {text[:50]}")
        elif len(text) < MIN_CHARS:
            rejected["too short"].append(text)
        elif key(text) in blocked:
            rejected["same text as test set"].append(text[:60])
        elif key(text) in seen:
            rejected["duplicate"].append(text[:60])
        else:
            seen.add(key(text))
            kept.append({"text": text, "label": lab})
    return kept, rejected


def load_real(path: Path | None = None) -> list[dict]:
    """Rows of real_labeled.csv ([] if the file does not exist). Invalid / test-set rows are skipped."""
    path = path or REAL_CSV
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        pairs = [(r.get("text", ""), r.get("label", "")) for r in csv.DictReader(f)]
    return clean_rows(pairs)[0]


def save_real(rows: list[dict], path: Path | None = None) -> None:
    with open(path or REAL_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["text", "label"])
        w.writeheader()
        w.writerows(rows)
