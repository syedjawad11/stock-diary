"""Stock questions. Gemma only picks the intent; code computes and fills a fixed template."""
from datetime import date
from typing import Dict, List

from .model_adapter import generate_json
from .models import Intent, Movement, Product, Question, StockRow

SYSTEM = """Classify a stock question from a food wholesaler (English, Roman Urdu or Urdu).
Return JSON {"intent": ..., "product_id": ...}.
intent is one of:
- low_stock: what is running low / kya kam hai / کیا کم ہے
- balance: how much of ONE product is left (set product_id from the catalogue)
- today: what came in or went out today / aaj kya aaya, kya gaya
- unknown: anything else
product_id is null unless intent is balance.

Catalogue (id | names):
{catalogue}"""

UNIT_UR = {"carton": "کارٹن", "bag": "بوری", "tin": "ٹین", "packet": "پیکٹ", "box": "ڈبہ"}


def classify(text: str, catalogue: List[Product]) -> Question:
    cat = "\n".join(f"{p.id} | {p.name_en}; {p.name_ur}; {', '.join(p.aliases)}" for p in catalogue)
    q = generate_json(SYSTEM.replace("{catalogue}", cat), text, Question)
    if q.intent == Intent.BALANCE and q.product_id not in {p.id for p in catalogue}:
        return Question(intent=Intent.UNKNOWN)
    return q


def _qty_en(qty: int, unit: str) -> str:
    return f"{qty} {unit}" + ("" if qty == 1 else ("es" if unit == "box" else "s"))


def _qty_ur(qty: int, unit: str) -> str:
    return f"{qty} {UNIT_UR.get(unit, unit)}"


def answer(q: Question, stock: List[StockRow], today_moves: List[Movement]) -> Dict[str, str]:
    by_id = {row.product.id: row for row in stock}
    if q.intent == Intent.LOW_STOCK:
        low = [row for row in stock if row.is_low]
        if not low:
            return {"answer_en": "Nothing is low right now.", "answer_ur": "ابھی کوئی چیز کم نہیں ہے۔"}
        en = "; ".join(f"{r.product.name_en}: {_qty_en(r.qty, r.product.unit)}" for r in low)
        ur = "؛ ".join(f"{r.product.name_ur}: {_qty_ur(r.qty, r.product.unit)}" for r in low)
        return {"answer_en": f"Running low: {en}.", "answer_ur": f"کم سٹاک: {ur}۔"}
    if q.intent == Intent.BALANCE and q.product_id in by_id:
        r = by_id[q.product_id]
        return {"answer_en": f"{r.product.name_en}: {_qty_en(r.qty, r.product.unit)} in stock.",
                "answer_ur": f"{r.product.name_ur}: {_qty_ur(r.qty, r.product.unit)} موجود ہیں۔"}
    if q.intent == Intent.TODAY:
        if not today_moves:
            return {"answer_en": "No entries yet today.", "answer_ur": "آج ابھی کوئی اندراج نہیں ہوا۔"}
        totals: Dict[tuple, int] = {}
        for m in today_moves:
            key = (m.product_id, m.direction.value)
            totals[key] = totals.get(key, 0) + m.qty
        en_parts, ur_parts = [], []
        for (pid, direction), qty in totals.items():
            p = by_id[pid].product
            en_parts.append(f"{'in' if direction == 'in' else 'out'} {_qty_en(qty, p.unit)} {p.name_en}")
            ur_parts.append(f"{p.name_ur} {_qty_ur(qty, p.unit)} {'آئے' if direction == 'in' else 'نکلے'}")
        return {"answer_en": f"Today ({date.today():%d %b}): " + "; ".join(en_parts) + ".",
                "answer_ur": "آج: " + "، ".join(ur_parts) + "۔"}
    return {"answer_en": "I can answer: what is low, how much of one product is left, or what moved today.",
            "answer_ur": "میں یہ بتا سکتا ہوں: کیا کم ہے، کسی چیز کا کتنا سٹاک ہے، یا آج کیا آیا گیا۔"}
