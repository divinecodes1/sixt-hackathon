"""What does this LLM endpoint support? About ten small calls, a few thousand tokens in total. Run it first with any new key.

Uses the judge's own variables (JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY, JUDGE_LLM_MODEL). The key is never printed.

    python3 Project_3/dev_tools/probe_gateway.py

It checks: a basic call without temperature and the model id the endpoint reports (must be Haiku 4.5); whether
temperature 0 is accepted (newer Anthropic API versions reject it with HTTP 400); whether 5 identical calls agree; assistant prefill; extended thinking (the THINKING_BUDGET setting needs it); json_schema output.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("JUDGE_LLM_BASE_URL", "").rstrip("/")
KEY = os.environ.get("JUDGE_LLM_API_KEY", "")
MODEL = os.environ.get("JUDGE_LLM_MODEL", "")


def call(payload: dict) -> tuple[int, dict | str, float]:
    payload = {"model": MODEL, **payload}
    req = urllib.request.Request(f"{BASE}/chat/completions", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read()), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200], time.time() - t
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, str(e), time.time() - t


def text(body) -> str:
    return body["choices"][0]["message"]["content"] if isinstance(body, dict) else ""


def main() -> None:
    if not (BASE and KEY and MODEL):
        sys.exit("set JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY and JUDGE_LLM_MODEL first")
    rows = []
    q = [{"role": "user", "content": "A rental policy says: 'Extensions are usually possible if the car is not "
                                     "reserved.' A reply says: 'You can always extend.' In one sentence: does the "
                                     "reply promise more than the policy?"}]

    # 1. Control call WITHOUT temperature: separates key/URL/model problems from a temperature rejection.
    code, body, dt = call({"max_tokens": 60, "messages": q})
    reported = body.get("model") if isinstance(body, dict) else None
    hint = {401: "key refused", 403: "key refused", 404: "wrong base URL or model id", 0: "endpoint unreachable"}
    rows.append(("basic call (no temperature)", code == 200, f"HTTP {code}, {dt:.1f}s"
                 + (f", model reported: {reported}" if code == 200 else f" ({hint.get(code, 'see body')}): {body}")))
    if code != 200:
        print_rows(rows)
        sys.exit(1)
    is_haiku = bool(reported) and "haiku" in reported.lower() and ("4-5" in reported or "4.5" in reported)
    rows.append(("model is Haiku 4.5", is_haiku, f"endpoint reports {reported!r}"))

    # 2. Same call WITH temperature 0: does the gateway accept it?
    code, body, _ = call({"temperature": 0, "max_tokens": 60, "messages": q})
    temp_ok = code == 200
    rejected = code == 400 and "temperature" in str(body).lower()
    rows.append(("temperature 0 accepted", temp_ok, f"HTTP {code}" + ("" if temp_ok else f": {body}")
                 + (" -> the judge resends without temperature automatically; set JUDGE_LLM_OMIT_TEMPERATURE=1 "
                    "to skip the rejected attempt" if rejected else "")))
    temp = {"temperature": 0} if temp_ok else {}

    # 3. Repeatability with the settings the judge will really use. A gateway that silently drops temperature
    #    shows up here as differing answers (sampling at the default temperature).
    n = 5
    outs = [text(call({**temp, "max_tokens": 120, "messages": q})[1]) for _ in range(n)]
    distinct = len(set(outs))
    rows.append((f"repeatable ({'temperature 0' if temp_ok else 'no temperature'})", distinct == 1,
                 f"{distinct} distinct answer(s) in {n} calls"
                 + ("" if distinct == 1 else " (if temperature was accepted, it may be silently ignored)")))

    code, body, _ = call({**temp, "max_tokens": 30, "messages": [
        {"role": "user", "content": 'Answer with JSON {"ok": true}.'}, {"role": "assistant", "content": "<json>"}]})
    t = text(body)
    rows.append(("assistant prefill", code == 200 and not t.lstrip().startswith("I"),
                 f"HTTP {code}, answer starts: {t[:40]!r}" if code == 200 else f"HTTP {code}: {body}"))

    code, body, dt = call({"max_tokens": 1300, "thinking": {"type": "enabled", "budget_tokens": 1024},
                           "messages": q})
    rows.append(("extended thinking", code == 200, f"HTTP {code}, {dt:.1f}s"
                 + ("" if code == 200 else f": {body}")))

    schema = {"type": "object", "properties": {"verdict": {"type": "string", "enum": ["PASS", "FAIL"]}},
              "required": ["verdict"], "additionalProperties": False}
    code, body, _ = call({**temp, "max_tokens": 50, "messages": q, "response_format": {
        "type": "json_schema", "json_schema": {"name": "v", "strict": True, "schema": schema}}})
    rows.append(("json_schema output", code == 200, f"HTTP {code}, answer: {text(body)[:60]!r}"
                 if code == 200 else f"HTTP {code}: {body}"))
    print_rows(rows)


def print_rows(rows) -> None:
    for name, ok, detail in rows:
        print(f"{'OK ' if ok else 'NO '} {name:26} {detail}")


if __name__ == "__main__":
    main()
