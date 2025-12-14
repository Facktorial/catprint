import importlib
from typing import Any

__all__ = ["printer", "render", "effects", "templates", "utils", "receipt"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        mod = importlib.import_module(f"catprint.{name}")
        globals()[name] = mod
        return mod
    raise AttributeError(f"module {__name__} has no attribute {name}")

