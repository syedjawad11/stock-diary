# Stock Diary

## Try it live

Try the [live demo](https://stock-diary-lscy.onrender.com), where each visitor gets their own sandbox seeded with sample stock. It runs on Render's free plan, so the first load after idle can take about a minute. The model is Gemma 4 (26B A4B) on Cloudflare Workers AI, with limits of 5 model calls per minute and 30 per day per visitor.

A bilingual (Urdu, Roman Urdu, English) stock book for Hamza Mart, a small
grocery store run by Jawad's friend Hamza. Type a line like "20 carton basmati aaye, 5 laal
mirch nikle"; Gemma parses it into proposed stock movements, you confirm, and
plain Python keeps the ledger, running balances, and low-stock flags. Ask
"kis cheez ka stock kam hai?" and get a plain-language answer, filled in from
the real numbers — Gemma only picks the question's intent, never the figures.

**Hamza Mart** is a real shop. The products and quantities in the demo are
sample data, not Hamza's real stock.

What you can do:

- **AI entry**: type a sentence; Gemma proposes movements; you check and confirm.
  Unit words are checked too ("5 bori laal mirch" when mirch is counted in packets
  is blocked until you confirm the unit).
- **Add / remove stock by hand**: pick a product, quantity, reason. No AI involved.
- **New product**: add your own product (private to your sandbox); Gemma can then
  recognise it in typed entries.
- **Ask**: what is low, what to reorder ("kal kya mangwana hai?"), one product's
  balance, or today's movements. Gemma only picks the question type; Python fills
  in every number. The reorder list is "minimum to clear the low-stock alert",
  not a forecast.
- Inventory with search, Low / Out of stock filters, and overview counts.

Built for the DEV Hacktoberfest Weekend Challenge: Build for a Friend (Oct
2026), for Hamza, a friend of Jawad's who owns a grocery store in Pakistan (rice,
spices, packaged food, cartons).

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull gemma4:e4b
MODEL_BACKEND=ollama uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Hosted environment variables

Set on Render for the public demo:

```
MODEL_BACKEND=cloudflare
CF_ACCOUNT_ID=...
CF_API_TOKEN=...
SESSION_SECRET=...
DB_PATH=...
```

Hosting: Render web service on the free plan (sleeps after 15 minutes idle,
about a minute to wake).

Rate limits on model calls: 5 per minute and 30 per day per visitor, 60 per
day per IP, 400 per day across the whole demo. Manual stock changes don't
count. Limits are in memory, so a server restart clears them.

The public demo uses a synthetic catalogue only. Each visitor gets an
isolated sandbox (signed cookie) with a reset button. Pressing Reset also
deletes sandboxes that have been inactive for more than 24 hours.

## Credits

- [Gemma 4](https://ai.google.dev/gemma) by Google, an open-weight model: the only AI the app runs.
  Hosted through [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/), local through [Ollama](https://ollama.com).
- [FastAPI](https://fastapi.tiangolo.com), [Pydantic](https://docs.pydantic.dev), [uvicorn](https://www.uvicorn.org),
  [httpx](https://www.python-httpx.org), [itsdangerous](https://itsdangerous.palletsprojects.com),
  [python-dotenv](https://github.com/theskumar/python-dotenv), [pytest](https://pytest.org), SQLite.
- Fonts: Inter and Noto Nastaliq Urdu (Google Fonts).
- No code was copied from other projects. Built with Claude Code (orchestration) and OpenAI Codex
  (worker and reviewer models) as development tools; neither runs inside the app. Task briefs and
  reviews are in [`.agent/`](.agent/).
- Demo video narration: ElevenLabs. The demo catalogue was drafted by local Gemma and checked by hand.

## Known limits

- Not yet handed over to Hamza; no testing in the real shop yet.
- Parsing accuracy was measured on 12 sentences (12/12 on both backends), not at scale.
- No voice input, no photos of bills, no login: each browser gets its own sandbox.
- Free hosting means a cold start after idle.
- Units are checked by word, not converted (no cartons-to-packets maths).

## Licence

MIT, see [LICENSE](LICENSE).

## Commits after the submission deadline

None.
