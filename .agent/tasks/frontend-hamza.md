# Task C: Hamza Mart warehouse frontend

Files you may change: `app/static/index.html`, `app/static/style.css`, `app/static/app.js`, `app/static/i18n.js`. Touch nothing else (backend is being changed by others in parallel; code against the contract only).
Read first: `AGENTS.md`, `API.md` (whole file, especially "Hamza Mart upgrade"), `app/models.py` (`NewProduct`, `UNITS`), then all four static files.

Keep: plain JS (ES5 style like the existing code, no build step, no frameworks, no new external scripts), EN/Urdu toggle with RTL, dark mode tokens, every existing feature (AI entry -> proposals -> confirm, toast undo, recent entries undo, ask box, reset, quota line). Every new visible string goes in BOTH `en` and `ur` in i18n.js (natural Urdu, not transliteration). Numbers/ids wrapped in `<bdi>` like now.

## 1. Hamza Mart identity
- Header: square "HM" monogram badge (CSS only), title "Hamza Mart" with sub-title "Warehouse stock account" / Urdu "گودام سٹاک کھاتہ". Small pill "Fictional demo shop · synthetic data" / Urdu equivalent. Secondary line "Stock Diary · powered by Gemma (open model)". Reset button stays in the header.
- `<title>`: "Hamza Mart · Stock Diary". Tighten the palette into a professional look: keep green primary, add a deep navy/ink header bar with the monogram, subtle shadows, consistent 8px spacing scale, tabular numerals for quantities (`font-variant-numeric: tabular-nums`).

## 2. Layout
- Remove the 480px cap. Mobile (<900px): single column as now. Desktop (>=900px): max-width ~1200px; overview cards row on top full width; then two columns: LEFT (≈60%) inventory panel + recent entries; RIGHT (≈40%) action panel with tabs.
- Action panel tabs (buttons with aria-selected, role="tablist"): "AI entry" (existing textarea + proposals), "Add / remove stock" (manual form), "New product" (form), "Ask" (existing ask box). On mobile the same tabs sit above inventory. Proposals stay inside the AI entry tab.

## 3. Overview cards
Three cards from `state.stock`: Products (count), Low stock (count of is_low && qty > 0), Out of stock (count of qty == 0). NEVER sum quantities across units. Clicking Low / Out sets the inventory filter; clicking Products sets All.

## 4. Inventory panel
- Search input (matches name_en, name_ur, aliases, case-insensitive) + filter segmented control All / Low / Out of stock.
- Desktop: table with columns Product (name in current language, small muted other-language name), Unit, In stock, Low at (threshold), Status badge (OK / Low / Out), and a small "Adjust" button that opens the manual tab with that product preselected. Mobile: card rows with the same info.
- Custom products (id starts with "custom-") get a small "New" tag.
- Empty-filter state message.

## 5. Manual Add / Remove stock (tab)
- Fields: product `<select>` (all products from state, current language, unit shown), direction segmented control Add (in) / Remove (out), quantity `<input type="number" min="1" step="1" inputmode="numeric">`, reason (optional, maxlength 120).
- Validate quantity with `/^\d+$/` on the raw string and > 0 and <= 100000. Decimals/blank -> inline error, do NOT parseInt-truncate.
- Live preview line: "Now 7 → after 12 cartons". If remove would go below 0, show error and disable Save.
- Save: POST /api/confirm `{confirm_key, lines:[{product_id, qty, direction}], note}`; note = reason or "manual add"/"manual remove". Generate confirm_key once per intended save (random hex, 24 chars) and reuse it if the user retries after a network error; new key after success or after any field change. On success refresh state from the response, show the existing toast with Undo (set `state.lastSaved` from `data.saved`), clear qty/reason. On 409 insufficient_stock show the server message.

## 6. New product (tab)
- Fields: English name (required, 2–60), Urdu name (optional), other names/aliases (comma separated, up to 8), unit `<select>` from carton, bag, tin, packet, box, piece (show Urdu unit words in Urdu mode — reuse/extend the unit-word map in i18n.js; piece = عدد), low-stock alert at (int >= 0, same digit validation).
- Submit: POST /api/products `{key, product:{name_en, name_ur, aliases, unit, low_threshold}}` (key generated per intended create, reused on retry). On success: refresh state from response, toast "Added <name>. Now add its opening stock.", switch to the Add/remove tab with `created.id` preselected and direction = Add, focus qty. Errors: duplicate_product / too_many_products / bad_request -> show `message_en`/`message_ur` from the response.
- Bridge from AI: in proposals, when a line has `problem === "unknown_product"`, add a button "Create “<product_text>” as new product" that switches to the New product tab with English name prefilled with product_text and its unit select set to the proposal's unit if it is one of the units. (The proposal stays; after creating, the user can re-check the entry.)

## 7. Proposals: unit_mismatch
`problemText` already has a string. Additionally show "This product is counted in <unit>" and a button "Use <unit>" that clears `problem` for that line client side (only the unit_mismatch problem) so confirm is allowed.

## 8. Ask tab
Add a chip "Reorder list" / "کیا منگوانا ہے" that asks "kal kya mangwana hai?". If the /api/ask response has `items` (restock), render them below the answer as a small table: product, have, low at, order at least (+unit). Keep answer text in the current language.

## 9. Rate limit text
If an error has `error === "rate_limited"`: `scope === "day"` -> "Daily limit reached for this demo. Manual add/remove still works." ; otherwise -> "Too many checks in a minute. Wait a minute and try again." (+ Urdu). Manual forms never count against the quota — say so in the quota line tooltip/hint: "AI checks used today: 3 of 30".

## 10. Recent entries
Open by default on desktop (`open` attribute set via JS when width >= 900). Show direction as a coloured IN/OUT badge, product name, qty+unit, note, time, and "Undone" status for reversed rows (existing undo button stays).

## Done when
- `node --check app/static/app.js` and `node --check app/static/i18n.js` pass.
- Every key used via tr() exists in both en and ur (write a quick node one-liner to verify and report its output).
- You cannot run the server with the new backend; just keep to the contract. Report: files changed, what each section does, how verified, anything not done.
