# Status: HF26 Stock Diary (workspace memory)

Read this first when resuming. Update it at every milestone or break.
Last updated: Sun 4 Oct 2026, ~16:00 Malta. Hamza Mart upgrade shipped and live. Jawad on a short break.

## Deadline
- Submission closes Mon 5 Oct 06:59 UTC (08:59 Malta).
- Our targets: code freeze ~20:00, post published ~23:00 Sun.

## Where things are
- Repo: https://github.com/syedjawad11/stock-diary (public, branch main)
- Live: https://stock-diary-lscy.onrender.com (Render free plan, Frankfurt)
  - DEPLOYS ARE MANUAL in practice: autoDeploy=yes but GitHub pushes don't reach Render
    (GitHub app likely not connected). Trigger: POST /v1/services/<id>/deploys with RENDER_API_KEY.
  - Render service id: srv-db14qeqd0e5s73e45edg, owner tea-db14310u01pc73co2c6g
  - Free plan sleeps after 15 min idle; ~1 min cold start. Starter needs a card (Render returned 402).
- Model: Gemma 4 26B A4B on Cloudflare Workers AI (thinking disabled). Local dev: Ollama gemma4:e4b.
- Secrets: only in `.env` (git-ignored). Keys: MODEL_BACKEND, OLLAMA_MODEL, CF_ACCOUNT_ID,
  CF_API_TOKEN, SESSION_SECRET, RENDER_API_KEY. Never print values.
- Last code commit: 54f5522 (deployed, live verified); later commits are records only. Tests: 42 passing (`.venv/bin/python -m pytest -q`).

## Done
- [x] Workspace setup (Ollama, Codex CLI, venv, git)
- [x] Idea picked: Stock Diary (bilingual stock book for the importer friend in Pakistan)
- [x] Backend: ledger (Codex), model adapter, parse, questions, API, sandboxes, rate limits
- [x] Frontend: mobile-first, EN/Urdu toggle with RTL, dark mode (Sonnet)
- [x] CI: GitHub Actions on py3.9 and 3.12
- [x] Cloudflare thinking-budget bug fixed (12/12 spike)
- [x] Deployed to Render, live URL tested end to end (parse, stock guard, 3 question types)
- [x] Hamza Mart upgrade (16:05): private products, manual add/remove, restock intent, unit-mismatch guard,
      warehouse UI (desktop + phone, EN/UR). Sol reviewed; its 3 findings fixed. Live smoke passed on Cloudflare Gemma.
- [x] Doubled-bracket fix in low-stock answers + README "Try it live" (Codex, verified)

## Next (in order)
1. Jawad reviews the new UI on his phone (EN + Urdu); fix what feels wrong. Redeploy by API after any push.
2. README: credits, known limits, MIT licence (check LICENSE exists). Features section already done.
3. Final Sol check of the whole repo diff before freeze (upgrade diff already reviewed at 15:40).
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

## Post material (collect here as we go)
- Hamza Mart is a fictional shop; the friend is a wholesaler and has not seen it yet. Say both plainly.
- Upgrade story (15:15–16:00): Sol brainstormed and ranked ideas; three GPT-6 Sol workers built ledger,
  restock intent and frontend in parallel against a written contract (API.md); Claude wired main.py and
  tests; browser click-through caught 2 frontend bugs; Sol's diff review caught 3 real bugs
  (unit-check bypass, mismatch hidden by stock shortage, reset-during-parse 500). All fixed before deploy.
- Principle held: Gemma reads language and picks intents; Python computes every number (reorder list
  = minimum to clear the low-stock alert, not a forecast).
- Screenshots of the new UI: scratchpad only (not in repo); retake for the post.

## Open issues / notes
- Render GitHub auto-deploy not firing (autoDeploy=yes). Optional fix: connect the Render GitHub app.
- Minor, accepted: frontend Reset doesn't discard an in-flight AI parse; backend returns a clean
  unknown_product error, so nothing breaks.
- Starter upgrade only if Jawad adds a card on Render Billing.
- Quotas are in-memory; a Render restart clears them (acceptable).
