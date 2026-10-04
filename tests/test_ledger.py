from datetime import date, datetime, timedelta, timezone

import pytest

from app.ledger import (
    AlreadyReversed,
    DuplicateProduct,
    InsufficientStock,
    Ledger,
    NotFound,
    TooManyProducts,
    UnknownProduct,
)
from app.models import Direction, NewProduct, PostLine, Product


@pytest.fixture
def catalogue():
    return [
        Product(
            id="rice", name_en="Rice", name_ur="چاول", aliases=["rice"],
            unit="bag", low_threshold=2, opening_qty=5,
        ),
        Product(
            id="chilli", name_en="Chilli", name_ur="مرچ", aliases=["chilli"],
            unit="carton", low_threshold=3, opening_qty=3,
        ),
        Product(
            id="oil", name_en="Oil", name_ur="تیل", aliases=["oil"],
            unit="can", low_threshold=0, opening_qty=0,
        ),
    ]


@pytest.fixture
def clock():
    class Clock:
        value = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)

        def __call__(self):
            return self.value

    return Clock()


@pytest.fixture
def ledger(tmp_path, catalogue, clock):
    return Ledger(str(tmp_path / "stock.sqlite"), catalogue, now=clock)


def line(product_id, qty, direction):
    return PostLine(product_id=product_id, qty=qty, direction=direction)


def test_seeding_and_visitor_isolation(ledger):
    assert ledger.ensure_visitor("a") is True
    assert ledger.ensure_visitor("a") is False
    assert ledger.ensure_visitor("b") is True
    assert ledger.balance("a", "rice") == 5
    assert ledger.balance("a", "oil") == 0
    assert ledger.recent("a") == []
    ledger.post("a", [line("rice", 2, Direction.OUT)], "sale", "one")
    assert ledger.balance("a", "rice") == 3
    assert ledger.balance("b", "rice") == 5


def test_preview_is_cumulative_and_read_only_even_below_zero(ledger):
    ledger.ensure_visitor("a")
    lines = [
        line("rice", 4, Direction.OUT),
        line("rice", 3, Direction.OUT),
        line("oil", 2, Direction.IN),
        line("rice", 1, Direction.IN),
    ]
    assert ledger.preview("a", lines) == [(5, 1), (1, -2), (0, 2), (-2, -1)]
    assert ledger.balance("a", "rice") == 5
    assert ledger.balance("a", "oil") == 0


def test_post_in_and_out_and_idempotent_key(ledger):
    ledger.ensure_visitor("a")
    lines = [line("oil", 4, Direction.IN), line("rice", 2, Direction.OUT)]
    saved = ledger.post("a", lines, "delivery and sale", "key-1")
    assert [movement.direction for movement in saved] == [Direction.IN, Direction.OUT]
    assert [movement.qty for movement in saved] == [4, 2]
    assert all(movement.note == "delivery and sale" for movement in saved)
    assert all(datetime.fromisoformat(movement.created_at).tzinfo is not None for movement in saved)
    again = ledger.post("a", [line("rice", 5, Direction.OUT)], "different", "key-1")
    assert [movement.id for movement in again] == [movement.id for movement in saved]
    assert ledger.balance("a", "oil") == 4
    assert ledger.balance("a", "rice") == 3
    assert len(ledger.recent("a")) == 2


def test_insufficient_stock_is_atomic_including_cumulative_lines(ledger):
    ledger.ensure_visitor("a")
    with pytest.raises(InsufficientStock) as exc:
        ledger.post("a", [line("rice", 6, Direction.OUT)], "too much", "bad-1")
    assert (exc.value.product_id, exc.value.available, exc.value.requested) == (
        "rice", 5, 6,
    )
    with pytest.raises(InsufficientStock) as exc:
        ledger.post(
            "a", [line("rice", 3, Direction.OUT), line("rice", 3, Direction.OUT)],
            "stacked", "bad-2",
        )
    assert (exc.value.available, exc.value.requested) == (2, 3)
    assert ledger.balance("a", "rice") == 5
    assert ledger.recent("a") == []
    assert len(ledger.post("a", [line("rice", 1, Direction.OUT)], "valid", "bad-2")) == 1


def test_unknown_product_rejects_whole_post(ledger):
    ledger.ensure_visitor("a")
    with pytest.raises(UnknownProduct) as exc:
        ledger.post(
            "a", [line("rice", 1, Direction.OUT), line("missing", 1, Direction.IN)],
            "unknown", "bad",
        )
    assert exc.value.code == "unknown_product"
    assert ledger.balance("a", "rice") == 5
    assert ledger.recent("a") == []
    with pytest.raises(UnknownProduct):
        ledger.preview("a", [line("missing", 1, Direction.IN)])


def test_undo_and_repeated_undo_and_reversal_rejected(ledger):
    ledger.ensure_visitor("a")
    original = ledger.post("a", [line("rice", 2, Direction.OUT)], "sale", "one")[0]
    reversal = ledger.undo("a", original.id)
    assert reversal.reverses == original.id
    assert reversal.direction == Direction.IN
    assert reversal.note == "reversal of #{}".format(original.id)
    assert ledger.balance("a", "rice") == 5
    with pytest.raises(AlreadyReversed):
        ledger.undo("a", original.id)
    with pytest.raises(AlreadyReversed):
        ledger.undo("a", reversal.id)


def test_undo_in_requires_available_stock_and_other_visitor_is_not_found(ledger):
    ledger.ensure_visitor("a")
    ledger.ensure_visitor("b")
    received = ledger.post("a", [line("oil", 2, Direction.IN)], "received", "one")[0]
    ledger.post("a", [line("oil", 2, Direction.OUT)], "sold", "two")
    with pytest.raises(InsufficientStock) as exc:
        ledger.undo("a", received.id)
    assert (exc.value.available, exc.value.requested) == (0, 2)
    assert ledger.balance("a", "oil") == 0
    with pytest.raises(NotFound):
        ledger.undo("b", received.id)


def test_reset_and_stock_low_boundary(ledger):
    ledger.ensure_visitor("a")
    rows = ledger.stock("a")
    assert [row.product.id for row in rows] == ["rice", "chilli", "oil"]
    assert [(row.qty, row.is_low) for row in rows] == [(5, False), (3, True), (0, True)]
    ledger.post("a", [line("rice", 3, Direction.OUT)], "sale", "one")
    assert ledger.stock("a")[0].is_low is True
    ledger.reset("a")
    assert ledger.balance("a", "rice") == 5
    assert ledger.recent("a") == []
    assert len(ledger.post("a", [line("rice", 1, Direction.OUT)], "new", "one")) == 1


def test_recent_excludes_opening_and_includes_reversed_by(ledger):
    ledger.ensure_visitor("a")
    first = ledger.post("a", [line("rice", 1, Direction.OUT)], "sale", "one")[0]
    second = ledger.post("a", [line("chilli", 1, Direction.IN)], "receipt", "two")[0]
    reversal = ledger.undo("a", first.id)
    recent = ledger.recent("a")
    assert [movement.id for movement in recent] == [reversal.id, second.id, first.id]
    assert recent[-1].reversed_by == reversal.id
    assert recent[0].reversed_by is None
    assert [movement.id for movement in ledger.recent("a", limit=1)] == [reversal.id]


def test_today_uses_utc_date_and_excludes_opening(ledger, clock):
    ledger.ensure_visitor("a")
    first = ledger.post("a", [line("rice", 1, Direction.OUT)], "day one", "one")[0]
    clock.value += timedelta(days=1)
    second = ledger.post("a", [line("rice", 1, Direction.OUT)], "day two", "two")[0]
    assert [m.id for m in ledger.today("a", date(2026, 10, 4))] == [first.id]
    assert [m.id for m in ledger.today("a", date(2026, 10, 5))] == [second.id]
    assert ledger.today("a", date(2026, 10, 6)) == []


def test_purge_inactive_deletes_only_older_visitors_and_their_rows(ledger, clock):
    ledger.ensure_visitor("old")
    ledger.post("old", [line("rice", 1, Direction.OUT)], "sale", "one")
    clock.value += timedelta(hours=25)
    ledger.ensure_visitor("fresh")
    assert ledger.purge_inactive(now=clock.value) == 1
    assert ledger.recent("old") == []
    assert ledger.balance("old", "rice") == 0
    assert ledger.balance("fresh", "rice") == 5
    assert ledger.purge_inactive(now=clock.value) == 0
    assert ledger.ensure_visitor("old") is True


def test_memory_database_keeps_one_connection(catalogue):
    ledger = Ledger(":memory:", catalogue)
    assert ledger.ensure_visitor("a") is True
    assert ledger.balance("a", "rice") == 5
    assert ledger.ensure_visitor("a") is False


def new_product(name, **kwargs):
    return NewProduct(name_en=name, unit="box", low_threshold=2, **kwargs)


def test_add_product_normalises_fields_and_starts_at_zero(ledger, catalogue):
    created = ledger.add_product(
        "a", new_product("  Green   Tea  ", name_ur="  سبز چائے  ",
                         aliases=[" GREEN   TEA ", "green tea", " ", "X" * 41]), "create-1"
    )
    assert created.id.startswith("custom-")
    assert created.name_en == "Green Tea"
    assert created.name_ur == "سبز چائے"
    assert created.unit == "box"
    assert created.opening_qty == 0
    assert created.aliases == ["green tea", "سبز چائے"]
    assert [p.id for p in ledger.catalogue_for("a")] == [p.id for p in catalogue] + [created.id]
    assert [p.id for p in ledger.catalogue] == [p.id for p in catalogue]
    assert (ledger.stock("a")[-1].product.id, ledger.stock("a")[-1].qty) == (created.id, 0)


def test_add_product_same_key_is_idempotent(ledger):
    first = ledger.add_product("a", new_product("Tea"), "same")
    again = ledger.add_product("a", new_product("Different"), "same")
    assert again == first
    assert [p.id for p in ledger.catalogue_for("a") if p.id.startswith("custom-")] == [first.id]


def test_duplicate_product_name_vs_custom_and_seed(ledger):
    ledger.add_product("a", new_product("Tea"), "one")
    with pytest.raises(DuplicateProduct):
        ledger.add_product("a", new_product("tEa"), "two")
    with pytest.raises(DuplicateProduct):
        ledger.add_product("a", new_product("RICE"), "three")
    assert len(ledger.catalogue_for("a")) == 4
    assert ledger.add_product("b", new_product("Tea"), "one").name_en == "Tea"


def test_custom_product_cap(ledger):
    for index in range(30):
        ledger.add_product("a", new_product("Item {}".format(index)), str(index))
    assert len(ledger.catalogue_for("a")) == 33
    with pytest.raises(TooManyProducts):
        ledger.add_product("a", new_product("Extra"), "extra")
    assert ledger.add_product("a", new_product("Changed"), "0").name_en == "Item 0"


def test_custom_product_isolation(ledger):
    created = ledger.add_product("a", new_product("Tea"), "one")
    assert created.id not in [p.id for p in ledger.catalogue_for("b")]
    assert created.id not in [row.product.id for row in ledger.stock("b")]
    with pytest.raises(UnknownProduct):
        ledger.balance("b", created.id)
    with pytest.raises(UnknownProduct):
        ledger.preview("b", [line(created.id, 1, Direction.IN)])
    with pytest.raises(UnknownProduct):
        ledger.post("b", [line(created.id, 1, Direction.IN)], "wrong visitor", "one")


def test_custom_product_post_undo_and_insufficient_stock(ledger):
    created = ledger.add_product("a", new_product("Tea"), "create")
    assert ledger.preview("a", [line(created.id, 10, Direction.IN)]) == [(0, 10)]
    ledger.post("a", [line(created.id, 10, Direction.IN)], "received", "in")
    outgoing = ledger.post("a", [line(created.id, 3, Direction.OUT)], "sold", "out")[0]
    assert ledger.balance("a", created.id) == 7
    ledger.undo("a", outgoing.id)
    assert ledger.balance("a", created.id) == 10
    with pytest.raises(InsufficientStock):
        ledger.post("a", [line(created.id, 99, Direction.OUT)], "too much", "bad")
    assert ledger.balance("a", created.id) == 10


def test_reset_and_purge_remove_custom_products(ledger, clock):
    first = ledger.add_product("a", new_product("Tea"), "one")
    ledger.reset("a")
    assert first.id not in [p.id for p in ledger.catalogue_for("a")]
    with pytest.raises(UnknownProduct):
        ledger.balance("a", first.id)

    second = ledger.add_product("old", new_product("Coffee"), "two")
    clock.value += timedelta(hours=25)
    ledger.ensure_visitor("fresh")
    assert ledger.purge_inactive(now=clock.value) == 2
    assert ledger._db.execute(
        "SELECT COUNT(*) FROM visitor_products WHERE visitor_id = ?", ("old",)
    ).fetchone()[0] == 0
    assert second.id not in [p.id for p in ledger.catalogue_for("old")]
    with pytest.raises(UnknownProduct):
        ledger.balance("old", second.id)
    # Reusing the key after cascade deletion must create a new row.
    assert ledger.add_product("old", new_product("Coffee"), "two").id == second.id


def test_invalid_unit_and_slug_collisions(ledger):
    with pytest.raises(ValueError):
        ledger.add_product("a", NewProduct(name_en="Tea", unit="crate", low_threshold=0), "bad")
    first = ledger.add_product("a", new_product("Green Tea"), "one")
    second = ledger.add_product("a", new_product("Green-Tea"), "two")
    assert first.id == "custom-green-tea"
    assert second.id == "custom-green-tea-2"
