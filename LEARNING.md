# LEARNING.md

Plain-English notes on what was built and why it matters.

## Step 2: Repo setup

- **Package layout** (`agentguard/`, `api/`, `web/`, `tests/`): mirrors PLAN.md so each part of the system (agent loop, tools, guardrails, memory, harness, tracing) has one obvious home. Empty packages are placeholders for later steps.
- **`config.py`**: one place for the five guardrail on/off switches. `CONFIGS` lists the 7 setups that will be compared (none, each guardrail alone, all together). Describing every experiment as a config makes it reproducible.
- **Cached LLM client** (`llm/`): every model call goes through one function that checks an on-disk cache first. Why it matters: free-tier APIs have tight daily token limits, so a re-run must never pay twice for an answer, and a cache also makes results repeatable. The Groq and Gemini backends and the daily token budget arrive in Step 4.
- **`run_meta.json` helper**: records model IDs, settings and the git commit next to the results, so any number can be traced back to the code that produced it.
- **Secrets**: keys come only from `AGENTGUARD_*` environment variables. `.env` is git-ignored and `.env.example` holds names only. The optional pre-commit hook runs gitleaks to block key-like strings. Why it matters: free-tier keys pushed to a public repo get scraped within minutes. Reading: the gitleaks README (pre-commit section).
- **Docker**: the container runs as a non-root user with a read-only filesystem, no Linux capabilities and no privilege escalation. The agent's code runner will execute inside it later, so locking the container down is the second layer behind the sandbox.
- **CI**: GitHub Actions runs ruff and pytest on every push.

How to check: `pytest` and `ruff check .` should both pass.
