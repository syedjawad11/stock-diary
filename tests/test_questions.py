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
