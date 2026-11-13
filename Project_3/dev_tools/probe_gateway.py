"""What does this LLM endpoint support? Five small calls, about 2,000 tokens in total. Run it first with any new key.

Uses the judge's own variables (JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY, JUDGE_LLM_MODEL). The key is never printed.

    python3 Project_3/dev_tools/probe_gateway.py

It checks: a basic call and the model id the endpoint reports; whether temperature 0 gives the same answer three
times; assistant prefill; extended thinking (the THINKING_BUDGET setting needs it); json_schema output.
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

    code, body, dt = call({"temperature": 0, "max_tokens": 60, "messages": q})
    rows.append(("basic call", code == 200, f"HTTP {code}, {dt:.1f}s, model reported: "
                 f"{body.get('model') if isinstance(body, dict) else body}"))
    if code != 200:
        print_rows(rows)
        sys.exit(1)

    outs = [text(call({"temperature": 0, "max_tokens": 60, "messages": q})[1]) for _ in range(3)]
    same = len(set(outs)) == 1
    rows.append(("temperature 0 repeatable", same, f"{len(set(outs))} distinct answer(s) in 3 calls"))

    code, body, _ = call({"temperature": 0, "max_tokens": 30, "messages": [
        {"role": "user", "content": 'Answer with JSON {"ok": true}.'}, {"role": "assistant", "content": "<json>"}]})
    t = text(body)
    rows.append(("assistant prefill", code == 200 and not t.lstrip().startswith("I"),
                 f"HTTP {code}, answer starts: {t[:40]!r}"))

    code, body, dt = call({"max_tokens": 1300, "thinking": {"type": "enabled", "budget_tokens": 1024},
                           "messages": q})
    rows.append(("extended thinking", code == 200, f"HTTP {code}, {dt:.1f}s"
                 + ("" if code == 200 else f": {body}")))

    schema = {"type": "object", "properties": {"verdict": {"type": "string", "enum": ["PASS", "FAIL"]}},
              "required": ["verdict"], "additionalProperties": False}
    code, body, _ = call({"temperature": 0, "max_tokens": 50, "messages": q, "response_format": {
        "type": "json_schema", "json_schema": {"name": "v", "strict": True, "schema": schema}}})
    rows.append(("json_schema output", code == 200, f"HTTP {code}, answer: {text(body)[:60]!r}"
                 if code == 200 else f"HTTP {code}: {body}"))
    print_rows(rows)


def print_rows(rows) -> None:
    for name, ok, detail in rows:
        print(f"{'OK ' if ok else 'NO '} {name:26} {detail}")


if __name__ == "__main__":
    main()
