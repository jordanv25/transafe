"""Template-grammar generator for synthetic complaint text.

A complaint is built as   [opener] CORE [closer]   where CORE is picked from a
per-category grammar of templates with slots ({loc}, {route}, {dur}...).
Noise (typos, slang, code-mixing, elongation) is then injected so the
classifier sees realistic, messy text.  Used for (a) training data and
(b) the live simulator.
"""
from __future__ import annotations

import random
import re

from app.data.gazetteer import PLACES, ROUTES

DURS = ["10 minutes", "15 mins", "20 minutes", "half an hour", "30 mins", "45 minutes",
        "almost an hour", "1 hour", "over an hour", "1.5 hrs", "2 hours", "2 hrs", "three hours", "25 mins", "40 minutes"]
TIMES = ["since 8am", "since morning", "since 6 pm", "from 7:30", "since 5pm", "for ages", "since last evening"]
COUNTS = ["50", "100", "60", "more than 100", "nearly 80", "200", "around 70"]
LINES = ["Purple Line", "Green Line", "Yellow Line", "purple line", "green line", "yellow line"]

T = {
"overcrowding": [
 "bus {route} is jam packed at {loc}, cannot even stand properly",
 "so crowded in the bus at {loc} this morning, people are hanging from the door",
 "overcrowded bus again, {n} people squeezed in near {loc}",
 "no space to even breathe in {route} bus from {loc}",
 "metro at {loc} is packed like sardines, could not board three trains",
 "huge rush at {loc} bus stop, bus is already full and not stopping",
 "bus is so full that women and kids cannot get in at {loc}",
 "stampede like situation at {loc} station during peak hours",
 "not enough buses on {route}, every bus is overflowing with passengers",
 "standing for the whole journey, bus {route} is always packed at {loc}",
 "platform at {loc} is dangerously crowded, queue goes outside the station",
 "too many passengers, too few buses on {route}",
 "footboard travel everywhere on {route}, so crowded",
 "queue at {loc} metro is huge, whole station is jammed with people",
 "no ladies seats available, bus {route} overloaded at {loc}",
 "{loc} bus stop is chaos, hundreds waiting and only one bus came",
 "bheed bahut jyada hai {route} bus mein {loc} ke paas",
 "tumba jana in bus {route} at {loc}, no place to stand",
 "crowd control needed at {loc}, the {line} trains are packed beyond capacity",
 "morning rush at {loc} is unmanageable, coaches completely full",
 "two trains left full, third one also packed at {loc}",
 "passengers pushing each other to get into bus {route} at {loc}",
],
"delay": [
 "bus {route} is {dur} late at {loc}",
 "waiting at {loc} for {dur}, no bus yet",
 "metro running late again, {dur} delay on the {line}",
 "{route} bus did not come on time, waiting {time}",
 "stuck in traffic at {loc} for {dur}, bus barely moving",
 "bus frequency is terrible, {route} comes once in {dur}",
 "delay of {dur} at {loc}, going to be late for work because of this",
 "scheduled bus never arrives on time at {loc} stop",
 "trains are delayed again at {loc}, waited {dur}",
 "{route} was supposed to come earlier but still not here at {loc}",
 "bus {route} reached {dur} behind schedule, missed my connection",
 "waiting {time} at {loc}, bus is very late",
 "late bus again on {route}, {dur} wasted at the stop",
 "bus {dur} late hai {loc} pe, bahut der ho gayi",
 "bus tumba late aagide {loc} alli, {dur} wait madide",
 "last bus from {loc} came very late, reached home after midnight",
 "no punctuality on {route}, buses bunch up and then {dur} gap",
 "the train interval at {loc} is {dur}, way more than the promised schedule",
 "slow moving bus, took {dur} extra from {loc}",
 "app says 5 min but bus {route} still not arrived after {dur}",
],
"safety": [
 "man was harassing women in bus {route} near {loc}",
 "pickpocketing is common at {loc} bus stand, my phone got stolen",
 "bus stop at {loc} has no lights, very unsafe after dark",
 "conductor allowed drunk men to board {route} bus, women scared",
 "accident near {loc}, bus hit a two wheeler",
 "doors keep open while moving, students hanging, dangerous on {route}",
 "someone touched me inappropriately inside the bus at {loc}",
 "no security at {loc} station at night, feels unsafe",
 "broken footboard on bus {route} and people almost fell",
 "smoke coming from the engine of bus {route} at {loc}, passengers panicking",
 "child nearly fell off the bus at {loc} because door was open",
 "eve teasing near {loc} bus stop everyday, please add patrol",
 "wet slippery floor in the metro at {loc}, an elderly man fell",
 "cctv not working at {loc}, theft of bag happened",
 "fight broke out inside bus {route}, no staff intervened",
 "stalker following women at {loc} stop, we need police presence",
 "bus went over a pothole and a passenger got injured near {loc}",
 "unsafe to travel alone on {route} at night, group of men troubling women",
 "wire hanging loose and sparks at {loc} station, serious danger",
 "bag snatched at {loc}, no police around the bus bay",
],
"driver_behavior": [
 "driver of {route} was rude and shouted at passengers at {loc}",
 "bus did not stop at {loc} even though we waved",
 "conductor refused to give change and abused me",
 "driver was using mobile phone while driving bus {route}",
 "rash driving by {route} driver near {loc}, overspeeding, sudden braking",
 "driver skipped the stop at {loc} and went straight",
 "conductor misbehaved with an elderly woman on {route}",
 "driver asked us to get down in the middle of the road before {loc}",
 "bus {route} driver took a different route and ignored passengers requests",
 "staff at {loc} counter were very rude and unhelpful",
 "driver refused to open the door for passengers at {loc}",
 "driver jumped red signal at {loc} with a full bus",
 "conductor arguing and shouting at students on {route}",
 "driver ne bus nahi roki {loc} pe, conductor bahut badtameezi se baat kar raha tha",
 "driver bus nillisalla at {loc}, conductor tumba rude",
 "driver was talking on phone and braked suddenly, many passengers fell forward",
 "metro staff at {loc} behaved badly and refused to help",
 "bus {route} driver switched off the engine and took a long break while we waited",
 "conductor made fun of a passenger who asked for the stop name",
 "driver kept overtaking dangerously on {route} and ignored our complaints",
],
"vehicle_condition": [
 "bus {route} is very dirty, seats are torn and smelly",
 "AC not working in the bus {route}, sweating like crazy",
 "windows are broken in the bus and rain is coming inside",
 "seats are broken, floor is filthy in the metro coach",
 "bus is leaking water from the roof when it rains",
 "the metro coach AC is off, so hot inside",
 "lights not working inside bus {route}, very dark",
 "bad smell and garbage inside the bus at {loc}",
 "bus is old and rattling with loud noise, bumpy ride",
 "toilet at {loc} station is locked and dirty",
 "no drinking water and dirty platform at {loc}",
 "handles are broken and seats are dusty on {route}",
 "cockroaches inside the bus {route}, so unhygienic",
 "bus tumba kasa, seat kharab {route}",
 "bus mein bahut ganda smell aa rahi hai, seats toot gayi hain",
 "bus {route} windows stuck and no fan working, suffocating",
 "metro train floor is wet and dirty at {loc}, no cleaning staff",
 "bus is in terrible condition, rusted body and loose seats",
 "bin overflowing and foul smell at {loc} bus stand",
 "AC vents dripping water on passengers in {route}",
],
"fare_ticketing": [
 "conductor charged extra fare for {route}, ticket says less",
 "ticket machine not working at {loc}, no tickets issued",
 "UPI payment failed but money got deducted, no ticket",
 "smart card recharge failed at {loc} station, balance not updated",
 "no change given, conductor asking exact amount only",
 "bus pass not accepted on {route}, conductor insisted on ticket",
 "metro card gate not opening at {loc}, card deducted twice",
 "fare increased suddenly without notice on {route}",
 "app shows wrong ticket price for {loc}",
 "QR ticket not scanning at {loc} gate",
 "refund not received for failed ticket booking",
 "charged full fare for my small child on {route}",
 "conductor not giving ticket, taking cash directly",
 "conductor ne chutta nahi diya, paisa kat gaya but ticket nahi mila",
 "chillare illa antha conductor ticket kodalilla in {route}",
 "token vending machine at {loc} ate my money",
 "overcharged for the ticket from {loc}, they said fare is more",
 "the recharge on my metro card is not reflecting for two days",
 "swipe machine in bus {route} is dead, forced to pay cash and extra",
 "double charged on app for one ticket to {loc}",
],
"breakdown": [
 "bus {route} broke down near {loc}, passengers stranded",
 "metro services halted at {loc} due to technical glitch",
 "bus cancelled without notice, no service on {route} today",
 "trip cancelled, depot says no driver available",
 "{line} not operating, stuck inside tunnel without announcement",
 "bus engine failed at {loc}, waiting for another bus",
 "all buses on {route} missing, total service failure",
 "metro train stopped at {loc} for long, power failure",
 "puncture on the bus at {loc}, stuck in the middle of road",
 "ghost bus alert, app shows bus but never arrives on {route}",
 "signal failure at {loc}, whole line suspended",
 "route {route} discontinued without information",
 "bus stopped midway and driver told everyone to get off",
 "bus ne beech raste mein jawab de diya, engine kharab, {loc} ke paas",
 "bus {route} overheated and stopped at {loc}, no replacement sent",
 "trains suspended between {loc} and {loc2}, track fault",
 "door malfunction at {loc}, train stuck at the platform",
 "no buses at all on {route} since morning, depot says crew shortage",
 "bus tyre burst at {loc}, everyone stranded",
 "technical snag on the {line}, services stopped",
],
"accessibility": [
 "lift not working at {loc} station, senior citizens have to climb stairs",
 "no ramp for wheelchair at {loc} bus stop",
 "bus stop at {loc} has no shelter, standing in rain and sun",
 "no announcement of stops in bus {route}, visually impaired passenger could not know",
 "escalator broken at {loc} station for weeks",
 "digital display board at {loc} showing wrong timings",
 "footpath to {loc} bus stop is broken and full of potholes",
 "no seating at {loc} bus stop for elderly people waiting",
 "bus floor too high, elderly and pregnant women struggle to board {route}",
 "tactile path blocked at {loc} metro station",
 "no destination board on the bus {route}, nobody knows where it goes",
 "stairs are very steep and have no handrail at {loc}",
 "stop names missing in kannada at {loc}, confusing for passengers",
 "no wheelchair space in the {line} coach",
 "foot over bridge near {loc} has broken steps and is difficult for old people",
 "the lift at {loc} is out of order again, how will disabled passengers go up",
 "route map and timetable missing at {loc} bus stop",
 "audio announcements not working in the metro, hard for blind passengers",
],
"other": [
 "thank you for the quick help at {loc}",
 "what time is the first bus from {loc}?",
 "great ride on the metro today, very smooth",
 "how do I apply for a student bus pass?",
 "driver was very helpful today, appreciate it",
 "is {route} running today?",
 "new buses look amazing, good work",
 "which metro line goes to {loc}?",
 "lost my wallet in bus {route}, how do I contact the depot?",
 "can I carry a bicycle in the metro?",
 "good morning bengaluru, enjoying the ride",
 "what is the fare from {loc} to {loc2}?",
 "the {line} is a game changer, saved me an hour",
 "kudos to the staff at {loc} for helping an old man",
 "which bus goes from {loc} to {loc2}?",
 "love how clean the stations are",
 "bus timing from {loc} to {loc2} please",
 "very polite conductor on {route} today, thanks",
 "thanks to the driver of {route} who waited for me, so kind",
 "the conductor was kind and helped me find my stop, thank you",
 "appreciate the staff at {loc} for the help, great service",
 "smooth and comfortable ride on {route} today, well done",
],
}

OPENERS = ["", "", "", "", "", "@BMTC_Bengaluru ", "@OfficialBMRCL ", "Hi team, ", "Complaint: ", "Urgent: ",
           "Seriously, ", "Update: ", "Again: ", "FYI ", "Pls look into this. ", "Dear sir, ", "Hello BMTC, ", "Ugh. ", "Sir, "]
CLOSERS = ["", "", "", "", "", "", " please fix this", " pls act", " #BMTC", " #NammaMetro", " #Bengaluru", " !!",
           " worst service", " @BMTC_Bengaluru", " \U0001F621", " \U0001F64F", " every single day", " no one cares",
           " waiting for action", " third time this week", "!!!", ". Unacceptable.", " #PublicTransport", " thank you"]

SLANG = {"please": "pls", "because": "bcoz", "you": "u", "minutes": "mins", "hours": "hrs", "message": "msg",
         "government": "govt", "tomorrow": "tmrw", "people": "ppl", "passengers": "pax", "something": "smthng"}

KEYB = {"a": "sq", "b": "vn", "c": "xv", "d": "sf", "e": "wr", "f": "dg", "g": "fh", "h": "gj", "i": "uo", "j": "hk",
        "k": "jl", "l": "k", "m": "n", "n": "bm", "o": "ip", "p": "o", "q": "w", "r": "et", "s": "ad", "t": "ry",
        "u": "yi", "v": "cb", "w": "qe", "x": "zc", "y": "tu", "z": "x"}

_LOC_ALIASES = [(p[0], p[4], p[5]) for p in PLACES]


def pick_location(rng: random.Random, name: str | None = None):
    """Return (canonical, surface alias)."""
    if name:
        for n, al, _ in _LOC_ALIASES:
            if n == name:
                return n, rng.choice(al)
    names = [x[0] for x in _LOC_ALIASES]
    weights = [x[2] for x in _LOC_ALIASES]
    n = rng.choices(names, weights)[0]
    al = next(a for nn, a, _ in _LOC_ALIASES if nn == n)
    return n, rng.choice(al)


def _typo(word: str, rng: random.Random) -> str:
    if len(word) < 4 or any(c.isdigit() for c in word):
        return word
    i = rng.randrange(1, len(word) - 1)
    op = rng.choice(["del", "swap", "sub", "dup"])
    if op == "del":
        return word[:i] + word[i + 1:]
    if op == "swap":
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    if op == "dup":
        return word[:i] + word[i] + word[i:]
    c = word[i].lower()
    return word[:i] + rng.choice(KEYB.get(c, c)) + word[i + 1:]


def add_noise(text: str, rng: random.Random, p_typo=0.35) -> str:
    words = text.split(" ")
    out = []
    for w in words:
        bare = re.sub(r"[^\w]", "", w)
        if bare.lower() in SLANG and rng.random() < 0.4:
            w = w.replace(bare, SLANG[bare.lower()])
        elif rng.random() < p_typo * 0.15 and not w.startswith(("@", "#")):
            w = _typo(w, rng)
        elif rng.random() < 0.015 and len(bare) > 3 and bare.isalpha():
            ch = rng.choice(re.findall(r"[aeiou]", bare) or ["o"])
            w = w.replace(ch, ch * 3, 1)
        out.append(w)
    t = " ".join(out)
    r = rng.random()
    if r < 0.45:
        t = t.lower()
    elif r < 0.50:
        t = t.upper()
    return t


def generate(rng: random.Random, category: str | None = None, loc: str | None = None,
             route: str | None = None, noisy: bool = True, template_id: int | None = None) -> dict:
    cat = category or rng.choice(list(T))
    tid = template_id if template_id is not None else rng.randrange(len(T[cat]))
    tpl = T[cat][tid]
    canon, surface = pick_location(rng, loc)
    _, surface2 = pick_location(rng)
    r = route or rng.choice(ROUTES)
    if rng.random() < 0.3:
        r = r.lower()
    core = tpl.format(loc=surface, loc2=surface2, route=r, dur=rng.choice(DURS), time=rng.choice(TIMES),
                      n=rng.choice(COUNTS), line=rng.choice(LINES))
    # sentences about metro should not carry a bus route number
    clean = rng.choice(OPENERS) + core + rng.choice(CLOSERS)
    text = add_noise(clean, rng) if noisy else clean
    return {"text": text.strip(), "clean": clean.strip(), "category": cat, "template_id": tid,
            "location": canon if "{loc}" in tpl else None}


def build_dataset(n_per_class: int = 700, seed: int = 7):
    rng = random.Random(seed)
    rows, seen = [], set()
    for cat in T:
        k, tries = 0, 0
        while k < n_per_class and tries < n_per_class * 20:
            tries += 1
            row = generate(rng, cat)
            if row["text"] in seen:
                continue
            seen.add(row["text"])
            rows.append(row)
            k += 1
    rng.shuffle(rows)
    return rows
