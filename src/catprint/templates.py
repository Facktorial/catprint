from __future__ import annotations

import importlib.resources
try:
    import tomllib
except Exception:
    tomllib = None
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


_TOML_PATH = Path(__file__).resolve().parents[1] / ".." / "templates.toml"


@dataclass
class Template:
    key: str
    name: str
    address: str
    logo: str

    def header(self) -> str:
        return f"""\
{self.name}
{self.address}
******************************************

"""

    def footer(self) -> str:
        from time import gmtime, strftime

        return f"""\
Číslo pokladní:   0xDEADBEEF
Datum      Čas       Obchod  POS   Transak
{strftime("%Y-%m-%d %H:%M:%S", gmtime())}  42      34        007
Číslo dokladu:
123-456-789-{strftime("%Y%m%d%H%M%S", gmtime())}
******************************************
catprint v0.0.0 running on PufOS
******************************************
DATUM VYSTAVENÍ JE DATUM ZDANIT.PLNĚNÍ
USCHOVEJTE PRO REKLAMACI! *DĚKUJEME*
Číslo provozovny: -1
Pokrmy jsou určené k okamžité spotřebě
"""

    def logo_path(self) -> Path:
        # Logo lives in the package assets
        with importlib.resources.path("catprint.assets", self.logo) as p:
            return Path(p)


def _load_templates() -> Dict[str, Template]:
    # try same-dir then parent
    path = Path(__file__).resolve().parents[2] / "templates.toml"
    if not path.exists():
        path = Path(__file__).resolve().parents[1] / ".." / "templates.toml"
    # Prefer stdlib tomllib (Py3.11+), else try 'tomli', else fall back to a tiny parser
    data = None
    if tomllib is not None:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    else:
        try:
            import tomli as _tomli

            with path.open("rb") as fh:
                data = _tomli.load(fh)
        except Exception:
            # tiny fallback: parse only [templates.*] sections and simple key = "value" pairs
            data = {"templates": {}}
            cur = None
            for ln in path.read_text(encoding="utf8").splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                if ln.startswith("[") and ln.endswith("]"):
                    sec = ln[1:-1].strip()
                    if sec.startswith("templates."):
                        cur = sec.split(".", 1)[1]
                        data["templates"][cur] = {}
                    else:
                        cur = None
                    continue
                if cur is None:
                    continue
                if "=" in ln:
                    k, v = ln.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"')
                    data["templates"][cur][k] = v

    templates: Dict[str, Template] = {}
    for key, cfg in (data.get("templates") or {}).items():
        templates[key] = Template(
            key=key, name=cfg.get("name", ""), address=cfg.get("address", ""), logo=cfg.get("logo", ""),
        )
    return templates


_TEMPLATES = _load_templates()


def get_template(key: str) -> Template:
    return _TEMPLATES[key]


def list_templates() -> list[str]:
    return list(_TEMPLATES.keys())
