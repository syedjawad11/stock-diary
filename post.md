---
title: I Built a Roman Urdu Stock Book for My Friend's Grocery Store
published: false
tags: devchallenge, weekendchallenge, hf26challenge, ai
cover_image: https://raw.githubusercontent.com/syedjawad11/stock-diary/main/docs/cover.png
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

## What I Built

My friend Hamza owns a grocery store called Hamza Mart. He keeps stock in his head and on paper, and the notes move between Urdu, Roman Urdu, and English. [JAWAD: one sentence on how you know Hamza or a moment you saw him counting stock.]

I built Stock Diary so he can record stock in the language he already uses. He can type, “20 carton basmati aaye, 5 packet haldi nikle,” and see proposed movements: which product, how many, which unit, and whether stock came in or went out. The proposal also shows the balance before and after. He can edit it or confirm it. Nothing is saved until he confirms.

That confirmation matters. A plausible sentence is not a reliable stock entry if the unit is wrong. If Hamza writes “5 bori laal mirch” but chilli is counted in packets, Stock Diary stops the entry until he picks the right unit. It also stops an outgoing movement of five when only three are left. The model helps read the sentence; plain Python checks the numbers and posts the confirmed movement to a SQLite ledger.

He can ask “kis cheez ka stock kam hai?” for low stock, “kal kya mangwana hai?” for a reorder list, or ask for one product's balance or today's movements. The reorder list gives the minimum quantity needed to clear each low-stock alert. It is not a sales forecast. For tasks that need no language interpretation, he can add or remove stock manually, add his own products, search, and filter for Low or Out items. The interface also has a full Urdu layout with right-to-left text, dark mode, and a phone-sized view.

I built this from what I know of how Hamza works, not from a session with him. He has not used it yet, and the handover is pending. All stock figures in the public demo are sample data, not Hamza Mart's real stock.

## Demo

Try the [live Stock Diary demo](https://stock-diary-lscy.onrender.com). It runs on Render's free plan, so the first load after a period of inactivity can take about a minute. The video shows the hosted and local Gemma backends running the same app code.

{% embed VIDEO_URL %}

The public demo gives each visitor a separate sandbox through a signed cookie. You can reset yours. Sandboxes are purged after 24 hours, and each visitor is limited to five model calls per minute and 30 per day, with a global daily cap as well. These limits keep the demo inside Cloudflare's free allowance.

## Code

The [repository](https://github.com/syedjawad11/stock-diary) has the app, tests, and setup instructions. The demo catalogue and entries are synthetic. You can also run Gemma locally with Ollama, without cloud keys.

{% embed https://github.com/syedjawad11/stock-diary %}

## How I Built It

I had one Sunday inside the challenge window. My first idea was an invoice matcher, but I dropped it before writing code. It depended on reading bill images, and it was further from a problem I knew Hamza had. A stock book gave me a smaller and more useful starting point: one line of messy language, a review step, and a balance that must be correct.

My rule for the architecture was: **Gemma reads, Python counts.** Google's Gemma 4 is an open-weight model and the only AI in the running app. It turns mixed-language text into proposed product movements against the shop's catalogue. For questions, it selects an intent such as `low_stock`, `restock`, `balance`, or `today`. Python fills fixed bilingual answer templates with ledger values. Gemma never writes a number to the ledger. Quantities are integers, and the ledger arithmetic is plain Python with pytest tests.

Both model routes go through `app/model_adapter.py` and are selected with `MODEL_BACKEND`:

| Backend | Model and place it runs | Result on my 12 test sentences |
| --- | --- | --- |
| Hosted demo | Gemma 4 26B A4B on Cloudflare Workers AI | 12/12, about 1–2 seconds each |
| Local | Gemma 4 e4b through Ollama on my 16 GB MacBook | 12/12, about 4–9 seconds each; first call about 13 seconds while it loads |

The 12 sentences covered Roman Urdu, Urdu script, English, and mixed input. One deliberately said “chawal 10 aaye” when the catalogue contained two kinds of rice; a correct response had to leave the product unresolved instead of guessing. This is a useful check for the language boundary, but it is not a measure of accuracy across a working shop.

I hit a specific problem with the hosted model: multi-line entries came back empty. Cloudflare's Gemma 4 had thinking mode enabled by default, and its reasoning used the available token budget before it returned the structured answer. Setting this in the request fixed the empty output:

```json
"chat_template_kwargs": {"enable_thinking": false}
```

After that change, the hosted model completed all 12 test cases in roughly one to two seconds each. A parse used about nine Cloudflare neurons in this check; the free allowance is 10,000 neurons per day. That is why the public demo has visitor and global limits.

The rest of the stack is FastAPI, Pydantic, SQLite, uvicorn, httpx, pytest, and a vanilla JavaScript frontend. Render serves the backend and frontend; I triggered deploys through the Render API. There are 42 pytest tests, and GitHub Actions runs them on Python 3.9 and 3.12 on every push.

The checks caught more than parsing mistakes. A review of the code found that editing a quantity could bypass the unit warning, that an insufficient-stock error could hide a unit mismatch, and that resetting a sandbox during a parse could return a server error. I fixed those cases with tests. A browser click-through at phone and desktop widths caught two frontend issues, which I also fixed. The demo video was recorded with Playwright, and I generated its narration with ElevenLabs.

## Why Does Open Innovation Matter?

A small grocery store cannot assume it can pay a per-call model bill indefinitely. An open-weight model can run on a laptop Hamza already owns, with no model subscription. Local inference also means his stock entries can stay on that machine. His stock is his business information, and the app should give him a way to keep it at the shop.

The hosted demo does send model requests to Cloudflare's servers. I chose that route so people can try the app in a browser. The model itself is open-weight, and the local Ollama route is the part that lets the same product work without a cloud model provider. Switching `MODEL_BACKEND` moves between those routes without rewriting the stock workflow. If a host changes its prices or stops serving the model, that local path still exists.

Open weights also let me test the language Hamza actually uses: Roman Urdu mixed with English and Urdu script. A rigid stock form would make him translate his own notes into the software's categories before recording them. Here the model proposes the interpretation, but the review screen and Python checks keep that flexibility from silently changing a balance.

There are limits I want to be clear about:

- Hamza has not used Stock Diary yet. There has been no testing with his real stock.
- Model accuracy was checked on 12 sentences, not at shop scale.
- The free Render service has cold starts. Demo call quotas can reset if the server restarts.
- There is no voice input, bill photo input, or login. The public version uses a sandbox for each visitor.

## My Agent Session

I used Claude Code as the build orchestrator for the plan, architecture, shared `API.md` contract, integration, tests, and deploys. OpenAI Codex ran GPT models as workers on defined files for the ledger, restock intent, and frontend, then as a reviewer. Three workers built those parts in parallel against the written API contract. Claude Code and Codex were build tools only; the running app calls Gemma.

I did not record a DevRelay session. The repository keeps the [task briefs and review notes](https://github.com/syedjawad11/stock-diary/tree/main/.agent) in `.agent/tasks/` and `.agent/reviews/`, including the review that found the three bugs before deployment.

## Prize Categories

- **Best Use of Gemma:** Gemma is the only runtime AI and runs both locally through Ollama and on Cloudflare Workers AI.
- **Best Use of Render:** Render hosts the FastAPI backend and frontend that call Gemma for the public demo.
- **Best Use of GitHub Copilot:** GitHub Actions runs all 42 tests on Python 3.9 and 3.12 on every push, so a broken ledger can't reach the live demo unnoticed.
- **Best Use of ElevenLabs:** ElevenLabs generated the narration for the demo video.

Next I want to hand Stock Diary to Hamza and see how it fits a real day at Hamza Mart. If he wants it, voice input in Urdu is the next feature I would try. If you have built a tool for a shopkeeper, how did you handle notes that switch between scripts and product names?
