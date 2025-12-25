from catprint import utils


def test_jobs_column_and_default_for_non_admins():
    # Jobs column still exists but companies column holds the company->positions mapping
    # create a non-admin user and check that they have companies dict populated
    pid = 'jobs_test_1'
    utils.add_person(pid, name='Jobs User', images=[], password='x', position='Engineer', is_admin=False, jobs=['Engineer','QA'])
    p = utils.get_person_by_id(pid)
    assert p is not None
    assert isinstance(p.get('companies'), dict)
    # non-admins should have free_coffee with Barista only
    assert 'free_coffee' in p.get('companies', {})
    assert p.get('companies', {}).get('free_coffee') == ['Barista']


def test_admin_can_have_many_jobs():
    pid = 'jobs_admin_1'
    utils.add_person(pid, name='Jobs Admin', images=[], password='x', position='Manager', is_admin=True, jobs=['Manager','Engineer','Barista'])
    p = utils.get_person_by_id(pid)
    assert p.get('is_admin') is True
    assert len(p.get('jobs')) >= 2
