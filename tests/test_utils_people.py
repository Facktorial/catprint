import tempfile
from catprint import utils


def test_get_person_includes_password(tmp_path):
    dbp = tmp_path.joinpath("people.db")
    # initialize empty DB
    utils.ensure_people_db(db_path=str(dbp))
    utils.add_person("tadeas", name="Tadeas", max_clearance=2, images=[], password="s3cr3t", db_path=str(dbp))
    p = utils.get_person_by_id("tadeas", db_path=str(dbp))
    assert p is not None
    assert p["id"] == "tadeas"
    assert p["password"] == "s3cr3t"
