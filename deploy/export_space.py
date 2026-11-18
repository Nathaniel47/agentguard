"""Build a folder that can be pushed to a Hugging Face Space (Docker SDK).

    python deploy/export_space.py [output_dir]      # default: build/space

It copies only what the running app needs (no tests, datasets or run records) and swaps in the
Space's README, which carries the YAML header Hugging Face reads.
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = ("agentguard", "api", "web")
FILES = ("Dockerfile", "requirements.txt", ".dockerignore")
RESULTS = (
    "results_table.md",
    "limitations.md",
    "chart_attack_success.png",
    "chart_by_config.png",
    "chart_cost.png",
)


def export(out: Path, root: Path = ROOT) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for folder in FOLDERS:
        shutil.copytree(root / folder, out / folder, ignore=ignore)
    for name in FILES:
        shutil.copy(root / name, out / name)
    (out / "results").mkdir()
    for name in RESULTS:
        if (root / "results" / name).exists():
            shutil.copy(root / "results" / name, out / "results" / name)
    shutil.copy(root / "deploy" / "space_README.md", out / "README.md")
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "space"
    print(f"Exported to {export(target)}")
