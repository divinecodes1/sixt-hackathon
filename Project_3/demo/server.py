"""Live demo of team Divinecodes' Project 3 judge: the real final_judge.py, one reply at a time, every step visible.

    python3 Project_3/demo/server.py            # real claude-haiku-4.5 via Project_3/.env (key stays on this server)
    python3 Project_3/demo/server.py --mock     # UI rehearsal with the unit tests' fake LLM: NOT real verdicts
    open http://127.0.0.1:8765

What it shows: the deterministic number rule, every LLM call (parsed JSON, latency), the decision path and the final
verdict, for the original and the edited reply of a labelled case, each judged on its own as in run_judge.py. When a
dev case is judged, its own source reply is left out of the few-shot examples, like grouped cross-validation.

Rules kept: final_judge.py is imported unchanged; the demo only wraps its LLM client to record calls. The API key is
read from the environment or Project_3/.env, never sent to the browser, never logged. Binds to 127.0.0.1 only.
Stdlib only.
"""
from __future__ import annotations

import argparse
import glob
import http.server
import json
import os
import re
import sys
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
P3 = os.path.dirname(HERE)
STARTER = os.path.join(P3, "starter_pack")
RESULTS = os.path.join(P3, "results")
sys.path.insert(0, STARTER)


def _load_env(path: str) -> None:
    """KEY=value lines; values already in the environment win. Nothing is printed."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$", line)
            if m and not line.lstrip().startswith("#") and m[2] and not os.environ.get(m[1]):
                os.environ[m[1]] = m[2].strip("'\"")


def _redact(msg: str) -> str:
    """Never show a secret in an error: mask the key and gateway values, and any sk- style token."""
    for name in ("JUDGE_LLM_API_KEY", "JUDGE_LLM_BASE_URL"):
        v = os.environ.get(name, "")
        if len(v) >= 6:
            msg = msg.replace(v, f"[{name}]")
    return re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "[redacted]", msg)


def _jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


CRITERIA = {
    "c1": ("Criterion 1 · over-promise", os.path.join(STARTER, "JUDGE1_CRITERION.md"),
           os.path.join(STARTER, "dev_pairs.jsonl"), os.path.join(STARTER, "dev_pairs.jsonl")),
    "c2": ("Criterion 2 · states the policy correctly", os.path.join(P3, "criterion2/CRITERION.md"),
           os.path.join(P3, "criterion2/c2_dev_pairs.jsonl"), os.path.join(P3, "criterion2/c2_dev_pairs.jsonl")),
    "mock_numbers": ("Mock · wrong numbers", os.path.join(P3, "mock_criteria/numbers/CRITERION.md"),
                     os.path.join(P3, "mock_criteria/numbers/c2_dev_pairs.jsonl"),
                     os.path.join(P3, "mock_criteria/numbers/eval_pairs.jsonl")),
    "mock_filler": ("Mock · filler and pleasantries", os.path.join(P3, "mock_criteria/filler/CRITERION.md"),
                    os.path.join(P3, "mock_criteria/filler/c2_dev_pairs.jsonl"),
                    os.path.join(P3, "mock_criteria/filler/eval_pairs.jsonl")),
}
CRITERIA = {k: v for k, v in CRITERIA.items() if all(os.path.exists(p) for p in v[1:])}

MAX_REQUEST_BYTES = 100_000
MAX_QUESTION_CHARS = 5_000
MAX_REPLY_CHARS = 20_000
MAX_LANG_CHARS = 16


class Demo:
    def __init__(self) -> None:
        import final_judge as fj
        self.fj = fj
        self.policy = _read(os.path.join(STARTER, "policy.md"))
        self.data = {k: {"name": n, "criterion": _read(c), "dev": _jsonl(d), "cases": _jsonl(e)}
                     for k, (n, c, d, e) in CRITERIA.items()}
        self.lock = threading.Lock()  # prepare() sets module state: one judgment at a time
        self.prepared: tuple | None = None
        self.calls: list[dict] = []
        self.path = ""
        self._wrap()

    def _wrap(self) -> None:
        fj, demo = self.fj, self
        roles = {fj.SYSTEM_CHECK: "check", fj.SYSTEM_VERIFY: "verify", fj.SYSTEM_HOLISTIC: "holistic"}
        real_chat, real_trace = fj._chat, fj._trace

        def chat(system, user, prefill="", thinking=0):
            t0 = time.time()
            text = real_chat(system, user, prefill=prefill, thinking=thinking)
            role = roles.get(system, "other")
            if role == "verify" and "<findings>" in user and fj.SECOND_LOOK_INSTRUCTIONS[:40] in user:
                role = "second_look"
            if role == "holistic" and "<dispute>" in user:
                role = "adjudicate"
            parsed = json.loads(json.dumps(_quiet_json(text))) if role != "holistic" and role != "adjudicate" else None
            demo.calls.append({"role": role, "ms": round((time.time() - t0) * 1000), "json": parsed,
                               "text": text[-4000:],
                               "verdict": _quiet_verdict(text) if role in ("holistic", "adjudicate") else None})
            return text

        def trace(t, path, verdict):
            demo.path = path
            return real_trace(t, path, verdict)

        def _quiet_json(text):
            m = re.findall(r"<json>(.*?)</json>", text, flags=re.S) or re.findall(r"(\{.*\})", text, flags=re.S)
            for chunk in reversed(m):
                try:
                    return json.loads(chunk)
                except ValueError:
                    continue
            return None

        def _quiet_verdict(text):
            m = re.findall(r"<verdict>\s*(PASS|FAIL)\s*</verdict>", text, flags=re.I)
            return m[-1].upper() if m else None

        fj._chat, fj._trace = chat, trace

    def _prepare(self, cid: str, exclude_source: str | None) -> int:
        key = (cid, exclude_source)
        dev = [c for c in self.data[cid]["dev"] if c.get("source_id") != exclude_source]
        if self.prepared != key:
            self.fj.prepare(self.data[cid]["criterion"], self.policy, dev)
            self.prepared = key
        return self.fj.CONFIG["examples_text"].count("<example ")

    def judge(self, body: dict) -> dict:
        if not isinstance(body, dict):
            return {"error": "request body must be a JSON object"}
        cid = body.get("c") if body.get("c") in self.data else "c1"
        question, reply, lang = str(body.get("question", "")), str(body.get("reply", "")), str(body.get("lang", "en"))
        if not reply.strip():
            return {"error": "empty reply"}
        if len(question) > MAX_QUESTION_CHARS:
            return {"error": f"question exceeds {MAX_QUESTION_CHARS} characters"}
        if len(reply) > MAX_REPLY_CHARS:
            return {"error": f"reply exceeds {MAX_REPLY_CHARS} characters"}
        if len(lang) > MAX_LANG_CHARS or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", lang):
            return {"error": "invalid language code"}
        fj = self.fj
        with self.lock:
            n_examples = self._prepare(cid, body.get("source_id") or None)
            mode = fj.CONFIG["number_rule"]
            rule = {"mode": mode,
                    "numbers": [{"tok": t, "value": v, "in_policy": v in fj.CONFIG["policy_numbers"]}
                                for t, v in fj.numbers_in(reply)],
                    "unknown": fj.unknown_numbers(reply, fj.CONFIG["policy_numbers"]) if mode != "off" else []}
            self.calls, self.path = [], ""
            t0 = time.time()
            out = {"rule": rule, "examples": n_examples, "excluded_source": body.get("source_id") or None}
            try:
                out["verdict"] = fj.judge(question, reply, lang, self.data[cid]["criterion"], self.policy)
            except Exception as e:  # noqa: BLE001 - shown in the UI; an outage is not a verdict
                out["error"] = _redact(f"{type(e).__name__}: {e}")
            out.update(calls=self.calls, path=self.path, ms=round((time.time() - t0) * 1000))
            return out

    def state(self, mock: bool) -> dict:
        fj = self.fj
        settings = {k: getattr(fj, k) for k in ("NUMBER_RULE_MAX", "EXAMPLE_STYLE", "PREFILL", "THINKING_BUDGET",
                                                 "SECOND_LOOK", "ADJUDICATE")}
        return {"model": os.environ.get("JUDGE_LLM_MODEL", ""), "mock": mock,
                "key": bool(os.environ.get("JUDGE_LLM_API_KEY") and os.environ.get("JUDGE_LLM_BASE_URL")),
                "cache": bool(os.environ.get("JUDGE_LLM_CACHE")), "settings": settings, "policy": self.policy,
                "criteria": [{"id": k, "name": v["name"], "criterion": v["criterion"], "cases": len(v["cases"]),
                              "dev": len(v["dev"])} for k, v in self.data.items()]}

    def cases(self, cid: str) -> list[dict]:
        keep = ("case_id", "source_id", "lang", "orig_lang", "question_original", "question", "original", "edited",
                "edit_type", "edit_family", "original_label", "edited_label", "edit_note")
        return [{k: c.get(k) for k in keep} for c in self.data.get(cid, self.data["c1"])["cases"]]


def _report(path: str) -> dict | None:
    txt = _read(path)
    get = lambda pat: (lambda m: float(m[1]) if m else None)(re.search(pat, txt))  # noqa: E731
    combined = get(r"COMBINED \(the score\)\s+([\d.]+)")
    if combined is None:
        return None
    types = {}
    for m in re.finditer(r"^\s{2}(\w+)\s+(\d+)\s+([\d.]+|n/a)\s+([\d.]+|n/a)", txt, flags=re.M):
        types[m[1]] = {"n": int(m[2]), "catch": None if m[3] == "n/a" else float(m[3]),
                       "keep": None if m[4] == "n/a" else float(m[4])}
    return {"file": os.path.relpath(path, P3), "title": txt.splitlines()[0][:120], "combined": combined,
            "catch": get(r"macro catch\s+([\d.]+)"), "keep": get(r"macro keep\s+([\d.]+)"),
            "kappa": get(r"kappa vs construction\s+(-?[\d.]+)"), "same": get(r"same verdict ([\d.]+)"),
            "types": types, "mtime": os.path.getmtime(path)}


def results() -> dict:
    reports = [r for r in (_report(p) for p in sorted(glob.glob(os.path.join(RESULTS, "*report*.txt")))) if r]
    exp = os.path.join(RESULTS, "experiments.md")
    rows = []
    if os.path.exists(exp):
        for line in _read(exp).splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if line.startswith("|") and len(cells) >= 9 and cells[0] not in ("time",) and not set(cells[0]) <= set("-"):
                rows.append(cells)
    return {"baseline": _report(os.path.join(STARTER, "baseline_report.txt")), "reports": reports,
            "experiments": rows}


def make_handler(demo: Demo, mock: bool):
    index = os.path.join(HERE, "index.html")

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "DivinecodesJudgeDemo/1.0"
        sys_version = ""

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
                             "object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                with open(index, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif u.path == "/api/health":
                self._json({"status": "ok", "mode": "mock" if mock else "live",
                            "model_configured": bool(os.environ.get("JUDGE_LLM_MODEL")),
                            "gateway_configured": bool(os.environ.get("JUDGE_LLM_API_KEY") and
                                                       os.environ.get("JUDGE_LLM_BASE_URL"))})
            elif u.path == "/api/state":
                self._json(demo.state(mock))
            elif u.path == "/api/cases":
                self._json(demo.cases(q.get("c", ["c1"])[0]))
            elif u.path == "/api/results":
                self._json(results())
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if urllib.parse.urlparse(self.path).path != "/api/judge":
                return self._send(404, b"not found", "text/plain")
            if self.headers.get_content_type() != "application/json":
                return self._json({"error": "Content-Type must be application/json"}, 415)
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._json({"error": "invalid Content-Length"}, 400)
            if n < 0 or n > MAX_REQUEST_BYTES:
                return self._json({"error": "request too large"}, 413)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._json({"error": "bad JSON"}, 400)
            if not isinstance(body, dict):
                return self._json({"error": "request body must be a JSON object"}, 400)
            result = demo.judge(body)
            self._json(result, 400 if result.get("error") in {
                "empty reply", "invalid language code",
                f"question exceeds {MAX_QUESTION_CHARS} characters",
                f"reply exceeds {MAX_REPLY_CHARS} characters",
            } else 200)

        def log_message(self, fmt, *args):
            sys.stderr.write("demo: " + (fmt % args) + "\n")

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--mock", action="store_true", help="fake LLM from the unit tests (UI rehearsal only)")
    a = ap.parse_args()
    mock_server = None
    if a.mock:
        import test_final_judge as t
        mock_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), t.MockLLM)
        threading.Thread(target=mock_server.serve_forever, daemon=True).start()
        os.environ.update(JUDGE_LLM_BASE_URL=f"http://127.0.0.1:{mock_server.server_port}", JUDGE_LLM_API_KEY="mock",
                          JUDGE_LLM_MODEL="claude-haiku-4.5 (MOCK)")
    else:
        _load_env(os.path.join(P3, ".env"))
    os.environ.pop("JUDGE_LLM_CACHE", None)  # a live demo shows live answers
    demo = Demo()
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(demo, a.mock))
    print(f"Judge demo on http://127.0.0.1:{a.port}  ({'MOCK model' if a.mock else os.environ.get('JUDGE_LLM_MODEL', '?')}"
          f", key {'set' if demo.state(a.mock)['key'] else 'missing'})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        if mock_server is not None:
            mock_server.shutdown()
            mock_server.server_close()


if __name__ == "__main__":
    main()
