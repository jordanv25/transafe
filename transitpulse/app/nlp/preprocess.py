"""Text normalisation for noisy social-media / portal complaints.

Steps: unicode + HTML clean-up, URL/mention/hashtag handling, emoji signals,
elongation squeeze, slang + contraction expansion, romanised Hindi / Kannada
(code-mixed) lexicon mapping, unit normalisation, tokenisation.
(Processing Indian-language text is part of Unit I.)
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field

URL_RE = re.compile(r"https?://\S+|www\.\S+")
MENTION_RE = re.compile(r"@\w+")
HASHTAG_RE = re.compile(r"#(\w+)")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
ANGRY = set("\U0001F621\U0001F620\U0001F92C\U0001F624")

SLANG = {
    "pls": "please", "plz": "please", "plss": "please", "bcoz": "because", "bcz": "because", "bcs": "because",
    "bcause": "because", "cuz": "because", "coz": "because", "bcoz.": "because", "u": "you", "ur": "your",
    "r": "are", "govt": "government", "ppl": "people", "pax": "passengers", "mins": "minutes", "min": "minutes",
    "hrs": "hours", "hr": "hour", "msg": "message", "tmrw": "tomorrow", "smthng": "something", "w8": "wait",
    "ac": "ac", "btw": "by the way", "asap": "as soon as possible", "bz": "busy", "bcos": "because",
    "bcoz": "because", "rs": "rupees", "inr": "rupees", "kms": "kilometres", "km": "kilometres",
    "bmtc": "bmtc", "bmrcl": "bmrcl", "bcz.": "because", "dont": "do not", "cant": "cannot", "wont": "will not",
    "didnt": "did not", "doesnt": "does not", "isnt": "is not", "wasnt": "was not", "hasnt": "has not",
    "havent": "have not", "couldnt": "could not", "shouldnt": "should not", "its": "its", "im": "i am",
    "ive": "i have", "thats": "that is", "whats": "what is", "wont.": "will not", "cannot": "cannot",
}

# romanised Hindi (hi) and Kannada (kn) -> English gloss
CODE_MIX = {
    "bheed": ("crowd", "hi"), "bahut": ("very", "hi"), "bohot": ("very", "hi"), "bahot": ("very", "hi"),
    "jyada": ("too much", "hi"), "zyada": ("too much", "hi"), "nahi": ("not", "hi"), "nahin": ("not", "hi"),
    "nhi": ("not", "hi"), "der": ("delay", "hi"), "deri": ("delay", "hi"), "kharab": ("broken", "hi"),
    "ganda": ("dirty", "hi"), "gandi": ("dirty", "hi"), "gandagi": ("dirt", "hi"), "band": ("closed", "hi"),
    "bekar": ("useless", "hi"), "dhakka": ("push", "hi"), "paisa": ("money", "hi"), "paise": ("money", "hi"),
    "chutta": ("change", "hi"), "chhutta": ("change", "hi"), "badtameezi": ("rude behaviour", "hi"),
    "gaali": ("abuse", "hi"), "ghanta": ("hour", "hi"), "ghante": ("hours", "hi"), "kat": ("deducted", "hi"),
    "khatarnak": ("dangerous", "hi"), "bacche": ("children", "hi"), "gir": ("fall", "hi"), "toot": ("broken", "hi"),
    "jawab": ("stopped", "hi"), "roki": ("stopped", "hi"), "rokne": ("stop", "hi"), "aayi": ("came", "hi"),
    "aaya": ("came", "hi"), "mein": ("in", "hi"), "pe": ("at", "hi"), "ke": ("of", "hi"), "paas": ("near", "hi"),
    "hai": ("is", "hi"), "hain": ("are", "hi"), "tha": ("was", "hi"), "thi": ("was", "hi"), "ho": ("be", "hi"),
    "gaya": ("went", "hi"), "gayi": ("went", "hi"), "aane": ("coming", "hi"), "mujhe": ("me", "hi"),
    "maine": ("i", "hi"), "diya": ("gave", "hi"), "mili": ("got", "hi"), "jagah": ("space", "hi"),
    "seat": ("seat", "hi"), "khade": ("standing", "hi"), "rehne": ("staying", "hi"), "aur": ("and", "hi"),
    "ek": ("one", "hi"), "bhi": ("also", "hi"), "aaj": ("today", "hi"), "daag": ("stains", "hi"),
    "ka": ("of", "hi"), "ne": ("", "hi"), "se": ("from", "hi"), "kar": ("do", "hi"), "raha": ("", "hi"),
    "rahi": ("", "hi"), "sakte": ("can", "hi"), "kya": ("what", "hi"), "ki": ("of", "hi"), "lekin": ("but", "hi"),
    "hota": ("happens", "hi"), "hote": ("happen", "hi"), "hoga": ("will be", "hi"), "kiya": ("did", "hi"),
    "tumba": ("very", "kn"), "thumba": ("very", "kn"), "jasti": ("too much", "kn"), "jana": ("people", "kn"),
    "bandilla": ("did not come", "kn"), "illa": ("not", "kn"), "ide": ("is", "kn"), "aagide": ("is", "kn"),
    "alli": ("at", "kn"), "madide": ("did", "kn"), "nillisalla": ("did not stop", "kn"), "chillare": ("change", "kn"),
    "kasa": ("garbage", "kn"), "mele": ("on", "kn"), "dhool": ("dust", "kn"), "kodalilla": ("did not give", "kn"),
    "antha": ("that", "kn"), "swalpa": ("little", "kn"), "bega": ("fast", "kn"),
}
# words that are real English and must not be treated as code-mixed (ambiguous)
CODE_MIX_AMBIGUOUS = {"seat", "ho", "kar", "ke", "pe", "ka", "ne", "se", "ki", "mein", "ek", "kat", "gir", "ide",
                      "band", "hai", "der", "tha", "thi"}
# tokens that count as strong evidence of code-mixing
CODE_MIX_STRONG = {k for k in CODE_MIX if k not in CODE_MIX_AMBIGUOUS}

GENERIC_TAGS = {"bmtc", "nammametro", "bengaluru", "bangalore", "publictransport", "namma", "bmrcl", "blr"}
NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10}

TOKEN_RE = re.compile(r"\d+(?:[.:]\d+)?[a-z]*|[a-z]+(?:'[a-z]+)?|[^\w\s]")


@dataclass
class Normalized:
    raw: str
    text: str                        # normalised string
    tokens: list[str]
    hashtags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    code_mixed: list[tuple] = field(default_factory=list)   # (token, gloss, lang)
    exclaims: int = 0
    caps_ratio: float = 0.0
    angry: bool = False
    emojis: int = 0


def _split_hashtag(tag: str) -> str:
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", tag)
    return " ".join(p.lower() for p in parts) if parts else tag.lower()


def normalize(raw: str) -> Normalized:
    t = unicodedata.normalize("NFKC", html.unescape(raw or ""))
    letters = [c for c in t if c.isalpha()]
    caps = (sum(c.isupper() for c in letters) / len(letters)) if len(letters) > 12 else 0.0
    exclaims = t.count("!")
    emojis = EMOJI_RE.findall(t)
    angry = any(e in ANGRY for e in emojis)
    t = URL_RE.sub(" ", t)
    mentions = MENTION_RE.findall(t)
    t = MENTION_RE.sub(" ", t)
    hashtags = HASHTAG_RE.findall(t)
    t = HASHTAG_RE.sub(lambda m: " " if m.group(1).lower() in GENERIC_TAGS else " " + _split_hashtag(m.group(1)) + " ", t)
    t = EMOJI_RE.sub(" ", t)
    t = t.replace("₹", " rupees ").replace("&", " and ")
    t = t.lower()
    t = re.sub(r"(\w)\1{2,}", r"\1\1", t)                      # sooo -> soo
    t = re.sub(r"(\d)\s*(minutes|mins|min|hours|hrs|hr|h)\b", r"\1 \2", t)
    t = re.sub(r"(\d)(minutes|mins|min|hours|hrs|hr)\b", r"\1 \2", t)
    t = re.sub(r"\b(\d)\s*(am|pm)\b", r"\1\2", t)
    t = t.replace("'", "")
    raw_tokens = TOKEN_RE.findall(t)
    out, code = [], []
    for tok in raw_tokens:
        if tok in CODE_MIX and tok not in {"seat"}:
            gloss, lang = CODE_MIX[tok]
            if tok in CODE_MIX_STRONG:
                code.append((tok, gloss, lang))
            if gloss:
                out.extend(gloss.split())
            continue
        out.append(SLANG.get(tok, tok))
    tokens = " ".join(out).split()
    # drop pure punctuation except sentence enders (kept out entirely for modelling)
    tokens = [x for x in tokens if re.search(r"\w", x)]
    return Normalized(raw=raw, text=" ".join(tokens), tokens=tokens, hashtags=hashtags, mentions=mentions,
                      code_mixed=code, exclaims=exclaims, caps_ratio=caps, angry=angry, emojis=len(emojis))
