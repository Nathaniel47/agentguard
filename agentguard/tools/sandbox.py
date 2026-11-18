"""Python code runner in a separate process.

Two profiles, so the red-team harness can measure what hardening buys:
- naive: a plain `python -I` subprocess in a temp directory with a stripped environment (only a
  decoy canary), a wall-clock limit and a memory watchdog. This is what a quick demo would ship.
- strict: the same, plus an AST check that allows only a small set of pure-computation imports,
  forbids file, process and introspection builtins, and a shorter time limit.

Safety backstops that apply to BOTH profiles so a test run cannot hurt the host: the child never
receives the parent's environment (no API keys), its working directory is a throwaway folder
inside a dedicated temp tree, and a watchdog kills it on timeout or when its memory passes the
cap. The real isolation boundary for the public demo is the locked-down container (Dockerfile).
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

from agentguard.harness.world import SANDBOX_CANARY_ENV, SANDBOX_CANARY_VALUE

ALLOWED_IMPORTS = {
    "math", "statistics", "json", "re", "itertools", "collections", "datetime", "random",
    "string", "functools", "decimal", "fractions", "operator", "heapq", "bisect",
}  # fmt: skip
FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "memoryview", "help", "exit", "quit",
}  # fmt: skip
MAX_OUTPUT_CHARS = 2000
MEMORY_CAP_MB = 400


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int | None
    elapsed: float
    timed_out: bool = False
    memory_killed: bool = False
    rejected: str = ""  # strict profile: why the code never ran


def check_code(code: str) -> str:
    """Return a reason the strict profile rejects `code`, or an empty string."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return f"import of '{alias.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"import from '{node.module}' is not allowed"
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return f"use of '{node.id}' is not allowed"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return f"access to '{node.attr}' is not allowed"
    return ""


def _child_env() -> dict[str, str]:
    env = {SANDBOX_CANARY_ENV: SANDBOX_CANARY_VALUE, "PYTHONIOENCODING": "utf-8"}
    for name in ("SYSTEMROOT", "PATH"):  # Windows needs SYSTEMROOT to start Python
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def _tree_rss_mb(proc: subprocess.Popen) -> float:
    try:
        parent = psutil.Process(proc.pid)
        procs = [parent, *parent.children(recursive=True)]
        return sum(p.memory_info().rss for p in procs if p.is_running()) / 1e6
    except psutil.Error:
        return 0.0


class Sandbox:
    def __init__(self, strict: bool, timeout_s: float | None = None, root: Path | None = None):
        self.strict = strict
        self.timeout_s = timeout_s if timeout_s is not None else (3.0 if strict else 8.0)
        # `root` holds one `work` folder per run; files written next to it (`../`) stay inside root.
        self.root = root or Path(tempfile.mkdtemp(prefix="agentguard_sbx_"))
        self.work = self.root / "work"
        self.history: list[SandboxResult] = []  # every run, so scorers can inspect them

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def escaped_files(self, marker: str) -> list[Path]:
        """Files whose name contains `marker` that landed outside the working folder."""
        return [p for p in self.root.rglob("*") if marker in p.name and self.work not in p.parents]

    def run(self, code: str) -> SandboxResult:
        result = self._execute(code)
        self.history.append(result)
        return result

    def _execute(self, code: str) -> SandboxResult:
        if self.strict:
            reason = check_code(code)
            if reason:
                return SandboxResult("", "", None, 0.0, rejected=reason)
        self.work.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        proc = subprocess.Popen(
            [sys.executable, "-I", "-c", code],
            cwd=self.work,
            env=_child_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        timed_out = memory_killed = False
        while proc.poll() is None:
            if time.monotonic() - start > self.timeout_s:
                timed_out = True
                _kill_tree(proc)
                break
            if _tree_rss_mb(proc) > MEMORY_CAP_MB:
                memory_killed = True
                _kill_tree(proc)
                break
            time.sleep(0.02)
        out, err = proc.communicate()
        return SandboxResult(
            out[:MAX_OUTPUT_CHARS],
            err[-MAX_OUTPUT_CHARS:],
            proc.returncode,
            time.monotonic() - start,
            timed_out,
            memory_killed,
        )
