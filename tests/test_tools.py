import pytest

from agentguard.harness.world import SANDBOX_CANARY_VALUE
from agentguard.tools.env import Environment
from agentguard.tools.registry import build_tools
from agentguard.tools.sandbox import Sandbox, check_code


@pytest.fixture
def env():
    e = Environment(strict_sandbox=True)
    yield e
    e.close()


def call(env, name, **args):
    return build_tools(env)[name].run(args)


def test_five_tools_registered(env):
    assert set(build_tools(env)) == {"search", "run_code", "calendar", "email", "database"}


def test_search_ranks_by_overlap_and_marks_results_untrusted(env):
    res = call(env, "search", query="refund policy")
    assert res.text.startswith("[refund-policy]")
    assert not res.trusted


def test_calendar_list_add_delete(env):
    assert "Dentist" in call(env, "calendar", action="list", date="2026-03-02").text
    assert (
        "Added event 7"
        in call(env, "calendar", action="add", date="2026-03-09", time="10:00", title="Review").text
    )
    assert "Deleted 1" in call(env, "calendar", action="delete", event_id=7).text
    assert 7 not in env.snapshot()["calendar_ids"]


def test_email_goes_to_outbox_only(env):
    call(env, "email", action="send", to="x@example.test", subject="s", body="b")
    assert env.snapshot()["outbox"] == [
        {"recipient": "x@example.test", "subject": "s", "body": "b"}
    ]
    assert call(env, "email", action="send").error  # no recipient


def test_inbox_is_untrusted(env):
    res = call(env, "email", action="read_inbox", limit=1)
    assert "office party" in res.text.lower() and not res.trusted


def test_database_select_and_write_and_error(env):
    assert (
        "Accra" in call(env, "database", sql="SELECT city FROM customers WHERE id='FAKE-C001'").text
    )
    call(env, "database", sql="DELETE FROM customers WHERE id='FAKE-C001'")
    assert "FAKE-C001" not in env.snapshot()["customers"]
    assert call(env, "database", sql="SELEKT 1").error


def test_plant_places_text_in_each_channel(env):
    env.plant("search_result", "PLANTED-A")
    env.plant("email_body", "PLANTED-B")
    env.plant("calendar_event", "PLANTED-C")
    env.plant("db_row", "PLANTED-D")
    assert "PLANTED-A" in call(env, "search", query="refund").text
    assert "PLANTED-B" in call(env, "email", action="read_inbox", limit=1).text
    assert "PLANTED-C" in call(env, "calendar", action="list", date="2026-03-02").text
    assert (
        "PLANTED-D"
        in call(env, "database", sql="SELECT * FROM customers WHERE id='FAKE-C002'").text
    )
    with pytest.raises(ValueError):
        env.plant("nope", "x")


def test_code_runner_computes(env):
    assert call(env, "run_code", code="print(sum(range(10)))").text == "45"


@pytest.mark.parametrize(
    "code,reason",
    [
        ("import os", "import of 'os'"),
        ("from subprocess import run", "import from 'subprocess'"),
        ("open('x', 'w')", "'open'"),
        ("__import__('os')", "'__import__'"),
        ("().__class__.__bases__", "is not allowed"),
        ("eval('1')", "'eval'"),
        ("def f(:", "syntax error"),
    ],
)
def test_strict_profile_rejects(code, reason):
    assert reason in check_code(code)


def test_strict_profile_allows_pure_computation():
    assert check_code("import math\nprint(math.sqrt(2))") == ""


def test_strict_rejection_never_runs_code(env):
    res = call(env, "run_code", code="import os\nos.system('echo hi')")
    assert res.error and "rejected" in res.text


def test_naive_profile_leaks_env_canary_but_not_real_env(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_GROQ_API_KEY", "real-key-should-not-leak")
    sb = Sandbox(strict=False, timeout_s=5)
    try:
        out = sb.run("import os\nprint(dict(os.environ))")
        assert SANDBOX_CANARY_VALUE in out.stdout
        assert "real-key-should-not-leak" not in out.stdout
    finally:
        sb.close()


def test_naive_profile_can_write_outside_work_dir_but_stays_in_temp_tree():
    sb = Sandbox(strict=False, timeout_s=5)
    try:
        sb.run("open('../escape_marker.txt', 'w').write('x')")
        found = sb.escaped_files("escape_marker")
        assert found and sb.root in found[0].parents
    finally:
        sb.close()


def test_strict_profile_blocks_that_same_escape():
    sb = Sandbox(strict=True, timeout_s=5)
    try:
        res = sb.run("open('../escape_marker.txt', 'w').write('x')")
        assert res.rejected and sb.escaped_files("escape_marker") == []
    finally:
        sb.close()


def test_time_limit_kills_runaway_code():
    sb = Sandbox(strict=True, timeout_s=1)
    try:
        res = sb.run("while True:\n    pass")
        assert res.timed_out and res.elapsed < 4
    finally:
        sb.close()


def test_memory_watchdog_kills_hog():
    sb = Sandbox(strict=False, timeout_s=20)
    try:
        res = sb.run("x = []\nwhile True:\n    x.append(' ' * 10**7)")
        assert res.memory_killed or res.timed_out
    finally:
        sb.close()


def test_snapshot_survives_a_dropped_table(env):
    call(env, "database", sql="DROP TABLE customers")
    assert env.snapshot()["customers"] == {}
