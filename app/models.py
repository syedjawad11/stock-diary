"""Shared data shapes. Every module imports from here; nobody redefines these."""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Direction(str, Enum):
    IN = "in"
    OUT = "out"


class Product(BaseModel):
    id: str  # slug, e.g. "basmati-5kg"
    name_en: str
    name_ur: str  # Urdu script
    aliases: List[str]  # lowercase English / Roman Urdu / Urdu names the friend might type
    unit: str  # one fixed unit per product, e.g. "carton", "bag"
    low_threshold: int = Field(ge=0)  # LOW when quantity <= this
    opening_qty: int = Field(ge=0)  # demo seed stock


UNITS = ["carton", "bag", "tin", "packet", "box", "piece"]


class NewProduct(BaseModel):
    """A product a visitor adds to their own sandbox. Server assigns the id; stock starts at 0."""
    name_en: str = Field(min_length=2, max_length=60)
    name_ur: str = Field("", max_length=60)  # optional; falls back to name_en
    aliases: List[str] = Field(default_factory=list, max_length=8)  # each <= 40 chars
    unit: str  # one of UNITS
    low_threshold: int = Field(ge=0, le=100000)


# --- What the model returns (validated before anything touches the ledger) ---

class ParsedLine(BaseModel):
    product_text: str  # the words the user used for the product
    product_id: Optional[str] = None  # model's pick from the catalogue; None if unsure
    qty: int = Field(gt=0)
    unit: Optional[str] = None
    direction: Direction


class ParseResult(BaseModel):
    lines: List[ParsedLine]


class Intent(str, Enum):
    LOW_STOCK = "low_stock"
    BALANCE = "balance"
    TODAY = "today"
    RESTOCK = "restock"
    UNKNOWN = "unknown"


class Question(BaseModel):
    intent: Intent
    product_id: Optional[str] = None


# --- Ledger records (computed by plain code only) ---

class Movement(BaseModel):
    id: int
    product_id: str
    qty: int  # always positive; direction gives the sign
    direction: Direction
    note: str  # the original sentence, or "reversal of #n"
    created_at: str  # ISO 8601 UTC
    reverses: Optional[int] = None  # id of the movement this one undoes
    reversed_by: Optional[int] = None


class StockRow(BaseModel):
    product: Product
    qty: int
    is_low: bool


class PostLine(BaseModel):
    product_id: str
    qty: int = Field(gt=0)
    direction: Direction
