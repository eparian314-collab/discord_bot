"""
Verify that EasyOCR model assets exist before enabling OCR-dependent commands.

Usage:
    python scripts/diagnostics/ocr_watchdog.py
"""

from __future__ import annotations

from pathlib import Path
import os
import sys

MODEL_HINTS = (
    "craft_mlt_25k.pth",
    "craft_refiner_CTW1500.pth",
    "english_g2.pth",
)

DEFAULT_DIR_CANDIDATES = (
    os.getenv("EASYOCR_MODEL_DIR"),
    Path("cache") / "easyocr",
    Path("cache") / "ocr_models",
)


def resolve_candidate_paths() -> list[Path]:
    paths: list[Path] = []
    for candidate in DEFAULT_DIR_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            paths.append(path)
    return paths


def has_required_models(directory: Path) -> bool:
    if not directory.exists():
        return False
    present = {path.name for path in directory.glob("*.pth")}
    return any(name in present for name in MODEL_HINTS)


def main() -> int:
    candidates = resolve_candidate_paths()
    if not candidates:
        print("No EasyOCR directories found. Set EASYOCR_MODEL_DIR or populate cache/easyocr.", file=sys.stderr)
        return 1

    for directory in candidates:
        if has_required_models(directory):
            print(f"EasyOCR models detected in {directory}")
            return 0

    print(
        "EasyOCR model files were not located. "
        "Ensure craft/english .pth weights are present before enabling ENABLE_OCR_TRAINING.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
