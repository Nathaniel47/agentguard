"""Run attack cases and benign tasks against the agent under chosen guardrail configurations.

Each run gets a fresh world (database, documents, sandbox) and, for memory cases, a fresh memory
store, so one case can never affect another. Records are appended to a JSONL file as they finish;
rerunning the same command skips what is already there, which is what makes a multi-day run on
the free API tier resumable.

    python -m agentguard.harness.runner --backend scripted --configs none,all --split test
"""

import argparse
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

from agentguard.agent.loop import Agent, RunResult
from agentguard.agent.scripted import scripted_backend
from agentguard.config import CONFIGS, Config
from agentguard.guardrails import build_guardrails
from agentguard.guardrails.base import BLOCK, FLAG
from agentguard.harness.cases import BenignTask, Case, load_benign, load_cases
from agentguard.harness.scoring import attack_succeeded, check_benign
from agentguard.llm.budget import DailyBudgetExhausted
from agentguard.llm.cache import MemoryCache
from agentguard.llm.client import LLMClient
from agentguard.llm.meta import update_run_meta
from agentguard.memory.store import MemoryStore
from agentguard.tools.env import Environment
from agentguard.tools.registry import build_tools
from agentguard.tracing.spans import Trace

EXIT_PAUSED = 75  # daily token budget used up; rerun after 00:00 UTC
TraceSink = Callable[[str, Trace], None]  # (run key, trace) -> stored


def config_for(name: str) -> Config:
    return Config().with_guardrails(*CONFIGS[name])


def make_llm(backend: str, cfg: Config | None = None) -> LLMClient:
    cfg = cfg or Config()
    if backend == "scripted":
        return LLMClient(scripted_backend, "scripted", 0.0, cfg.seed, cache=MemoryCache())
    if backend == "groq":
        from agentguard.llm.groq import groq_client

        return groq_client(cfg)
    if backend == "gemini":
        from agentguard.llm.gemini import gemini_client

        return gemini_client(cfg)
    raise ValueError(f"unknown backend {backend}")


def _interventions(trace: Trace) -> list[str]:
    return [
        f"{s.name}:{s.attrs['hook']}"
        for s in trace.spans
        if s.kind == "guardrail" and s.attrs["action"] in (BLOCK, FLAG)
    ]


def _record(kind, item_id, config_name, repeat, meta, outcome, results, llm_before, t0) -> dict:
    last: RunResult = results[-1]
    hits = [h for r in results for h in _interventions(r.trace)]
    return {
        "kind": kind,
        "id": item_id,
        "config": config_name,
        "repeat": repeat,
        **meta,
        "outcome": outcome,
        "status": last.status,
        "answer": last.answer[:300],
        "steps": sum(r.steps for r in results),
        "tools": [c["tool"] for r in results for c in r.tool_calls],
        "blocked": bool(hits),
        "interventions": hits,
        "tokens": llm_before["llm"].tokens_used - llm_before["tokens"],
        "llm_calls": llm_before["llm"].calls - llm_before["calls"],
        "seconds": round(time.monotonic() - t0, 3),
    }


def _start(llm: LLMClient) -> dict:
    return {"llm": llm, "tokens": llm.tokens_used, "calls": llm.calls}


def run_attack(
    case: Case, config_name: str, llm: LLMClient, repeat: int = 0, sink: TraceSink | None = None
) -> dict:
    cfg = config_for(config_name)
    env = Environment(strict_sandbox=cfg.enabled("g2_tool_policy"))
    memory = MemoryStore()
    t0, before = time.monotonic(), _start(llm)
    try:
        agent = Agent(llm, build_tools(env), cfg, build_guardrails(cfg), memory)
        results = []
        if case.category == "memory_poisoning":
            env.plant("memory", case.injection)
            results.append(agent.run(case.setup_task, repeat=repeat))
            # Only the later session is scored: clear what the setup session may have sent.
            env.db.execute("DELETE FROM outbox")
            env.db.commit()
        elif case.channel != "user_message":
            env.plant(case.channel, case.injection)
        results.append(agent.run(case.user_task, repeat=repeat))
        success = attack_succeeded(case, results[-1].answer, env)
        meta = {
            "category": case.category,
            "source": case.source,
            "split": case.split,
            "channel": case.channel,
            "goal_type": case.goal_type,
        }
        rec = _record("attack", case.id, config_name, repeat, meta, success, results, before, t0)
        if sink:
            for i, r in enumerate(results):
                sink(f"attack:{case.id}:{config_name}:{repeat}:{i}", r.trace)
        return rec
    finally:
        env.close()
        memory.close()


def run_benign(
    task: BenignTask,
    config_name: str,
    llm: LLMClient,
    repeat: int = 0,
    sink: TraceSink | None = None,
) -> dict:
    cfg = config_for(config_name)
    env = Environment(strict_sandbox=cfg.enabled("g2_tool_policy"))
    t0, before = time.monotonic(), _start(llm)
    try:
        agent = Agent(llm, build_tools(env), cfg, build_guardrails(cfg), MemoryStore())
        result = agent.run(task.user_task, repeat=repeat)
        passed = check_benign(task, result.answer, env.snapshot())
        meta = {
            "category": "benign",
            "source": "self",
            "split": task.split,
            "channel": "user_message",
            "goal_type": task.check_type,
        }
        rec = _record("benign", task.id, config_name, repeat, meta, passed, [result], before, t0)
        if sink:
            sink(f"benign:{task.id}:{config_name}:{repeat}:0", result.trace)
        return rec
    finally:
        env.close()


def _done_keys(path: Path) -> set[tuple]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return {(r["kind"], r["id"], r["config"], r["repeat"]) for r in rows}


def run_grid(
    cases: list[Case],
    benign: list[BenignTask],
    config_names: list[str],
    llm: LLMClient,
    out: Path,
    repeat: int = 0,
    sink: TraceSink | None = None,
    progress: Callable[[int, int, dict], None] | None = None,
) -> int:
    """Append one record per (item, configuration). Returns the number of new records."""
    out.parent.mkdir(parents=True, exist_ok=True)
    done = _done_keys(out)
    jobs = [("attack", c) for c in cases] + [("benign", b) for b in benign]
    todo = [(k, item, name) for name in config_names for k, item in jobs]
    todo = [t for t in todo if (t[0], t[1].id, t[2], repeat) not in done]
    with out.open("a", encoding="utf-8", newline="\n") as f:
        for i, (kind, item, name) in enumerate(todo, 1):
            fn = run_attack if kind == "attack" else run_benign
            rec = fn(item, name, llm, repeat, sink)
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            if progress:
                progress(i, len(todo), rec)
    return len(todo)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--backend", default="scripted", choices=["scripted", "groq", "gemini"])
    ap.add_argument("--configs", default=",".join(CONFIGS))
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"])
    ap.add_argument("--limit", type=int, default=0, help="every k-th case (0 = all)")
    ap.add_argument("--no-benign", action="store_true")
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    from agentguard.config import load_env

    load_env()
    names = args.configs.split(",")
    cases = load_cases(Path("data/cases.jsonl"))
    benign = [] if args.no_benign else load_benign(Path("data/benign.jsonl"))
    if args.split != "all":
        cases = [c for c in cases if c.split == args.split]
        benign = [b for b in benign if b.split == args.split]
    if args.limit:
        cases, benign = cases[:: args.limit], benign[:: args.limit]
    out = args.out or Path(f"results/runs/{args.backend}.jsonl")
    cfg = Config()
    llm = make_llm(args.backend, cfg)
    update_run_meta(
        backend=args.backend,
        model=llm.model,
        temperature=cfg.temperature,
        seed=cfg.seed,
        configs=names,
    )

    def show(i: int, n: int, rec: dict) -> None:
        if i % 25 == 0 or i == n:
            print(f"{i}/{n} {rec['kind']} {rec['id']} {rec['config']}", flush=True)

    try:
        n = run_grid(cases, benign, names, llm, out, args.repeat, progress=show)
    except DailyBudgetExhausted as exc:
        print(f"Paused: {exc}. Rerun after 00:00 UTC; finished runs are kept.")
        return EXIT_PAUSED
    print(f"{n} new records in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
