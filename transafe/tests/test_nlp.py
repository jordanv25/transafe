import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TRANSAFE_BACKFILL_HOURS", "0.5")
os.environ.setdefault("TRANSAFE_SIM", "0")

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
