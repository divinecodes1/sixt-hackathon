"""Vercel entry point for the live demo: the unchanged demo/server.py handler as a Python serverless function.

Secrets come from Vercel environment variables (JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY, JUDGE_LLM_MODEL); nothing is
read from a .env file in the deployment and the key is never sent to the browser. No response cache.
"""
import os
import sys
import urllib.parse

P3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(P3, "demo"))
os.environ.pop("JUDGE_LLM_CACHE", None)  # a live demo shows live answers

import server  # noqa: E402

_Handler = server.make_handler(server.Demo(), False)


class handler(_Handler):  # Vercel looks for a top-level `handler` (BaseHTTPRequestHandler subclass)
    """vercel.json rewrites every path to /api/index?__p=<original path>; restore it for the demo's router."""

    def _restore_path(self) -> None:
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
        orig = [v for k, v in q if k == "__p"]
        if orig:
            rest = urllib.parse.urlencode([(k, v) for k, v in q if k != "__p"])
            self.path = "/" + orig[0].lstrip("/") + ("?" + rest if rest else "")

    def do_GET(self):
        self._restore_path()
        super().do_GET()

    def do_POST(self):
        self._restore_path()
        super().do_POST()
