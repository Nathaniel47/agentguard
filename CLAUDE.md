# CLAUDE.md: AgentGuard coding rules

- Follow PLAN.md; if anything conflicts, PLAN.md wins. Work one BUILD_STEPS.md step at a time.
- Python 3.11, no LangChain/LlamaIndex/LangGraph. Keep the agent loop plain and each guardrail a separate hook.
- Secrets only from environment variables named `AGENTGUARD_*`. Never commit `.env`; `.env.example` has names with empty values.
- All attacks target this app only. Email is a mock outbox, the code runner is sandboxed, test data is synthetic. Never use real services or real personal data.
- Scoring is automatic (state checks and success markers). No LLM judge.
- Every LLM call goes through the cached client in `agentguard/llm/`. Fixed seeds; record model IDs, temperature, seed and git commit in `results/run_meta.json`.
- Format and lint with ruff (line length 100). Write tests in `tests/` for every feature; run `pytest` before each commit.
- Code comments only for non-obvious reasons. Plain-English explanations go in LEARNING.md, not chat.
- Commit with the step name in the message, then push. Never add attribution to commits or PRs: no `Co-Authored-By` lines and no "Generated with" text.
