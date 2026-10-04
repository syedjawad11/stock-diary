# Task B: restock intent

Files you may change: `app/questions.py`, `tests/test_questions.py`. Touch nothing else.
Read first: `AGENTS.md`, `app/models.py` (`Intent.RESTOCK` already exists; `UNITS` includes "piece"), `API.md` ("/api/ask" in the Hamza Mart section), `app/questions.py`.

## Goal
Gemma can classify a restock question; code builds the answer. The model never computes numbers.

## Changes
1. `SYSTEM` prompt: add intent `restock`: what to order / reorder / buy next / kal kya mangwana hai / kya mangwana hai / order list / کیا منگوانا ہے. Keep low_stock for "what is low". product_id null for restock.
2. `UNIT_UR`: add `"piece": "عدد"`. `_qty_en`: plural of piece is pieces (existing rule already works; check).
3. `answer()` gains a branch for `Intent.RESTOCK`:
   - low rows = `[r for r in stock if r.is_low]` in stock order.
   - none -> `{"answer_en": "Nothing needs reordering right now.", "answer_ur": "ابھی کچھ منگوانے کی ضرورت نہیں۔"}`
   - otherwise for each row: `need = r.product.low_threshold + 1 - r.qty` (always >= 1 because is_low means qty <= threshold; guard with max(1, need)).
     EN: `"Restock list (minimum to clear the low alert): " + "; ".join(f"{name_en}: order at least {_qty_en(need, unit)} (have {qty})") + "."`
     UR: `"منگوانے کی فہرست (کم از کم): " + "؛ ".join(f"{name_ur}: کم از کم {_qty_ur(need, unit)} (موجود {qty})") + "۔"`
   - Also add `"items": [{"product_id": ..., "qty": r.qty, "low_threshold": ..., "min_order": need}]` to the returned dict ONLY for restock, so the UI can render a table. Return type becomes `Dict[str, object]`; other intents unchanged.
4. Unknown-intent help text: mention reorder too: EN "I can answer: what is low, what to reorder, how much of one product is left, or what moved today." UR "میں یہ بتا سکتا ہوں: کیا کم ہے، کیا منگوانا ہے، کسی چیز کا کتنا سٹاک ہے، یا آج کیا آیا گیا۔"

## Tests (tests/test_questions.py, keep the existing test)
- restock with two low rows (qty 3 thr 7 -> 5; qty 0 thr 0 -> 1) and one not-low row: exact EN string, items list exact, not-low row absent.
- restock with nothing low -> the "Nothing needs reordering" message, no items key.
- piece unit renders "1 piece" / "2 pieces" and Urdu "عدد".
- classify(): monkeypatch `questions.generate_json` to return Question(intent=Intent.RESTOCK) and check it passes through.

Done when `.venv/bin/python -m pytest -q tests/test_questions.py` passes. Python 3.9. Report files changed, verification, assumptions.
