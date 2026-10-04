"""One door to the model. Gemma either runs locally (Ollama) or on Cloudflare Workers AI.

The rest of the app calls `generate_json(system, user, schema_model)` and gets back a
validated Pydantic object, whichever backend is configured. No other module knows
which backend is in use.
"""
import json
import os
import re
import time
from typing import Optional, Type, TypeVar

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()  # local .env, if present; real environment variables win
T = TypeVar("T", bound=BaseModel)

BACKEND = os.environ.get("MODEL_BACKEND", "ollama")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
CF_MODEL = os.environ.get("CF_MODEL", "@cf/google/gemma-4-26b-a4b-it")
TIMEOUT = float(os.environ.get("MODEL_TIMEOUT", "60"))


class ModelUnavailable(Exception):
    """The backend could not be reached, or never produced valid output."""


def backend_name() -> str:
    return "Gemma 4 on Cloudflare Workers AI" if BACKEND == "cloudflare" else "Gemma 4 on this machine (Ollama)"


def _extract_json(text: str) -> str:
    # Models sometimes wrap JSON in ``` fences or add a sentence; take the outermost object.
    match = re.search(r"\{.*\}", text, re.S)
    return match.group(0) if match else text


def _call_ollama(messages: list, schema: dict) -> str:
    resp = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": False,
              "format": schema, "options": {"temperature": 0}},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _call_cloudflare(messages: list, schema: dict) -> str:
    account = os.environ["CF_ACCOUNT_ID"].strip()
    token = os.environ["CF_API_TOKEN"].strip()
    resp = httpx.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{CF_MODEL}",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": messages, "temperature": 0, "max_completion_tokens": 600,
              # Gemma 4 thinks by default; the reasoning would eat the token budget. Off.
              "chat_template_kwargs": {"enable_thinking": False},
              "response_format": {"type": "json_schema", "json_schema": schema}},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()
    result = body.get("result", body)
    if isinstance(result, dict) and "choices" in result:
        content = result["choices"][0]["message"]["content"]
    else:
        content = result.get("response") if isinstance(result, dict) else result
    # With JSON mode some models return the object itself rather than a string.
    return content if isinstance(content, str) else json.dumps(content)


def generate_json(system: str, user: str, schema_model: Type[T], retries: int = 1) -> T:
    """Ask Gemma for JSON matching `schema_model`. Validates; retries once on bad output."""
    schema = schema_model.model_json_schema()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    call = _call_cloudflare if BACKEND == "cloudflare" else _call_ollama
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            raw = call(messages, schema)
        except (httpx.HTTPError, KeyError) as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
            continue
        try:
            return schema_model.model_validate_json(_extract_json(raw))
        except ValidationError as exc:
            last_error = exc
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "That was not valid. Reply with only the JSON object."},
            ]
    raise ModelUnavailable(str(last_error))
