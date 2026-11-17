"""Measure the two speed numbers quoted in the README "Results" section.

    python scripts/benchmark.py                       # about 15 minutes (each trial backfills 50 h of history)
    python scripts/benchmark.py --seeds 2             # fewer trials, about 8 minutes
    python scripts/benchmark.py --history-hours 3     # the old 3-hour start-up, about 2 minutes

1. Latency - mean time the NLP pipeline needs per complaint (normalise -> spell-correct -> classify -> places ->
   severity -> POS), measured on the hand-written complaints in gold_test.py. This is the "latency_ms" KPI of the dashboard.
   It depends on the computer, so quote it together with the machine.
2. Detection delay - minutes of *simulated* time between injecting an incident (every scenario of the simulator, at
   its default place) and the Emerging-trends panel flagging that place or route. The engine starts with the same
   history as the demo (50 hours by default, which activates the time-of-day baseline). Trials where the place was already flagged by chance before the incident are skipped.
"""
import argparse
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.engine.core as core                                          # noqa: E402
from app.data.gold_test import GOLD, GOLD_NEW                            # noqa: E402
from app.engine.simulator import SCENARIOS, Simulator                    # noqa: E402

STEP = 30.0           # simulated seconds between checks
GIVE_UP = 60 * 60.0   # simulated seconds


def new_engine(tmp: Path, seed: int, hours: float):
    core.DB_PATH = tmp / f"bench_{seed}.sqlite3"          # never touch the real data_store.sqlite3
    eng = core.Engine()
    sim = Simulator(eng, seed=seed)
    sim.backfill(hours, log=lambda *_: None)
    return eng, sim


def latency(tmp: Path, passes=4):
    eng, _ = new_engine(tmp, 0, 0.25)                       # history length does not affect per-complaint cost
    texts = [t for _, t in GOLD + GOLD_NEW]
    for t in texts[:30]:                                    # warm-up (first calls load caches)
        eng.analyzer.analyze(t)
    ms = [eng.analyzer.analyze(t)["latency_ms"] for _ in range(passes) for t in texts]
    eng.db.close()
    return statistics.mean(ms), statistics.median(ms), max(ms), len(ms)


def flagged(eng, inc):
    labels = [i["label"] for i in eng.trends.emerging(eng.vtime)["items"]]
    return any(inc["location"] in l or (inc["route"] and f"Route {inc['route']}" == l) for l in labels)


def detection_delays(tmp: Path, seeds: int, hours: float):
    delays, missed, skipped = [], 0, 0
    for kind in SCENARIOS:
        for seed in range(1, seeds + 1):
            eng, sim = new_engine(tmp, seed, hours)
            inc = sim.trigger(kind)
            if flagged(eng, inc):
                skipped += 1
                eng.db.close()
                continue
            t0, found = eng.vtime, None
            while eng.vtime - t0 < GIVE_UP:
                v0 = eng.vtime
                eng.vtime += STEP
                sim.step(v0, eng.vtime, publish=False, auto=False)
                if flagged(eng, inc):
                    found = (eng.vtime - t0) / 60.0
                    break
            eng.db.close()
            if found is None:
                missed += 1
            else:
                delays.append(found)
            print(f"  {kind:14s} seed {seed}: " + (f"flagged after {found:4.1f} min" if found else "NOT flagged within 60 min"))
    return delays, missed, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=4, help="trials per scenario (default 4 -> 24 trials)")
    ap.add_argument("--history-hours", type=float, default=50, help="simulated history before each incident (default 50, like the demo)")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        t0 = time.time()
        mean, med, mx, n = latency(tmp)
        print(f"\nLatency over {n} complaints: mean {mean:.1f} ms, median {med:.1f} ms, max {mx:.1f} ms  "
              f"({platform.processor() or platform.machine()}, Python {platform.python_version()})\n")
        print(f"Detection delay (simulated minutes after injection, {args.history_hours:g} h of history):")
        delays, missed, skipped = detection_delays(tmp, args.seeds, args.history_hours)
    if delays:
        print(f"\nDetected {len(delays)} of {len(delays) + missed} incidents ({skipped} skipped: already flagged). "
              f"Delay: mean {statistics.mean(delays):.1f} min, median {statistics.median(delays):.1f} min, "
              f"worst {max(delays):.1f} min   [{time.time() - t0:.0f} s to run]")


if __name__ == "__main__":
    main()
