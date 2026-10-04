# Stock Diary

A bilingual (Urdu, Roman Urdu, English) stock book for a small import/export
and wholesale business. Type a line like "20 carton basmati aaye, 5 laal
mirch nikle"; Gemma parses it into proposed stock movements, you confirm, and
plain Python keeps the ledger, running balances, and low-stock flags. Ask
"kis cheez ka stock kam hai?" and get a plain-language answer, filled in from
the real numbers — Gemma only picks the question's intent, never the figures.

Built for the DEV Hacktoberfest Weekend Challenge: Build for a Friend (Oct
2026), for a friend of Jawad's who runs a small import/export and wholesale
business in Pakistan (rice, spices, packaged food, cartons).

**Live demo:** (link pending)

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

Render credits: (placeholder — promo claimed, balance to confirm before
publishing)

Rate limits: (placeholder — fill in the actual per-visitor and global caps
before publishing)

The public demo uses a synthetic catalogue only. Each visitor gets an
isolated sandbox (signed cookie) with a reset button; sandboxes purge after
24 hours.

## Credits

(filled in before submission — model, libraries, any non-trivial code reused)

## Known limits

(filled in before submission)

## Commits after the submission deadline

None.
