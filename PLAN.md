# Plan: Invoice Match (working name)

Status: DRAFT, not yet reviewed by GPT-6.1 Sol. First action in Claude Code:
`/second-opinion` on this file, then update it.

## Who it is for

Jawad's friend, who runs a small import/export business and handles supplier
invoices and stock himself. Problem: checking each supplier invoice against
what was ordered is manual, so short shipments, price changes, and arithmetic
errors get paid.

OPEN: Jawad to ask him (a) what goes wrong most often, (b) how he checks today.
His answers adjust the flag list below and are quoted in the post.

## What it does (one screen)

1. Drop in a supplier invoice (PDF or photo) and the purchase order (CSV).
2. A local open-weight model (Gemma 4 through Ollama) reads the invoice into
   structured line items.
3. Plain Python matches invoice against order and flags discrepancies.
4. It drafts a dispute email to the supplier listing them.

Nothing leaves the laptop. No API key. No cost per invoice.

## Design

| File | Job | Owner |
| --- | --- | --- |
| `models.py` | Pydantic shapes: `InvoiceLine`, `Invoice`, `POLine`, `Flag`, `MatchResult` | Claude |
| `extract.py` | Invoice file -> `Invoice`. Text PDFs: pypdf text to Gemma. Images/scans: page image to Gemma vision. Ollama structured output (JSON schema), validated by Pydantic, one retry on invalid JSON. | Claude |
| `match.py` | `match(invoice, po_lines, price_tol=0.01) -> MatchResult`. No model calls. | Worker |
| `tests/test_match.py` | One test per flag type plus a clean invoice | Worker |
| `samples/make_samples.py` | Generates 4 synthetic invoices (PDF + PNG) and matching PO CSVs with seeded errors | Worker |
| `email_draft.py` | Flags -> dispute email. Figures are inserted by code from `MatchResult`; Gemma only words the message around them. | Claude |
| `app.py` | Streamlit page: upload, extracted table (editable), flags, amount in dispute, email draft | Claude |

Flags (`match.py`):
- `QTY_MISMATCH` invoiced quantity differs from ordered
- `PRICE_VARIANCE` unit price differs from PO price beyond tolerance
- `NOT_ORDERED` invoice line with no PO line
- `NOT_INVOICED` PO line absent from invoice (information only)
- `LINE_MATH` quantity x unit price does not equal line total
- `TOTAL_MATH` lines do not sum to subtotal, or subtotal + tax does not equal total

Line matching: by SKU when both sides have one, otherwise closest description
(`difflib`, standard library) above a threshold. Each flag carries the money
impact; the result totals the amount in dispute.

Stack: Python 3.9+, Streamlit, `ollama` Python client, Pydantic, pypdf,
pypdfium2 (PDF page to image), pandas, pytest. reportlab only for sample generation.

## Order of work (Malta time, Sun 4 Oct)

| When | Step | Gate |
| --- | --- | --- |
| 14:00 | `bash scripts/doctor.sh`; install Ollama if missing; pull the Gemma 4 tag the report suggests; `git init` here | Both Codex models answer; Ollama serves |
| 14:15 | `/second-opinion` on this plan; adjust | |
| 14:30 | In parallel: worker builds `samples/make_samples.py`; Claude writes `models.py` and a throwaway extraction spike | |
| 15:15 | **GO / NO-GO on extraction**: 4 sample invoices, compare extracted lines with truth | At least 3 of 4 text PDFs fully correct. If images fail, ship text PDFs only and say so in the post |
| 15:15 | Worker: `match.py` + tests. Claude: `extract.py` proper | Tests green, run by Claude |
| 17:00 | `app.py`, then `email_draft.py` | End to end on all samples |
| 18:30 | Reviewer checks full diff. Fix only real bugs. | |
| 19:15 | README (setup, sample walk-through, credits, limits), MIT licence, push to GitHub (public) | Fresh clone runs |
| 19:45 | Record demo video (2 to 3 min). Send to the friend; ask for his reaction. | |
| 20:15 | **Code freeze.** Write `post.md`. | |
| 22:00 | Reviewer critiques the post against the judging criteria. Revise. | |
| 23:00 | Publish on DEV. Check tags and that the embed and video work. | |
| Mon 08:59 | Hard deadline. Buffer only. | |

## Cut list (drop in this order when behind)

1. Photo/scan support (keep text PDFs)
2. Gemma wording of the email (use a plain template filled by code)
3. Editable extracted table
4. Fuzzy description matching (require SKU)

Never cut: tests on `match.py`, the README, three hours for the post.

## Risks

- **Extraction accuracy on a small model.** The whole project depends on it.
  Tested first; the editable table lets the user correct a misread line, and
  the post reports the measured accuracy honestly.
- **MacBook memory.** 8GB means the smallest Gemma 4 tag and weaker reading.
- **GPT-6.1 Sol may be rejected by the Codex CLI on a ChatGPT login** (open
  issue openai/codex#49703). The review script falls back to GPT-6 Sol.
- **No deployed demo.** Local by design, so the demo is a video. State that
  plainly in the post; it is the point, not a gap.
- **Friend does not reply today.** Then the post says it was built for him and
  not yet handed over. Do not invent a quote.

## Prize categories to enter

- Best Use of Gemma (featured, $200): Gemma 4 run locally through Ollama.
- Overall.
Do not list categories the project does not really use.

## Decisions log

- 4 Oct 13:40: Chose the importer friend over a tool for Jawad's own AR desk,
  because the theme is judged on building for another real person.
