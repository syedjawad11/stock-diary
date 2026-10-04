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
    assert "Laal mirch" in res["answer_en"]
    assert "3" in res["answer_en"]


def test_empty_text_rejected(client):
    assert client.post("/api/parse", json={"text": "  "}).status_code == 400


# --- Hamza Mart upgrade: private products, manual entries, unit check, restock ---

NEW = {"name_en": "Shan biryani masala", "name_ur": "شان بریانی مصالحہ", "aliases": ["biryani masala"],
       "unit": "packet", "low_threshold": 4}


def create(client, key="create-key-1", product=None):
    return client.post("/api/products", json={"key": key, "product": product or NEW})


def test_create_product_is_private_and_idempotent(client):
    r = create(client)
    assert r.status_code == 200
    pid = r.json()["created"]["id"]
    assert pid.startswith("custom-") and stock_of(r.json(), pid) == 0
    again = create(client).json()
    assert [row["product"]["id"] for row in again["stock"]].count(pid) == 1
    other = TestClient(main.app)
    assert pid not in {row["product"]["id"] for row in other.get("/api/state").json()["stock"]}
    body = {"confirm_key": "steal-key-1", "lines": [{"product_id": pid, "qty": 1, "direction": "in"}]}
    assert other.post("/api/confirm", json=body).json()["error"] == "unknown_product"


def test_duplicate_and_invalid_products_rejected(client):
    create(client)
    assert create(client, key="create-key-2").json()["error"] == "duplicate_product"
    bad = dict(NEW, name_en="Something", unit="litre")
    r = create(client, key="create-key-3", product=bad)
    assert r.status_code == 400 and r.json()["error"] == "bad_request"
    r = create(client, key="create-key-4", product=dict(NEW, name_en="Other", low_threshold=-1))
    assert r.status_code == 400


def test_manual_add_remove_on_new_product_and_parse_sees_it(client, monkeypatch):
    pid = create(client).json()["created"]["id"]
    add = {"confirm_key": "manual-add-1", "lines": [{"product_id": pid, "qty": 10, "direction": "in"}], "note": "manual add"}
    assert stock_of(client.post("/api/confirm", json=add).json(), pid) == 10
    over = {"confirm_key": "manual-out-1", "lines": [{"product_id": pid, "qty": 11, "direction": "out"}]}
    assert client.post("/api/confirm", json=over).status_code == 409
    frac = {"confirm_key": "manual-out-2", "lines": [{"product_id": pid, "qty": 2.5, "direction": "out"}]}
    assert client.post("/api/confirm", json=frac).status_code == 400
    seen = {}

    def fake(system, user, model):
        seen["system"] = system
        return ParseResult(lines=[ParsedLine(product_text="biryani masala", product_id=pid, qty=3, direction=Direction.OUT)])
    monkeypatch.setattr(parse, "generate_json", fake)
    p = client.post("/api/parse", json={"text": "3 biryani masala nikle"}).json()["proposals"][0]
    assert pid in seen["system"]
    assert (p["product_id"], p["balance_before"], p["balance_after"], p["problem"]) == (pid, 10, 7, None)
    assert client.post("/api/reset").json() and pid not in {
        r["product"]["id"] for r in client.get("/api/state").json()["stock"]}


def test_unit_mismatch_flagged(client, monkeypatch):
    stub_parse(monkeypatch, [ParsedLine(product_text="laal mirch", product_id="red-chilli-powder", qty=5,
                                        unit="bags", direction=Direction.IN)])
    p = client.post("/api/parse", json={"text": "5 bags laal mirch aaye"}).json()["proposals"][0]
    assert p["problem"] == "unit_mismatch" and p["unit"] == "packet"
    stub_parse(monkeypatch, [ParsedLine(product_text="laal mirch", product_id="red-chilli-powder", qty=5,
                                        unit="packets", direction=Direction.IN)])
    p = client.post("/api/parse", json={"text": "5 packets laal mirch aaye"}).json()["proposals"][0]
    assert p["problem"] is None


def test_rate_limit_scope(client, monkeypatch):
    stub_parse(monkeypatch, [ParsedLine(product_text="tea", product_id="black-tea", qty=1, direction=Direction.IN)])
    for _ in range(3):
        client.post("/api/parse", json={"text": "1 chai aayi"})
    assert client.post("/api/parse", json={"text": "1 chai aayi"}).json()["scope"] == "minute"
    monkeypatch.setattr(main, "PER_DAY", 3)
    assert client.post("/api/parse", json={"text": "1 chai aayi"}).json()["scope"] == "day"


def test_ask_restock_numbers_from_code(client, monkeypatch):
    monkeypatch.setattr(questions, "generate_json", lambda s, u, m: Question(intent=Intent.RESTOCK))
    res = client.post("/api/ask", json={"text": "kal kya mangwana hai"}).json()
    assert res["intent"] == "restock"
    mirch = next(i for i in res["items"] if i["product_id"] == "red-chilli-powder")
    assert (mirch["qty"], mirch["min_order"]) == (3, 5)  # threshold 7: needs 8 to clear


def test_unit_mismatch_kept_when_stock_is_short(client, monkeypatch):
    stub_parse(monkeypatch, [ParsedLine(product_text="laal mirch", product_id="red-chilli-powder", qty=5,
                                        unit="bags", direction=Direction.OUT)])
    p = client.post("/api/parse", json={"text": "5 bags laal mirch nikle"}).json()["proposals"][0]
    assert p["problem"] == "insufficient_stock" and p["unit_mismatch"] is True and p["stated_unit"] == "bags"


def test_product_removed_during_parse_is_a_clean_error(client, monkeypatch):
    pid = create(client).json()["created"]["id"]

    def reset_mid_parse(system, user, model):
        client.post("/api/reset")
        return ParseResult(lines=[ParsedLine(product_text="biryani masala", product_id=pid, qty=1, direction=Direction.IN)])
    monkeypatch.setattr(parse, "generate_json", reset_mid_parse)
    r = client.post("/api/parse", json={"text": "1 biryani masala aaya"})
    assert r.status_code in (200, 422)
    if r.status_code == 200:  # resolve() dropped the stale id
        assert r.json()["proposals"][0]["problem"] == "unknown_product"
