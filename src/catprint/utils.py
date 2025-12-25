from dataclasses import dataclass
import logging
import asyncio
from typing import Iterable, List
import random

try:
    from bleak import BleakScanner
except Exception:  # pragma: no cover - allow running tests without bleak installed
    BleakScanner = None

_LOG = logging.getLogger(__name__)

# serialize scanner operations to avoid overlapping BlueZ calls
_scan_lock: asyncio.Lock | None = None

# Canonical job positions
POSITIONS = ["Engineer", "QA", "Manager", "Security", "Barista"]


def _get_scan_lock() -> asyncio.Lock:
    global _scan_lock
    if _scan_lock is None:
        _scan_lock = asyncio.Lock()
    return _scan_lock


@dataclass
class MockPrinter:
    name: str
    address: str


async def scan_for_printers(mock_mode: bool = False):
    """Return available MX06 printers or mock devices when requested."""
    if mock_mode:
        return [
            MockPrinter("MX06", "AA:BB:CC:DD:EE:01"),
            MockPrinter("MX06", "AA:BB:CC:DD:EE:02"),
        ]
    if BleakScanner is None:
        _LOG.warning("Bleak is not available; returning empty device list")
        return []

    # avoid concurrent scans that can confuse BlueZ
    lock = _get_scan_lock()
    async with lock:
        devices = await BleakScanner.discover()
    # Debug log discovered device names for easier troubleshooting
    _LOG.debug("Discovered devices: %s", [(getattr(d, "name", None), getattr(d, "address", None)) for d in devices])

    # Match any device whose name contains 'mx06' (case-insensitive).
    matches: List = []
    for d in devices:
        name = getattr(d, "name", None)
        if name and "mx06" in name.lower():
            matches.append(d)
    return matches


def find_printer_by_address(printers: Iterable, address: str):
    return next((p for p in printers if getattr(p, "address", None) == address), None)

# --- Simple people DB helpers for ID card lookup ---
import sqlite3
from pathlib import Path

DEFAULT_PEOPLE_DB = Path(__file__).parent.parent.joinpath("data/people.db")

PUBLIC_PHOTOS = Path(__file__).parent.parent.parent.joinpath("public", "photos")  # project-root/public/photos
PUBLICS = Path(__file__).parent.parent.parent.joinpath("public")  # project-root/public/photos


def ensure_people_db(db_path: Path | str | None = None):
    path = Path(db_path) if db_path else DEFAULT_PEOPLE_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure public photos dir exists
    PUBLIC_PHOTOS.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        conn = sqlite3.connect(path)
        c = conn.cursor()
        # include new columns: position, is_admin and pokeball_count
        c.execute("CREATE TABLE people (id TEXT PRIMARY KEY, name TEXT, max_clearance INTEGER, images TEXT, password TEXT, position TEXT, is_admin INTEGER DEFAULT 0, pokeball_count INTEGER DEFAULT 0)")
        # seed sample data with positions and non-admin; admins (150,151) seeded with pokeballs
        c.executemany(
            "INSERT INTO people (id, name, max_clearance, images, password, position, is_admin, pokeball_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("1001", "Jakub Dvorak", 3, "[]", "admin", "Engineer", 0, 0),
                ("1002", "Alice Smith", 2, "[]", "admin", "Manager", 0, 0),
                ("1003", "Bob", 1, "[]", "admin", "Security", 0, 0),
                ("150", "Admin One", 4, "[\"user150.png\"]", "admin", "Manager", 1, 6),
                ("151", "Admin Two", 4, "[\"user151.png\"]", "admin", "Manager", 1, 6),
            ],
        )
        conn.commit()
        conn.close()
    else:
        # Ensure new columns exist for older DBs
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("PRAGMA table_info(people)")
        cols = [row[1] for row in c.fetchall()]
        if 'images' not in cols:
            c.execute("ALTER TABLE people ADD COLUMN images TEXT")
            # populate empty lists for existing rows
            c.execute("UPDATE people SET images = '[]' WHERE images IS NULL")
            conn.commit()
        if 'password' not in cols:
            c.execute("ALTER TABLE people ADD COLUMN password TEXT")
            c.execute("UPDATE people SET password = 'admin' WHERE password IS NULL")
            conn.commit()
        if 'position' not in cols:
            c.execute("ALTER TABLE people ADD COLUMN position TEXT")
            c.execute("UPDATE people SET position = '' WHERE position IS NULL")
            conn.commit()
        if 'is_admin' not in cols:
            c.execute("ALTER TABLE people ADD COLUMN is_admin INTEGER DEFAULT 0")
            c.execute("UPDATE people SET is_admin = 0 WHERE is_admin IS NULL")
            conn.commit()
        if 'pokeball_count' not in cols:
            c.execute("ALTER TABLE people ADD COLUMN pokeball_count INTEGER DEFAULT 0")
            c.execute("UPDATE people SET pokeball_count = 0 WHERE pokeball_count IS NULL")
            conn.commit()
        if 'jobs' not in cols:
            c.execute("ALTER TABLE people ADD COLUMN jobs TEXT DEFAULT '[]'")
            c.execute("UPDATE people SET jobs = '[]' WHERE jobs IS NULL")
            conn.commit()
        if 'companies' not in cols:
            # companies column stores JSON: {"ikea": ["Sales", "Stock"], "free_coffee": ["Barista"], ...}
            c.execute("ALTER TABLE people ADD COLUMN companies TEXT DEFAULT '{}'")
            c.execute("UPDATE people SET companies = '{}' WHERE companies IS NULL")
            conn.commit()
            
            # ONLY normalize when first adding the companies column (one-time migration)
            # Normalize companies for existing rows: admins -> all companies, non-admins -> free_coffee only
            try:
                from catprint.templates import get_template, list_templates
                c.execute("SELECT id, is_admin, companies, jobs FROM people")
                rows = c.fetchall()
                for rid, isadm, companies_json, jobs_json in rows:
                    try:
                        jobs_list = _json.loads(jobs_json or '[]') if jobs_json is not None else []
                    except Exception:
                        jobs_list = []
                    try:
                        companies_dict = _json.loads(companies_json or '{}')
                    except Exception:
                        companies_dict = {}
                    
                    if int(isadm):
                        # Admins get all positions from all templates
                        companies_dict = {}
                        for tpl_key in list_templates():
                            try:
                                tpl_pos = get_template(tpl_key).positions
                                if tpl_pos:
                                    companies_dict[tpl_key] = tpl_pos
                            except Exception:
                                pass
                        # Admins keep their current jobs (preserve parsed jobs_list)
                        if not jobs_list:
                            jobs_list = []
                    else:
                        # Non-admins: only free_coffee with Barista
                        companies_dict = {}
                        try:
                            fc_pos = get_template("free_coffee").positions
                            if fc_pos and "Barista" in fc_pos:
                                companies_dict["free_coffee"] = ["Barista"]
                        except Exception:
                            pass
                        # Non-admins: jobs = ["Barista"] only
                        jobs_list = ["Barista"]
                    
                    c.execute("UPDATE people SET companies = ? WHERE id = ?", (_json.dumps(companies_dict, ensure_ascii=False), rid))
                    c.execute("UPDATE people SET jobs = ? WHERE id = ?", (_json.dumps(jobs_list, ensure_ascii=False), rid))
                conn.commit()
            except Exception:
                pass
                
        # Ensure legacy rows for IDs 150 and 151 are set as admins and given a default pokeball count and jobs
        try:
            c.execute("UPDATE people SET is_admin = 1 WHERE id IN ('150','151')")
            c.execute("UPDATE people SET pokeball_count = 6 WHERE id IN ('150','151')")
            # Store per-company positions: admins get all from all companies
            admin_companies = {
                "ikea": ["Sales", "Stock", "Manager"],
                "free_coffee": ["Barista", "Manager", "Cashier"],
                "decima": []
            }
            c.execute("UPDATE people SET companies = ? WHERE id IN ('150','151')", (json.dumps(admin_companies),))
            conn.commit()
        except Exception:
            pass
        conn.close()
    return str(path)

essure_db = ensure_people_db  # alias for internal convenience


def get_person_by_id(person_id: str, db_path: Path | str | None = None):
    """Return dict {id,name,max_clearance,images,password,position,is_admin,pokeball_count,jobs,companies} or None if not found."""
    path = ensure_people_db(db_path)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    # include all fields including companies
    c.execute("SELECT id, name, max_clearance, images, password, position, is_admin, pokeball_count, jobs, companies FROM people WHERE id = ?", (str(person_id),))
    row = c.fetchone()
    conn.close()
    if row:
        imgs = []
        if row[3]:
            try:
                import json as _json

                imgs = _json.loads(row[3])
            except Exception:
                imgs = [s.strip() for s in str(row[3]).split(',') if s.strip()]
        jobs = []
        if row[8]:
            try:
                import json as _json

                jobs = _json.loads(row[8])
            except Exception:
                jobs = [s.strip() for s in str(row[8]).split(',') if s.strip()]
        companies = {}
        if row[9]:
            try:
                import json as _json
                companies = _json.loads(row[9])
            except Exception:
                companies = {}
        return {
            "id": row[0],
            "name": row[1],
            "max_clearance": int(row[2]),
            "images": imgs,
            "password": row[4],
            "position": row[5] or "",
            "is_admin": bool(row[6]),
            "pokeball_count": int(row[7]) if row[7] is not None else 0,
            "jobs": jobs,
            "companies": companies,
        }
    return None


def build_clearance_options(max_level: int):
    """Build clearance options in the form requested by the user.

    Examples:
      max_level=1 -> ['1A']
      max_level=2 -> ['1A','1B','2A','2B']
      max_level=3 -> ['1A','1B','2A','2B','3']
      max_level=4 -> ['1A','1B','2A','2B','3','4']
    """
    opts = []
    if max_level <= 0:
        return opts

    # Level 1
    if max_level == 1:
        opts.append("1A")
    else:
        opts.extend(["1A", "1B"])  # when at least 2 levels include both A/B for level 1

    # Level 2
    if max_level >= 2:
        opts.extend(["2A", "2B"])  # always include both for level 2

    # Levels >= 3 are represented as plain numbers
    for level in range(3, max_level + 1):
        opts.append(str(level))

    return opts


def attach_existing_image(person_id: str, image_name: str, db_path: Path | str | None = None) -> bool:
    """Attach an existing image from PUBLIC_PHOTOS to a person.

    The image is referenced by filename only (no paths are stored in DB). The file must exist in PUBLIC_PHOTOS.
    Returns True on success, False if the person was not found or image does not exist."""
    import json as _json
    path = ensure_people_db(db_path)
    # Validate file exists in public photos
    img_path = PUBLIC_PHOTOS.joinpath(image_name)
    if not img_path.exists():
        return False

    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("SELECT images FROM people WHERE id = ?", (str(person_id),))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    imgs = []
    if row[0]:
        try:
            imgs = _json.loads(row[0])
        except Exception:
            imgs = [s.strip() for s in str(row[0]).split(',') if s.strip()]
    # Avoid duplicates
    if image_name not in imgs:
        imgs.append(str(image_name))
        c.execute("UPDATE people SET images = ? WHERE id = ?", (_json.dumps(imgs, ensure_ascii=False), str(person_id)))
        conn.commit()
    conn.close()
    return True


def populate_people_db_from_json(json_path: str | Path | object, db_path: Path | str | None = None, default_password: str = 'admin'):
    """Load people records from provided JSON file-like or path and upsert into people DB.

    Accepts:
      - a filepath (str/Path)
      - a file-like object with .read()
    JSON format: {"data": [{"id": ..., "name": ..., "image": "filename"}, ...]}
    The `image` field can be a single string or list of filenames; it will be stored as a JSON list in the DB (filenames only).

    Returns the number of records processed.
    """
    import json as _json
    path = ensure_people_db(db_path)

    # Accept file-like objects (UploadedFile from Streamlit) or file path
    if hasattr(json_path, 'read'):
        raw = json_path.read()
        # raw may be bytes
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        data = _json.loads(raw)
    else:
        with open(str(json_path), 'r', encoding='utf-8') as fh:
            data = _json.load(fh)

    records = data.get('data', []) if isinstance(data, dict) else data
    conn = sqlite3.connect(path)
    c = conn.cursor()
    count = 0
    for rec in records:
        pid = str(rec.get('id'))
        name = rec.get('name') or ''
        images = []
        img = rec.get('image')
        if isinstance(img, list):
            images = img
        elif isinstance(img, str):
            images = [img]
        # default max_clearance if not provided
        max_clear = int(rec.get('max_clearance', 3))
        imgs_json = _json.dumps(images, ensure_ascii=False)
        password = rec.get('password', default_password) or default_password
        position = rec.get('position', '')
        is_admin = 1 if rec.get('is_admin') else 0
        jobs = rec.get('jobs', None)
        # If jobs not provided, assign defaults: admins -> all positions, non-admins -> 2 random jobs
        if jobs is None:
            if is_admin:
                jobs = POSITIONS
            else:
                jobs = random.sample(POSITIONS, 2)
        elif isinstance(jobs, str):
            try:
                jobs = _json.loads(jobs)
            except Exception:
                jobs = [jobs]
        jobs_json = _json.dumps(jobs, ensure_ascii=False)
        pokeball_count = int(rec.get('pokeball_count', 0))
        # Upsert, including password, position, is_admin, pokeball_count and jobs
        c.execute(
            "INSERT OR REPLACE INTO people (id, name, max_clearance, images, password, position, is_admin, pokeball_count, jobs) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, name, max_clear, imgs_json, password, position, is_admin, pokeball_count, jobs_json),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def list_images_for_person(person_id: str, db_path: Path | str | None = None):
    p = get_person_by_id(person_id, db_path=db_path)
    return p.get('images', []) if p else []


def list_public_photos():
    """Return list of filenames present in PUBLIC_PHOTOS."""
    if not PUBLIC_PHOTOS.exists():
        return []
    return [p.name for p in PUBLIC_PHOTOS.iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg')]


def available_images_for_person(person_id: str, db_path: Path | str | None = None, admin: bool | None = None):
    """Return available public image filenames for a person.

    If admin=True return all public photos. If admin=False, return only subset (attached images + those matching the person's position).
    If admin is None, determine from DB record's is_admin field.
    """
    p = get_person_by_id(person_id, db_path=db_path)
    if not p:
        return []
    if admin is None:
        admin = bool(p.get('is_admin', False))
    public = list_public_photos()
    if admin:
        return public
    pos = (p.get('position') or '').lower()
    subset = [n for n in public if pos and pos in n.lower()]
    return sorted(set(p.get('images', []) + subset))

# --- CRUD helpers for people DB ---
def add_person(person_id: str, name: str = "", max_clearance: int = 1, images: list | None = None, password: str = 'admin', position: str = '', is_admin: bool = False, pokeball_count: int = 0, jobs: list | None = None, db_path: Path | str | None = None):
    """Insert a new person record or replace existing one."""
    import json as _json
    path = ensure_people_db(db_path)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    imgs_json = _json.dumps(images or [], ensure_ascii=False)

    # For non-admins, force jobs to ["Barista"] regardless of input
    if is_admin:
        jobs_json = _json.dumps(jobs or [], ensure_ascii=False)
    else:
        jobs_json = _json.dumps(["Barista"], ensure_ascii=False)
    
    # Set companies based on is_admin
    if is_admin:
        # Admins get all positions from all templates
        companies_dict = {}
        try:
            from catprint.templates import get_template, list_templates
            for tpl_key in list_templates():
                try:
                    tpl_pos = get_template(tpl_key).positions
                    if tpl_pos:
                        companies_dict[tpl_key] = tpl_pos
                except Exception:
                    pass
        except Exception:
            pass
    else:
        # Non-admins: only free_coffee with Barista position
        companies_dict = {}
        try:
            from catprint.templates import get_template
            fc_pos = get_template("free_coffee").positions
            if fc_pos and "Barista" in fc_pos:
                companies_dict["free_coffee"] = ["Barista"]
        except Exception:
            pass
    
    companies_json = _json.dumps(companies_dict, ensure_ascii=False)
    c.execute(
        "INSERT OR REPLACE INTO people (id, name, max_clearance, images, password, position, is_admin, pokeball_count, jobs, companies) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(person_id), name, int(max_clearance), imgs_json, password, position, 1 if is_admin else 0, int(pokeball_count), jobs_json, companies_json),
    )
    conn.commit()
    conn.close()


def update_person(person_id: str, name: str | None = None, max_clearance: int | None = None, password: str | None = None, position: str | None = None, is_admin: int | None = None, pokeball_count: int | None = None, jobs: list | None = None, companies: dict | None = None, db_path: Path | str | None = None) -> bool:
    """Update fields for an existing person. Returns True if updated, False if not found."""
    import json as _json
    path = ensure_people_db(db_path)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("SELECT id, name, max_clearance, images, password, position, is_admin, pokeball_count, jobs, companies FROM people WHERE id = ?", (str(person_id),))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    cur_name = row[1]
    cur_max = int(row[2])
    cur_pw = row[4]
    cur_pos = row[5] if row[5] is not None else ''
    cur_admin = int(row[6]) if row[6] is not None else 0
    cur_pok = int(row[7]) if row[7] is not None else 0
    try:
        cur_jobs = _json.loads(row[8]) if row[8] else []
    except Exception:
        cur_jobs = [s.strip() for s in str(row[8]).split(',') if s.strip()]
    try:
        cur_companies = _json.loads(row[9]) if len(row) > 9 and row[9] else {}
    except Exception:
        cur_companies = {}

    new_name = name if name is not None else cur_name
    new_max = int(max_clearance) if max_clearance is not None else cur_max
    new_pw = password if password is not None else cur_pw
    new_pos = position if position is not None else cur_pos
    new_admin = int(is_admin) if is_admin is not None else cur_admin
    new_pok = int(pokeball_count) if pokeball_count is not None else cur_pok
    new_jobs = jobs if jobs is not None else cur_jobs
    new_companies = companies if companies is not None else cur_companies

    # When companies are updated, derive jobs from all positions across all companies
    if companies is not None:
        all_positions = []
        for company_positions in new_companies.values():
            if company_positions:
                all_positions.extend(company_positions)
        # Remove duplicates and sort
        new_jobs = sorted(list(set(all_positions)))
        # Non-admins who have no positions get Barista as default
        if not new_admin and not new_jobs:
            new_jobs = ["Barista"]
    else:
        # Only force Barista if jobs field is explicitly being set (backward compat)
        if not new_admin and jobs is not None:
            new_jobs = ["Barista"]

    # DEBUG: Print what we're about to commit
    jobs_json = _json.dumps(new_jobs, ensure_ascii=False)
    companies_json = _json.dumps(new_companies or {}, ensure_ascii=False)
    print(f"\n=== UPDATE_PERSON DEBUG ===")
    print(f"Person ID: {person_id}")
    print(f"Jobs to save: {jobs_json}")
    print(f"Companies to save: {companies_json}")
    
    c.execute(
        "UPDATE people SET name = ?, max_clearance = ?, password = ?, position = ?, is_admin = ?, pokeball_count = ?, jobs = ?, companies = ? WHERE id = ?",
        (new_name, new_max, new_pw, new_pos, new_admin, new_pok, jobs_json, companies_json, str(person_id)),
    )
    conn.commit()
    
    # DEBUG: Read back what was actually saved
    c.execute("SELECT jobs, companies FROM people WHERE id = ?", (str(person_id),))
    saved_row = c.fetchone()
    if saved_row:
        print(f"After commit - Jobs in DB: {saved_row[0]}")
        print(f"After commit - Companies in DB: {saved_row[1]}")
    else:
        print(f"ERROR: Person {person_id} not found after commit!")
    print(f"=== END DEBUG ===\n")
    
    conn.close()
    return True

def delete_person(person_id: str, db_path: Path | str | None = None) -> bool:
    """Delete person record. Returns True if deleted, False if not found."""
    path = ensure_people_db(db_path)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("SELECT COUNT(1) FROM people WHERE id = ?", (str(person_id),))
    found = c.fetchone()[0]
    if not found:
        conn.close()
        return False
    c.execute("DELETE FROM people WHERE id = ?", (str(person_id),))
    conn.commit()
    conn.close()
    return True


def add_image_for_person(person_id: str, uploaded_file, filename: str | None = None, db_path: Path | str | None = None) -> str:
    """Save uploaded image into PUBLIC_PHOTOS and add its filename to the person's images list. Returns the stored filename as string."""
    import json as _json
    import hashlib
    from pathlib import Path as _Path

    db_file = ensure_people_db(db_path)
    images_dir = PUBLIC_PHOTOS
    images_dir.mkdir(parents=True, exist_ok=True)

    # Read bytes from uploaded_file (Streamlit's UploadedFile has .read())
    if hasattr(uploaded_file, 'read'):
        img_bytes = uploaded_file.read()
    elif isinstance(uploaded_file, (bytes, bytearray)):
        img_bytes = bytes(uploaded_file)
    else:
        raise ValueError("uploaded_file must provide bytes via .read() or be bytes-like")

    # Derive extension
    ext = None
    if filename and '.' in filename:
        ext = filename.rsplit('.', 1)[-1]
    else:
        # default to png
        ext = 'png'

    name_hash = hashlib.sha1(img_bytes).hexdigest()[:10]
    out_name = f"{person_id}_{name_hash}.{ext}"
    out_path = images_dir.joinpath(out_name)
    with open(out_path, 'wb') as fh:
        fh.write(img_bytes)

    # Update DB: store filename only
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("SELECT images FROM people WHERE id = ?", (str(person_id),))
    row = c.fetchone()
    imgs = []
    if row and row[0]:
        try:
            imgs = _json.loads(row[0])
        except Exception:
            imgs = [s.strip() for s in str(row[0]).split(',') if s.strip()]
    imgs.append(str(out_name))
    imgs_json = _json.dumps(imgs, ensure_ascii=False)
    c.execute("UPDATE people SET images = ? WHERE id = ?", (imgs_json, str(person_id)))
    conn.commit()
    conn.close()
    return str(out_name)


def remove_image_for_person(person_id: str, image_name: str, db_path: Path | str | None = None) -> bool:
    """Remove image entry (by filename) from person's images list and delete the file if it resides under PUBLIC_PHOTOS. Returns True if removed."""
    import json as _json
    from pathlib import Path as _Path

    db_file = ensure_people_db(db_path)
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("SELECT images FROM people WHERE id = ?", (str(person_id),))
    row = c.fetchone()
    if not row or not row[0]:
        conn.close()
        return False
    try:
        imgs = _json.loads(row[0])
    except Exception:
        imgs = [s.strip() for s in str(row[0]).split(',') if s.strip()]
    if image_name not in imgs:
        conn.close()
        return False
    imgs = [i for i in imgs if i != image_name]
    c.execute("UPDATE people SET images = ? WHERE id = ?", (_json.dumps(imgs, ensure_ascii=False), str(person_id)))
    conn.commit()
    conn.close()

    # Try to delete file if it's in our public/photos dir
    try:
        imgs_dir = PUBLIC_PHOTOS
        p = _Path(imgs_dir.joinpath(image_name))
        if p.exists() and imgs_dir in p.parents:
            p.unlink()
    except Exception:
        pass
    return True
