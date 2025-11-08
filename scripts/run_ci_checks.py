#!/usr/bin/env python3
"""
Helper script to run the full verification loop (pytest + simulations) locally.

Usage:
    python scripts/run_ci_checks.py [--pytest-args "..."] [--skip-tests] [--skip-sim]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, cmd: list[str], env: dict[str, str] | None = None) -> None:
    """Run a subprocess step and exit early on failure."""
    print(f"\n=== Running {name} ===")
    completed = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env or os.environ.copy(),
        check=False,
    )
    if completed.returncode != 0:
        print(f"\n{name} failed with exit code {completed.returncode}")
        sys.exit(completed.returncode)
    print(f"{name} passed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run tests and simulations.")
    parser.add_argument(
        "--pytest-args",
        default="",
        help="Optional extra arguments forwarded to pytest (e.g. '-m smoke').",
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest run.")
    parser.add_argument("--skip-sim", action="store_true", help="Skip simulation run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.skip_tests:
        pytest_cmd = [sys.executable, "-m", "pytest"]
        if args.pytest_args:
            pytest_cmd.extend(args.pytest_args.split())
        run_step("pytest suite", pytest_cmd)
    else:
        print("Skipping pytest run.")

    if not args.skip_sim:
        sim_env = os.environ.copy()
        sim_env.setdefault("PYTHONIOENCODING", "utf-8")
        run_step(
            "simulation suite",
            [sys.executable, "scripts/simulation_test.py"],
            env=sim_env,
        )
    else:
        print("Skipping simulation run.")

    print("\nAll requested checks passed successfully.")


if __name__ == "__main__":
    main()
