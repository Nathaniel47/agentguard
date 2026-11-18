"""Confirms every sandbox_escape case can actually succeed against the naive runner (so the
marker works) and that the strict profile stops all of them."""

import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from agentguard.harness.cases import load_cases
from agentguard.harness.scoring import sandbox_marker_fired
from agentguard.tools.sandbox import Sandbox

CASES = [c for c in load_cases(Path("data/cases.jsonl")) if c.category == "sandbox_escape"]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def local_listener():
    server = HTTPServer(("127.0.0.1", 47831), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield
    server.shutdown()


def _run(case, strict, timeout):
    sb = Sandbox(strict=strict, timeout_s=timeout)
    try:
        res = sb.run(case.injection)
        return sandbox_marker_fired(case, res, sb)
    finally:
        sb.close()


def test_there_are_twenty_sandbox_cases():
    assert len(CASES) == 20


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.goal_type != "resource_abuse"], ids=lambda c: c.id
)
def test_marker_fires_on_naive_runner(case, local_listener):
    if "/etc/passwd" in case.injection or "'env'" in case.injection or "/proc/" in case.injection:
        if sys.platform == "win32":
            pytest.skip("POSIX-only case; runs in the Linux container and CI")
    assert _run(case, strict=False, timeout=8)


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.goal_type != "resource_abuse"], ids=lambda c: c.id
)
def test_strict_runner_stops_case(case, local_listener):
    assert not _run(case, strict=True, timeout=3)


def test_resource_cases_run_past_limit_naively_and_are_stopped_strictly():
    case = next(c for c in CASES if c.goal_type == "resource_abuse" and "sleep" in c.injection)
    assert _run(case, strict=False, timeout=6)  # limit_s is 5, naive keeps running
    assert not _run(case, strict=True, timeout=3)
