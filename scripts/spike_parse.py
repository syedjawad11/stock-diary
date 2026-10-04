"""Accuracy spike: run sample sentences through parse_sentence and compare with expected movements."""
import json, sys, time
sys.path.insert(0, ".")
from app.models import Product
from app.parse import parse_sentence

CAT = [Product(**p) for p in json.load(open("data/catalogue.json"))["products"]]
CASES = [
    ("20 carton basmati aaye", [("basmati-5kg", 20, "in")]),
    ("5 packet laal mirch nikle", [("red-chilli-powder", 5, "out")]),
    ("aaj 20 carton basmati aaye, 5 carton nikle", [("basmati-5kg", 20, "in"), ("basmati-5kg", 5, "out")]),
    ("received 12 tins of cooking oil", [("cooking-oil-5l", 12, "in")]),
    ("sold 3 bags sugar and 4 boxes of dates", [("sugar-50kg", 3, "out"), ("khajoor-dates", 4, "out")]),
    ("10 bori chini aayi", [("sugar-50kg", 10, "in")]),
    ("haldi ke 8 packet bheje", [("turmeric-haldi", 8, "out")]),
    ("15 کارٹن چائے آئے", [("black-tea", 15, "in")]),
    ("چنے کی 6 بوریاں بیچیں", [("chickpeas-chanay", 6, "out")]),
    ("namak 10 packet aaya aur 2 packet gaya", [("pink-salt", 10, "in"), ("pink-salt", 2, "out")]),
    ("sella chawal 5 bag nikle", [("sella-rice-25kg", 5, "out")]),
    ("chawal 10 aaye", [(None, 10, "in")]),  # ambiguous: must not guess
]
ok = 0
for text, want in CASES:
    t = time.time()
    try:
        got = [(l.product_id, l.qty, l.direction.value) for l in parse_sentence(text, CAT)]
    except Exception as e:
        got = [f"ERROR {e}"]
    good = got == want
    ok += good
    print(f"{'PASS' if good else 'FAIL'} {time.time()-t:5.1f}s  {text!r}\n      got {got}\n     want {want}")
print(f"\n{ok}/{len(CASES)} correct")
