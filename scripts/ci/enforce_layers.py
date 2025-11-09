#!/usr/bin/env python3
"""
Verify layering guardrails:
 - engines stay Discord-free
 - cogs do not import implementation-layer engines
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, Set

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = PROJECT_ROOT / "core" / "engines"
COG_DIR = PROJECT_ROOT / "cogs"
BASELINE_PATH = PROJECT_ROOT / "docs" / "architecture" / "layering_baseline.json"

ENGINE_PATTERN = re.compile(r"^\s*(?:from|import)\s+discord(?:\b|\.)", re.MULTILINE)
COG_PATTERN = re.compile(r"^\s*from\s+(?:core|discord_bot\.core)\.engines", re.MULTILINE)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def gather_engine_discord_imports() -> Set[str]:
    results: Set[str] = set()
    for path in ENGINE_DIR.rglob("*.py"):
        if ENGINE_PATTERN.search(_read_text(path)):
            results.add(_rel(path))
    return results


def gather_cog_engine_imports() -> Set[str]:
    results: Set[str] = set()
    for path in COG_DIR.rglob("*.py"):
        if COG_PATTERN.search(_read_text(path)):
            results.add(_rel(path))
    return results


def load_baseline() -> Dict[str, Set[str]]:
    if not BASELINE_PATH.exists():
        return {"engine_discord_import": set(), "cog_engine_import": set()}
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {
        "engine_discord_import": set(data.get("engine_discord_import", [])),
        "cog_engine_import": set(data.get("cog_engine_import", [])),
    }


def write_baseline(snapshot: Dict[str, Set[str]]) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "engine_discord_import": sorted(snapshot.get("engine_discord_import", [])),
        "cog_engine_import": sorted(snapshot.get("cog_engine_import", [])),
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def compare(current: Dict[str, Set[str]], baseline: Dict[str, Set[str]]) -> int:
    exit_code = 0
    for key in ("engine_discord_import", "cog_engine_import"):
        current_set = current.get(key, set())
        baseline_set = baseline.get(key, set())
        new_entries = sorted(current_set - baseline_set)
        if new_entries:
            exit_code = 1
            print(f"[ERROR] New {key.replace('_', ' ')} violations:")
            for entry in new_entries:
                print(f"  - {entry}")
        stale_entries = sorted(baseline_set - current_set)
        if stale_entries:
            print(f"[INFO] Baseline contains resolved {key.replace('_', ' ')} entries:")
            for entry in stale_entries:
                print(f"  - {entry}")
    if exit_code == 0:
        print("Layering guardrails satisfied (no new violations).")
    return exit_code


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check layering guardrails.")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite the baseline file with the current violation snapshot.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    snapshot = {
        "engine_discord_import": gather_engine_discord_imports(),
        "cog_engine_import": gather_cog_engine_imports(),
    }

    if args.update_baseline:
        write_baseline(snapshot)
        print(f"Wrote baseline with {len(snapshot['engine_discord_import'])} engine entries "
              f"and {len(snapshot['cog_engine_import'])} cog entries.")
        return 0

    baseline = load_baseline()
    return compare(snapshot, baseline)


if __name__ == "__main__":
    sys.exit(main())
