import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TRANSAFE_BACKFILL_HOURS", "0.5")
os.environ.setdefault("TRANSAFE_SIM", "0")
os.environ.setdefault("TRANSAFE_LIVE", "0")      # never poll real feeds from tests

import pytest

from app.nlp.edit_distance import align, distance
from app.nlp.language_model import NGramLM
from app.nlp.location import LocationExtractor
from app.nlp.preprocess import normalize
from app.nlp import severity, pos_tagger
from app.engine.search import BM25Index


def test_edit_distance():
    assert distance("kitten", "sitting") == 3
    assert distance("teh", "the") == 1            # transposition
    assert distance("bus", "bus") == 0
    d, ops = align("intention", "execution")
    assert d == 5 and sum(o[0] != "match" for o in ops) == 5


def test_lm_is_a_distribution():
    sents = [["bus", "is", "late"], ["bus", "is", "full"], ["metro", "is", "late"]]
    for method in ("laplace", "addk", "kn"):
        lm = NGramLM(2, method).fit(sents)
        total = sum(lm.prob(w, ("is",)) for w in lm.vocab if w != "<s>")
        assert total == pytest.approx(1.0, abs=0.02), method
    assert NGramLM(2, "mle").fit(sents).prob("full", ("metro",)) == 0.0
    assert NGramLM(2, "kn").fit(sents).prob("full", ("metro",)) > 0.0


def test_normalize_code_mixed_and_slang():
    n = normalize("@BMTC_Bengaluru bus tumba late pls #SilkBoardJam 45mins")
    assert "very" in n.tokens and "please" in n.tokens
    assert "silk" in n.tokens and "board" in n.tokens
    assert "kn" in {l for _, _, l in n.code_mixed}


def test_location_fuzzy_and_route():
    lx = LocationExtractor()
    locs = lx.locations("stuck near silk bord for ages".split())
    assert locs and locs[0]["name"] == "Silk Board"
    locs = lx.locations("waiting at marthahalli".split())
    assert locs and locs[0]["name"] == "Marathahalli"
    assert LocationExtractor.routes("Bus 335E never comes, 500D too") == ["335E", "500D"]
    assert LocationExtractor.routes("about 50 people on the bus") == []


def test_severity_ordering_and_negation():
    def sc(txt, cat):
        n = normalize(txt)
        return severity.score(n.tokens, n.text, cat, n)["score"]
    assert sc("a man was injured in an accident, children screaming", "safety") > sc("seat is slightly dirty", "vehicle_condition")
    assert sc("bus is 2 hours late again", "delay") > sc("bus is 10 minutes late", "delay")
    assert sc("no accident today but the bus is late", "delay") < sc("accident today and the bus is late", "delay")
    assert severity.parse_minutes("waited half an hour") == 30
    assert severity.parse_minutes("stuck for 2 hours") == 120


def test_pos_and_phrases():
    t = pos_tagger.tag("the rude conductor refused to give change".split())
    tags = dict((w, g) for w, g, _ in t)
    assert tags["the"] == "DET" and tags["conductor"] == "NOUN"
    assert "rude conductor" in pos_tagger.noun_phrases(t)


def test_bm25():
    ix = BM25Index()
    ix.add(1, "ac not working in bus".split())
    ix.add(2, "bus late at silk board".split())
    ix.add(3, "broken seats and ac leaking".split())
    top = [d for d, _ in ix.search(["ac", "working"])]
    assert top[0] == 1 and 2 not in top


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_api_analyze(client):
    r = client.post("/api/analyze", json={"text": "Bus 335E broke dwn near Silk Bord, stuck 45 mins, women stranded!!"}).json()
    assert r["category"] == "breakdown" and r["location"] == "Silk Board" and r["route"] == "335E"
    assert r["severity_level"] in ("high", "critical")
    assert abs(sum(r["probs"].values()) - 1) < 0.01


def test_api_analyze_noise_slider(client):
    text = "Bus 335E broke down near Silk Board, very late and the conductor was rude to passengers"
    clean = client.post("/api/analyze", json={"text": text, "noise": 0, "seed": 1}).json()
    assert clean["noisy_text"] == text and clean["original"] == text and clean["noise"] == 0     # 0 % = untouched
    a = client.post("/api/analyze", json={"text": text, "noise": 100, "seed": 1}).json()
    b = client.post("/api/analyze", json={"text": text, "noise": 100, "seed": 1}).json()
    assert a["noisy_text"] == b["noisy_text"] != text and a["original"] == text         # same seed, same typos
    changed = sum(x.lower() != y.lower() for x, y in zip(text.split(" "), a["noisy_text"].split(" ")))
    assert changed >= 5 and len(a["corrections"]) >= 2                                  # typos added, spell-checker fixed some
    assert client.post("/api/analyze", json={"text": text, "noise": 101}).status_code == 422


def test_api_ingest_and_search(client):
    r = client.post("/api/complaints", json={"text": "AC not working in bus 500D at Hebbal, dirty seats", "source": "Test"}).json()
    assert r["category"] == "vehicle_condition" and r["cluster_id"]
    hits = client.get("/api/complaints", params={"q": "ac not working"}).json()
    assert hits and any(h["id"] == r["id"] for h in hits)
    assert client.get(f"/api/issues/{r['cluster_id']}").json()["count"] >= 1
    assert client.get("/api/export.csv").text.startswith("id,ts")


def test_api_non_complaint_filtered(client):
    r = client.post("/api/analyze", json={"text": "What time is the first metro from Whitefield?"}).json()
    assert r["category"] == "other" and not r["actionable"] and r["severity"] == 0


def test_burst_detection(client):
    from app.main import engine, sim
    sim.trigger("bus_breakdown", "Silk Board")
    for _ in range(25):
        engine.vtime += 60
        sim.step(engine.vtime - 60, engine.vtime, publish=False, auto=False)
    labels = [i["label"] for i in engine.snapshot()["emerging"]["items"]]
    assert any("Silk Board" in l for l in labels)


# ---------------------------------------------------------------- time-of-day aware trend baseline
_RUSH_MIX = [("overcrowding", "Silk Board", "335E"), ("delay", "Majestic", None), ("overcrowding", None, "500D"),
             ("delay", "Hebbal", "G4"), ("safety", "KR Puram", None), ("breakdown", None, "335E"),
             ("fare_ticketing", "MG Road", None), ("overcrowding", "Majestic", None), ("delay", None, None),
             ("vehicle_condition", "Marathahalli", "500D")]


def _trend_log(prev_days, today_scale=1.0, until_hour=9.5, extra=()):
    """Noise-free complaint log that follows the simulator's daily curve (quiet night, morning rush).
    `prev_days` full days, then today up to `until_hour`; today may run `today_scale` times busier."""
    from datetime import datetime
    from app.engine.simulator import TZ, base_rate
    from app.engine.trends import DAY, TrendEngine

    day0 = datetime(2026, 3, 2, tzinfo=TZ).timestamp()
    te = TrendEngine()

    def add_day(d, hours, scale):
        t, acc, i = day0 + d * DAY, 0.0, 0
        while t < day0 + d * DAY + hours * 3600:
            acc += base_rate(t) * scale
            while acc >= 1.0:
                cat, loc, rt = _RUSH_MIX[i % len(_RUSH_MIX)]
                te.add({"actionable": True, "ts": t + 30.0, "category": cat, "location": loc, "route": rt,
                        "severity": 40.0, "source": "test", "mode": "bus"})
                i, acc = i + 1, acc - 1.0
            t += 60.0

    for d in range(prev_days):
        add_day(d, 24, 1.0)
    add_day(prev_days, until_hour, today_scale)
    for e in extra:
        te.add(e)
    return te, day0 + prev_days * DAY


def _alert_times(te, today_start, first_hour=6.5, last_hour=9.5):
    """Times (hours) between first_hour and last_hour, every 5 minutes, at which anything is flagged."""
    out, h = [], first_hour
    while h <= last_hour:
        if te.emerging(today_start + h * 3600)["items"]:
            out.append(round(h, 2))
        h += 5 / 60
    return out


def test_rush_hour_ramp_up_raises_no_alert():
    # 3 normal days, then a day that is 10% busier but has NO incident: the morning ramp-up must stay quiet
    te, today = _trend_log(prev_days=3, today_scale=1.1)
    assert te.slot_days(today + 8.5 * 3600) == 3
    assert _alert_times(te, today) == []


def test_rush_hour_ramp_up_false_alarms_with_fresh_log():
    # Same ramp-up but only today exists (< 2 previous days): falls back to the 3-hour baseline, which mistakes
    # the ramp-up for a burst. This proves the test above would catch a regression.
    te, today = _trend_log(prev_days=0, today_scale=1.1)
    assert te.slot_days(today + 8.5 * 3600) == 0
    assert len(_alert_times(te, today)) > 5


def test_real_burst_still_detected_during_rush_hour():
    from app.engine.trends import RECENT
    burst = [{"actionable": True, "ts": None, "category": "breakdown", "location": "Yelahanka", "route": "G4",
              "severity": 70.0, "source": "test", "mode": "bus"} for _ in range(10)]
    te, today = _trend_log(prev_days=3, until_hour=8.5)
    now = today + 8.5 * 3600
    for k, e in enumerate(burst):
        e["ts"] = now - RECENT + 120 * (k + 1)           # ten breakdown reports in 20 minutes at a new place
        te.add(e)
    labels = [i["label"] for i in te.emerging(now)["items"]]
    assert any("Yelahanka" in l for l in labels)


# ---------------------------------------------------------------- real labelled data (never trained on test complaints)
def test_real_data_validation_and_test_set_guard():
    from app.data.gold_test import GOLD, GOLD_NEW
    from app.data.real_data import clean_rows
    msg = "Bus 335E skipped our stop at Hebbal again"
    kept, rej = clean_rows([(msg, "Driver Behavior"), (msg.upper(), "delay"), ("bus is late", "nonsense"), ("hi", "delay"),
                            (GOLD[0][1], "overcrowding"), (GOLD_NEW[0][1], "overcrowding")])
    assert kept == [{"text": msg, "label": "driver_behavior"}]           # label normalised, duplicate dropped
    assert len(rej["duplicate"]) == 1 and len(rej["bad label"]) == 1 and len(rej["too short"]) == 1
    assert len(rej["same text as test set"]) == 2                          # both test batches are protected


def test_import_csv_script_merges_and_reports(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("import_csv", Path(__file__).resolve().parent.parent / "scripts" / "import_csv.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src, out = tmp_path / "in.csv", tmp_path / "real.csv"
    src.write_text("Text,Label\nAC not working in bus 500D since Monday,vehicle_condition\nMetro gate charged me twice,fare_ticketing\n"
                   "random words here please,not_a_class\n", encoding="utf-8-sig")
    assert mod.main([str(src), "--out", str(out), "--dry-run"]) == 0 and not out.exists()
    assert mod.main([str(src), "--out", str(out)]) == 0
    from app.data.real_data import load_real
    assert [r["label"] for r in load_real(out)] == ["vehicle_condition", "fare_ticketing"]
    assert mod.main([str(src), "--out", str(out)]) == 0                    # second run adds nothing
    assert len(load_real(out)) == 2
    assert "skipped - bad label: 1" in capsys.readouterr().out
    assert load_real(tmp_path / "missing.csv") == []                        # no file -> synthetic-only training


# ---------------------------------------------------------------- live sources (mocked HTTP, no network)
def _client(handler):
    import httpx
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_x_source_parses_and_uses_since_id():
    import httpx
    from app.ingest.sources import XSource
    calls = []

    def handler(req: httpx.Request):
        calls.append(dict(req.url.params))
        assert req.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json={"data": [{"id": "12", "text": "Bus 500D late again @ Hebbal", "created_at": "2026-10-30T04:30:00.000Z"},
                                                  {"id": "11", "text": "BMTC AC not working", "created_at": "2026-10-30T04:00:00.000Z"}],
                                         "meta": {"newest_id": "12"}})

    src = XSource("tok", client=_client(handler))
    items = src.fetch()
    assert [i.ext_id for i in items] == ["11", "12"] and items[0].ts < items[1].ts     # oldest first
    src.fetch()
    assert "since_id" not in calls[0] and calls[1]["since_id"] == "12"


def test_x_source_errors_are_readable():
    import httpx
    from app.ingest.sources import SourceError, XSource
    for status, msg in ((401, "bearer token"), (402, "credits"), (429, "rate limit")):
        src = XSource("tok", client=_client(lambda req, s=status: httpx.Response(s)))
        with pytest.raises(SourceError, match=msg):
            src.fetch()


def test_reddit_source_dedupes_and_relogins():
    import httpx
    from app.ingest.sources import RedditSource, SourceError

    def handler(req: httpx.Request):
        if req.url.host == "www.reddit.com":
            return httpx.Response(200, json={"access_token": "abc"})
        post = {"data": {"name": "t3_x1", "title": "BMTC bus skipped our stop", "selftext": "third time this week", "created_utc": 1_700_000_000}}
        return httpx.Response(200, json={"data": {"children": [post]}})

    src = RedditSource("id", "secret", subreddits=["bangalore"], client=_client(handler))
    first = src.fetch()
    assert len(first) == 1 and "skipped our stop" in first[0].text
    assert src.fetch() == []                                   # same post is not returned twice

    expired = RedditSource("id", "secret", subreddits=["bangalore"],
                           client=_client(lambda req: httpx.Response(200, json={"access_token": "abc"}) if req.url.host == "www.reddit.com" else httpx.Response(401)))
    with pytest.raises(SourceError):
        expired.fetch()
    assert expired.token is None                               # next poll logs in again


def test_ingest_items_keeps_post_time_and_marks_source(client):
    from app.ingest.runner import ingest_items
    from app.ingest.sources import Item
    from app.main import engine
    old = engine.vtime - 3600
    n = ingest_items(engine, "X / Twitter (live)", [Item("1", "Bus 335E broke down near Silk Board", old), Item("2", "   ", old)])
    rec = engine.recent[0]
    assert n == 1 and rec["source"] == "X / Twitter (live)" and rec["ts"] == old


def test_meta_and_sources_in_simulator_mode(client):
    meta = client.get("/api/meta").json()
    assert meta["live"] is False and "maps_key" in meta
    assert client.get("/api/sources").json() == {"live": False, "sources": []}
