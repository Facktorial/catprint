import importlib.resources
import itertools
from catprint.compat import batched, LANCZOS, FLIP_LEFT_RIGHT, ROTATE_270
import PIL
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageEnhance
try:
    from catprint.printer import PRINTER_WIDTH
except Exception:
    # allow importing render even when optional deps (bleak) for printer are not installed
    PRINTER_WIDTH = 384
import importlib


def image_page(
    image: PIL.Image.Image, *, dither=True, contrast=1.2, sharpen=True, threshold=212
) -> PIL.Image.Image:
    """
    Convert image to 1-bit for thermal printing with quality enhancements.
    Args:
        image: Input PIL Image
        dither: Use Floyd-Steinberg dithering (better for photos/complex images)
        contrast: Contrast adjustment (1.0 = no change, >1.0 = more contrast)
        sharpen: Apply sharpening filter
        threshold: Threshold value for 1-bit conversion (0-255, default 212)
    """
    # Resize first if needed
    if image.width > PRINTER_WIDTH:
        new_height = int(image.height * PRINTER_WIDTH / image.width)
        image = image.resize((PRINTER_WIDTH, new_height), LANCZOS)
    # Convert to grayscale first
    if image.mode != "L":
        image = image.convert("L")
    # Enhance contrast for better text readability
    if contrast != 1.0:
        enhancer = PIL.ImageEnhance.Contrast(image)
        image = enhancer.enhance(contrast)
    # Sharpen for better text clarity
    if sharpen:
        enhancer = PIL.ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.5)
    # Convert to 1-bit with optional dithering
    if dither:
        # Floyd-Steinberg dithering (better for photos and complex images)
        from catprint.compat import DITHER_FLOYD

        image = image.convert("1", dither=DITHER_FLOYD if DITHER_FLOYD is not None else None)
    else:
        # Simple threshold (better for text and line art)
        image = image.point(lambda x: 0 if x < threshold else 255, mode="1")
    return image


def pdf_page(image: PIL.Image.Image, *, contrast=1.5, threshold=212) -> PIL.Image.Image:
    """
    Specialized rendering for PDF pages - optimized for text clarity.
    Uses higher contrast and no dithering for crisp text.
    """
    return image_page(
        image, dither=False, contrast=contrast, sharpen=True, threshold=threshold
    )


def photo(image: PIL.Image.Image) -> PIL.Image.Image:
    """
    Specialized rendering for photos - uses dithering for better gradients.
    """
    return image_page(image, dither=True, contrast=1.1, sharpen=False)


def text(text: str, *, font_size: int = 18, line_length: int = 44) -> PIL.Image.Image:
    font = PIL.ImageFont.truetype(
        str(
            importlib.resources.files("catprint").joinpath(
                "fonts/NotoSansMono_ExtraCondensed-Regular.ttf"
            )
        ),
        font_size,
    )
    left, top, right, bottom = font.getbbox("Č")
    height = int((bottom - top) * 1.4)
    lines = [
        "".join(subline)
        for line in text.splitlines()
        for subline in batched(line, line_length)
    ]
    img = PIL.Image.new("1", (PRINTER_WIDTH, len(lines) * height), color="white")
    draw = PIL.ImageDraw.Draw(img)
    for y, line in enumerate(lines):
        draw.text((0, y * height), line, fill="black", font=font)
    return img


def banner(text: str) -> PIL.Image.Image:
    font = PIL.ImageFont.truetype(
        str(
            importlib.resources.files("catprint").joinpath(
                "fonts/NotoSans_ExtraCondensed-Black.ttf"
            )
        ),
        PRINTER_WIDTH,
    )
    left, top, right, bottom = font.getbbox(text)
    text_width, text_height = int(right - left), int(bottom - top)
    canvas_width = text_width
    canvas_height = PRINTER_WIDTH
    img = PIL.Image.new("1", (canvas_width, canvas_height), color="white")
    PIL.ImageDraw.Draw(img).text(
        (
            (canvas_width - text_width) // 2 - left,
            (canvas_height - text_height) // 2 - top,
        ),
        text,
        fill="black",
        font=font,
    )
    # use compatibility rotation constant
    return img.transpose(ROTATE_270 if ROTATE_270 is not None else PIL.Image.ROTATE_270)


def text_banner(text: str, *, font_size: int = 18) -> PIL.Image.Image:
    font = PIL.ImageFont.truetype(
        str(
            importlib.resources.files("catprint").joinpath(
                "fonts/NotoSansMono_ExtraCondensed-Regular.ttf"
            )
        ),
        font_size,
    )
    _, _, char_width, char_height = font.getbbox("#")
    banner_img = banner(text)
    img = PIL.Image.new("1", (banner_img.width, banner_img.height), color="white")
    draw = PIL.ImageDraw.Draw(img)
    text_iter = itertools.cycle(c for c in text if c != " ")
    rows = int(banner_img.height / char_height)
    cols = int(banner_img.width / char_width)
    for y in range(rows):
        line_text = ""
        for x in range(cols):
            if banner_img.getpixel(
                (int((x + 0.5) * char_width), int((y + 0.5) * char_height))
            ):
                line_text += " "
            else:
                line_text += next(text_iter)
        draw.text((0, y * char_height), line_text, fill="black", font=font)
    return img


def stack(*images: PIL.Image.Image) -> PIL.Image.Image:
    max_width = max(img.width for img in images)
    resized_images = [
        img
        if img.width == max_width
        else img.resize((max_width, int(img.height * max_width / img.width)))
        for img in images
    ]
    total_height = sum(img.height for img in resized_images)
    mode = images[0].mode
    stacked_image = PIL.Image.new(mode, (max_width, total_height))
    y_offset = 0
    for img in resized_images:
        stacked_image.paste(img, (0, y_offset))
        y_offset += img.height
    return stacked_image


def blank(height: int) -> PIL.Image.Image:
    return PIL.Image.new("1", (PRINTER_WIDTH, height), color="white")
