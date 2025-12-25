from catprint import utils


def test_nonadmin_gets_two_random_jobs():
    pid = 'jobs_assign_test_1'
    # add person without passing jobs => companies dict should be populated
    utils.add_person(pid, name='RandJobs', images=[], password='x', position='Engineer', is_admin=False)
    p = utils.get_person_by_id(pid)
    assert p is not None
    assert isinstance(p.get('companies'), dict)
    # non-admins should have only free_coffee with Barista
    assert 'free_coffee' in p.get('companies', {})
    assert p.get('companies', {}).get('free_coffee') == ['Barista']
    # should not have ikea
    assert 'ikea' not in p.get('companies', {})


def test_admin_gets_all_jobs_by_default():
    pid = 'jobs_assign_admin'
    utils.add_person(pid, name='AdminJobs', images=[], password='x', position='Manager', is_admin=True)
    p = utils.get_person_by_id(pid)
    assert p is not None
    assert p.get('is_admin') is True
    # admins should get all positions from all templates in companies dict
    assert isinstance(p.get('companies'), dict)
    # should have ikea positions
    assert 'ikea' in p.get('companies', {})
    assert set(p.get('companies', {}).get('ikea', [])) == {"Sales", "Stock", "Manager"}
