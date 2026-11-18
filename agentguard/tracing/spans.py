"""Trace of one agent run: an ordered list of spans (LLM call, tool call, guardrail decision).

The span fields (name, kind, attributes, start offset, duration) are the same ones an
OpenTelemetry span carries, so exporting to OTel later is a mapping, not a redesign.
"""

import time
from dataclasses import asdict, dataclass, field


@dataclass
class Span:
    kind: str  # "input" | "llm" | "tool" | "guardrail" | "output"
    name: str
    attrs: dict
    start_s: float  # seconds since the trace began
    duration_s: float = 0.0


@dataclass
class Trace:
    spans: list[Span] = field(default_factory=list)
    _t0: float = field(default_factory=time.monotonic, repr=False)

    def add(self, kind: str, name: str, started: float | None = None, **attrs) -> Span:
        now = time.monotonic()
        start = started if started is not None else now
        span = Span(kind, name, attrs, start - self._t0, now - start)
        self.spans.append(span)
        return span

    def now(self) -> float:
        return time.monotonic()

    def to_dict(self) -> dict:
        return {"spans": [asdict(s) for s in self.spans]}
