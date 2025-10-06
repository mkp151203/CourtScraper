"""
CAPTCHA OCR Utility
Automatically detects text from CAPTCHA images using EasyOCR
"""

import easyocr
from PIL import Image, ImageEnhance, ImageFilter
import io
import re

# Initialize EasyOCR reader once (it's expensive to create)
_reader = None

def get_reader():
    """Get or create EasyOCR reader instance"""
    global _reader
    if _reader is None:
        try:
            # Initialize with English language, GPU if available
            # Restrict to lowercase letters and numbers for court CAPTCHAs
            _reader = easyocr.Reader(
                ['en'], 
                gpu=False
            )
            print("[INFO] EasyOCR reader initialized with lowercase + numbers only")
        except Exception as e:
            print(f"[ERROR] Failed to initialize EasyOCR: {e}")
            _reader = False  # Mark as failed
    return _reader if _reader is not False else None


def detect_captcha_text(image_bytes: bytes) -> str:
    """
    Detect text from CAPTCHA image using EasyOCR
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        Detected text from the CAPTCHA image (cleaned and uppercase)
    """
    try:
        reader = get_reader()
        if reader is None:
            print("[WARNING] EasyOCR not available, returning empty string")
            return ""
        
        # Load image from bytes
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Preprocess the image for better OCR accuracy
        image = preprocess_captcha_image(image)
        
        # Convert PIL image to bytes for EasyOCR
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Extract text using EasyOCR
        # Returns list of (bbox, text, confidence)
        results = reader.readtext(img_byte_arr, detail=1, paragraph=False,allowlist='abcdefghijklmnopqrstuvwxyz0123456789')
        
        # Combine all detected text
        text = ' '.join([result[1] for result in results])
        
        # Clean the text
        text = clean_captcha_text(text)
        
        return text
        
    except Exception as e:
        print(f"[WARNING] CAPTCHA OCR failed: {e}")
        # Return empty string if OCR fails
        return ""


def preprocess_captcha_image(image: Image.Image) -> Image.Image:
    """
    Preprocess CAPTCHA image to improve OCR accuracy
    
    Args:
        image: PIL Image object
        
    Returns:
        Preprocessed PIL Image
    """
    try:
        # Resize image for better OCR (larger is better for tesseract)
        width, height = image.size
        new_width = width * 2
        new_height = height * 2
        image = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Convert to grayscale
        image = image.convert('L')
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        
        # Increase sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        
        # Apply threshold to get binary image (black text on white background)
        threshold = 128
        image = image.point(lambda p: 255 if p > threshold else 0)
        
        # Apply slight blur to reduce noise
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        return image
        
    except Exception as e:
        print(f"[WARNING] Image preprocessing failed: {e}")
        return image


def clean_captcha_text(text: str) -> str:
    """
    Clean extracted text from CAPTCHA
    
    Args:
        text: Raw OCR output
        
    Returns:
        Cleaned text (lowercase alphanumeric only)
    """
    # Remove whitespace
    text = text.strip()
    
    # Remove all non-alphanumeric characters
    text = re.sub(r'[^a-z0-9]', '', text.lower())
    
    # Keep lowercase for court CAPTCHAs
    # (they only use lowercase letters and numbers)
    
    return text


def is_easyocr_available() -> bool:
    """
    Check if EasyOCR is available and initialized
    
    Returns:
        True if EasyOCR is available, False otherwise
    """
    try:
        reader = get_reader()
        return reader is not None
    except Exception:
        return False
