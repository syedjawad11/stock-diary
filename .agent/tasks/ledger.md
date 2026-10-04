NOTE: PLAN.md and AGENTS.md still describe an old idea (Invoice Match) and are being rewritten. Ignore their product description. The product is now "Stock Diary": a bilingual stock book for a small wholesaler. Read app/models.py and API.md.

GOAL: Write the stock ledger, plain Python + SQLite (stdlib sqlite3), with pytest tests. No model calls. Quantities are ints.

FILES YOU MAY CREATE: app/ledger.py, tests/test_ledger.py, tests/__init__.py (empty), tests/conftest.py (optional).
DO NOT TOUCH: app/models.py, API.md, anything else. Do not commit. Do not install packages (fastapi, pydantic 2, pytest are installed in .venv; run tests with `.venv/bin/pytest -q`).

INTERFACE (app/ledger.py):
```python
class LedgerError(Exception): code: str   # subclasses below set code
class UnknownProduct(LedgerError): code = "unknown_product"
class InsufficientStock(LedgerError): code = "insufficient_stock"   # carries product_id, available, requested
class AlreadyReversed(LedgerError): code = "already_reversed"
class NotFound(LedgerError): code = "not_found"

class Ledger:
    def __init__(self, db_path: str, catalogue: List[Product]) -> None  # creates tables; db_path may be ":memory:" (keep one connection then); check_same_thread=False and a threading.Lock around writes
    def ensure_visitor(self, visitor_id: str) -> bool   # if unknown: record visitor + seed one IN movement per product with qty=opening_qty (note "opening stock"; skip qty 0). Returns True if newly created. Updates last_seen.
    def reset(self, visitor_id: str) -> None             # delete visitor's movements, reseed opening stock
    def balance(self, visitor_id: str, product_id: str) -> int
    def stock(self, visitor_id: str) -> List[StockRow]    # catalogue order; is_low = qty <= low_threshold
    def preview(self, visitor_id: str, lines: List[PostLine]) -> List[Tuple[int, int]]  # (before, after) per line, applying lines cumulatively in order (two lines of the same product stack). No writes, no errors for negatives (caller decides).
    def post(self, visitor_id: str, lines: List[PostLine], note: str, key: str) -> List[Movement]
        # Atomic: all or nothing in one transaction. Raises UnknownProduct for ids not in catalogue,
        # InsufficientStock if any running balance would go below 0 (cumulative across lines).
        # Idempotent: same (visitor_id, key) again returns the originally saved movements, no new rows.
    def undo(self, visitor_id: str, movement_id: int) -> Movement
        # Inserts the opposite-direction movement with reverses=movement_id, note "reversal of #<id>".
        # NotFound if the movement isn't this visitor's; AlreadyReversed if reversed already or it is itself a reversal.
        # InsufficientStock if undoing an IN would make the balance negative.
    def recent(self, visitor_id: str, limit: int = 10) -> List[Movement]   # newest first; exclude opening-stock rows; fill reversed_by
    def today(self, visitor_id: str, day: datetime.date) -> List[Movement]  # movements created on that UTC date, excl. opening stock
    def purge_inactive(self, older_than_hours: int = 24, now: Optional[datetime] = None) -> int  # delete visitors (and their rows) whose last_seen is older; return count
```
Balances are always SUM computed in SQL/Python from movements (IN minus OUT), never a stored mutable counter. created_at = UTC ISO 8601. Allow injecting a clock: Ledger(..., now: Callable[[], datetime] = utcnow) as an optional 3rd kwarg for tests. Python 3.9-compatible syntax (use typing.List/Optional, no `|` unions, no match).

TESTS (tests/test_ledger.py), use a small fixture catalogue of 3 products defined in the test (do not depend on any data file): seeding, isolation between two visitors, cumulative preview, post IN/OUT, insufficient stock incl. cumulative across two lines and atomicity (nothing saved), unknown product, idempotent key, undo + already reversed + undo of reversal rejected + undo making negative rejected + other visitor's movement NotFound, reset, is_low boundary (qty == threshold is low), recent excludes opening stock and shows reversed_by, today filter, purge_inactive.

DONE = `.venv/bin/pytest -q tests/test_ledger.py` green. Report files, test count, assumptions.
