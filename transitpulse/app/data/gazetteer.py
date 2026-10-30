"""Bengaluru gazetteer: bus hubs, metro stations and neighbourhoods.

Coordinates are approximate (good enough for a city-level map).
Each entry: (canonical name, type, lat, lng, [aliases], popularity weight)
"""

PLACES = [
    ("Majestic", "hub", 12.9774, 77.5726, ["majestic", "kempegowda bus station", "kbs", "kempegowda bus stand", "kg bus stand"], 10),
    ("Silk Board", "junction", 12.9177, 77.6233, ["silk board", "silkboard", "central silk board"], 10),
    ("Marathahalli", "area", 12.9569, 77.7011, ["marathahalli", "marathalli", "marthahalli"], 8),
    ("KR Puram", "hub", 13.0050, 77.6957, ["kr puram", "krpuram", "k r puram", "krishnarajapuram"], 8),
    ("Hebbal", "junction", 13.0358, 77.5970, ["hebbal", "hebbala"], 8),
    ("Electronic City", "area", 12.8440, 77.6568, ["electronic city", "electronics city", "e city", "ecity"], 8),
    ("Whitefield", "area", 12.9698, 77.7500, ["whitefield", "white field"], 7),
    ("Banashankari", "hub", 12.9255, 77.5468, ["banashankari", "banashankri", "banashankari tcm"], 6),
    ("Jayanagar", "area", 12.9308, 77.5838, ["jayanagar", "jayanagara", "jaya nagar"], 6),
    ("JP Nagar", "area", 12.9063, 77.5857, ["jp nagar", "j p nagar", "jayaprakash nagar"], 5),
    ("BTM Layout", "area", 12.9166, 77.6101, ["btm layout", "btm"], 5),
    ("HSR Layout", "area", 12.9116, 77.6389, ["hsr layout", "hsr"], 5),
    ("Koramangala", "area", 12.9352, 77.6245, ["koramangala", "koramangla", "koramangal"], 6),
    ("Indiranagar", "area", 12.9784, 77.6408, ["indiranagar", "indira nagar", "indranagar"], 6),
    ("MG Road", "metro", 12.9756, 77.6066, ["mg road", "m g road", "mahatma gandhi road", "mg road metro"], 7),
    ("Shivajinagar", "hub", 12.9857, 77.6057, ["shivajinagar", "shivaji nagar", "shivajinagara"], 6),
    ("Yeshwanthpur", "hub", 13.0285, 77.5409, ["yeshwanthpur", "yeshwantpur", "yesvantpur", "yeshwanthapura"], 6),
    ("Rajajinagar", "area", 12.9916, 77.5520, ["rajajinagar", "rajaji nagar"], 4),
    ("Malleshwaram", "area", 13.0035, 77.5643, ["malleshwaram", "malleswaram"], 4),
    ("Peenya", "area", 13.0285, 77.5197, ["peenya"], 4),
    ("Nagasandra", "metro", 13.0473, 77.5000, ["nagasandra"], 3),
    ("Kengeri", "area", 12.9179, 77.4837, ["kengeri"], 4),
    ("Yelahanka", "area", 13.1007, 77.5963, ["yelahanka"], 4),
    ("Bellandur", "area", 12.9304, 77.6784, ["bellandur"], 5),
    ("Sarjapur Road", "road", 12.9100, 77.6850, ["sarjapur road", "sarjapur"], 4),
    ("Bannerghatta Road", "road", 12.8960, 77.5990, ["bannerghatta road", "bannerghatta", "bannergatta road"], 4),
    ("Hosur Road", "road", 12.9000, 77.6350, ["hosur road", "hosur rd"], 5),
    ("Domlur", "area", 12.9610, 77.6387, ["domlur"], 3),
    ("Ulsoor", "area", 12.9816, 77.6280, ["ulsoor", "halasuru"], 3),
    ("KR Market", "hub", 12.9628, 77.5750, ["kr market", "city market", "k r market"], 5),
    ("Basavanagudi", "area", 12.9422, 77.5750, ["basavanagudi"], 3),
    ("Vijayanagar", "metro", 12.9709, 77.5340, ["vijayanagar", "vijaya nagar"], 3),
    ("Nayandahalli", "junction", 12.9422, 77.5232, ["nayandahalli", "nayandahalli junction"], 3),
    ("Hoodi", "area", 12.9915, 77.7157, ["hoodi"], 3),
    ("Kadugodi", "area", 12.9965, 77.7612, ["kadugodi", "kadugodi tree park"], 3),
    ("Hennur", "area", 13.0360, 77.6410, ["hennur", "hennur cross"], 3),
    ("Nagawara", "area", 13.0450, 77.6200, ["nagawara"], 3),
    ("Banaswadi", "area", 13.0120, 77.6510, ["banaswadi"], 3),
    ("Mahadevapura", "area", 12.9910, 77.6920, ["mahadevapura"], 3),
    ("Tin Factory", "junction", 12.9966, 77.6717, ["tin factory"], 3),
    ("ITPL", "area", 12.9850, 77.7365, ["itpl", "tech park whitefield"], 3),
    ("Baiyappanahalli", "metro", 12.9905, 77.6520, ["baiyappanahalli", "byappanahalli"], 4),
    ("Trinity", "metro", 12.9733, 77.6170, ["trinity", "trinity circle", "trinity metro"], 3),
    ("Cubbon Park", "metro", 12.9763, 77.5929, ["cubbon park"], 2),
    ("Lalbagh", "area", 12.9507, 77.5848, ["lalbagh"], 2),
    ("Bommanahalli", "area", 12.9081, 77.6247, ["bommanahalli"], 3),
    ("Bommasandra", "area", 12.8128, 77.6870, ["bommasandra"], 2),
    ("Kempegowda Airport", "hub", 13.1986, 77.7066, ["kempegowda airport", "airport", "kia", "bial", "devanahalli"], 4),
    ("Kadubeesanahalli", "area", 12.9366, 77.6957, ["kadubeesanahalli", "kadubisanahalli"], 2),
    ("Ramamurthy Nagar", "area", 13.0120, 77.6700, ["ramamurthy nagar", "rm nagar"], 2),
]

METRO_LINES = {
    "purple line": "Purple Line",
    "green line": "Green Line",
    "yellow line": "Yellow Line",
}

# plausible BMTC-style route numbers used for recognition and the simulator
ROUTES = [
    "335E", "500D", "500K", "201", "210", "356", "365", "378", "411", "290E",
    "G4", "G2", "KIA-9", "V-500D", "V-335E", "401", "412", "365C", "250", "314",
]
