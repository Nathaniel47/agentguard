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

## Step 3: Data pipeline

- **What a "case" is** (`harness/cases.py`): one attack, described as data. It says where the attacker's text enters (the user, a search result, an email, a calendar event, a database row, or memory), what the user is innocently asking for, and a **goal** that says how to detect success. Describing attacks as data means the same 220 cases can be replayed against every guardrail configuration.
- **State-based success markers**: success is never judged by reading the answer. It is a canary string in the output, an email in the mock outbox addressed to the attacker, a deleted row, a file written outside the sandbox, and so on. Why it matters: results are reproducible and cannot be argued about. The trade-off is some false negatives, because an agent that does the bad thing in a way we did not anticipate is not counted.
- **Public data, adapted** (`harness/load_public.py`): InjecAgent (MIT) and deepset/prompt-injections (Apache-2.0) are downloaded at pinned commits with file hashes recorded. Only their wording is reused. Their original goals target other apps (smart locks, banking) or have no checkable outcome, so we attach goals that fit this app. Reading: the InjecAgent paper (Zhan et al., 2024) for how indirect injection is benchmarked.
- **Self-written cases** (`harness/self_cases.py`): built from framings x actions, so coverage is systematic but less creative than human red-teaming. This is stated as a limitation in the data report.
- **Synthetic world** (`harness/world.py`): fake customers with `FAKE-` IDs and `.test` / `example.test` emails, so nothing can be a real person or a deliverable address.
- **Dev/test split**: a seeded 30/70 split per category. Tune guardrails on dev only, then report on test, otherwise the numbers would flatter the guardrails. Reading: any intro to train/validation/test discipline, e.g. the scikit-learn "cross-validation" guide section on held-out data.
- **Benign tasks**: 40 normal requests with automatic checks. Without them a guardrail that blocks everything would look perfect, so every guardrail is also scored on how often it wrongly blocks normal work.

How to check: `python -m agentguard.harness.build_dataset` rebuilds everything and fails loudly on duplicate IDs, duplicate attack text, missing canaries or invalid fields. Then read `results/data_report.md` and run `pytest`.
