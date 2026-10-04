# Stock Diary: instructions for Codex

Read `BRIEF.md` and `PLAN.md` first. The orchestrator (Claude Code) tells you
whether you are a worker or a reviewer.

- Worker: do only the task given, touch only the named files, do not commit,
  do not install packages (no network in your sandbox; report missing ones).
  End with: files changed, how verified, assumptions, anything not done.
- Reviewer: read-only. Lead with what would break or miss the deadline
  (Mon 5 Oct 2026, 08:59 Malta). Give file, problem, fix. End with a verdict.

Project rules:
- The only AI at runtime is Gemma: local Ollama (`gemma4:e4b`) for
  development, or Cloudflare Workers AI (`@cf/google/gemma-4-26b-a4b-it`) for
  the hosted public demo. Both go through `app/model_adapter.py`. Never add
  a closed or hosted proprietary model API.
- `app/ledger.py` and all arithmetic are plain Python with pytest tests. No
  model calls there. Quantities are ints — see `app/models.py` (`qty: int`
  on `ParsedLine`, `Movement`, `PostLine`). No floats.
- Sample and demo data are synthetic. No real supplier, customer, or stock
  data.
- Python 3.9+ compatible.
- Shapes come from `app/models.py`; do not redefine them.
