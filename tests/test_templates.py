from catprint.templates import get_template


def test_ikea_template_flags():
    tpl = get_template("ikea")
    assert tpl.supports_receipt is True
    assert tpl.supports_id_card is False
    assert isinstance(tpl.positions, list)
    assert "Manager" in tpl.positions


def test_free_coffee_flags():
    tpl = get_template("free_coffee")
    assert tpl.supports_receipt is True
    assert tpl.supports_id_card is True
    assert isinstance(tpl.positions, list)
    assert "Barista" in tpl.positions
