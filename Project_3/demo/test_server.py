"""HTTP contract tests for the local Project 3 demo (no real key or external network)."""
from __future__ import annotations

import http.client
import json
import os
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "starter_pack"))

import server  # noqa: E402
import test_final_judge as mock_judge  # noqa: E402


class DemoHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.llm = server.http.server.ThreadingHTTPServer(("127.0.0.1", 0), mock_judge.MockLLM)
        threading.Thread(target=cls.llm.serve_forever, daemon=True).start()
        cls.saved = {k: os.environ.get(k) for k in ("JUDGE_LLM_BASE_URL", "JUDGE_LLM_API_KEY", "JUDGE_LLM_MODEL")}
        os.environ.update(JUDGE_LLM_BASE_URL=f"http://127.0.0.1:{cls.llm.server_port}",
                          JUDGE_LLM_API_KEY="mock", JUDGE_LLM_MODEL="claude-haiku-4.5 (MOCK)")
        cls.demo = server.Demo()
        cls.httpd = server.http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(cls.demo, True))
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.llm.shutdown()
        cls.llm.server_close()
        for key, value in cls.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def request(self, method: str, path: str, body=None, content_type="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": content_type} if payload is not None else {}
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        headers = dict(response.getheaders())
        conn.close()
        return response.status, headers, data

    def test_health_and_security_headers(self):
        status, headers, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok", "mode": "mock", "model_configured": True,
                                            "gateway_configured": True})
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(int(headers["Content-Length"]), len(body))

    def test_ui_contains_guided_interactions(self):
        status, _, body = self.request("GET", "/")
        page = body.decode("utf-8")
        self.assertEqual(status, 200)
        for text in ("Choose a reply", "Run the judge", "Understand the decision", "Clear harmful edit",
                     "Write my own", "Safe extension", "Why did the judge decide this?"):
            self.assertIn(text, page)

    def test_state_and_cases_contract(self):
        status, _, body = self.request("GET", "/api/state")
        state = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(state["mock"])
        self.assertIn("c1", {c["id"] for c in state["criteria"]})
        status, _, body = self.request("GET", "/api/cases?c=c1")
        cases = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(len(cases), 226)
        self.assertIn("original", cases[0])

    def test_mock_judgment_flow(self):
        status, _, body = self.request("POST", "/api/judge", {
            "c": "c1", "question": "Can I extend?", "reply": "You can always extend at the counter.", "lang": "en"
        })
        result = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(result["path"], "call1_fail>verify_confirms")
        self.assertEqual([c["role"] for c in result["calls"]], ["check", "verify"])

    def test_rejects_bad_requests(self):
        status, _, _ = self.request("POST", "/api/judge", ["not", "an", "object"])
        self.assertEqual(status, 400)
        status, _, _ = self.request("POST", "/api/judge", {"reply": "ok", "lang": "<script>"})
        self.assertEqual(status, 400)
        status, _, _ = self.request("POST", "/api/judge", {"reply": "ok"}, content_type="text/plain")
        self.assertEqual(status, 415)


if __name__ == "__main__":
    unittest.main()
