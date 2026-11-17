"""Import real, hand-labelled complaints into app/data/real_labeled.csv (used for training).

    python scripts/import_csv.py my_complaints.csv            # merge into real_labeled.csv
    python scripts/import_csv.py my_complaints.csv --dry-run  # only report, write nothing
    python scripts/import_csv.py my_complaints.csv --replace  # start the file again
    python scripts/import_csv.py my_complaints.csv --out other.csv

Input: a CSV with the columns `text` and `label`. Valid labels:
    overcrowding, delay, safety, driver_behavior, vehicle_condition, fare_ticketing,
    breakdown, accessibility, other        ("Driver Behavior" / "driver-behavior" are accepted)

Rows are skipped (and listed) when the label is unknown, the text is too short, the text is a duplicate,
or the text is also in the hand-written test set (gold_test.py) - test complaints must never be trained on.
Afterwards run `python run.py --retrain` to train on synthetic + real data.

Only import posts you are allowed to use (check each platform's terms; remove usernames and phone numbers).
Complaints meant for TESTING go into app/data/gold_test.py instead, never into this file.
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import CATEGORIES                                   # noqa: E402
from app.data.real_data import REAL_CSV, clean_rows, load_real, save_real   # noqa: E402


def read_pairs(path: Path):
    """Yield (text, label) from a CSV with `text` and `label` columns (header case-insensitive)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = {(c or "").strip().lower(): c for c in (reader.fieldnames or [])}
        if "text" not in cols or "label" not in cols:
            sys.exit(f"error: {path} needs the columns text,label (found: {reader.fieldnames})")
        return [(r[cols["text"]], r[cols["label"]]) for r in reader]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path, help="CSV with columns text,label")
    ap.add_argument("--out", type=Path, default=REAL_CSV, help=f"output file (default: {REAL_CSV})")
    ap.add_argument("--replace", action="store_true", help="overwrite the output file instead of merging")
    ap.add_argument("--dry-run", action="store_true", help="validate and report only")
    args = ap.parse_args(argv)

    if not args.csv.exists():
        sys.exit(f"error: {args.csv} not found")
    pairs = read_pairs(args.csv)
    existing = [] if args.replace else load_real(args.out)
    kept, rejected = clean_rows(pairs, existing=existing)

    print(f"read {len(pairs)} rows from {args.csv}")
    print(f"  accepted: {len(kept)}")
    for reason, items in rejected.items():
        if items:
            print(f"  skipped - {reason}: {len(items)}")
            for item in items[:3]:
                print(f"      {item}")
            if len(items) > 3:
                print(f"      ... and {len(items) - 3} more")
    total = existing + kept
    counts = Counter(r["label"] for r in total)
    print(f"{args.out.name} would hold {len(total)} rows: " + ", ".join(f"{c} {counts[c]}" for c in CATEGORIES if counts[c]))

    if args.dry_run:
        print("dry run: nothing written")
        return 0
    if not kept and not args.replace:
        print("nothing new to add; file unchanged")
        return 0
    save_real(total, args.out)
    print(f"wrote {args.out}. Next: python run.py --retrain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
