from __future__ import annotations

import asyncio
from typing import List

from PIL import Image

try:
    import numpy as np  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - fallback if numpy missing
    np = None  # type: ignore[assignment]

try:
    from mmocr.utils.ocr import MMOCR
except ImportError:  # pragma: no cover - mmocr optional
    MMOCR = None  # type: ignore[assignment]

try:
    import pytesseract
except ImportError:  # pragma: no cover - fallback when MMOCR is unavailable
    pytesseract = None  # type: ignore[assignment]


class MMOCRClient:
    """Wrapper that runs MMOCR locally and falls back to pytesseract if needed."""

    def __init__(self, det_model: str = "DB_r18", recog_model: str = "CRNN"):
        self._mmocr = None
        if MMOCR:
            self._mmocr = MMOCR(det=det_model, recog=recog_model)

    async def read_text(self, image: Image.Image) -> List[str]:
        """Detect text lines from the provided PIL image."""
        if self._mmocr is not None and np is not None:
            array = np.array(image.convert("RGB"))
            try:
                raw_result = await asyncio.to_thread(self._mmocr.readtext, array)
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(f"MMOCR inference failed: {exc}") from exc
            texts: List[str] = []
            for entry in raw_result:
                if isinstance(entry, dict):
                    text = entry.get("text") or entry.get("transcription")
                else:
                    text = entry
                if isinstance(text, str):
                    clean = text.strip()
                    if clean:
                        texts.append(clean)
            return texts

        if pytesseract:
            extracted = await asyncio.to_thread(pytesseract.image_to_string, image)
            return [line for line in extracted.splitlines() if line.strip()]

        raise RuntimeError(
            "MMOCR is not installed and no fallback OCR backend is available. "
            "Install mmocr (and its dependencies) or ensure pytesseract is available."
        )
