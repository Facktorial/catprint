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


def id_card(
    company: str,
    name: str,
    photo: PIL.Image.Image | None = None,
    logo: PIL.Image.Image | None = None,
    description: str = "",
    *,
    width: int = PRINTER_WIDTH,
    padding: int = 6,
    pokeball_count: int = 0,
    pokeball_icon: PIL.Image.Image | None = None,
) -> PIL.Image.Image:
    """Render a simple ID card image: logo + company, name, photo, description and pokeballs.

    The card is rendered at a 16:9 aspect ratio with the given `width` (default PRINTER_WIDTH)
    so it fits the printer width while keeping a 16:9 layout.
    Returns a printer-ready 1-bit image.
    """
    # Fonts (reverted to previous sizes, increased desc font for contrast)
    header_font = PIL.ImageFont.truetype(
        str(importlib.resources.files("catprint").joinpath("fonts/NotoSans_ExtraCondensed-Black.ttf")),
        20,
    )
    name_font = PIL.ImageFont.truetype(
        str(importlib.resources.files("catprint").joinpath("fonts/NotoSansMono_ExtraCondensed-Regular.ttf")),
        22,
    )
    desc_font = PIL.ImageFont.truetype(
        str(importlib.resources.files("catprint").joinpath("fonts/NotoSansMono_ExtraCondensed-Regular.ttf")),
        16,
    )

    # Determine card height for 16:9 (width x height = 16:9)
    card_height = max(int(width * 9 / 16), 64)

    # Prepare images and scale to fit the card area
    logo_img = None
    if logo is not None:
        logo_img = logo.copy().convert("RGB")
        # slightly larger logo for better visibility
        max_logo_h = int(card_height * 0.25)
        logo_img.thumbnail((max_logo_h, max_logo_h))

    # Static photo box size (square)
    photo_box_size = int(card_height * 0.6)
    photo_img = None
    if photo is not None:
        photo_img = photo.copy()
        # Resize to fit box
        photo_img.thumbnail((photo_box_size, photo_box_size))
        # Process photo with same quality as receipt images (dithering for gradients)
        photo_img = image_page(photo_img, dither=True, contrast=1.2, sharpen=False)
        # Convert back to RGB so it can be pasted on the canvas
        photo_img = photo_img.convert("RGB")

    # Description: respect explicit newlines, otherwise wrap
    desc_lines = []
    if description:
        if "\n" in description:
            desc_lines = [ln for ln in description.splitlines() if ln.strip() != ""]
        else:
            max_chars = max(20, int(width / 10))
            for i in range(0, len(description), max_chars):
                desc_lines.append(description[i : i + max_chars])

    # Canvas fixed to 16:9
    canvas = PIL.Image.new("RGB", (width, card_height), color=(255, 255, 255))
    draw = PIL.ImageDraw.Draw(canvas)

    x = padding
    y = padding

    # Logo and company name (top-left)
    if logo_img:
        canvas.paste(logo_img, (x, y))
        x += logo_img.width + padding

    draw.text((x, y), company, font=header_font, fill="black")

    # Name (left-aligned, below header)
    # use slightly tighter spacing between header/logo and name
    name_y = y + (logo_img.height if logo_img else 32) + max(2, padding // 3)
    draw.text((padding, name_y), name, font=name_font, fill="black")

    # Use font metrics to compute consistent name height regardless of case
    try:
        ascent, descent = name_font.getmetrics()
        name_h = ascent + descent
    except Exception:
        name_bbox = name_font.getbbox(name)
        name_h = name_bbox[3] - name_bbox[1]

    divider_y = name_y + name_h + padding // 2
    # stop the divider before the photo area with a small right margin
    divider_end = max(padding, width - padding - photo_box_size - padding // 2)
    # divider will be drawn after the description background so it sits on top of the bg

    # Photo box on the right (reserve space even when no photo)
    photo_x = width - padding - photo_box_size
    photo_y = padding
    if photo_img:
        # center photo inside the box vertically if smaller
        py = photo_y + (photo_box_size - photo_img.height) // 2
        px = photo_x + (photo_box_size - photo_img.width) // 2
        canvas.paste(photo_img, (px, py))
    else:
        # draw empty box outline
        draw.rectangle([photo_x, photo_y, photo_x + photo_box_size, photo_y + photo_box_size], outline="black", width=2)

    # Description below divider with larger line spacing and a light background for contrast
    desc_y = divider_y + padding
    if desc_lines:
        try:
            d_ascent, d_descent = desc_font.getmetrics()
            line_h = d_ascent + d_descent
        except Exception:
            line_h = desc_font.getbbox("Č")[3] - desc_font.getbbox("Č")[1]
        # slightly tighter line spacing to reduce vertical gaps
        spacing = int(line_h * 1.25)
        # draw background rectangle for better contrast (use near-white so final 1-bit conversion with no dithering stays clean)
        bg_top = desc_y - int(spacing * 0.25)
        bg_bottom = desc_y + spacing * len(desc_lines) + int(spacing * 0.25)
        # reserve space for pokeballs so description won't overlap the bottom icons
        try:
            poke_inner = (28, 28)
            poke_gap = 8
            poke_rows = 2
            poke_height_est = poke_rows * poke_inner[1] + poke_gap * (poke_rows - 1)
            poke_start_est = card_height - padding - poke_height_est
            bg_bottom = min(bg_bottom, poke_start_est - 4)
        except Exception:
            pass
        draw.rectangle([padding - 2, bg_top, width - padding - photo_box_size - 2, bg_bottom], fill=(245, 245, 245))
        for ln in desc_lines:
            draw.text((padding, desc_y), ln, font=desc_font, fill="black")
            desc_y += spacing

        # Draw divider line below name (ensure it's on top of the description background)
        draw.line([(padding, divider_y), (divider_end, divider_y)], fill="black", width=2)

    # ensure description starts slightly closer to the divider
    desc_y = divider_y + max(4, padding // 2)

    # Draw pokeballs area (bottom-left) - two rows, up to 6 items
    # use smaller icons and tighter gaps to keep the area compact
    if pokeball_count and pokeball_icon is not None:
        try:
            icon = pokeball_icon.copy().convert("RGBA")
            inner = (28, 28)
            gap = 8
            cols = 3
            rows = 2
            # compute area height for icons
            poke_height = rows * inner[1] + gap * (rows - 1)
            start_x = padding
            start_y = card_height - padding - poke_height
            for i in range(min(6, int(pokeball_count))):
                r = i // cols
                c = i % cols
                px = start_x + c * (inner[0] + gap)
                py = start_y + r * (inner[1] + gap)
                ik = icon.resize(inner, PIL.Image.Resampling.LANCZOS)
                canvas.paste(ik, (px, py), ik)
        except Exception:
            pass



    # Convert to printer-friendly 1-bit image
    # Use no dithering for the ID card to avoid dotted backgrounds on light fills
    # Use standard threshold for grayscale photos
    return image_page(canvas, dither=False, contrast=1.6, sharpen=True, threshold=160)
