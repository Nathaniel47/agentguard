"""Run attack cases and benign tasks against the agent under chosen guardrail configurations.

Each run gets a fresh world (database, documents, sandbox) and, for memory cases, a fresh memory
store, so one case can never affect another. Records are appended to a JSONL file as they finish;
rerunning the same command skips what is already there, which is what makes a multi-day run on
the free API tier resumable.

    python -m agentguard.harness.runner --backend scripted --configs none,all --split test
"""

import argparse
import json
import random
import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from agentguard.agent.loop import Agent, RunResult
from agentguard.agent.scripted import scripted_backend
from agentguard.config import CONFIGS, RATE_LIMITS, Config
from agentguard.guardrails import build_guardrails
from agentguard.guardrails.base import BLOCK, FLAG
from agentguard.guardrails.baseline import KeywordBlocklist
from agentguard.harness.cases import BenignTask, Case, load_benign, load_cases
from agentguard.harness.scoring import attack_succeeded, check_benign
from agentguard.llm.budget import DailyBudgetExhausted
from agentguard.llm.cache import MemoryCache
from agentguard.llm.client import LLMClient
from agentguard.llm.meta import META_PATH, update_run_meta
from agentguard.memory.store import MemoryStore
from agentguard.tools.env import Environment
from agentguard.tools.registry import build_tools
from agentguard.tracing.spans import Trace
from agentguard.tracing.store import TraceStore

EXIT_PAUSED = 75  # daily token budget used up; rerun after 00:00 UTC
TraceSink = Callable[[str, Trace], None]  # (run key, trace) -> stored


BASELINES = {"keyword": KeywordBlocklist}  # simple comparison points, not part of CONFIGS


def config_for(name: str, seed: int = 42, temperature: float = 0.0) -> Config:
    names = () if name in BASELINES else CONFIGS[name]
    return replace(Config(seed=seed, temperature=temperature), guardrails=frozenset(names))


def guardrails_for(name: str, cfg: Config) -> list:
    return [BASELINES[name]()] if name in BASELINES else build_guardrails(cfg)


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
        "seed": llm_before["llm"].seed,
        "temperature": llm_before["llm"].temperature,
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
        "model_calls": llm_before["llm"].logical_calls - llm_before["logical"],
        "est_tokens": llm_before["llm"].est_tokens - llm_before["est"],
        "seconds": round(time.monotonic() - t0, 3),
    }


def _start(llm: LLMClient) -> dict:
    return {
        "llm": llm,
        "tokens": llm.tokens_used,
        "calls": llm.calls,
        "logical": llm.logical_calls,
        "est": llm.est_tokens,
    }


def run_attack(
    case: Case, config_name: str, llm: LLMClient, repeat: int = 0, sink: TraceSink | None = None
) -> dict:
    cfg = config_for(config_name, llm.seed, llm.temperature)
    env = Environment(strict_sandbox=cfg.enabled("g2_tool_policy"))
    memory = MemoryStore()
    t0, before = time.monotonic(), _start(llm)
    try:
        agent = Agent(llm, build_tools(env), cfg, guardrails_for(config_name, cfg), memory)
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
    cfg = config_for(config_name, llm.seed, llm.temperature)
    env = Environment(strict_sandbox=cfg.enabled("g2_tool_policy"))
    t0, before = time.monotonic(), _start(llm)
    try:
        agent = Agent(llm, build_tools(env), cfg, guardrails_for(config_name, cfg), MemoryStore())
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


def sample_per_category(cases: list[Case], k: int, seed: int = 42) -> list[Case]:
    """A seeded, repeatable sample of up to k cases from every category."""
    rng = random.Random(seed)
    picked = []
    for category in sorted({c.category for c in cases}):
        group = sorted((c for c in cases if c.category == category), key=lambda c: c.id)
        rng.shuffle(group)
        picked += group[:k]
    return picked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--backend", default="scripted", choices=["scripted", "groq", "gemini"])
    ap.add_argument("--configs", default=",".join([*CONFIGS, *BASELINES]))
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"])
    ap.add_argument("--limit", type=int, default=0, help="every k-th case (0 = all)")
    ap.add_argument("--per-category", type=int, default=0, help="seeded sample per category")
    ap.add_argument("--benign-count", type=int, default=0, help="first N benign tasks (0 = all)")
    ap.add_argument("--no-benign", action="store_true")
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--save-traces", action="store_true", help="store every trace in SQLite")
    args = ap.parse_args(argv)

    from agentguard.config import load_env

    load_env()
    names = args.configs.split(",")
    cases = load_cases(Path("data/cases.jsonl"))
    benign = [] if args.no_benign else load_benign(Path("data/benign.jsonl"))
    if args.split != "all":
        cases = [c for c in cases if c.split == args.split]
        benign = [b for b in benign if b.split == args.split]
    if args.per_category:
        cases = sample_per_category(cases, args.per_category)
    if args.benign_count:
        benign = benign[: args.benign_count]
    if args.limit:
        cases, benign = cases[:: args.limit], benign[:: args.limit]
    out = args.out or Path(f"results/runs/{args.backend}.jsonl")
    cfg = Config(seed=args.seed, temperature=args.temperature)
    llm = make_llm(args.backend, cfg)
    meta = json.loads(META_PATH.read_text(encoding="utf-8")) if META_PATH.exists() else {}
    runs = meta.get("runs", {})
    runs[out.stem] = {
        "backend": args.backend,
        "model": llm.model,
        "temperature": cfg.temperature,
        "seed": cfg.seed,
        "configs": names,
        "split": args.split,
        "per_category": args.per_category,
        "benign_count": args.benign_count,
    }
    update_run_meta(runs=runs, rate_limits_assumed=RATE_LIMITS)

    def show(i: int, n: int, rec: dict) -> None:
        if i % 25 == 0 or i == n:
            print(f"{i}/{n} {rec['kind']} {rec['id']} {rec['config']}", flush=True)

    sink = TraceStore().sink() if args.save_traces else None
    try:
        n = run_grid(cases, benign, names, llm, out, args.repeat, sink=sink, progress=show)
    except DailyBudgetExhausted as exc:
        print(f"Paused: {exc}. Rerun after 00:00 UTC; finished runs are kept.")
        return EXIT_PAUSED
    print(f"{n} new records in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
