"""
Test suite for image processing pipeline.
"""
import pytest
from PIL import Image
import numpy as np
import io
from pathlib import Path
import cv2

# Mock Discord attachment for testing
class MockAttachment:
    def __init__(self, content_type, valid_image=True):
        self.content_type = content_type
        self._valid = valid_image
        
    async def read(self):
        if not self._valid:
            return b'invalid bytes'
        # Create a small test image
        img = Image.new('RGB', (100, 100), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

@pytest.mark.asyncio
async def test_attachment_validation():
    """Test MIME type validation."""
    # Valid image
    valid = MockAttachment('image/png', True)
    assert valid.content_type.startswith('image/')
    
    # Invalid type
    invalid = MockAttachment('text/plain', False)
    assert not invalid.content_type.startswith('image/')

@pytest.mark.asyncio
async def test_image_decode():
    """Test image bytes to PIL conversion."""
    attachment = MockAttachment('image/png', True)
    img_bytes = await attachment.read()
    
    try:
        img = Image.open(io.BytesIO(img_bytes))
        img.verify()
        assert True  # Image decoded successfully
    except Exception:
        pytest.fail("Failed to decode valid image bytes")

@pytest.mark.asyncio
async def test_preprocessing():
    """Test image preprocessing pipeline."""
    # Create test image
    img = Image.new('RGB', (100, 100), color='white')
    
    # Test grayscale
    gray = img.convert('L')
    assert gray.mode == 'L'
    
    # Test numpy conversion
    np_img = np.array(gray)
    assert isinstance(np_img, np.ndarray)
    
    # Test blur
    blurred = cv2.GaussianBlur(np_img, (3,3), 0)
    assert blurred.shape == np_img.shape
    
    # Test thresholding
    threshold = cv2.threshold(blurred, 0, 255, cv2.THRESH_OTSU)[1]
    assert threshold.shape == np_img.shape

@pytest.mark.asyncio
async def test_invalid_image():
    """Test handling of invalid image data."""
    attachment = MockAttachment('image/png', False)
    img_bytes = await attachment.read()
    
    with pytest.raises(Exception):
        img = Image.open(io.BytesIO(img_bytes))
        img.verify()

if __name__ == '__main__':
    pytest.main([__file__])