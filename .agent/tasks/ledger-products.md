# Task A: per-visitor products in the ledger

Files you may change: `app/ledger.py`, `tests/test_ledger.py`. Touch nothing else.
Read first: `AGENTS.md`, `app/models.py` (use `Product`, `NewProduct`, `UNITS` from there), `API.md` (section "Hamza Mart upgrade"), `app/ledger.py`.

## Goal
Visitors can add their own products. The seed catalogue passed to `Ledger(...)` stays immutable and shared; each visitor's custom products live in SQLite and are visible only to that visitor.

## Interface (exact)
- New table `visitor_products(visitor_id TEXT NOT NULL REFERENCES visitors(id) ON DELETE CASCADE, id TEXT NOT NULL, name_en TEXT NOT NULL, name_ur TEXT NOT NULL, aliases TEXT NOT NULL /* JSON list */, unit TEXT NOT NULL, low_threshold INTEGER NOT NULL, created_key TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(visitor_id, id), UNIQUE(visitor_id, created_key))`. Created with CREATE TABLE IF NOT EXISTS in `__init__`.
- New errors: `class DuplicateProduct(LedgerError): code = "duplicate_product"`, `class TooManyProducts(LedgerError): code = "too_many_products"`. Module constant `MAX_CUSTOM_PRODUCTS = 30`.
- `def catalogue_for(self, visitor_id: str) -> List[Product]`: seed products in seed order, then the visitor's custom products ordered by created_at, rowid. Custom `Product.opening_qty = 0`.
- `def add_product(self, visitor_id: str, new: NewProduct, key: str) -> Product`:
  - under the lock, in one transaction (`_begin`), ensure the visitor exists (`_ensure_locked`).
  - If a row with (visitor_id, created_key=key) exists, return that product (idempotent), no error.
  - Normalise: name_en stripped, inner whitespace collapsed; name_ur stripped, empty -> name_en; unit must be in `UNITS` else raise `ValueError`; aliases: lowercase, strip, collapse spaces, drop empties and those > 40 chars, dedupe preserving order, then add `name_en.lower()` and `name_ur` (if different) if not present.
  - Duplicate: raise `DuplicateProduct` if name_en (case-insensitive) equals any seed or this visitor's custom product name_en.
  - Cap: raise `TooManyProducts` if the visitor already has `MAX_CUSTOM_PRODUCTS`.
  - id = `"custom-" + slug(name_en)` where slug = lowercase ascii letters/digits joined by "-", max 30 chars, fallback "item" if empty; if taken for this visitor append `-2`, `-3`, ...
  - Stock starts at 0: insert NO movement.
- Make product checks visitor-aware: replace `_check_product(product_id)` with `_check_product(visitor_id, product_id)` that accepts seed ids or this visitor's custom ids (query the table; must work inside the locked transaction without re-taking the lock). Use it in `balance`, `preview`, `post`. `post` must check inside its transaction. A visitor posting another visitor's custom id gets `UnknownProduct`.
- `stock(visitor_id)` returns one `StockRow` per product in `catalogue_for(visitor_id)` (so new products appear at qty 0). Avoid deadlock: `catalogue_for` takes the lock itself, so build an internal `_catalogue_locked(visitor_id)` used by both.
- `reset(visitor_id)` also deletes that visitor's `visitor_products`. `purge_inactive` removes them via the FK cascade (foreign_keys pragma is already on; verify with a test).
- Keep every existing public method signature working (existing tests must stay green unchanged).

## Tests to add in `tests/test_ledger.py`
1. add_product returns a Product with id starting `custom-`, unit kept, qty 0 in `stock`, normalised aliases include the lowercased name.
2. Same key twice -> same product, only one row in catalogue_for.
3. Duplicate name (different case, also vs a seed product) -> DuplicateProduct.
4. Cap: 30 ok, 31st -> TooManyProducts (use a small loop).
5. Isolation: A's product absent from `catalogue_for("b")` and `stock("b")`; `post("b", [line(a_id, 1, IN)], ...)` -> UnknownProduct.
6. A can post IN 10, OUT 3, undo the OUT -> balance 10; OUT 99 -> InsufficientStock and balance unchanged.
7. reset clears custom products; purge_inactive clears them too.
8. Bad unit -> ValueError. Two products whose names slug the same get distinct ids.

## Done when
`.venv/bin/python -m pytest -q tests/test_ledger.py` passes (all old + new). Python 3.9 compatible (no `X | Y` types, no match). Report: files changed, how verified, assumptions.
