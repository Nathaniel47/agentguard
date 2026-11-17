# AgentGuard: Secure Tool-Using Agent with Red-Team Harness

A small LLM agent with five tools and long-term memory, wrapped in separate guardrails, plus an automated red-team harness that attacks it and measures which guardrail stops which attack.

> Status: setup complete (Step 2). See [PLAN.md](PLAN.md) for the design and [BUILD_STEPS.md](BUILD_STEPS.md) for progress.

Demo link, architecture diagram and results table: added in Step 8.

## Run locally

Requires Python 3.11.

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env   # then fill in the keys you have
pytest
uvicorn api.main:app --reload
```

macOS / Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # then fill in the keys you have
pytest
uvicorn api.main:app --reload
```

Docker: `docker compose up --build` (API on http://localhost:8000, health check at `/health`).

Lint and format: `ruff check .` and `ruff format .`. Optional commit hooks (gitleaks secret scan, ruff): `pre-commit install`.

## Safety

All attacks target this app only. Email is a mock outbox, the code runner is sandboxed, and test data is synthetic. No real services or personal data are used.

## Datasets and licences

Public test sets are chosen and their licences recorded in Step 3.
