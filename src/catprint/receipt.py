from __future__ import annotations

import base64
import io
from typing import Iterable, List, Optional

import PIL.Image

from . import render
from catprint.templates import get_template


def _decode_image_from_base64(s: str) -> PIL.Image.Image:
    return PIL.Image.open(io.BytesIO(base64.b64decode(s)))


def _convert_pdf_bytes(pdf_bytes: bytes, dpi: int = 150) -> List[PIL.Image.Image]:
    try:
        import pdf2image
    except Exception as e:
        raise RuntimeError("pdf2image is required to process PDF blocks: " + str(e))
    return pdf2image.convert_from_bytes(pdf_bytes, dpi=dpi)


def render_blocks(
    blocks: Iterable,
    *,
    include_template: bool | None = None,
    include_logo: bool | None = None,
    include_header_footer: bool | None = None,
    template=None,
) -> List[PIL.Image.Image]:
    """Render a list of blocks into printer-ready pages.

    Blocks may be either dict-like (as sent to the HTTP API) or objects with attributes
    (as used by the Streamlit app). Supported block types: text, banner, image, pdf.

    Compatibility: the legacy flag `include_template` controls both logo and header/footer
    when provided. New flags `include_logo` and `include_header_footer` can be used to
    control them independently.
    """
    pages: List[PIL.Image.Image] = []

    tpl = template

    # Resolve inclusion flags
    if include_template is not None:
        incl_logo = bool(include_template)
        incl_hf = bool(include_template)
    else:
        incl_logo = bool(include_logo)
        incl_hf = bool(include_header_footer)

    if incl_logo and tpl is not None:
        pages.append(render.image_page(PIL.Image.open(tpl.logo_path())))
    if incl_hf and tpl is not None:
        pages.append(render.text(tpl.header()))

    for block in blocks:
        # support both dict and object
        btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        data = block.get("data") if isinstance(block, dict) else getattr(block, "data", None)
        meta = block.get("meta") if isinstance(block, dict) else getattr(block, "meta", None)

        if btype == "text":
            if data and str(data).strip():
                pages.append(render.text(str(data)))

        elif btype == "banner":
            if data and str(data).strip():
                pages.append(render.text_banner(str(data)))

        elif btype == "image":
            img = None
            if isinstance(data, str):
                img = _decode_image_from_base64(data)
            elif isinstance(data, PIL.Image.Image):
                img = data
            if img is not None:
                pages.append(render.image_page(img))

        elif btype == "pdf":
            # data may already be a list of PIL images (Streamlit), or base64 PDF bytes,
            # or a file-like object (UploadedFile). If `data` is None, skip.
            if data is None:
                continue

            pages_list: List[PIL.Image.Image]
            if isinstance(data, list):
                pages_list = data
            else:
                # support file-like objects
                if hasattr(data, "read"):
                    pdf_bytes = data.read()
                elif isinstance(data, str):
                    pdf_bytes = base64.b64decode(data)
                elif isinstance(data, (bytes, bytearray)):
                    pdf_bytes = bytes(data)
                else:
                    # unknown format - ignore the block instead of raising
                    continue
                dpi = int(meta.get("dpi", 150)) if meta else 150
                pages_list = _convert_pdf_bytes(pdf_bytes, dpi=dpi)

            for p in pages_list:
                # Resize to printer width while maintaining aspect ratio
                aspect_ratio = p.height / p.width
                new_height = int(384 * aspect_ratio)
                from catprint.compat import LANCZOS
                resized_img = p.resize((384, new_height), LANCZOS if LANCZOS is not None else PIL.Image.LANCZOS)
                contrast = float(meta.get("contrast", 1.5)) if meta else 1.5
                threshold = int(meta.get("threshold", 212)) if meta else 212
                pages.append(render.pdf_page(resized_img, contrast=contrast, threshold=threshold))

        elif btype == "id_card":
            # data is a dict with keys: name, photo, description, template (optional)
            if not isinstance(data, dict):
                continue
            person_name = data.get("name", "")
            description = data.get("description", "")
            photo = data.get("photo")
            tpl_key = data.get("template")

            tpl = None
            if tpl_key:
                try:
                    tpl = get_template(tpl_key)
                except Exception:
                    tpl = None

            # Prepare photo image
            photo_img = None
            if isinstance(photo, PIL.Image.Image):
                photo_img = photo
            elif isinstance(photo, str):
                # Try base64 first
                try:
                    photo_img = PIL.Image.open(io.BytesIO(base64.b64decode(photo)))
                except Exception:
                    photo_img = None
                # Try file path or package resource
                if photo_img is None:
                    try:
                        # direct filesystem path
                        photo_img = PIL.Image.open(photo)
                    except Exception:
                        try:
                            # package asset path
                            asset_path = importlib.resources.files("catprint").joinpath("assets", photo)
                            if asset_path.exists():
                                photo_img = PIL.Image.open(asset_path)
                        except Exception:
                            photo_img = None
            elif hasattr(photo, "read"):
                try:
                    photo_img = PIL.Image.open(io.BytesIO(photo.read()))
                except Exception:
                    photo_img = None

            logo_img = None
            company_name = ""
            if tpl is not None:
                try:
                    logo_img = PIL.Image.open(tpl.logo_path())
                    company_name = tpl.name
                except Exception:
                    logo_img = None

            pages.append(render.id_card(company=company_name, name=person_name, photo=photo_img, logo=logo_img, description=description))

    if incl_hf and tpl is not None:
        pages.append(render.text(tpl.footer()))

    return pages
