"""Direct tests for deterministic stock question answers."""

from app import questions
from app.models import Intent, Product, Question, StockRow


def test_low_stock_answer_with_bracketed_product_name():
    stock = [
        StockRow(
            product=Product(
                id="khajoor-dates",
                name_en="Khajoor (dates)",
                name_ur="کھجور (dates)",
                aliases=[],
                unit="box",
                low_threshold=25,
                opening_qty=25,
            ),
            qty=25,
            is_low=True,
        ),
        StockRow(
            product=Product(
                id="cooking-oil",
                name_en="Cooking oil 5L",
                name_ur="کھانے کا تیل",
                aliases=[],
                unit="tin",
                low_threshold=4,
                opening_qty=4,
            ),
            qty=4,
            is_low=True,
        ),
    ]

    result = questions.answer(Question(intent=Intent.LOW_STOCK), stock, [])

    assert result["answer_en"] == "Running low: Khajoor (dates): 25 boxes; Cooking oil 5L: 4 tins."
    assert result["answer_ur"] == "کم سٹاک: کھجور (dates): 25 ڈبہ؛ کھانے کا تیل: 4 ٹین۔"
    for answer in result.values():
        assert "((" not in answer
        assert ") (" not in answer


def _stock_row(product_id, name_en, name_ur, unit, qty, threshold, is_low):
    return StockRow(
        product=Product(
            id=product_id,
            name_en=name_en,
            name_ur=name_ur,
            aliases=[],
            unit=unit,
            low_threshold=threshold,
            opening_qty=qty,
        ),
        qty=qty,
        is_low=is_low,
    )


def test_restock_lists_minimum_orders_in_stock_order():
    stock = [
        _stock_row("rice", "Rice", "چاول", "bag", 3, 7, True),
        _stock_row("oil", "Oil", "تیل", "tin", 10, 4, False),
        _stock_row("spice", "Spice", "مصالحہ", "packet", 0, 0, True),
    ]

    result = questions.answer(Question(intent=Intent.RESTOCK), stock, [])

    assert result["answer_en"] == (
        "Restock list (minimum to clear the low alert): "
        "Rice: order at least 5 bags (have 3); "
        "Spice: order at least 1 packet (have 0)."
    )
    assert result["answer_ur"] == (
        "منگوانے کی فہرست (کم از کم): "
        "چاول: کم از کم 5 بوری (موجود 3)؛ "
        "مصالحہ: کم از کم 1 پیکٹ (موجود 0)۔"
    )
    assert result["items"] == [
        {"product_id": "rice", "qty": 3, "low_threshold": 7, "min_order": 5},
        {"product_id": "spice", "qty": 0, "low_threshold": 0, "min_order": 1},
    ]


def test_restock_with_nothing_low_has_no_items():
    stock = [_stock_row("oil", "Oil", "تیل", "tin", 10, 4, False)]

    result = questions.answer(Question(intent=Intent.RESTOCK), stock, [])

    assert result == {
        "answer_en": "Nothing needs reordering right now.",
        "answer_ur": "ابھی کچھ منگوانے کی ضرورت نہیں۔",
    }


def test_piece_unit_singular_plural_and_urdu():
    assert questions._qty_en(1, "piece") == "1 piece"
    assert questions._qty_en(2, "piece") == "2 pieces"
    assert questions._qty_ur(1, "piece") == "1 عدد"


def test_classify_passes_through_restock(monkeypatch):
    def fake_generate_json(system, text, shape):
        assert "restock" in system
        assert text == "kal kya mangwana hai?"
        assert shape is Question
        return Question(intent=Intent.RESTOCK)

    monkeypatch.setattr(questions, "generate_json", fake_generate_json)

    assert questions.classify("kal kya mangwana hai?", []) == Question(intent=Intent.RESTOCK)
