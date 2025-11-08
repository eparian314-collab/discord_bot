from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageFilter, ImageOps


class Preprocessor:
    """Apply safe filters so Android and iPhone screenshots become clearer for MMOCR."""

    def enhance(self, image_bytes: bytes) -> Image.Image:
        """Load the image, normalize contrast, and lightly sharpen edges."""
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = image.size
        max_dimension = 2048
        scale = min(max_dimension / max(width, height), 1.0)
        if scale < 1.0:
            image = image.resize(
                (int(width * scale), int(height * scale)),
                resample=Image.LANCZOS,
            )

        image = ImageOps.autocontrast(image, cutoff=1)
        image = image.filter(ImageFilter.ModeFilter(size=3))
        image = image.filter(ImageFilter.MedianFilter(size=3))
        image = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=3))
        return image
