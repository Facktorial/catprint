import io
import os
from pathlib import Path
from PIL import Image
from catprint import utils


def test_attach_public_photo():
    # ensure public photos folder has seeded files (user150.png)
    photos_dir = utils.PUBLIC_PHOTOS
    assert photos_dir.exists(), "public/photos should exist"
    seed_photo = 'user150.png'
    seed_path = photos_dir.joinpath(seed_photo)
    assert seed_path.exists(), "seed photo should exist in public/photos"

    pid = '999'
    utils.add_person(pid, name='Test User', images=[], password='pw', position='Engineer', is_admin=False)
    ok = utils.attach_existing_image(pid, seed_photo)
    assert ok
    p = utils.get_person_by_id(pid)
    assert p is not None
    assert seed_photo in p.get('images', []), "attached image should be stored as filename only"


def test_seed_admins_exist():
    # Ensure seeded admin flags for 150 and 151
    a150 = utils.get_person_by_id('150')
    a151 = utils.get_person_by_id('151')
    assert a150 is not None and a150.get('is_admin') is True
    assert a151 is not None and a151.get('is_admin') is True


def test_list_public_photos():
    files = utils.list_public_photos()
    assert isinstance(files, list)
    assert 'user150.png' in files and 'user151.png' in files


def test_available_images_admin():
    files_admin = utils.available_images_for_person('150', admin=True)
    assert 'user150.png' in files_admin


def test_available_images_nonadmin_subset(tmp_path):
    # create a sample public photo that includes a position keyword
    photos_dir = utils.PUBLIC_PHOTOS
    photos_dir.mkdir(parents=True, exist_ok=True)
    test_name = 'barista_abc.png'
    p = photos_dir.joinpath(test_name)
    try:
        with open(p, 'wb') as fh:
            fh.write(b'\x89PNG\r\n')
        pid = '2000'
        utils.add_person(pid, name='Subset', images=['existing.png'], password='x', position='Barista', is_admin=False)
        res = utils.available_images_for_person(pid, admin=False)
        assert test_name in res or 'existing.png' in res
    finally:
        try:
            p.unlink()
        except Exception:
            pass


def test_add_image_saved_to_public(tmp_path):
    pid = '1000'
    utils.add_person(pid, name='Upload User', images=[], password='pw', position='QA', is_admin=False)
    # create a small red PNG in memory
    img = Image.new('RGB', (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    filename = utils.add_image_for_person(pid, buf, filename='upload.png')
    assert isinstance(filename, str)
    # file should be present in PUBLIC_PHOTOS
    out_file = utils.PUBLIC_PHOTOS.joinpath(filename)
    assert out_file.exists(), "Uploaded image should be saved into public/photos"

    p = utils.get_person_by_id(pid)
    assert filename in p.get('images', []), "DB should store filename only"
