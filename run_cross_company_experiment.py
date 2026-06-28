#!/usr/bin/env python3
"""Run the full cross-company enterprise-agent experiment locally."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str]) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cross-company agent experiment.")
    parser.add_argument("--fetch-public-sources", action="store_true")
    parser.add_argument("--python", default=sys.executable)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    py = args.python
    build_cmd = [py, "build_multi_company_corpus.py"]
    if args.fetch_public_sources:
        build_cmd.append("--fetch-public-sources")
    run(build_cmd)
    run([py, "generate_cross_company_attacks.py"])
    run([py, "enterprise_agent.py", "--mode", "control"])
    run([py, "enterprise_agent.py", "--mode", "secure"])
    run(
        [
            py,
            "evaluate_cross_company.py",
            "--run",
            "control=outputs/cross_company_agent/control/results.csv",
            "--run",
            "secure=outputs/cross_company_agent/secure/results.csv",
            "--outdir",
            str(Path("outputs/cross_company_agent/evaluation")),
        ]
    )


if __name__ == "__main__":
    main()
