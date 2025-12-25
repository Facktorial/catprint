import PIL.Image
import catprint.render as render


def test_id_card_not_all_black_with_midgray_photo():
    # Create a mid-gray photo and a small template
    photo = PIL.Image.new("RGB", (100, 100), color=(128, 128, 128))
    card = render.id_card(company="Test", name="Name", photo=photo, logo=None, description="Manager\nClearance 3", width=240)
    # card should be mode '1' (1-bit)
    assert card.mode == "1"
    # There should be at least one white and one black pixel in the result
    px = card.getdata()
    vals = set(px)
    assert 0 in vals and 255 in vals
