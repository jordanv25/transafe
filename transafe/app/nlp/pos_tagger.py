"""Part-of-speech tagging (Unit II): rule-based lexicon + suffix heuristics,
refined by Brill-style transformation rules (contextual tag-rewrite rules).

Tagset: universal POS (NOUN, VERB, ADJ, ADV, DET, PRON, ADP, CONJ, NUM, AUX, PART, PROPN).
Used to pull out noun-phrase "issue keywords" and to scope negation.
"""
from __future__ import annotations

import re

LEX = {}


def _add(tag, words):
    for w in words.split():
        LEX[w] = tag


_add("DET", "a an the this that these those some any no every each all both another")
_add("PRON", "i me my we us our you your he she it its they them their who whom what which myself")
_add("ADP", "at in on near from to of for with by about after before during since between into onto over under "
            "through inside outside behind opposite opp till until across towards")
_add("CONJ", "and or but because so if while although though as than")
_add("AUX", "is are was were be been being am do does did has have had will would can could should may might must shall")
_add("PART", "not never cannot")
_add("INTJ", "please thanks thank sorry hello hi sir")
_add("ADV", "very too really extremely still again always often never already just only even almost nearly "
            "totally completely badly again daily everyday now then here there today yesterday tomorrow "
            "late early slowly suddenly constantly repeatedly seriously")
_add("ADJ", "crowded overcrowded packed full empty dirty broken rude late slow unsafe dangerous worst terrible "
            "horrible bad good great old new torn leaking dark wet slippery noisy smelly hot cold loud steep "
            "narrow extra wrong stuck delayed cancelled suspended halted missing useless helpful clean smooth "
            "polite kind unprofessional filthy rusted dead stranded impossible scary")
_add("NOUN", "bus buses driver conductor metro train trains station stop stand platform passengers passenger "
             "people women woman man men kids children child seat seats door doors window windows ac fare ticket "
             "tickets card pass change money payment app machine gate lift escalator ramp staff guard security "
             "traffic signal route service trip depot crew engine tyre floor roof light lights fan toilet water "
             "smell garbage accident harassment theft phone coach line track power failure delay queue crowd "
             "rush space seats footboard handrail announcement display board timing timings schedule frequency "
             "refund recharge token qr upi cctv police camera elderly citizens bag wallet")
_add("VERB", "stopped stop wait waiting waited come came coming arrive arrived arriving broke break breaks "
             "refused refuse shouted shout abused abuse harassed harass stolen steal stole fell fall fallen "
             "charged charge deducted deduct failed fail work working worked running run ran skip skipped "
             "board boarded push pushing hang hanging drive driving drove miss missed need needs get got "
             "give gave take took see saw tried touched followed hit injured")

SUFFIX = [
    (re.compile(r".*(ing)$"), "VERB"), (re.compile(r".*(ed)$"), "VERB"),
    (re.compile(r".*(ly)$"), "ADV"), (re.compile(r".*(ous|ful|able|ible|ive|ic|al|less)$"), "ADJ"),
    (re.compile(r".*(tion|sion|ment|ness|ity|ance|ence|er|or|ist)$"), "NOUN"),
    (re.compile(r".*s$"), "NOUN"),
]

# Brill-style contextual transformations: (from_tag, to_tag, test(prev_tag, next_tag, word))
RULES = [
    ("VERB", "NOUN", lambda p, n, w: p in {"DET", "ADJ"} and n not in {"NOUN"}, "VERB->NOUN after DET/ADJ"),
    ("NOUN", "VERB", lambda p, n, w: p == "PART" or (p == "PRON" and w.endswith("ed")), "NOUN->VERB after PART/PRON"),
    ("ADJ", "NOUN", lambda p, n, w: p in {"DET"} and n in {"ADP", "AUX", "CONJ", None}, "ADJ->NOUN as head after DET"),
    ("NOUN", "ADJ", lambda p, n, w: p in {"AUX", "ADV"} and n in {None, "CONJ", "ADP"}, "NOUN->ADJ after AUX/ADV"),
    ("VERB", "ADJ", lambda p, n, w: p in {"AUX", "ADV"} and w.endswith("ed") and n in {None, "ADP", "CONJ"}, "VERB->ADJ predicative participle"),
    ("NOUN", "VERB", lambda p, n, w: p == "ADP" and w == "to", "after to"),
]


def tag(tokens: list[str]):
    """Return list of (token, tag, source) where source in lexicon/suffix/default/rule:<name>."""
    out = []
    for t in tokens:
        if t in LEX:
            out.append([t, LEX[t], "lexicon"])
        elif re.match(r"^\d+([.:]\d+)?(am|pm)?$", t):
            out.append([t, "NUM", "regex"])
        elif re.match(r"^\d+[a-z]{1,3}$", t) or re.match(r"^[a-z]{1,3}-?\d+[a-z]*$", t):
            out.append([t, "PROPN", "regex"])
        else:
            for rx, tg in SUFFIX:
                if rx.match(t):
                    out.append([t, tg, "suffix"])
                    break
            else:
                out.append([t, "NOUN", "default"])
    for _ in range(2):  # apply the rule list a couple of passes
        for i, item in enumerate(out):
            p = out[i - 1][1] if i > 0 else None
            n = out[i + 1][1] if i + 1 < len(out) else None
            for frm, to, test, name in RULES:
                if item[1] == frm and test(p, n, item[0]) and item[2] != "regex":
                    item[1], item[2] = to, "rule:" + name
                    break
    return [tuple(x) for x in out]


def noun_phrases(tagged, max_len=4):
    """Chunk (ADJ|VERB-participle|NOUN)* NOUN+ spans -> issue key-phrases."""
    phrases, cur = [], []
    for tok, tg, _ in tagged:
        if tg in {"NOUN", "ADJ", "PROPN"} or (tg == "VERB" and tok.endswith(("ed", "ing")) and cur):
            cur.append((tok, tg))
        else:
            _flush(cur, phrases, max_len)
            cur = []
    _flush(cur, phrases, max_len)
    return phrases


STOP_HEAD = {"people", "thing", "time", "way"}


def _flush(cur, phrases, max_len):
    while cur and cur[-1][1] not in {"NOUN", "PROPN"}:
        cur.pop()
    if not cur:
        return
    words = [w for w, _ in cur][-max_len:]
    if len(words) == 1 and (words[0] in STOP_HEAD or len(words[0]) < 3):
        return
    phrases.append(" ".join(words))
