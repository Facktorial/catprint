from dataclasses import dataclass
from typing import Iterable
from bleak import BleakScanner


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
    devices = await BleakScanner.discover()
    return [d for d in devices if d.name == "MX06"]


def find_printer_by_address(printers: Iterable, address: str):
    return next((p for p in printers if getattr(p, "address", None) == address), None)
