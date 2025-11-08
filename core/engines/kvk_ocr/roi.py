from __future__ import annotations

from typing import List, Tuple

from PIL import Image


class ROIExtractor:
    """Detect likely score table regions so MMOCR focuses on a narrow crop."""

    def segment(self, image: Image.Image) -> List[Image.Image]:
        """Return cropped image regions that cover common scoreboard layouts."""
        width, height = image.size
        if height < 1 or width < 1:
            return [image]

        ratios: Tuple[Tuple[float, float], ...] = (
            (0.35, 1.0),  # bottom 65% where rankings usually sit
            (0.45, 0.9),  # tighter middle-lower band
            (0.0, 0.5),   # fallback top half for alternative layouts
        )

        rois: List[Image.Image] = []
        seen: set[Tuple[int, int]] = set()
        for top_ratio, bottom_ratio in ratios:
            top = int(height * top_ratio)
            bottom = min(height, int(height * bottom_ratio))
            if bottom <= top:
                continue
            key = (top, bottom)
            if key in seen:
                continue
            seen.add(key)
            rois.append(image.crop((0, top, width, bottom)))

        if not rois:
            rois.append(image)

        return rois
