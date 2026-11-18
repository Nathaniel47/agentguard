from fastapi.testclient import TestClient

from agentguard.harness.cases import load_cases
from agentguard.harness.runner import make_llm, run_attack
from agentguard.tracing.spans import Trace
from agentguard.tracing.store import TraceStore
from api.main import WEB_DIR, create_app


def sample_trace() -> Trace:
    t = Trace()
    t.add("input", "user_task", text="<b>hi</b>")
    t.add("guardrail", "g1_input_screen", hook="input", action="block", reason="x")
    t.add("output", "final_answer", text="no", status="blocked_input")
    return t


def test_store_roundtrip_and_listing():
    store = TraceStore(":memory:")
    tid = store.save(sample_trace(), label="demo", meta={"config": "g1"})
    got = store.get(tid)
    assert got["label"] == "demo" and got["meta"] == {"config": "g1"}
    assert [s["kind"] for s in got["spans"]] == ["input", "guardrail", "output"]
    assert store.get("missing") is None
    assert store.recent()[0]["id"] == tid
    assert store.find_by_label("demo") == [tid]


def test_runner_sink_stores_every_session_of_a_run():
    store = TraceStore(":memory:")
    case = next(
        c
        for c in load_cases(__import__("pathlib").Path("data/cases.jsonl"))
        if c.category == "memory_poisoning"
    )
    run_attack(case, "g4", make_llm("scripted"), sink=store.sink())
    labels = [r["label"] for r in store.recent()]
    assert sorted(labels) == [f"attack:{case.id}:g4:0:0", f"attack:{case.id}:g4:0:1"]


def test_api_serves_traces_and_static_pages():
    store = TraceStore(":memory:")
    tid = store.save(sample_trace(), label="demo")
    client = TestClient(create_app(store))
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get(f"/api/trace/{tid}").json()["spans"][1]["attrs"]["action"] == "block"
    assert client.get("/api/trace/nope").status_code == 404
    assert client.get("/api/traces").json()[0]["id"] == tid
    assert "AgentGuard trace" in client.get("/trace.html").text


def test_viewer_never_parses_trace_text_as_html():
    js = (WEB_DIR / "trace.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js and "insertAdjacentHTML" not in js


def test_trace_lists_only_guardrails_that_handle_each_hook():
    case = next(
        c
        for c in load_cases(__import__("pathlib").Path("data/cases.jsonl"))
        if c.id == "tool-s-001"
    )
    store = TraceStore(":memory:")
    run_attack(case, "all", make_llm("scripted"), sink=store.sink())
    spans = store.get(store.recent()[0]["id"])["spans"]
    seen = {(s["name"], s["attrs"]["hook"]) for s in spans if s["kind"] == "guardrail"}
    assert ("g1_input_screen", "input") in seen
    assert ("g1_input_screen", "tool_call") not in seen
    assert ("g5_output_filter", "output") in seen
