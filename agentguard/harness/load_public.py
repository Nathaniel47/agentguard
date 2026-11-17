"""Download (pinned versions) and read the public prompt-injection sets.

Only the attacker's wording is reused. Every goal, success marker and target tool is our own,
so no public test case is run as-is against anything. Licences are recorded in SOURCES.
"""

import hashlib
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

RAW_DIR = Path("data/raw")

INJECAGENT_COMMIT = "f19c9f2c79a41046eb13c03c51a24c567a8ffa07"
DEEPSET_COMMIT = "4f61ecb038e9c3fb77e21034b22511b523772cdd"
_IA = f"https://raw.githubusercontent.com/uiuc-kang-lab/InjecAgent/{INJECAGENT_COMMIT}/data"
_DS = f"https://huggingface.co/datasets/deepset/prompt-injections/resolve/{DEEPSET_COMMIT}/data"

# local name -> url
FILES = {
    "attacker_cases_dh.jsonl": f"{_IA}/attacker_cases_dh.jsonl",
    "attacker_cases_ds.jsonl": f"{_IA}/attacker_cases_ds.jsonl",
    "deepset_train.parquet": f"{_DS}/train-00000-of-00001-9564e8b05b4757ab.parquet",
    "deepset_test.parquet": f"{_DS}/test-00000-of-00001-701d16158af87368.parquet",
}

SOURCES = {
    "injecagent": {
        "name": "InjecAgent (attacker cases)",
        "url": "https://github.com/uiuc-kang-lab/InjecAgent",
        "commit": INJECAGENT_COMMIT,
        "licence": "MIT",
        "use": "attacker instruction wording only (62 instructions)",
    },
    "deepset": {
        "name": "deepset/prompt-injections",
        "url": "https://huggingface.co/datasets/deepset/prompt-injections",
        "commit": DEEPSET_COMMIT,
        "licence": "Apache-2.0",
        "use": "English injection prompts only (label 1)",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(raw_dir: Path = RAW_DIR) -> dict[str, str]:
    """Fetch any missing file and return {name: sha256}. Existing files are not re-fetched."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        path = raw_dir / name
        if not path.exists():
            req = Request(url, headers={"User-Agent": "research-data-loader"})
            with urlopen(req, timeout=60) as resp:  # noqa: S310 - pinned https URLs above
                path.write_bytes(resp.read())
    return {name: sha256(raw_dir / name) for name in FILES}


_STOPWORDS = {"the", "and", "you", "to", "of", "is", "are", "what", "your", "for", "this", "all"}


def is_english(text: str) -> bool:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if len(words) < 3:
        return False
    return (
        sum(w in _STOPWORDS for w in words) >= 1
        and sum(ord(c) < 128 for c in text) / len(text) > 0.97
    )


def load_deepset(raw_dir: Path = RAW_DIR) -> tuple[list[str], dict]:
    """English label-1 prompts, de-duplicated and length-limited, in a stable order."""
    frames = [pd.read_parquet(raw_dir / f"deepset_{s}.parquet") for s in ("train", "test")]
    df = pd.concat(frames, ignore_index=True)
    injections = df[df.label == 1].text.tolist()
    stats = {"label1_total": len(injections)}
    seen, kept = set(), []
    for text in injections:
        text = text.strip()
        key = re.sub(r"\W+", " ", text.lower()).strip()
        if key in seen or not (20 <= len(text) <= 400) or not is_english(text):
            continue
        seen.add(key)
        kept.append(text)
    stats["kept"] = len(kept)
    stats["dropped"] = stats["label1_total"] - len(kept)
    return sorted(kept), stats


def load_injecagent(raw_dir: Path = RAW_DIR) -> tuple[dict[str, list[dict]], dict]:
    """Attacker cases grouped as 'dh' (direct harm) and 'ds' (data stealing), de-duplicated."""
    out, stats = {}, {}
    for kind in ("dh", "ds"):
        rows = [
            json.loads(line)
            for line in (raw_dir / f"attacker_cases_{kind}.jsonl").read_text("utf-8").splitlines()
            if line.strip()
        ]
        seen, kept = set(), []
        for row in rows:
            instr = row["Attacker Instruction"].strip()
            if instr not in seen:
                seen.add(instr)
                kept.append({"instruction": instr, "attack_type": row["Attack Type"]})
        out[kind] = sorted(kept, key=lambda r: r["instruction"])
        stats[kind] = {"rows": len(rows), "kept": len(kept)}
    return out, stats
