# Invoice Match: instructions for Codex

Read `BRIEF.md` and `PLAN.md` first. The orchestrator (Claude Code) tells you
whether you are a worker or a reviewer.

- Worker: do only the task given, touch only the named files, do not commit,
  do not install packages (no network in your sandbox; report missing ones).
  End with: files changed, how verified, assumptions, anything not done.
- Reviewer: read-only. Lead with what would break or miss the deadline
  (Mon 5 Oct 2026, 08:59 Malta). Give file, problem, fix. End with a verdict.

Project rules:
- `match.py` and all arithmetic are plain Python with pytest tests. No model
  calls there. Use `decimal.Decimal` for money, never float.
- The only AI at runtime is a local open-weight model through Ollama. Never add
  a hosted or closed API.
- Sample invoices are synthetic. No real supplier or customer data.
- Python 3.9+ compatible. Shapes come from `models.py`; do not redefine them.
