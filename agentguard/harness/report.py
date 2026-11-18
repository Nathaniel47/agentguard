"""Turn run records into the results table (Markdown and CSV) and three charts.

    python -m agentguard.harness.report

Inputs are the JSONL files written by the runner (results/runs/*.jsonl). Each file is one
"experiment": the scripted worst-case agent on the whole test split, the real model on a seeded
subset, and repeated real-model runs with different seeds for variance. Missing files are skipped.
"""

import csv
import json
import statistics
from pathlib import Path

from agentguard.harness.metrics import wilson

RUNS = Path("results/runs")
OUT = Path("results")
CONFIG_ORDER = ["none", "keyword", "g1", "g2", "g3", "g4", "g5", "all"]
LABELS = {
    "none": "No guardrails",
    "keyword": "Keyword blocklist (baseline)",
    "g1": "G1 input screen",
    "g2": "G2 tool policy",
    "g3": "G3 taint",
    "g4": "G4 memory gate",
    "g5": "G5 output filter",
    "all": "All five",
}
CATEGORIES = [
    "direct_injection",
    "indirect_injection",
    "jailbreak",
    "tool_abuse",
    "memory_poisoning",
    "data_exfiltration",
    "sandbox_escape",
]
EXPERIMENTS = {
    "scripted_test": "Scripted worst-case agent, whole test split",
    "groq_main": "Real model (Groq gpt-oss-20b), seeded sample, temperature 0",
}
VARIANCE_FILES = ("groq_var_s1", "groq_var_s2", "groq_var_s3")


def load(name: str, runs: Path = RUNS) -> list[dict]:
    path = runs / f"{name}.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def rate(rows: list[dict]) -> dict:
    wins = sum(1 for r in rows if r["outcome"])
    lo, hi = wilson(wins, len(rows))
    return {
        "k": wins,
        "n": len(rows),
        "rate": wins / len(rows) if rows else 0.0,
        "lo": lo,
        "hi": hi,
    }


def config_row(records: list[dict], config: str) -> dict | None:
    attacks = [r for r in records if r["kind"] == "attack" and r["config"] == config]
    benign = [r for r in records if r["kind"] == "benign" and r["config"] == config]
    if not attacks:
        return None
    runs = attacks + benign
    row = {"config": config, "asr": rate(attacks)}
    row["by_category"] = {
        c: rate([r for r in attacks if r["category"] == c])
        for c in CATEGORIES
        if any(r["category"] == c for r in attacks)
    }
    if benign:
        row["utility"] = rate(benign)
        failed_blocked = [r for r in benign if r["blocked"] and not r["outcome"]]
        row["false_block"] = len(failed_blocked) / len(benign)
    # Cache hits cost nothing on the API but are part of what a run needs, so cost is counted from
    # every model call (model_calls) and estimated tokens, not from what was billed.
    row["mean_tokens"] = statistics.fmean(r.get("est_tokens", r["tokens"]) for r in runs)
    row["mean_llm_calls"] = statistics.fmean(r.get("model_calls", r["llm_calls"]) for r in runs)
    return row


def table(records: list[dict]) -> list[dict]:
    rows = (config_row(records, c) for c in CONFIG_ORDER)
    return [r for r in rows if r]


def variance(by_seed: dict[str, list[dict]]) -> list[dict]:
    """Attack success rate per configuration for each seed, then mean and standard deviation."""
    out = []
    for config in CONFIG_ORDER:
        per_seed = []
        for records in by_seed.values():
            att = [r for r in records if r["kind"] == "attack" and r["config"] == config]
            if att:
                per_seed.append(rate(att)["rate"])
        if len(per_seed) >= 2:
            out.append(
                {
                    "config": config,
                    "seeds": len(per_seed),
                    "per_seed": per_seed,
                    "mean": statistics.fmean(per_seed),
                    "sd": statistics.stdev(per_seed),
                }
            )
    return out


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def cell(r: dict) -> str:
    return f"{r['k']}/{r['n']} ({pct(r['rate'])})"


def markdown_table(rows: list[dict]) -> str:
    cats = [c for c in CATEGORIES if any(c in r["by_category"] for r in rows)]
    head = [
        "Configuration",
        "Attack success (95% CI)",
        *cats,
        "Benign tasks passed",
        "False blocks",
    ]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        a = r["asr"]
        cells = [
            LABELS[r["config"]],
            f"{cell(a)} [{pct(a['lo'])}-{pct(a['hi'])}]",
            *(cell(r["by_category"][c]) if c in r["by_category"] else "n/a" for c in cats),
            cell(r["utility"]) if "utility" in r else "n/a",
            pct(r["false_block"]) if "false_block" in r else "n/a",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def cost_table(rows: list[dict]) -> str:
    lines = [
        "| Configuration | Mean model calls per run | Mean tokens per run (estimated) |",
        "|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {LABELS[r['config']]} | {r['mean_llm_calls']:.2f} | {r['mean_tokens']:.0f} |"
        )
    return "\n".join(lines)


def variance_table(rows: list[dict]) -> str:
    lines = [
        "| Configuration | Seeds | Attack success per seed | Mean | Std dev |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        per = ", ".join(pct(x) for x in r["per_seed"])
        sd = f"{100 * r['sd']:.1f} pts"
        lines.append(f"| {LABELS[r['config']]} | {r['seeds']} | {per} | {pct(r['mean'])} | {sd} |")
    return "\n".join(lines)


def write_csv(path: Path, tables: dict[str, list[dict]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["experiment", "config", "category", "successes", "n", "rate", "ci_low", "ci_high"]
        )
        for exp, rows in tables.items():
            for r in rows:
                parts = {"all attacks": r["asr"], **r["by_category"]}
                for cat, v in parts.items():
                    w.writerow(
                        [
                            exp,
                            r["config"],
                            cat,
                            v["k"],
                            v["n"],
                            f"{v['rate']:.4f}",
                            f"{v['lo']:.4f}",
                            f"{v['hi']:.4f}",
                        ]
                    )
                if "utility" in r:
                    u = r["utility"]
                    w.writerow(
                        [
                            exp,
                            r["config"],
                            "benign passed",
                            u["k"],
                            u["n"],
                            f"{u['rate']:.4f}",
                            f"{u['lo']:.4f}",
                            f"{u['hi']:.4f}",
                        ]
                    )


# ---- charts --------------------------------------------------------------------------------

BLUE, ORANGE, AQUA, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e"


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#c9c8c3")
    ax.spines["bottom"].set_color("#c9c8c3")
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.yaxis.grid(True, color="#e6e5e1", linewidth=0.8)
    ax.set_axisbelow(True)


def chart_attack_success(rows: list[dict], path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    picks = [("none", ORANGE), ("keyword", AQUA), ("all", BLUE)]
    by = {r["config"]: r for r in rows}
    cats = [c for c in CATEGORIES if any(c in r["by_category"] for r in rows)]
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=150)
    width = 0.26
    for i, (cfg, color) in enumerate(picks):
        if cfg not in by:
            continue
        xs, ys, lo, hi = [], [], [], []
        for j, c in enumerate(cats):
            v = by[cfg]["by_category"].get(c)
            if v is None:
                continue
            xs.append(j + (i - 1) * (width + 0.02))
            ys.append(100 * v["rate"])
            if v["k"] == 0:
                ax.text(xs[-1], 1.5, "0%", ha="center", fontsize=8, color=INK)
            lo.append(max(0.0, 100 * (v["rate"] - v["lo"])))
            hi.append(max(0.0, 100 * (v["hi"] - v["rate"])))
        ax.bar(
            xs,
            ys,
            width,
            color=color,
            label=LABELS[cfg],
            yerr=[lo, hi],
            error_kw={"ecolor": MUTED, "elinewidth": 1, "capsize": 2},
        )
    ax.set_xticks(range(len(cats)), [c.replace("_", "\n") for c in cats])
    ax.set_ylabel("Attacks that succeeded (%)", color=MUTED)
    ax.set_ylim(0, 105)
    ax.set_title(title, loc="left", color=INK, fontsize=11, pad=26)
    ax.legend(frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0, 1.0), ncols=3)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def chart_by_config(tables: dict[str, list[dict]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(tables)
    fig, axes = plt.subplots(1, n, figsize=(5.8 * n, 4.6), dpi=150, squeeze=False, sharey=True)
    for ax, (exp, rows) in zip(axes[0], tables.items(), strict=True):
        ys = list(range(len(rows)))[::-1]
        for y, r in zip(ys, rows, strict=True):
            a = r["asr"]
            ax.errorbar(
                100 * a["rate"],
                y,
                xerr=[[100 * max(0, a["rate"] - a["lo"])], [100 * max(0, a["hi"] - a["rate"])]],
                fmt="o",
                color=BLUE,
                ecolor=MUTED,
                elinewidth=1.2,
                capsize=3,
                markersize=7,
            )
            fb = f"{pct(r['false_block'])} wrongly blocked" if "false_block" in r else ""
            ax.text(104, y, fb, va="center", fontsize=8, color=MUTED)
        ax.set_yticks(ys, [LABELS[r["config"]] for r in rows])
        ax.set_xlim(-3, 100)
        ax.set_xlabel("Attacks that succeeded (%), with 95% interval", color=MUTED)
        ax.set_title(EXPERIMENTS.get(exp, exp), loc="left", fontsize=9, color=INK)
        _style(ax)
        ax.yaxis.grid(False)
        ax.xaxis.grid(True, color="#e6e5e1", linewidth=0.8)
    fig.suptitle(
        "Attack success by guardrail configuration (lower is better)",
        x=0.01,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.tight_layout(rect=(0, 0, 0.93, 1))
    fig.savefig(path)
    plt.close(fig)


def chart_cost(rows: list[dict], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.5, 4.4), dpi=150)
    names = [LABELS[r["config"]].replace(" (baseline)", "") for r in rows]
    vals = [r["mean_tokens"] for r in rows]
    bars = ax.barh(names[::-1], vals[::-1], color=BLUE, height=0.55)
    for b, v in zip(bars, vals[::-1], strict=True):
        ax.text(
            v + max(vals) * 0.01,
            b.get_y() + b.get_height() / 2,
            f"{v:.0f}",
            va="center",
            fontsize=8,
            color=INK,
        )
    ax.set_xlabel("Mean tokens per run, estimated (benign tasks and attacks)", color=MUTED)
    ax.set_title("What each guardrail costs the real model", loc="left", fontsize=11, color=INK)
    ax.xaxis.grid(True, color="#e6e5e1", linewidth=0.8)
    ax.yaxis.grid(False)
    _style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color="#e6e5e1", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


SAMPLE_CASES = ("ind-p-001", "mem-s-001", "tool-s-001")


def export_sample_traces(out: Path) -> list[Path]:
    """Save the full trace of a few attacks under no guardrails and under all five, as JSON."""
    from agentguard.harness.cases import load_cases
    from agentguard.harness.runner import make_llm, run_attack

    cases = {c.id: c for c in load_cases(Path("data/cases.jsonl"))}
    folder = out / "sample_traces"
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for case_id in SAMPLE_CASES:
        for config in ("none", "all"):
            traces: dict[str, dict] = {}

            def keep(label: str, trace, store: dict = traces) -> None:
                store[label] = trace.to_dict()

            run_attack(cases[case_id], config, make_llm("scripted"), sink=keep)
            path = folder / f"{case_id}_{config}.json"
            path.write_text(json.dumps(traces, indent=1, ensure_ascii=False), encoding="utf-8")
            written.append(path)
    return written


def main(runs: Path = RUNS, out: Path = OUT) -> dict[str, list[dict]]:
    out.mkdir(parents=True, exist_ok=True)
    tables = {name: table(load(name, runs)) for name in EXPERIMENTS}
    tables = {k: v for k, v in tables.items() if v}
    by_seed = {n: load(n, runs) for n in VARIANCE_FILES}
    var = variance({k: v for k, v in by_seed.items() if v})

    md = [
        "# Results\n",
        "Generated by `python -m agentguard.harness.report`. Every number comes "
        "from automatic checks on state; see `limitations.md` before quoting any of them.\n",
    ]
    for name, rows in tables.items():
        n_att = rows[0]["asr"]["n"]
        md += [
            f"## {EXPERIMENTS[name]}\n",
            f"{n_att} attack cases per configuration.\n",
            markdown_table(rows),
            "",
        ]
    real = tables.get("groq_main")
    if real:
        md += ["## Cost of each configuration (real model)\n", cost_table(real), ""]
    if var:
        md += [
            "## Variation between seeds (real model, temperature 0.7)\n",
            variance_table(var),
            "",
        ]
    (out / "results_table.md").write_text("\n".join(md), encoding="utf-8")
    write_csv(out / "results_table.csv", tables)
    if "scripted_test" in tables:
        chart_attack_success(
            tables["scripted_test"],
            out / "chart_attack_success.png",
            "Attack success by category: scripted worst-case agent, test split",
        )
    if tables:
        chart_by_config(tables, out / "chart_by_config.png")
    if real:
        chart_cost(real, out / "chart_cost.png")
    export_sample_traces(out)
    return tables


if __name__ == "__main__":
    main()
