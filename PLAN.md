# Plan: Stock Diary

Status: Reviewed by GPT-6.1 Sol twice (brainstorm, then hosting/partners/
frontend). Replaces the earlier "Invoice Match" idea, abandoned before any
code existed.

## Who it is for

Jawad's friend, who runs a small import/export and wholesale business in
Pakistan: rice, spices, packaged food, cartons. He tracks stock in his head
and on paper, in a mix of Urdu, Roman Urdu, and English.

The friend could not be reached this weekend. This design is built from what
Jawad knows of his business, not from his direct input. The post will say so
plainly and will not invent his feedback. Handover is pending.

## What it does (one screen)

1. He types a line in Urdu, Roman Urdu, or English: "20 carton basmati aaye, 5
   laal mirch nikle."
2. Gemma parses it into proposed stock movements against a small product
   catalogue.
3. He reviews the proposal (product match, quantity, direction, balance
   before/after) and confirms or edits before anything is saved.
4. Plain Python posts confirmed movements to the ledger, keeps running
   balances, and flags low stock.
5. He can ask a question like "kis cheez ka stock kam hai?" — Gemma only
   picks one of three intents (`low_stock`, `balance`, `today`); fixed
   bilingual templates filled in by code answer it.

No model call ever writes a number to the ledger. It only proposes; code
computes and confirms.

## Design

| File | Job | Owner |
| --- | --- | --- |
| `app/models.py` | Shared Pydantic shapes: `Product`, `ParsedLine`, `ParseResult`, `Intent`, `Question`, `Movement`, `StockRow`, `PostLine` | Claude — done |
| `API.md` | HTTP contract: `/api/state`, `/parse`, `/confirm`, `/undo`, `/ask`, `/reset` | Claude — done |
| `app/ledger.py` + `tests/test_ledger.py` | Confirm/undo/balance/low-stock arithmetic, plain Python, ints only, idempotent confirm | Codex worker (GPT-6 Sol) — in progress |
| `app/static/*` | Mobile-first HTML/CSS/vanilla JS page, Urdu RTL | Sonnet subagent |
| `data/catalogue.json` + UI strings | Synthetic demo catalogue (rice, spices, packaged food, cartons) and bilingual template text | Drafted by local Gemma, checked by Claude |
| `app/model_adapter.py` | One `generate_structured(...)` call; `MODEL_BACKEND=ollama` (local `gemma4:e4b`) or `cloudflare` (`@cf/google/gemma-4-26b-a4b-it` via Workers AI REST) | Claude |
| `app/parse.py` | Free text -> `ParseResult`, matched against catalogue aliases, validated by Pydantic, one retry on bad JSON | Claude |
| `app/questions.py` | Free text -> `Question` (intent only); code fills the fixed bilingual templates | Claude |
| `app/main.py` | FastAPI app: routes from `API.md`, visitor cookie, rate limits, 24h purge | Claude |
| `app/demo.py` | Per-visitor sandbox seeding/reset from the synthetic catalogue | Claude |
| `PLAN.md`, `AGENTS.md`, `README.md` | This rewrite | Sonnet subagent |
| `.github/workflows/test.yml` | CI running pytest (Copilot category evidence) | Later |

Hosting: FastAPI on Render (web service) serves the live demo. Cloudflare
Workers AI serves Gemma 4 (`@cf/google/gemma-4-26b-a4b-it`) for the hosted
parse/ask calls; local dev uses Ollama `gemma4:e4b` through the same
`app/model_adapter.py`. SQLite. Per-visitor sandbox via a signed cookie
(`sd_visitor`), a reset button, rate limits (5/min, 30/day per visitor, plus a
global daily cap), sandboxes purge after 24h. Demo catalogue is synthetic
only — no real customer, supplier, or stock data.

Stack: Python 3.9+, FastAPI, Pydantic, SQLite, `ollama` Python client /
Cloudflare Workers AI REST, pytest.

## Order of work (Malta time, Sun 4 Oct)

| When | Step | Gate |
| --- | --- | --- |
| 14:30–15:30 | Deploy FastAPI skeleton to Render; claim the Render Hacktoberfest credit; one authenticated hosted Gemma call through `model_adapter.py` | Public URL responds; the hosted Gemma call returns |
| 15:30–16:30 | Ledger (Codex worker) + `parse.py` (Claude) | Ledger tests green; sample sentences parse to the right lines |
| 16:30–17:30 | Static page end to end: type -> proposal -> confirm -> stock list, on a phone | Sentence to confirmed movement to updated stock works on a phone |
| 17:30–18:30 | `questions.py`, rate limits, reset, error states | Three question types answer correctly; quota and reset behave |
| 18:30–19:30 | Reviewer checks the full diff, fix real bugs only; GitHub Actions CI; README; licence | Fresh clone + CI run green |
| 19:30–20:00 | Smoke test both backends (Ollama and Cloudflare); record demo video | Both backends work end to end |
| 20:00 | **Code freeze.** | |
| 20:00–23:00 | Write and publish `post.md` | Published by 23:00 |
| Mon 08:59 | Hard deadline. | Buffer only. |

## Cut list (drop in this order when behind)

1. Optional partner categories (Entire, ElevenLabs)
2. CSV export / history polish
3. Open-ended questions beyond the three fixed intents
4. Cosmetic/animation extras

Never cut: live hosting, AI parsing, the confirm step, visitor isolation,
deterministic balances, tests on the ledger, three hours for the post.

Refused today: photo/OCR input, voice, WhatsApp integration, pack
conversions, forecasting, fine-tuning, GPU provisioning, account systems,
real business data.

## Risks

- **Render credit amount unknown.** Promo claimed, balance pending. Free tier
  sleeps after roughly a minute idle and has ephemeral disk — acceptable here
  because visitor sandboxes reseed from the catalogue anyway.
- **Cloudflare Workers AI free allowance** is 10,000 neurons/day, roughly 500
  parses. The per-visitor and global caps exist to stay inside that and to
  protect the $5 Workers plan from overage.
- **Gemma accuracy on Roman Urdu/Urdu is untested at scale.** Spike-test
  ~15 phrases early. Local `gemma4:e4b` parsed "aaj 20 carton basmati 5kg
  aaye, 5 carton laal mirch nikle" correctly in about 18s cold — a reasonable
  floor, not a guarantee for the hosted model.
- **MacBook RAM is 16GB**, not 8GB as the earlier plan assumed (corrected).
- **Friend unreachable this weekend.** Design reflects what Jawad knows of
  his business, not his direct input. Handover pending; the post will not
  invent his feedback.

## Prize categories to enter

- Gemma (featured, $200): the only runtime AI, doing the bilingual parsing.
- Render (featured, $200): hosts the working app.
- GitHub Copilot ($100): GitHub Actions CI runs the ledger tests.
- Entire ($100): only if setup is painless.
- ElevenLabs ($100): optional demo narration.
- Overall.

Explicitly skipping Backboard, Mastra, Temporal, SerpApi, Tiger Data,
TabPFN, Tinker, Arduino, DigitalOcean, MongoDB Atlas, Sentry Agent Tracing —
none of them solve a real need here, and adding one just for the category
costs build time the post needs more.

## Decisions log

- 4 Oct 13:40: Chose the importer friend over a tool for Jawad's own AR desk,
  because the theme is judged on building for another real person.
- 4 Oct 13:45: Re-picked from Invoice Match to Stock Diary after GPT-6.1
  Sol's brainstorm review scored it 29/30 — stronger theme fit, open-AI
  reliance, feasibility, and story than an OCR-dependent invoice matcher, and
  no vision-model risk.
- 4 Oct 14:00: Jawad asked for a live link, not a video demo. Moved hosting
  from "local Ollama + video" to Render (FastAPI) + Cloudflare Workers AI
  serving Gemma 4 for the public demo; kept local Ollama for development and
  as a fallback mode.
- 4 Oct 14:05: Split build-tool roles explicitly — Claude Code orchestrates
  and owns the shared contract, Sonnet and Codex (GPT-6 Sol) run as workers
  on well-specified files, local Gemma drafts simple content (catalogue, UI
  strings) for Claude to check. All of this is build-time only: Claude Code
  and Codex never run inside the shipped app, only Gemma does. Worth a line
  in the post — open orchestration on the build side, open-weight model at
  runtime.
