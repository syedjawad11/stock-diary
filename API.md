# HTTP API contract (frontend <-> FastAPI)

All JSON. Same origin. A signed cookie `sd_visitor` identifies the visitor's
private demo sandbox; the server sets it on first request. Shapes refer to
`app/models.py`.

Errors: HTTP 4xx/5xx with `{"error": "<code>", "message_en": "...", "message_ur": "..."}`.
Codes: `rate_limited` (429), `parse_failed` (422), `insufficient_stock` (409),
`unknown_product` (422), `already_reversed` (409), `model_unavailable` (503), `bad_request` (400).

## GET /api/state
```json
{
  "stock": [{"product": Product, "qty": 27, "is_low": false}],
  "recent": [Movement],            // newest first, max 10
  "quota": {"used_today": 3, "limit_today": 30}
}
```

## POST /api/parse  `{"text": "20 carton basmati aaye, 5 laal mirch nikle"}`
Nothing is saved. Returns proposals for the user to check.
```json
{
  "proposals": [
    {
      "product_text": "basmati",
      "product_id": "basmati-5kg",          // null if not matched
      "candidates": [Product],              // non-empty only when product_id is null
      "qty": 20,
      "unit": "carton",
      "direction": "in",
      "balance_before": 7,                  // null if product_id null
      "balance_after": 27,                  // null if product_id null
      "problem": null                       // or "unknown_product" | "insufficient_stock" | "unit_mismatch"
    }
  ],
  "confirm_key": "c1f0..."                  // idempotency key to send with /api/confirm
}
```

## POST /api/confirm
`{"confirm_key": "c1f0...", "lines": [PostLine], "note": "<original sentence>"}`
Atomic: all lines saved or none. Re-sending the same key returns the same result.
Response: same shape as GET /api/state plus `"saved": [Movement]`.

## POST /api/undo  `{"movement_id": 12}`
Adds a reversal movement. Response: GET /api/state shape.

## POST /api/ask  `{"text": "kis cheez ka stock kam hai?"}`
```json
{"intent": "low_stock", "answer_en": "Low: Laal mirch (3 cartons).", "answer_ur": "کم سٹاک: لال مرچ (3 کارٹن)"}
```
Answers are fixed templates filled by code. The model only picks the intent.

## POST /api/reset
Restores this visitor's sandbox to the demo opening stock. Does not reset quota.
Response: GET /api/state shape.

## Hamza Mart upgrade (4 Oct, afternoon)

### Per-visitor products
Each visitor's catalogue = the synthetic seed (`data/catalogue.json`) + products
they added. `GET /api/state` `stock` lists ALL of them, including new products
at qty 0. Custom product ids start with `custom-`. Products of one visitor are
invisible to every other visitor, including in parse/ask.

### POST /api/products
`{"key": "<8-64 chars, one per intended create>", "product": NewProduct}`
`NewProduct` = `{"name_en", "name_ur" (optional, ""), "aliases": [str], "unit": one of carton|bag|tin|packet|box|piece, "low_threshold": int >= 0}`.
Server lowercases/trims aliases and adds name_en/name_ur as aliases. Stock starts at 0.
Same key again returns the same product (idempotent).
Response: GET /api/state shape plus `"created": Product`.
Errors: `duplicate_product` (409, a product with that English name already exists),
`too_many_products` (409, cap 30 per visitor), `bad_request` (400, validation).

### Manual add / remove stock
No new endpoint. The UI posts to `POST /api/confirm` with one `PostLine`, a fresh
`confirm_key` per save (reused on retry), and `note` = the reason the user typed,
or "manual add" / "manual remove". Same ledger checks and undo as AI entries.

### /api/parse proposals
`problem` can now be `"unit_mismatch"` when the user's unit is a known unit
different from the product's unit (e.g. "5 bags laal mirch" when mirch is packets).
UI must block confirm until the user fixes it (editing qty/product clears it client side
only if the user confirms the unit is right: show the product's unit and a "Use <unit>" button).

### /api/ask
New intent `restock` ("kal kya mangwana hai?", "what should I reorder?").
Answer lists every low product with current qty, threshold, and
`minimum to clear the low alert = low_threshold + 1 - qty`. Not a forecast.

### Rate limit errors
`rate_limited` responses carry `"scope": "minute" | "day"` so the UI can say
"wait a minute" vs "come back tomorrow".
