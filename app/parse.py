"""Sentence -> proposed stock movements. Gemma reads the language; code checks everything after."""
import difflib
from typing import Dict, List, Optional

from .model_adapter import generate_json
from .models import ParsedLine, ParseResult, Product

SYSTEM = """You read stock entries for a small grocery store in Pakistan.
The user writes in English, Roman Urdu, Urdu script, or a mix.
Return every stock movement in the sentence as JSON: {"lines": [...]}.
Each line: product_text (the user's words for the product), product_id (the matching id
from the catalogue, or null if you are not sure which one), qty (positive whole number),
unit (the user's unit word, or null), direction ("in" or "out").

Direction words:
- in: aaye, aya, aayi, aa gaye, mila, mile, received, arrived, came, purchased, kharida, آئے, آیا, ملے, خریدا
- out: nikle, nikla, gaye, gaya, bheje, bheja, becha, bechi, sold, sent, dispatched, نکلے, گئے, بھیجے, بیچا
If one sentence mentions a product twice (e.g. "20 aaye, 5 nikle"), return two lines.
Never invent products that are not in the sentence. Never guess a product_id between two
similar products (e.g. "chawal" could be basmati or sella): use null.

Catalogue (id | names | unit):
{catalogue}"""


def catalogue_text(catalogue: List[Product]) -> str:
    return "\n".join(
        f"{p.id} | {p.name_en}; {p.name_ur}; {', '.join(p.aliases)} | {p.unit}" for p in catalogue
    )


def parse_sentence(text: str, catalogue: List[Product]) -> List[ParsedLine]:
    result = generate_json(SYSTEM.replace("{catalogue}", catalogue_text(catalogue)), text, ParseResult)
    return [resolve(line, catalogue) for line in result.lines]


def resolve(line: ParsedLine, catalogue: List[Product]) -> ParsedLine:
    """Keep the model's product_id only if it exists; otherwise try an exact alias match."""
    ids = {p.id for p in catalogue}
    if line.product_id in ids:
        return line
    words = line.product_text.strip().lower()
    exact = [p.id for p in catalogue if words in p.aliases or words in (p.name_en.lower(), p.name_ur)]
    return line.model_copy(update={"product_id": exact[0] if len(exact) == 1 else None})


def candidates(product_text: str, catalogue: List[Product], n: int = 3) -> List[Product]:
    """Closest products for the picker when the product is unclear."""
    words = product_text.strip().lower()
    scored: Dict[str, float] = {}
    for p in catalogue:
        names = p.aliases + [p.name_en.lower(), p.name_ur]
        best = max(difflib.SequenceMatcher(None, words, name).ratio() for name in names)
        if any(words and (words in name or name in words) for name in names):
            best = max(best, 0.9)
        scored[p.id] = best
    ranked = sorted(catalogue, key=lambda p: -scored[p.id])
    return [p for p in ranked[:n] if scored[p.id] >= 0.35]


def find(catalogue: List[Product], product_id: Optional[str]) -> Optional[Product]:
    return next((p for p in catalogue if p.id == product_id), None)
