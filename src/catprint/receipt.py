from __future__ import annotations

import base64
import io
from typing import Iterable, List, Optional

import PIL.Image

from . import render


def _decode_image_from_base64(s: str) -> PIL.Image.Image:
    return PIL.Image.open(io.BytesIO(base64.b64decode(s)))


def _convert_pdf_bytes(pdf_bytes: bytes, dpi: int = 150) -> List[PIL.Image.Image]:
    try:
        import pdf2image
    except Exception as e:
        raise RuntimeError("pdf2image is required to process PDF blocks: " + str(e))
    return pdf2image.convert_from_bytes(pdf_bytes, dpi=dpi)


def render_blocks(blocks: Iterable, *, include_template: bool = False, template=None) -> List[PIL.Image.Image]:
    """Render a list of blocks into printer-ready pages.

    Blocks may be either dict-like (as sent to the HTTP API) or objects with attributes
    (as used by the Streamlit app). Supported block types: text, banner, image, pdf.
    """
    pages: List[PIL.Image.Image] = []

    tpl = template

    if include_template and tpl is not None:
        pages.append(render.image_page(PIL.Image.open(tpl.logo_path())))
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

    if include_template and tpl is not None:
        pages.append(render.text(tpl.footer()))

    return pages
