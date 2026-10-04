"""API flow with the model stubbed out: parse -> confirm -> undo, sandboxes, limits."""
import os

os.environ["DB_PATH"] = ":memory:"
os.environ["LIMIT_PER_MINUTE"] = "3"

import pytest
from fastapi.testclient import TestClient

from app import main, parse, questions
from app.models import Direction, Intent, ParsedLine, ParseResult, Question


@pytest.fixture
def client(monkeypatch):
    main.QUOTA.__init__()
    return TestClient(main.app)


def stub_parse(monkeypatch, lines):
    monkeypatch.setattr(parse, "generate_json", lambda system, user, model: ParseResult(lines=lines))


def stock_of(state, pid):
    return next(r["qty"] for r in state["stock"] if r["product"]["id"] == pid)


def test_parse_confirm_undo(client, monkeypatch):
    stub_parse(monkeypatch, [ParsedLine(product_text="basmati", product_id="basmati-5kg", qty=20, direction=Direction.IN),
                             ParsedLine(product_text="basmati", product_id="basmati-5kg", qty=5, direction=Direction.OUT)])
    before = stock_of(client.get("/api/state").json(), "basmati-5kg")
    res = client.post("/api/parse", json={"text": "20 carton basmati aaye, 5 nikle"}).json()
    p = res["proposals"]
    assert [(x["balance_before"], x["balance_after"]) for x in p] == [(before, before + 20), (before + 20, before + 15)]
    lines = [{"product_id": x["product_id"], "qty": x["qty"], "direction": x["direction"]} for x in p]
    body = {"confirm_key": res["confirm_key"], "lines": lines, "note": "test"}
    saved = client.post("/api/confirm", json=body).json()
    assert stock_of(saved, "basmati-5kg") == before + 15
    again = client.post("/api/confirm", json=body).json()  # idempotent
    assert stock_of(again, "basmati-5kg") == before + 15
    undone = client.post("/api/undo", json={"movement_id": saved["saved"][1]["id"]}).json()
    assert stock_of(undone, "basmati-5kg") == before + 20


def test_unknown_product_gets_candidates(client, monkeypatch):
    stub_parse(monkeypatch, [ParsedLine(product_text="chawal", product_id=None, qty=10, direction=Direction.IN)])
    p = client.post("/api/parse", json={"text": "chawal 10 aaye"}).json()["proposals"][0]
    assert p["problem"] == "unknown_product"
    assert {c["id"] for c in p["candidates"]} >= {"basmati-5kg", "sella-rice-25kg"}


def test_model_invented_id_is_dropped(client, monkeypatch):
    stub_parse(monkeypatch, [ParsedLine(product_text="saffron", product_id="saffron-1kg", qty=1, direction=Direction.IN)])
    p = client.post("/api/parse", json={"text": "1 saffron aaya"}).json()["proposals"][0]
    assert p["product_id"] is None and p["problem"] == "unknown_product"


def test_insufficient_stock_rejected(client):
    body = {"confirm_key": "k" * 12, "lines": [{"product_id": "red-chilli-powder", "qty": 999, "direction": "out"}]}
    r = client.post("/api/confirm", json=body)
    assert r.status_code == 409 and r.json()["error"] == "insufficient_stock"


def test_visitors_are_isolated(client):
    other = TestClient(main.app)
    body = {"confirm_key": "iso-key-123", "lines": [{"product_id": "pink-salt", "qty": 5, "direction": "out"}]}
    mine = client.post("/api/confirm", json=body).json()
    theirs = other.get("/api/state").json()
    assert stock_of(theirs, "pink-salt") == stock_of(mine, "pink-salt") + 5


def test_reset_restores_opening_stock(client):
    start = client.get("/api/state").json()
    body = {"confirm_key": "reset-key-1", "lines": [{"product_id": "black-tea", "qty": 4, "direction": "out"}]}
    client.post("/api/confirm", json=body)
    assert client.post("/api/reset").json()["stock"] == start["stock"]


def test_rate_limit_per_minute(client, monkeypatch):
    stub_parse(monkeypatch, [ParsedLine(product_text="tea", product_id="black-tea", qty=1, direction=Direction.IN)])
    codes = [client.post("/api/parse", json={"text": "1 chai aayi"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_ask_low_stock_uses_code_numbers(client, monkeypatch):
    monkeypatch.setattr(questions, "generate_json", lambda s, u, m: Question(intent=Intent.LOW_STOCK))
    res = client.post("/api/ask", json={"text": "kya kam hai"}).json()
    assert "Red Chilli" in res["answer_en"] or "Chilli" in res["answer_en"]
    assert "3" in res["answer_en"]


def test_empty_text_rejected(client):
    assert client.post("/api/parse", json={"text": "  "}).status_code == 400
