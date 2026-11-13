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

    reject_temperature = False   # behave like Anthropic API version 2026-10-21: temperature -> HTTP 400
    fail_statuses: list[int] = []  # statuses to return (once each) before answering normally

    def _error(self, status: int, message: str):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": {"type": "invalid_request_error", "message": message}}).encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        MockLLM.bodies.append(body)
        if MockLLM.fail_statuses:
            return self._error(MockLLM.fail_statuses.pop(0), "overloaded")
        if MockLLM.reject_temperature and "temperature" in body:
            return self._error(400, "temperature: this parameter is not supported for this API version")
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        reply = re.findall(r'<reply lang="[^"]*">(.*?)</reply>', user, flags=re.S)[-1]
        if system == fj.SYSTEM_CHECK:
            kind = "check"
            bad = "always" in reply
            claim = {"quote": reply[:40], "number_vs_policy": "no_number", "violates_criterion": bad, "reason": "test"}
            if "dropcond" in reply:  # call 1 records a dropped condition but does not call it a violation
                claim["policy_conditions"] = [{"condition": "if not reserved", "status": "dropped"}]
            if "noevidence" in reply:  # "kept" without words of the reply to show for it
                claim["policy_conditions"] = [{"condition": "if not reserved", "status": "kept", "evidence": ""}]
            if "withevidence" in reply:  # "kept", quoting the reply (with different case and spacing)
                claim["policy_conditions"] = [{"condition": "if not reserved", "status": "kept",
                                               "evidence": "  IF THE CAR  is not reserved"}]
            if "badclause" in reply:
                claim.update(clause_id="C3", policy_rule="free upgrades are always guaranteed")
            if "goodclause" in reply:
                cid = next(k for k, v in fj.CONFIG["clauses"].items() if "Grace period" in v)
                claim.update(clause_id=cid, policy_rule="grace period of 29 minutes")
            out = "<json>" + json.dumps({"claims": [claim],
                                         "verdict": "FAIL" if bad else "PASS"}) + "</json>"
        elif system == fj.SYSTEM_VERIFY:
            kind = "verify"
            words = "words that are not in the reply at all" if "fakequote" in reply else reply[:25]
            out = "<json>" + json.dumps({"findings": [{"id": 1, "decision": "confirmed" if "counter" in reply
                                                       else "rejected", "reply_words": words,
                                                       "situation": "a customer at a branch where it is not possible"}]}) + "</json>"
        elif system == fj.SYSTEM_VERIFY_NEUTRAL:
            kind = "verify"
            out = "<json>" + json.dumps({"findings": [{"id": 1, "decision": "violation" if "counter" in reply
                                                       else "no_violation"}]}) + "</json>"
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
                                                   "SECOND_LOOK", "ADJUDICATE", "CONDITION_EVIDENCE", "CLAUSE_IDS",
                                                   "HEDGE_FROM_QUOTE", "VERIFY_DEANCHOR", "VERIFY_EXAMPLES",
                                                   "VERIFY_WITNESS", "VERIFY_SCOPED")}
        MockLLM.bodies.clear()

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(fj, k, v)
        fj.prepare(CRITERION, POLICY, DEV)

    def test_defaults_unchanged(self):
        self.assertEqual(self.saved, {"PREFILL": False, "THINKING_BUDGET": 0, "EXAMPLE_STYLE": "single",
                                      "NUMBER_RULE_MAX": "verdict", "SECOND_LOOK": False, "ADJUDICATE": False,
                                      "CONDITION_EVIDENCE": False, "CLAUSE_IDS": False, "HEDGE_FROM_QUOTE": False,
                                      "VERIFY_DEANCHOR": False, "VERIFY_EXAMPLES": False,
                                      "VERIFY_WITNESS": True, "VERIFY_SCOPED": False})  # W shipped 12:25 (dev 0.850 x3)
        self.assertEqual(fj._check_instructions(), fj.CHECK_INSTRUCTIONS)
        self.assertEqual(fj._verify_instructions(), fj.VERIFY_WITNESS_INSTRUCTIONS)
        self.assertEqual(self.calls_for("You can extend dropcond at the counter."), ("pass", ["check"]))
        MockLLM.bodies.clear()
        self.calls_for("You can usually extend your rental.")
        body = MockLLM.bodies[0]
        self.assertEqual((body["temperature"], body["messages"][-1]["role"]), (0, "user"))
        self.assertNotIn("thinking", body)

    def test_verify_examples_switch(self):
        self.assertEqual(self.calls_for("You can always extend at the counter."), ("fail", ["check", "verify"]))
        self.assertNotIn("<examples>", MockLLM.bodies[1]["messages"][1]["content"])  # default: call 2 sees none
        fj.VERIFY_EXAMPLES = True
        MockLLM.bodies.clear()
        self.assertEqual(self.calls_for("You can always extend at the counter."), ("fail", ["check", "verify"]))
        self.assertIn("<examples>", MockLLM.bodies[1]["messages"][1]["content"])

    def test_verify_witness_switch(self):
        fj.VERIFY_WITNESS = False
        self.assertEqual(self.calls_for("You can always extend fakequote at the counter."), ("fail", ["check", "verify"]))
        self.assertNotIn("reply_words", MockLLM.bodies[1]["messages"][1]["content"])  # default prompt unchanged
        fj.VERIFY_WITNESS = True
        MockLLM.bodies.clear()
        self.assertEqual(self.calls_for("You can always extend at the counter."), ("fail", ["check", "verify"]))
        self.assertIn("reply_words", MockLLM.bodies[1]["messages"][1]["content"])
        # a confirm whose quoted words are not in the reply is treated as a rejection: call 3 decides (mock: PASS)
        self.assertEqual(self.calls_for("You can always extend fakequote at the counter."),
                         ("pass", ["check", "verify", "holistic"]))

    def test_scoped_applies_to_witness_prompt(self):
        """VERIFY_SCOPED must not be a silent no-op now that the witness prompt is the default."""
        fj.VERIFY_WITNESS, fj.VERIFY_SCOPED = True, True
        self.calls_for("You can always extend at the counter.")
        content = MockLLM.bodies[1]["messages"][1]["content"]
        self.assertIn(fj.VERIFY_SCOPED_NOTE, content)
        self.assertIn("reply_words", content)

    def test_trace_logs_unwitnessed_confirms(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "trace.jsonl")
        old = {k: os.environ.get(k) for k in ("JUDGE_TRACE", "JUDGE_TRACE_REASONS")}
        try:
            os.environ.update(JUDGE_TRACE=path, JUDGE_TRACE_REASONS="1")
            fj.VERIFY_WITNESS = True
            self.calls_for("You can always extend fakequote at the counter.")
            row = json.loads(open(path, encoding="utf-8").readline())
            self.assertEqual([d["decision"] for d in row["verify"]], ["rejected_unwitnessed"])
        finally:
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def test_verify_scoped_switch(self):
        fj.VERIFY_WITNESS = False  # the scoped note applies to the plain verify prompt
        self.assertEqual(self.calls_for("You can always extend at the counter."), ("fail", ["check", "verify"]))
        self.assertNotIn(fj.VERIFY_SCOPED_NOTE, MockLLM.bodies[1]["messages"][1]["content"])  # default unchanged
        fj.VERIFY_SCOPED = True
        MockLLM.bodies.clear()
        self.assertEqual(self.calls_for("You can always extend at the counter."), ("fail", ["check", "verify"]))
        content = MockLLM.bodies[1]["messages"][1]["content"]
        self.assertIn(fj.VERIFY_SCOPED_NOTE, content)
        self.assertTrue(content.rstrip().endswith("</json>"))  # answer format still last

    def test_trace_reasons_opt_in(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "trace.jsonl")
        old = {k: os.environ.get(k) for k in ("JUDGE_TRACE", "JUDGE_TRACE_REASONS")}
        try:
            os.environ["JUDGE_TRACE"] = path
            os.environ.pop("JUDGE_TRACE_REASONS", None)
            self.calls_for("You can always extend at the counter.")
            os.environ["JUDGE_TRACE_REASONS"] = "1"
            self.calls_for("You can always extend at the counter.")
            rows = [json.loads(line) for line in open(path, encoding="utf-8")]
            self.assertNotIn("findings", rows[0])  # default trace: no reply text
            self.assertEqual(rows[1]["verdict"], rows[0]["verdict"])  # diagnostics never change the verdict
            self.assertTrue(rows[1]["findings"] and rows[1]["verify"])
        finally:
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

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


class Transport(Pipeline):
    """Gateway behaviour that must never abort a run or change the number of LLM calls."""

    def setUp(self):
        self._wait = fj._bj._wait
        fj._bj._wait = lambda attempt, retry_after: 0
        MockLLM.bodies.clear()

    def tearDown(self):
        fj._bj._wait = self._wait
        MockLLM.reject_temperature = False
        MockLLM.fail_statuses = []
        os.environ.pop("JUDGE_LLM_OMIT_TEMPERATURE", None)

    def test_temperature_sent_by_default(self):
        self.calls_for("You can usually extend your rental.")
        self.assertEqual(MockLLM.bodies[0]["temperature"], 0)

    def test_temperature_rejected_is_resent_without_it(self):
        MockLLM.reject_temperature = True
        before = fj.STATS["temperature_dropped"]
        self.assertEqual(self.calls_for("You can usually extend your rental."), ("pass", ["check"]))
        self.assertEqual([("temperature" in b) for b in MockLLM.bodies], [True, False])
        self.assertEqual(fj.STATS["temperature_dropped"], before + 1)

    def test_omit_temperature_env(self):
        os.environ["JUDGE_LLM_OMIT_TEMPERATURE"] = "1"
        MockLLM.reject_temperature = True
        self.assertEqual(self.calls_for("You can usually extend your rental."), ("pass", ["check"]))
        self.assertEqual(len(MockLLM.bodies), 1)
        self.assertNotIn("temperature", MockLLM.bodies[0])

    def test_overloaded_and_timeout_are_retried(self):
        MockLLM.fail_statuses = [529, 408]
        self.assertEqual(self.calls_for("You can usually extend your rental."), ("pass", ["check"]))
        self.assertEqual(len(MockLLM.bodies), 3)

    def test_other_400_still_fails_fast(self):
        MockLLM.fail_statuses = [400]
        with self.assertRaises(fj._bj.LLMError):
            fj.judge("Q?", "You can usually extend your rental.", "en", CRITERION, POLICY)
        self.assertEqual(len(MockLLM.bodies), 1)


class EvidenceSwitches(Settings):
    """CONDITION_EVIDENCE, CLAUSE_IDS, HEDGE_FROM_QUOTE, VERIFY_DEANCHOR (all default off)."""

    def test_quote_found(self):
        self.assertTrue(fj.quote_found("  IF THE CAR  is not reserved", "Yes, if the car is not reserved."))
        self.assertTrue(fj.quote_found("sofern das Auto nicht reserviert ist", "Ja, sofern das Auto nicht reserviert ist."))
        self.assertTrue(fj.quote_found("as long as the car is not reservd", "as long as the car is not reserved"))
        self.assertFalse(fj.quote_found("if the car is not reserved", "You can always extend."))
        self.assertFalse(fj.quote_found("", "anything"))

    def test_split_clauses_generic(self):
        c = fj.split_clauses(POLICY)
        self.assertTrue(any("Grace period" in v for v in c.values()))
        self.assertFalse(any(v.strip(" |-") in ("key | Rule", "") for v in c.values()))
        self.assertEqual(list(c), [f"C{i}" for i in range(1, len(c) + 1)])
        other = fj.split_clauses("# Shop\n\n- Returns within 30 days.\n- Only unused items.\n\nFree shipping over 50 EUR.")
        self.assertEqual(other, {"C1": "Shop: Returns within 30 days.", "C2": "Shop: Only unused items.",
                                 "C3": "Shop: Free shipping over 50 EUR."})

    def test_unproven_condition_goes_to_verify_and_can_pass(self):
        self.assertEqual(self.calls_for("You can extend noevidence in the app."), ("pass", ["check"]))  # switch off
        fj.CONDITION_EVIDENCE = True
        MockLLM.bodies.clear()
        self.assertEqual(self.calls_for("You can extend noevidence in the app."), ("pass", ["check", "verify"]))
        self.assertEqual(self.calls_for("You can extend noevidence at the counter."), ("fail", ["check", "verify"]))
        self.assertIn('"evidence"', MockLLM.bodies[0]["messages"][1]["content"])

    def test_proven_condition_needs_no_verify(self):
        fj.CONDITION_EVIDENCE = True
        self.assertEqual(self.calls_for("withevidence: you can extend if the car is not reserved, at the counter."),
                         ("pass", ["check"]))

    def test_clause_ids(self):
        fj.CLAUSE_IDS = True
        self.assertEqual(self.calls_for("goodclause: you may return 29 minutes late."), ("pass", ["check"]))
        self.assertEqual(self.calls_for("badclause: free upgrade at the counter."), ("fail", ["check", "verify"]))
        self.assertEqual(self.calls_for("badclause: free upgrade in the app."), ("pass", ["check", "verify"]))
        content = MockLLM.bodies[0]["messages"][1]["content"]
        self.assertIn("[C1] ", content)
        self.assertIn('"clause_id"', content)

    def test_hedge_from_quote_prompt(self):
        fj.HEDGE_FROM_QUOTE = True
        text = fj._check_instructions()
        self.assertIn('"hedge_words_reply"', text)
        self.assertNotIn("some, 1 = often", text)
        self.assertLess(text.index('"hedge_words_reply": []'), text.index('"gloss_en"'))
        self.assertEqual(self.calls_for("You can usually extend your rental."), ("pass", ["check"]))

    def test_all_schema_switches_compose(self):
        fj.CLAUSE_IDS = fj.CONDITION_EVIDENCE = fj.HEDGE_FROM_QUOTE = True
        text = fj._check_instructions()
        for field in ('"clause_id"', '"evidence"', '"hedge_words_reply"'):
            self.assertIn(field, text)

    def test_verify_deanchor(self):
        fj.VERIFY_DEANCHOR = True
        self.assertEqual(self.calls_for("You can always extend at the counter."), ("fail", ["check", "verify"]))
        content = MockLLM.bodies[1]["messages"][1]["content"]
        self.assertEqual(MockLLM.bodies[1]["messages"][0]["content"], fj.SYSTEM_VERIFY_NEUTRAL)
        self.assertNotIn("reviewer", content.lower())
        self.assertIn("passage:", content)
        # call 1 said fail, neutral call 2 says no violation: still a disagreement, so the tie-break decides
        self.assertEqual(self.calls_for("You can always extend in the app."), ("pass", ["check", "verify", "holistic"]))
