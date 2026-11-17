import os

import pytest

from agentguard.config import CONFIGS, GUARDRAILS, Config, groq_api_key, load_env


def test_seven_configurations():
    assert len(CONFIGS) == 7
    assert CONFIGS["all"] == GUARDRAILS
    assert CONFIGS["none"] == ()


def test_with_guardrails_toggles():
    cfg = Config().with_guardrails("g1_input_screen")
    assert cfg.enabled("g1_input_screen")
    assert not cfg.enabled("g5_output_filter")


def test_unknown_guardrail_rejected():
    with pytest.raises(ValueError):
        Config().with_guardrails("nope")


def test_missing_key_is_none(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_GROQ_API_KEY", raising=False)
    assert groq_api_key() is None


def test_load_env_reads_only_agentguard_names(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("AGENTGUARD_GROQ_API_KEY=abc\nOTHER=1\n")
    monkeypatch.delenv("AGENTGUARD_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OTHER", raising=False)
    load_env(env)
    assert groq_api_key() == "abc"
    assert "OTHER" not in os.environ
