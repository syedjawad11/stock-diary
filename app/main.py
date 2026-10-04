"""FastAPI app: one page plus the JSON API described in API.md."""
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, URLSafeSerializer
from pydantic import BaseModel, Field

from . import parse as parser
from . import questions
from .ledger import InsufficientStock, Ledger, LedgerError
from .model_adapter import ModelUnavailable, backend_name
from .models import NewProduct, PostLine, Product

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
CATALOGUE = [Product(**p) for p in json.loads((ROOT / "data" / "catalogue.json").read_text("utf-8"))["products"]]
LEDGER = Ledger(os.environ.get("DB_PATH", str(ROOT / "diary.sqlite")), CATALOGUE)
SIGNER = URLSafeSerializer(os.environ.get("SESSION_SECRET", "dev-only-secret"), salt="sd-visitor")
COOKIE = "sd_visitor"

PER_MINUTE = int(os.environ.get("LIMIT_PER_MINUTE", "5"))
PER_DAY = int(os.environ.get("LIMIT_PER_DAY", "30"))
PER_IP_DAY = int(os.environ.get("LIMIT_PER_IP_DAY", "60"))
GLOBAL_DAY = int(os.environ.get("LIMIT_GLOBAL_DAY", "400"))
MAX_TEXT = 300

app = FastAPI(title="Stock Diary")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# --- Model-call quotas (in memory: one process; a restart clears them, which is acceptable) ---

class Quota:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.minute: Dict[str, Deque[float]] = defaultdict(deque)
        self.day: Dict[str, int] = defaultdict(int)
        self.day_key = ""

    def _roll(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.day_key:
            self.day_key, self.day = today, defaultdict(int)

    def used(self, visitor: str) -> int:
        with self.lock:
            self._roll()
            return self.day["v:" + visitor]

    def take(self, visitor: str, ip: str) -> Optional[str]:
        """Count one model call. Returns the limit hit ("minute" or "day"), or None."""
        with self.lock:
            self._roll()
            now = time.time()
            window = self.minute[visitor]
            while window and now - window[0] > 60:
                window.popleft()
            if (self.day["v:" + visitor] >= PER_DAY or self.day["ip:" + ip] >= PER_IP_DAY
                    or self.day["all"] >= GLOBAL_DAY):
                return "day"
            if len(window) >= PER_MINUTE:
                return "minute"
            window.append(now)
            self.day["v:" + visitor] += 1
            self.day["ip:" + ip] += 1
            self.day["all"] += 1
            return None


QUOTA = Quota()

MESSAGES = {
    "rate_limited": ("Too many checks for now. Please wait a minute and try again.",
                     "ابھی بہت زیادہ درخواستیں ہو گئیں۔ ایک منٹ بعد دوبارہ کوشش کریں۔"),
    "rate_limited_day": ("Daily limit reached for this demo. Manual add/remove still works.",
                         "اس ڈیمو کی آج کی حد پوری ہو گئی۔ ہاتھ سے اندراج اب بھی چلتا ہے۔"),
    "duplicate_product": ("A product with that name already exists.", "اس نام کی چیز پہلے سے موجود ہے۔"),
    "too_many_products": ("This demo allows up to 30 new products.", "اس ڈیمو میں زیادہ سے زیادہ 30 نئی چیزیں شامل ہو سکتی ہیں۔"),
    "parse_failed": ("I couldn't read that entry. Try writing it like: 20 carton basmati aaye.",
                     "یہ اندراج سمجھ نہیں آیا۔ ایسے لکھیں: 20 کارٹن باسمتی آئے۔"),
    "insufficient_stock": ("Not enough stock for that.", "اتنا سٹاک موجود نہیں ہے۔"),
    "unknown_product": ("That product is not in the list.", "یہ چیز فہرست میں نہیں ہے۔"),
    "already_reversed": ("That entry was already undone.", "یہ اندراج پہلے ہی واپس ہو چکا ہے۔"),
    "not_found": ("Entry not found.", "اندراج نہیں ملا۔"),
    "model_unavailable": ("The model is busy or unreachable. Please try again.",
                          "ماڈل اس وقت دستیاب نہیں۔ دوبارہ کوشش کریں۔"),
    "bad_request": ("Please check what you typed and try again.",
                    "جو لکھا ہے اسے دیکھ کر دوبارہ کوشش کریں۔"),
}
STATUS = {"rate_limited": 429, "duplicate_product": 409, "too_many_products": 409, "parse_failed": 422, "insufficient_stock": 409, "unknown_product": 422,
          "already_reversed": 409, "not_found": 404, "model_unavailable": 503, "bad_request": 400}


def error(code: str, detail: str = "") -> JSONResponse:
    en, ur = MESSAGES[code]
    return JSONResponse({"error": code, "message_en": f"{en} {detail}".strip(), "message_ur": ur},
                        status_code=STATUS[code])


def rate_limited(scope: str) -> JSONResponse:
    en, ur = MESSAGES["rate_limited_day" if scope == "day" else "rate_limited"]
    return JSONResponse({"error": "rate_limited", "scope": scope, "message_en": en, "message_ur": ur},
                        status_code=429)


# Unit words the friend might type -> the catalogue's unit. Unknown words are not judged.
UNIT_WORDS = {
    "carton": ["carton", "cartons", "ctn", "ctns", "کارٹن"],
    "bag": ["bag", "bags", "bori", "boriyan", "bora", "sack", "sacks", "بوری", "بوریاں"],
    "tin": ["tin", "tins", "can", "cans", "dabba tin", "ٹین"],
    "packet": ["packet", "packets", "pkt", "pkts", "pack", "packs", "پیکٹ"],
    "box": ["box", "boxes", "dabba", "dabbe", "ڈبہ", "ڈبے"],
    "piece": ["piece", "pieces", "pc", "pcs", "adad", "عدد"],
}
UNIT_OF = {word: unit for unit, words in UNIT_WORDS.items() for word in words}


def unit_mismatch(stated: Optional[str], product: Product) -> bool:
    unit = UNIT_OF.get((stated or "").strip().lower())
    return unit is not None and unit != product.unit


@app.exception_handler(RequestValidationError)
async def invalid_body(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error("bad_request")


# --- Visitor sandbox ---

def visitor_of(request: Request) -> str:
    token = request.cookies.get(COOKIE)
    if token:
        try:
            return SIGNER.loads(token)
        except BadSignature:
            pass
    return secrets.token_urlsafe(16)


@app.middleware("http")
async def sandbox(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    visitor = visitor_of(request)
    request.state.visitor = visitor
    LEDGER.ensure_visitor(visitor)
    response = await call_next(request)
    response.set_cookie(COOKIE, SIGNER.dumps(visitor), max_age=86400, httponly=True, samesite="lax",
                        secure=request.url.scheme == "https")
    return response


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def catalogue(request: Request) -> List[Product]:
    return LEDGER.catalogue_for(request.state.visitor)


def state(visitor: str) -> dict:
    return {
        "stock": [row.model_dump() for row in LEDGER.stock(visitor)],
        "recent": [m.model_dump() for m in LEDGER.recent(visitor, 10)],
        "quota": {"used_today": QUOTA.used(visitor), "limit_today": PER_DAY},
        "backend": backend_name(),
    }


# --- Routes ---

class TextIn(BaseModel):
    text: str = ""


class ConfirmIn(BaseModel):
    confirm_key: str = Field(min_length=8, max_length=64)
    lines: List[PostLine] = Field(min_length=1, max_length=10)
    note: str = Field("", max_length=MAX_TEXT)


class UndoIn(BaseModel):
    movement_id: int


class ProductIn(BaseModel):
    key: str = Field(min_length=8, max_length=64)
    product: NewProduct


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def health() -> dict:
    return {"ok": True, "backend": backend_name()}


@app.get("/api/state")
def get_state(request: Request) -> dict:
    return state(request.state.visitor)


@app.post("/api/parse")
def parse_entry(body: TextIn, request: Request):
    visitor, text = request.state.visitor, body.text.strip()
    if not text or len(text) > MAX_TEXT:
        return error("bad_request")
    limited = QUOTA.take(visitor, client_ip(request))
    if limited:
        return rate_limited(limited)
    products = catalogue(request)
    try:
        lines = parser.parse_sentence(text, products)
    except ModelUnavailable:
        return error("model_unavailable")
    if not lines:
        return error("parse_failed")

    known = [PostLine(product_id=l.product_id, qty=l.qty, direction=l.direction) for l in lines if l.product_id]
    try:  # the visitor may have reset (dropping a custom product) while Gemma was reading
        balances = iter(LEDGER.preview(visitor, known))
    except LedgerError as exc:
        return error(exc.code)
    proposals = []
    for line in lines:
        product = parser.find(products, line.product_id)
        item = {"product_text": line.product_text, "product_id": line.product_id, "candidates": [],
                "qty": line.qty, "unit": product.unit if product else line.unit,
                "direction": line.direction.value, "balance_before": None, "balance_after": None, "problem": None,
                "stated_unit": line.unit, "unit_mismatch": False}
        if product:
            item["balance_before"], item["balance_after"] = next(balances)
            # Kept separately from `problem` so fixing the quantity can't skip the unit check.
            item["unit_mismatch"] = unit_mismatch(line.unit, product)
            if item["balance_after"] < 0:
                item["problem"] = "insufficient_stock"
            elif item["unit_mismatch"]:
                item["problem"] = "unit_mismatch"
        else:
            item["candidates"] = [p.model_dump() for p in parser.candidates(line.product_text, products)]
            item["problem"] = "unknown_product"
        proposals.append(item)
    return {"proposals": proposals, "confirm_key": secrets.token_hex(12)}


@app.post("/api/confirm")
def confirm(body: ConfirmIn, request: Request):
    visitor = request.state.visitor
    try:
        saved = LEDGER.post(visitor, body.lines, body.note.strip() or "entry", body.confirm_key)
    except InsufficientStock as exc:
        product = parser.find(catalogue(request), getattr(exc, "product_id", None))
        detail = f"{product.name_en}: {exc.available} available." if product and hasattr(exc, "available") else ""
        return error("insufficient_stock", detail)
    except LedgerError as exc:
        return error(exc.code)
    return {**state(visitor), "saved": [m.model_dump() for m in saved]}


@app.post("/api/undo")
def undo(body: UndoIn, request: Request):
    visitor = request.state.visitor
    try:
        LEDGER.undo(visitor, body.movement_id)
    except LedgerError as exc:
        return error(exc.code)
    return state(visitor)


@app.post("/api/ask")
def ask(body: TextIn, request: Request):
    visitor, text = request.state.visitor, body.text.strip()
    if not text or len(text) > MAX_TEXT:
        return error("bad_request")
    limited = QUOTA.take(visitor, client_ip(request))
    if limited:
        return rate_limited(limited)
    try:
        q = questions.classify(text, catalogue(request))
    except ModelUnavailable:
        return error("model_unavailable")
    today = LEDGER.today(visitor, datetime.now(timezone.utc).date())
    return {"intent": q.intent.value, **questions.answer(q, LEDGER.stock(visitor), today)}


@app.post("/api/products")
def add_product(body: ProductIn, request: Request):
    visitor = request.state.visitor
    try:
        created = LEDGER.add_product(visitor, body.product, body.key)
    except LedgerError as exc:
        return error(exc.code)
    except ValueError:
        return error("bad_request")
    return {**state(visitor), "created": created.model_dump()}


@app.post("/api/reset")
def reset(request: Request):
    visitor = request.state.visitor
    LEDGER.reset(visitor)
    LEDGER.purge_inactive(24)
    return state(visitor)
