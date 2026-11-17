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

Only the attacker's wording from public sets is reused; every goal, success marker and target tool is our own. Versions are pinned by commit and file hashes are in `data/manifest.json`.

| Source | Licence | Pinned version | What is used |
|---|---|---|---|
| [InjecAgent](https://github.com/uiuc-kang-lab/InjecAgent) (attacker cases) | MIT | `f19c9f2c` | 62 attacker instructions, reworded into 35 cases |
| [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections) | Apache-2.0 | `4f61ecb0` | English injection prompts, 30 cases |
| Self-written | this repo | n/a | 155 attack cases and 40 benign tasks |

Considered and not used: JailbreakBench and AgentDojo (both MIT). Their cases are mostly harmful-content requests or need their own task suites, which do not fit automatic state-based scoring here.

Rebuild the data: `python -m agentguard.harness.build_dataset` (downloads the pinned files into `data/raw/`, which is git-ignored). Outputs: `data/cases.jsonl` (220 cases), `data/benign.jsonl` (40 tasks), `data/manifest.json`, `results/data_report.md`.
