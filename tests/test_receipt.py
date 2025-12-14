from PIL import Image


def _make_white_image(w=384, h=50):
    return Image.new("RGB", (w, h), color=(255, 255, 255))


def test_render_blocks_text_and_image():
    from catprint import receipt

    blocks = [
        {"type": "text", "data": "Hello world"},
        {"type": "image", "data": _make_white_image()},
    ]

    pages = receipt.render_blocks(blocks)
    assert pages and all(hasattr(p, "width") for p in pages)


def test_render_blocks_pdf_list_pages():
    from catprint import receipt

    page1 = _make_white_image()
    page2 = _make_white_image(h=100)

    blocks = [{"type": "pdf", "data": [page1, page2], "meta": {"dpi": 150}}]
    pages = receipt.render_blocks(blocks)
    assert len(pages) == 2


def test_render_blocks_pdf_none_ignored():
    from catprint import receipt

    blocks = [{"type": "pdf", "data": None}]
    pages = receipt.render_blocks(blocks)
    assert pages == []
