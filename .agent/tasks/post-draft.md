# Task: draft the DEV submission post

Write `post.md` (replace its contents). Touch no other file. Do not commit.

## Goal
A DEV post for the Hacktoberfest Weekend Challenge "Build for a Friend". Judging, in order:
1. Writing quality (weighted MOST): clear, engaging; explains what was built, who it's for, why open innovation matters.
2. Relevance: open-source AI at the core; fits "build for a friend".
3. Creativity. 4. Technical execution. 5. Partner tech (for the categories we enter).

## Hard rules (breaking any is a failure)
- Keep the template's front matter and section headings exactly (see current `post.md`): What I Built, Demo, Code,
  How I Built It, Why Does Open Innovation Matter?, My Agent Session, Prize Categories. Keep the first italic
  "This is a submission for..." line. Delete the HTML comment hints.
- Front matter: `title:` (write a good one, < 70 chars), `published: false`,
  `tags: devchallenge, weekendchallenge, hf26challenge, ai` (max 4 tags), and `cover_image: COVER_IMAGE_URL`.
- First person, as Jawad. Direct, plain, unsentimental. No hype words ("revolutionary", "seamless", "game-changer",
  "empower", "delve"), no emoji, no exclamation marks. Short paragraphs. Use concrete examples.
- The friend: **Hamza**, a real person who owns a grocery store, **Hamza Mart**. First name and shop name only:
  no surname, no city, no photo. Country (Pakistan) is fine.
- Hamza has NOT used it yet. Handover is pending. Never invent his reaction, quotes, or feedback. Say plainly that
  the design comes from what Jawad knows of how Hamza works, and that the stock figures in the demo are sample
  data, not his real stock.
- Where only Jawad can supply a personal fact, insert a marked placeholder like
  `[JAWAD: one sentence on how you know Hamza / a moment you saw him counting stock]`. Use at most 3 placeholders.
  Do not make up the fact.
- Never claim anything not in the facts below. No made-up benchmarks or user numbers.
- Never call Gemma "open source"; say "open-weight model".
- Claude Code and Codex are BUILD tools only. The running app uses only Gemma.

## Placeholders to leave in exactly this form
- Video: in Demo, a line `{% embed VIDEO_URL %}` (Jawad is uploading to YouTube).
- Repo: in Code, `{% embed https://github.com/syedjawad11/stock-diary %}`.

## Facts you may use
Product
- Stock Diary: a bilingual (Urdu, Roman Urdu, English) stock book for Hamza Mart. Live: https://stock-diary-lscy.onrender.com
  (Render free plan: first load after idle can take ~1 minute; say so).
- Hamza keeps stock in his head and on paper, in a mix of Urdu, Roman Urdu and English.
- He types a line the way he'd say it: "20 carton basmati aaye, 5 packet haldi nikle". Gemma proposes stock
  movements (product, qty, unit, in/out) against the shop's catalogue. He reviews before/after balances and
  confirms or edits. Nothing is saved until he confirms.
- Plain Python posts confirmed movements to a SQLite ledger, keeps running balances, flags low stock. The model
  never writes a number to the ledger. Quantities are integers.
- Unit guard: "5 bori laal mirch" when chilli is counted in packets is blocked until he picks the right unit.
  Insufficient stock is also blocked (e.g. can't send out 5 when 3 are left).
- Ask questions: "kis cheez ka stock kam hai?", "kal kya mangwana hai?", one product's balance, today's movements.
  Gemma only picks the intent (low_stock, restock, balance, today); Python fills fixed bilingual templates with
  the real numbers. The reorder list is "minimum to clear the low-stock alert", not a forecast.
- Also: manual add/remove (no AI), add your own products (private to your sandbox; Gemma then recognises them),
  search and Low/Out filters, full Urdu UI with right-to-left layout, dark mode, mobile-first.
- Public demo: each visitor gets an isolated sandbox (signed cookie), reset button, sandboxes purge after 24h;
  rate limits 5 model calls/min and 30/day per visitor plus a global daily cap, to stay inside the free
  Cloudflare allowance.

Open-source AI at the core
- Model: Google's Gemma 4, open-weight. Two backends behind ONE file, `app/model_adapter.py`, switched by
  `MODEL_BACKEND`:
  - hosted: Gemma 4 26B A4B (`@cf/google/gemma-4-26b-a4b-it`) on Cloudflare Workers AI (the live demo);
  - local: Gemma 4 e4b through Ollama on Jawad's 16 GB MacBook, no cloud keys, nothing leaves the machine.
- The demo video shows both, same code.
- Accuracy check: 12 test sentences (Roman Urdu, Urdu script, English, mixed, plus one deliberately ambiguous
  "chawal 10 aaye" where the model must NOT guess between two rices). Hosted: 12/12, about 1–2 s each.
  Local e4b: 12/12, about 4–9 s each (first call ~13 s while the model loads).
- Cost note: ~9 Cloudflare "neurons" per parse; free allowance is 10,000 neurons/day.
- Rest of the stack is open source too: FastAPI, Pydantic, SQLite, uvicorn, httpx, pytest. Vanilla JS frontend.

Build story (good material; pick the strongest)
- Built in one Sunday inside the challenge window.
- First idea was an invoice matcher; dropped before any code because it relied on OCR/vision and fit the theme
  less well. Stock Diary fit a real person's daily problem.
- Bug worth telling: on Cloudflare, Gemma 4 returned EMPTY output on multi-line entries. Cause: thinking mode was
  on by default and the reasoning ate the whole token budget. Fix: `chat_template_kwargs: {enable_thinking: false}`.
  Result went to 12/12 at 1–2 s.
- Principle: "Gemma reads, Python counts." The model reads language and picks intents; deterministic code does
  every number, with tests.
- Process: Claude Code (Anthropic) was the orchestrator: plan, architecture, shared contract (`API.md`), wiring,
  tests, deploys. OpenAI Codex ran GPT models as parallel workers on well-specified files (ledger, question
  templates, frontend) and as a reviewer. Three workers built ledger, restock intent and frontend in parallel
  against the written API contract. Review of the diff caught 3 real bugs before deploy (unit-check bypass by
  editing the qty; a unit mismatch hidden behind an insufficient-stock error; a reset during a parse returning a
  500). A browser click-through at phone and desktop width caught 2 frontend bugs. All fixed with tests.
- 42 pytest tests; GitHub Actions runs them on Python 3.9 and 3.12 on every push.
- Hosting: Render web service (free plan). Deploys triggered through the Render API.
- Demo video: recorded with an automated browser (Playwright), narration generated with ElevenLabs.

Why open innovation matters (argue it, with these concrete points)
- A small grocery store can't carry a per-call API bill forever; an open-weight model can run on a laptop he
  already owns, with no subscription.
- His stock is his business; local inference means it never has to leave the shop.
- No lock-in: same code moves between a cloud host and a laptop by changing one environment variable. If a
  provider changes prices or shuts down, the app keeps working.
- Open weights handle the way people actually write in Pakistan: Roman Urdu mixed with English and Urdu script.
- Honest limit: the hosted demo runs on Cloudflare's servers; the open part is the model, which is why the local
  path matters.

My Agent Session section
- No DevRelay recording. Briefly describe the agent setup (orchestrator + workers + reviewer) and that the
  repo keeps the task briefs and review notes in `.agent/tasks/` and `.agent/reviews/`; link to
  https://github.com/syedjawad11/stock-diary/tree/main/.agent

Known limits (include a short honest list somewhere fitting)
- Not yet handed over; no real-shop testing. Free hosting cold starts. Model accuracy measured on 12 sentences,
  not at scale. No voice input, no photos of bills, no login (sandbox per visitor). Quotas reset if the server
  restarts.

Prize Categories section (list exactly these, one line each on how we qualify)
- Best Use of Gemma: the only AI at runtime; runs locally and on Cloudflare.
- Best Use of Render: hosts the app (FastAPI backend + frontend) that calls Gemma.
- Best Use of GitHub Copilot: GitHub Actions runs the test suite on every push (the category explicitly allows
  "automate your project with GitHub Actions").
- Best Use of ElevenLabs: narration for the demo video (category explicitly allows "generate narration for your demo").

Ending
- Close with what's next (handing it to Hamza, then voice input in Urdu if he wants it) and ask readers a
  specific question to invite comments (e.g. how they'd handle mixed-script input, or whether they've built
  for a shopkeeper).

## Length and shape
1,100–1,600 words. Open with Hamza and the problem in 2–3 sentences, before any tech. Include one short code
snippet that shows the "Gemma reads, Python counts" boundary or the thinking-mode fix (keep it real: the fix is
the `chat_template_kwargs` line above). One small table is fine (e.g. hosted vs local).

## Done looks like
`post.md` fully written, all rules above met. Reply with: word count, list of placeholders left, any fact you
were unsure of.
