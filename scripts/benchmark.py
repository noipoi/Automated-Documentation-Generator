#!/usr/bin/env python3
"""Measure wall-clock time of the custom generator vs. pdoc on the same project.

Usage (from the repository root):
    python scripts/benchmark.py            # 10 runs each
    python scripts/benchmark.py --runs 20

Both tools are started as separate processes, so the numbers include Python
start-up time for each. The script PRINTS what it measures; nothing is
hard-coded. Results depend on your machine - copy yours into docs/evaluation.md.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def time_command(cmd: list[str], env: dict[str, str], runs: int) -> list[float]:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        result = subprocess.run(cmd, env=env, cwd=ROOT, capture_output=True, text=True)
        elapsed = time.perf_counter() - start
        if result.returncode != 0:
            raise RuntimeError(f"command failed: {' '.join(cmd)}\n{result.stderr}")
        samples.append(elapsed)
    return samples


def summarise(name: str, samples: list[float]) -> None:
    print(
        f"{name:<18} runs={len(samples):<3} "
        f"mean={statistics.mean(samples):.3f}s  median={statistics.median(samples):.3f}s  "
        f"min={min(samples):.3f}s  max={max(samples):.3f}s"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=10, help="runs per tool (default 10)")
    args = parser.parse_args()

    print(f"Python {platform.python_version()} on {platform.platform()}")
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        custom = [sys.executable, "generate_docs.py", "--src", "src", "--output", f"{tmp}/DOCUMENTATION.md"]
        summarise("custom generator", time_command(custom, env, args.runs))

        probe = subprocess.run([sys.executable, "-c", "import pdoc"], capture_output=True)
        if probe.returncode != 0:
            print("pdoc            : SKIPPED (not installed - run: python -m pip install -r requirements.txt)")
            return 0
        pdoc = [sys.executable, "-m", "pdoc", "--output-directory", f"{tmp}/pdoc", "example_package"]
        summarise("pdoc", time_command(pdoc, env, args.runs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
