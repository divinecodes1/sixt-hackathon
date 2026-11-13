"""Offline tests for final_judge.py: parsing, the number rule, prepare(), and the full 3-call pipeline against a
local mock of an OpenAI-compatible endpoint (no API key, no network).

    python3 -m unittest test_final_judge -v
"""
from __future__ import annotations

import http.server
import json
import os
from pathlib import Path
import re
import threading
import unittest

import final_judge as fj
import run_judge

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY = Path(HERE, "policy.md").read_text(encoding="utf-8")
CRITERION = Path(HERE, "JUDGE1_CRITERION.md").read_text(encoding="utf-8")
DEV = run_judge._jsonl(os.path.join(HERE, "dev_pairs.jsonl"))


class MockLLM(http.server.BaseHTTPRequestHandler):
    """Call 1 flags replies containing 'always'; call 2 confirms if the quote has 'always'; call 3 says PASS."""
    log: list[str] = []
    bodies: list[dict] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        MockLLM.bodies.append(body)
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        reply = re.findall(r'<reply lang="[^"]*">(.*?)</reply>', user, flags=re.S)[-1]
        if system == fj.SYSTEM_CHECK:
            kind = "check"
            bad = "always" in reply
            claim = {"quote": reply[:40], "number_vs_policy": "no_number", "violates_criterion": bad, "reason": "test"}
            if "dropcond" in reply:  # call 1 records a dropped condition but does not call it a violation
                claim["policy_conditions"] = [{"condition": "if not reserved", "status": "dropped"}]
            out = "<json>" + json.dumps({"claims": [claim],
                                         "verdict": "FAIL" if bad else "PASS"}) + "</json>"
        elif system == fj.SYSTEM_VERIFY:
            kind = "verify"
            out = "<json>" + json.dumps({"findings": [{"id": 1, "decision": "confirmed" if "counter" in reply
                                                       else "rejected"}]}) + "</json>"
        else:
            kind = "holistic"
            out = "Fine.\n<verdict>PASS</verdict>"
        MockLLM.log.append(kind)
        last = body["messages"][-1]
        if last["role"] == "assistant" and out.startswith(last["content"]):
            out = out[len(last["content"]):]  # like the real API: only the continuation of a prefill comes back
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
        cls.server.server_close()
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


class Settings(Pipeline):
    """The recipe settings change only what they claim to change; defaults keep the measured behaviour."""
    def setUp(self):
        self.saved = {k: getattr(fj, k) for k in ("PREFILL", "THINKING_BUDGET", "EXAMPLE_STYLE", "NUMBER_RULE_MAX",
                                                   "SECOND_LOOK", "ADJUDICATE")}
        MockLLM.bodies.clear()

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(fj, k, v)
        fj.prepare(CRITERION, POLICY, DEV)

    def test_defaults_unchanged(self):
        self.assertEqual(self.saved, {"PREFILL": False, "THINKING_BUDGET": 0, "EXAMPLE_STYLE": "single",
                                      "NUMBER_RULE_MAX": "verdict", "SECOND_LOOK": False, "ADJUDICATE": False})
        self.assertEqual(self.calls_for("You can extend dropcond at the counter."), ("pass", ["check"]))
        MockLLM.bodies.clear()
        self.calls_for("You can usually extend your rental.")
        body = MockLLM.bodies[0]
        self.assertEqual((body["temperature"], body["messages"][-1]["role"]), (0, "user"))
        self.assertNotIn("thinking", body)

    def test_prefill_sent_and_restored(self):
        fj.PREFILL = True
        self.assertEqual(self.calls_for("You can always extend at the counter."), ("fail", ["check", "verify"]))
        self.assertEqual([b["messages"][-1] for b in MockLLM.bodies], [{"role": "assistant", "content": "<json>"}] * 2)

    def test_thinking_payload(self):
        fj.THINKING_BUDGET = 1024
        self.assertEqual(self.calls_for("You can usually extend your rental."), ("pass", ["check"]))
        body = MockLLM.bodies[0]
        self.assertEqual(body["thinking"], {"type": "enabled", "budget_tokens": 1024})
        self.assertNotIn("temperature", body)
        self.assertEqual(body["max_tokens"], fj.MAX_TOKENS + 1024)
        self.assertEqual(body["messages"][-1]["role"], "user")

    def test_contrast_examples(self):
        fj.EXAMPLE_STYLE = "contrast"
        fj.prepare(CRITERION, POLICY, DEV)
        text = fj.CONFIG["examples_text"]
        self.assertIn("<reply_a", text)
        self.assertIn("<label_b>FAIL</label_b>", text)
        self.assertEqual(self.calls_for("You can usually extend your rental."), ("pass", ["check"]))

    def test_number_rule_cap(self):
        fj.NUMBER_RULE_MAX = "hint"
        fj.prepare(CRITERION, POLICY, DEV)
        self.assertEqual(fj.CONFIG["number_rule"], "hint")
        verdict, calls = self.calls_for("You can return the car up to 40 minutes late.")
        self.assertEqual(calls, ["check"])
        self.assertIn("<code_check>", MockLLM.bodies[0]["messages"][1]["content"])


class ReviewFixes(Settings):
    """Fixes from the staff review: value-based overturn, example fill, second look, adjudication, trace."""
    def test_overturn_matches_value_not_substring(self):
        claim = {"quote": "a fee of 190 euros", "number_vs_policy": "same", "violates_criterion": False}
        self.assertFalse(fj._rule_overturned({"claims": [claim]}, ["19"]))
        self.assertTrue(fj._rule_overturned({"claims": [claim]}, ["190"]))

    def test_examples_fill_without_edit_type(self):
        pairs = [{k: v for k, v in c.items() if k != "edit_type"} for c in DEV]
        self.assertEqual(len(fj._pick_examples(pairs)), min(fj.MAX_EXAMPLES, len(pairs)))

    def test_second_look_rejects(self):
        fj.SECOND_LOOK = True
        self.assertEqual(self.calls_for("You can extend dropcond in the app."), ("pass", ["check", "verify"]))
        self.assertIn("<findings>", MockLLM.bodies[1]["messages"][1]["content"])

    def test_second_look_confirms_goes_to_tiebreak(self):
        fj.SECOND_LOOK = True
        self.assertEqual(self.calls_for("You can extend dropcond at the counter."),
                         ("pass", ["check", "verify", "holistic"]))

    def test_adjudicate_sends_dispute(self):
        fj.ADJUDICATE = True
        self.calls_for("You can always extend in the app.")
        self.assertIn("<dispute>", MockLLM.bodies[-1]["messages"][1]["content"])
        fj.ADJUDICATE = False
        self.calls_for("You can always extend in the app.")
        self.assertNotIn("<dispute>", MockLLM.bodies[-1]["messages"][1]["content"])

    def test_trace_written_only_when_set(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "trace.jsonl")
            os.environ["JUDGE_TRACE"] = path
            try:
                self.calls_for("You can always extend in the app.")
            finally:
                os.environ.pop("JUDGE_TRACE")
            with open(path, encoding="utf-8") as f:
                row = json.load(f)
            self.assertEqual((row["path"], row["calls"], row["verdict"]), ("verify_rejects>tiebreak", 3, "pass"))
            self.assertNotIn("always", json.dumps(row))  # reply text is hashed, not logged


if __name__ == "__main__":
    unittest.main()
