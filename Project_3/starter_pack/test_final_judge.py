"""Offline tests for final_judge.py: parsing, the number rule, prepare(), and the full 3-call pipeline against a
local mock of an OpenAI-compatible endpoint (no API key, no network).

    python3 -m unittest test_final_judge -v
"""
from __future__ import annotations

import http.server
import json
import os
import re
import threading
import unittest

import final_judge as fj
import run_judge

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY = open(os.path.join(HERE, "policy.md"), encoding="utf-8").read()
CRITERION = open(os.path.join(HERE, "JUDGE1_CRITERION.md"), encoding="utf-8").read()
DEV = run_judge._jsonl(os.path.join(HERE, "dev_pairs.jsonl"))


class MockLLM(http.server.BaseHTTPRequestHandler):
    """Call 1 flags replies containing 'always'; call 2 confirms if the quote has 'always'; call 3 says PASS."""
    log: list[str] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        reply = re.findall(r'<reply lang="[^"]*">(.*?)</reply>', user, flags=re.S)[-1]
        if system == fj.SYSTEM_CHECK:
            kind = "check"
            bad = "always" in reply
            out = "<json>" + json.dumps({"claims": [{"quote": reply[:40], "number_vs_policy": "no_number",
                                                     "violates_criterion": bad, "reason": "test"}],
                                         "verdict": "FAIL" if bad else "PASS"}) + "</json>"
        elif system == fj.SYSTEM_VERIFY:
            kind = "verify"
            out = "<json>" + json.dumps({"findings": [{"id": 1, "decision": "confirmed" if "counter" in reply
                                                       else "rejected"}]}) + "</json>"
        else:
            kind = "holistic"
            out = "Fine.\n<verdict>PASS</verdict>"
        MockLLM.log.append(kind)
        data = json.dumps({"model": "mock-haiku", "choices": [{"message": {"content": out},
                                                                "finish_reason": "stop"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class Parsing(unittest.TestCase):
    def test_json_last_tagged_block(self):
        self.assertEqual(fj._parse_json('x <json>{"a":1}</json> y <json>{"a":2}</json>'), {"a": 2})
        self.assertEqual(fj._parse_json('```json\n{"a": 3}\n```'), {"a": 3})
        self.assertIsNone(fj._parse_json("no json here"))

    def test_verdict_takes_last(self):
        self.assertEqual(fj._parse_verdict("PASS? no. <verdict>FAIL</verdict>"), "fail")
        self.assertEqual(fj._parse_verdict("reasoning ... FAIL ... final: PASS"), "pass")


class Numbers(unittest.TestCase):
    def test_locale_formats(self):
        self.assertEqual(fj._to_number("1.000,50"), 1000.5)
        self.assertEqual(fj._to_number("1,000"), 1000.0)
        self.assertEqual(fj._to_number("12,5"), 12.5)

    def test_rule_on_policy(self):
        pn = frozenset(v for _, v in fj.numbers_in(POLICY))
        self.assertEqual(fj.unknown_numbers("Up to 29 minutes, 500 EUR.", pn), [])
        self.assertEqual(fj.unknown_numbers("Up to 40 minutes.", pn), ["40"])

    def test_self_validation_modes(self):
        pn = frozenset(v for _, v in fj.numbers_in(POLICY))
        self.assertEqual(fj._validate_number_rule(pn, DEV), "verdict")
        harmless_with_new_number = [{"original": "Open 24/7.", "edited": "Hi! Open 24/7.", "edit_family": "harmless",
                                     "original_label": "pass", "edited_label": "pass"}]
        self.assertEqual(fj._validate_number_rule(pn, DEV + harmless_with_new_number), "off")
        self.assertEqual(fj._validate_number_rule(pn, []), "hint")


class Prepare(unittest.TestCase):
    def test_examples_balanced_and_deterministic(self):
        a = fj._pick_examples(DEV)
        self.assertEqual(a, fj._pick_examples(list(reversed(DEV))))
        self.assertLessEqual(len(a), fj.MAX_EXAMPLES)
        labels = [e["label"] for e in a]
        self.assertIn("FAIL", labels)
        self.assertIn("PASS", labels)


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockLLM)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.env = {k: os.environ.get(k) for k in ("JUDGE_LLM_BASE_URL", "JUDGE_LLM_API_KEY", "JUDGE_LLM_MODEL",
                                                   "JUDGE_LLM_CACHE")}
        os.environ.update(JUDGE_LLM_BASE_URL=f"http://127.0.0.1:{cls.server.server_port}", JUDGE_LLM_API_KEY="x",
                          JUDGE_LLM_MODEL="claude-haiku-4.5")
        os.environ.pop("JUDGE_LLM_CACHE", None)
        fj.prepare(CRITERION, POLICY, DEV)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        for k, v in cls.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def calls_for(self, reply):
        MockLLM.log.clear()
        verdict = fj.judge("Q?", reply, "en", CRITERION, POLICY)
        return verdict, list(MockLLM.log)

    def test_clean_reply_one_call(self):
        self.assertEqual(self.calls_for("You can usually extend your rental."), ("pass", ["check"]))

    def test_confirmed_violation_two_calls(self):
        self.assertEqual(self.calls_for("You can always extend at the counter."), ("fail", ["check", "verify"]))

    def test_rejected_violation_goes_to_tiebreak(self):
        self.assertEqual(self.calls_for("You can always extend in the app."), ("pass", ["check", "verify", "holistic"]))

    def test_number_rule_fails_without_overturn(self):
        verdict, calls = self.calls_for("You can return the car up to 40 minutes late.")
        self.assertEqual((verdict, calls), ("fail", ["check"]))

    def test_never_more_than_three_calls_and_runner_works(self):
        fast = run_judge._jsonl(os.path.join(HERE, "dev_pairs_fast.jsonl"))[:20]
        MockLLM.log.clear()
        res = run_judge.run(os.path.join(HERE, "final_judge.py"), fast, CRITERION, POLICY, DEV, workers=4)
        self.assertEqual(len(res), 20)
        replies = {(c["orig_lang"], c["question_original"], c["original"]) for c in fast} | \
                  {(c["lang"], c["question"], c["edited"]) for c in fast}
        self.assertLessEqual(len(MockLLM.log), 3 * len(replies))


if __name__ == "__main__":
    unittest.main()
