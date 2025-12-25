from catprint import utils


def test_pokeball_column_present_and_defaults():
    pid = 'pb_test_1'
    # create a fresh person to ensure the column exists and is returned
    utils.add_person(pid, name='PB Check', images=[], password='x', position='QA', is_admin=False, pokeball_count=1)
    p = utils.get_person_by_id(pid)
    assert p is not None
    assert 'pokeball_count' in p
    assert isinstance(p.get('pokeball_count'), int)
    assert p.get('pokeball_count') == 1


def test_update_pokeball_count():
    pid = '3000'
    utils.add_person(pid, name='PB Test', images=[], password='x', position='QA', is_admin=False, pokeball_count=2)
    p = utils.get_person_by_id(pid)
    assert p.get('pokeball_count') == 2
    utils.update_person(pid, pokeball_count=5)
    p2 = utils.get_person_by_id(pid)
    assert p2.get('pokeball_count') == 5
