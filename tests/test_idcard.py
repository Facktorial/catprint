from PIL import Image


def _white(w=384, h=200):
    return Image.new("RGB", (w, h), color=(255, 255, 255))


def test_render_id_card_image():
    from catprint import render

    logo = _white(64, 64)
    photo = _white(120, 120)
    img = render.id_card(company="ACME Ltd.", name="Alice Smith", photo=photo, logo=logo, description="Engineer")
    assert img.width == 384


def test_receipt_renders_id_card_block():
    from catprint import receipt

    photo = _white(120, 120)
    blocks = [{"type": "id_card", "data": {"name": "Bob", "description": "QA", "template": "ikea", "photo": photo}}]
    pages = receipt.render_blocks(blocks)
    assert len(pages) == 1
    assert pages[0].width == 384
