# AgentGuard: Secure Tool-Using Agent with Red-Team Harness

A small LLM agent with five tools and long-term memory, wrapped in separate guardrails, plus an automated red-team harness that attacks it and measures which guardrail stops which attack.

> Status: Steps 1 to 7 complete (data, agent, guardrails, harness, evaluation, demo). See [PLAN.md](PLAN.md) for the design and [BUILD_STEPS.md](BUILD_STEPS.md) for progress.

Demo link, architecture diagram and results summary: added in Step 8. To deploy the demo yourself, follow [DEPLOY.md](DEPLOY.md); the evaluation is in [results/](results/results_table.md) with its [limitations](results/limitations.md).

## Run locally

Requires Python 3.11.

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env   # then fill in the keys you have
pytest
uvicorn api.main:app --reload --port 7860
```

macOS / Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # then fill in the keys you have
pytest
uvicorn api.main:app --reload --port 7860
```

Docker: `docker compose up --build` (arena at http://localhost:7860, health check at `/health`). Set `AGENTGUARD_ARENA_BACKEND=groq` and a Groq key in `.env` to use the real model; the default is the offline scripted agent.

Lint and format: `ruff check .` and `ruff format .`. Optional commit hooks (gitleaks secret scan, ruff): `pre-commit install`.

## Reproduce the evaluation

```bash
# Free, offline: scripted worst-case agent on the whole test split (8 configurations)
python -m agentguard.harness.runner --backend scripted --split test --out results/runs/scripted_test.jsonl

# Real model (needs AGENTGUARD_GROQ_API_KEY in .env); resumable, pauses with exit code 75 when the
# free daily token allowance is used up
python -m agentguard.harness.runner --backend groq --split test --per-category 3 --benign-count 8   --configs none,all,g1,g2,g3,keyword,g4,g5 --out results/runs/groq_main.jsonl
python -m agentguard.harness.runner --backend groq --split test --per-category 3 --no-benign   --configs none,all --seed 1 --temperature 0.7 --out results/runs/groq_var_s1.jsonl   # also seeds 2, 3

# Table, charts and sample traces
python -m agentguard.harness.report
```

The records behind the table are in `results/runs/`. Read `results/limitations.md` before quoting a number.

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
