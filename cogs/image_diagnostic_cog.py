"""
Image processing diagnostic cog for testing OCR pipeline stages.
"""
import io
import logging
import os

import cv2
import discord
import numpy as np
from discord.ext import commands
from PIL import Image

logger = logging.getLogger(__name__)

class ImageDiagnosticCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_debug_image = None

    @commands.command(name='testimg')
    async def test_image_intake(self, ctx):
        """Test basic image intake pipeline."""
        if not ctx.message.attachments:
            return await ctx.send("❌ Please attach an image to test.")

        attachment = ctx.message.attachments[0]
        
        # Stage 1: Validate MIME type
        if not attachment.content_type or not attachment.content_type.startswith("image/"):
            return await ctx.send("❌ Not a valid image file. Content-Type: " + str(attachment.content_type))

        try:
            # Stage 2: Download bytes
            img_bytes = await attachment.read()
            
            # Stage 3: Convert to PIL Image
            img = Image.open(io.BytesIO(img_bytes))
            img.verify()  # Verify image integrity
            
            # Store for debug
            self._last_debug_image = img_bytes
            
            await ctx.send("✅ Image successfully received and decoded!")
            
        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}", exc_info=True)
            return await ctx.send(f"⚠️ Image processing failed: {str(e)}")

    @commands.command(name='preprocess')
    async def test_preprocessing(self, ctx):
        """Test image preprocessing pipeline."""
        if not self._last_debug_image:
            return await ctx.send("❌ No image to process. Use !testimg first.")

        try:
            # Load the last tested image
            img = Image.open(io.BytesIO(self._last_debug_image))
            
            # Stage 1: Convert to grayscale
            gray = img.convert('L')
            await self._save_and_send(ctx, gray, "1_grayscale.png", "Grayscale conversion")
            
            # Stage 2: Convert to numpy for OpenCV
            np_img = np.array(gray)
            
            # Stage 3: Apply Gaussian blur
            blurred = cv2.GaussianBlur(np_img, (3,3), 0)
            blur_pil = Image.fromarray(blurred)
            await self._save_and_send(ctx, blur_pil, "2_blurred.png", "After Gaussian blur")
            
            # Stage 4: Otsu's thresholding
            threshold = cv2.threshold(blurred, 0, 255, cv2.THRESH_OTSU)[1]
            thresh_pil = Image.fromarray(threshold)
            await self._save_and_send(ctx, thresh_pil, "3_threshold.png", "After Otsu thresholding")
            
            # Store final preprocessed image
            self._last_debug_image = thresh_pil
            
        except Exception as e:
            logger.error(f"Preprocessing failed: {str(e)}", exc_info=True)
            return await ctx.send(f"⚠️ Preprocessing failed: {str(e)}")

    @commands.command(name='ocr')
    async def test_ocr(self, ctx):
        """Test OCR on preprocessed image."""
        if not self._last_debug_image:
            return await ctx.send("❌ No preprocessed image. Use !testimg and !preprocess first.")

        try:
            provider = self._get_ocr_provider()
            if provider == 'easyocr':
                text = await self._run_easyocr(self._last_debug_image)
            else:
                text = await self._run_tesseract(self._last_debug_image)
            
            # Format and send results
            if not text:
                await ctx.send("⚠️ No text detected in image.")
            else:
                await ctx.send(f"📝 Detected text:\n```\n{text}\n```")
                
        except Exception as e:
            logger.error(f"OCR failed: {str(e)}", exc_info=True)
            return await ctx.send(f"⚠️ OCR failed: {str(e)}")

    async def _save_and_send(self, ctx, img: Image.Image, filename: str, stage: str):
        """Save debug image and send to channel."""
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        await ctx.send(f"Debug image for: {stage}", 
                      file=discord.File(buffer, filename))

    async def _run_tesseract(self, img: Image.Image) -> str:
        """Run Tesseract OCR."""
        import pytesseract
        return pytesseract.image_to_string(img, config='--psm 6')

    async def _run_easyocr(self, img: Image.Image) -> str:
        """Run EasyOCR."""
        import easyocr
        reader = easyocr.Reader(['en'])
        results = reader.readtext(np.array(img))
        return '\n'.join(text for _, text, _ in results)

    def _get_ocr_provider(self) -> str:
        """Resolve OCR provider from bot config or environment variables."""
        config = getattr(self.bot, "config", None)
        if isinstance(config, dict):
            value = config.get("OCR_PROVIDER")
            if isinstance(value, str) and value.strip():
                return value.strip().lower()

        env_value = os.getenv("OCR_PROVIDER", "")
        if env_value:
            return env_value.strip().lower()
        return "tesseract"

async def setup(bot):
    await bot.add_cog(ImageDiagnosticCog(bot))
