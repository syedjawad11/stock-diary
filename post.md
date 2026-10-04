---
title: I Built a Roman Urdu Stock Book for My Friend's Grocery Store
published: true
tags: devchallenge, weekendchallenge, hf26challenge, ai
cover_image: https://raw.githubusercontent.com/syedjawad11/stock-diary/main/docs/cover.png
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

## What I Built

Hamza and I grew up together. Today he runs Hamza Mart, a grocery store, and his stock lives in a paper register and in his memory, written and thought in a mix of Urdu, Roman Urdu, and English. I wanted to turn those same notes into balances he could check.

Stock Diary turns “20 carton basmati aaye, 5 packet haldi nikle” (“20 cartons of basmati came in, 5 packets of turmeric went out”) into two proposed stock movements. Each shows the product, quantity, unit, direction, and the balance before and after. He can correct the proposal before confirming it. Nothing is saved until he confirms.

That confirmation matters. A plausible sentence is not a reliable stock entry if the unit is wrong. If Hamza writes “5 bori laal mirch” but chilli is counted in packets, Stock Diary stops the entry until he picks the right unit. It also stops an outgoing movement of five when only three are left. The model helps read the sentence; plain Python checks the numbers and posts the confirmed movement to a SQLite ledger.

He can also ask “kis cheez ka stock kam hai?” (“What is running low?”) or “kal kya mangwana hai?” (“What should I order tomorrow?”). Gemma only works out which question he is asking; Python answers from the ledger. The reorder list gives the minimum needed to clear each low-stock alert, not a forecast. Manual entries and new products cover the everyday work, with a full Urdu interface (right to left) and a layout that fits a phone.

I built this from what I know of how Hamza works, not from a session with him. He has not used it yet; I'm showing it to him this week. All stock figures in the public demo are sample data, not Hamza Mart's real stock.

## Demo

Try the [live Stock Diary demo](https://stock-diary-lscy.onrender.com): enter the sentence above, check the proposed balances, then confirm and look at the updated stock. Try “5 bori laal mirch aayi” to see the unit warning. Render's free plan can take about a minute to wake after inactivity. The video shows hosted and local Gemma running the same app code.

{% embed https://youtu.be/s6pBkxYO72M %}

Each browser gets a separate sandbox with a reset button. AI requests are limited to five per minute and 30 per day per visitor, with extra per-IP and global daily limits. These keep usage low; they don't guarantee the demo stays inside Cloudflare's free allowance.

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

The checks caught more than parsing mistakes. A review of the code found that editing a quantity could bypass the unit warning, that an insufficient-stock error could hide a unit mismatch, and that resetting a sandbox during a parse could return a server error. I fixed the frontend unit-warning logic and added API regression tests for the mismatch response and for a reset during a parse. A browser click-through at phone and desktop widths caught two frontend issues, which I also fixed. The demo video was recorded with Playwright, and I generated its narration with ElevenLabs.

## Why Does Open Innovation Matter?

A small grocery store can't plan around a per-call model bill. Open weights give Stock Diary a local option: I ran Gemma 4 through Ollama on my 16 GB MacBook with no cloud keys at all. That shows a working alternative to paying a provider for every entry. It doesn't yet tell me what hardware Hamza would need, and that's part of the handover.

His stock is his business information. The public demo sends requests to Cloudflare so anyone can try it in a browser, but in a local setup every entry stays on the machine running the app. Both routes go through the same model adapter and the same stock workflow, so switching `MODEL_BACKEND` changes the inference provider without touching the ledger. If a host changes its prices or stops serving the model, the local path still works.

The code is MIT-licensed, so another shop can adapt the catalogue, the product aliases and the interface for its own stock.

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
- **Best Use of GitHub Copilot:** GitHub Actions runs all 42 tests on Python 3.9 and 3.12 on every push, so a ledger regression shows up on the commit that caused it.
- **Best Use of ElevenLabs:** ElevenLabs generated the narration for the demo video.

This week I'm handing Stock Diary to Hamza to see how it fits a real day at Hamza Mart, and I'll add what he says to the comments. If he wants it, voice input in Urdu is the next feature I would try. If you have built a tool for a shopkeeper, how did you handle notes that switch between scripts and product names?
