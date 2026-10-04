# Status: HF26 Stock Diary (workspace memory)

Read this first when resuming. Update it at every milestone or break.
Last updated: Sun 4 Oct 2026, ~15:05 Malta. Jawad is on a 10–15 min break.

## Deadline
- Submission closes Mon 5 Oct 06:59 UTC (08:59 Malta).
- Our targets: code freeze ~20:00, post published ~23:00 Sun.

## Where things are
- Repo: https://github.com/syedjawad11/stock-diary (public, branch main, auto-deploys to Render)
- Live: https://stock-diary-lscy.onrender.com (Render free plan, Frankfurt)
  - Render service id: srv-db14qeqd0e5s73e45edg, owner tea-db14310u01pc73co2c6g
  - Free plan sleeps after 15 min idle; ~1 min cold start. Starter needs a card (Render returned 402).
- Model: Gemma 4 26B A4B on Cloudflare Workers AI (thinking disabled). Local dev: Ollama gemma4:e4b.
- Secrets: only in `.env` (git-ignored). Keys: MODEL_BACKEND, OLLAMA_MODEL, CF_ACCOUNT_ID,
  CF_API_TOKEN, SESSION_SECRET, RENDER_API_KEY. Never print values.
- Last commit: c83b664. Tests: 22 passing (`.venv/bin/python -m pytest -q`).

## Done
- [x] Workspace setup (Ollama, Codex CLI, venv, git)
- [x] Idea picked: Stock Diary (bilingual stock book for the importer friend in Pakistan)
- [x] Backend: ledger (Codex), model adapter, parse, questions, API, sandboxes, rate limits
- [x] Frontend: mobile-first, EN/Urdu toggle with RTL, dark mode (Sonnet)
- [x] CI: GitHub Actions on py3.9 and 3.12
- [x] Cloudflare thinking-budget bug fixed (12/12 spike)
- [x] Deployed to Render, live URL tested end to end (parse, stock guard, 3 question types)
- [x] Doubled-bracket fix in low-stock answers + README "Try it live" (Codex, verified)

## Next (in order)
1. Urdu/RTL visual check of the live page (screenshot, phone width).
2. Jawad tries real entries on his phone; fix what feels wrong.
3. Sol review of the full diff (`scripts/codex-review.sh`).
4. README: credits, limits, MIT licence (check LICENSE exists).
5. Record the demo video (60–90 s).
6. Code freeze ~20:00.
7. post.md: Codex worker drafts from the template, Claude edits, Sol critiques. Tags: devchallenge, weekendchallenge, hf26challenge.
8. Publish ~23:00. Optional: Entire capture, ElevenLabs narration.

## Prize categories we enter
Gemma, Render, GitHub Copilot (via Actions CI), Entire (if painless), ElevenLabs (optional). Skip the rest.

## Working rules (from Jawad)
- Delegate to Codex (worker GPT-6 Sol; reviewer GPT-6.1 Sol) and Sonnet to save Claude usage; local Gemma for easy drafts.
- Claude orchestrates, runs every worker result before calling it done, and commits.
- Synthetic data only. Don't invent the friend's feedback; the post says handover is pending.
- Claude Code and Codex are build tools only, never a runtime dependency.

## Open issues / notes
- Starter upgrade only if Jawad adds a card on Render Billing.
- Quotas are in-memory; a Render restart clears them (acceptable).
