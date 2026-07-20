"""Image compression and processing for product uploads."""
import re
from io import BytesIO
from PIL import Image


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def compress_image(
    file_bytes: bytes,
    max_width: int = 1200,
    webp_quality: int = 80,
) -> bytes:
    """Resize and compress an image to WebP format.

    - Resizes to max_width preserving aspect ratio (no upscale).
    - Converts RGBA/P mode to RGB for WebP compatibility.
    - Returns compressed WebP bytes.
    """
    img = Image.open(BytesIO(file_bytes))

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="WEBP", quality=webp_quality)
    return buf.getvalue()


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def get_compressed_filename(sku: str, timestamp: int, folder: str = "misc") -> str:
    """Generate a .webp filename using the product SKU and folder prefix."""
    return f"{folder}/{_slugify(sku)}_{timestamp}.webp"
