import asyncio


class FakeDevice:
    def __init__(self, name, address):
        self.name = name
        self.address = address


def test_scan_matches_mx06(monkeypatch):
    from catprint import utils

    async def fake_discover():
        return [
            FakeDevice("MX06", "AA:BB:CC:DD:EE:01"),
            FakeDevice("mx06-01", "AA:BB:CC:DD:EE:02"),
            FakeDevice(None, "AA:BB:CC:DD:EE:03"),
            FakeDevice("OTHER", "AA:BB:CC:DD:EE:04"),
        ]

    class DummyScanner:
        @staticmethod
        async def discover():
            return await fake_discover()

    monkeypatch.setattr(utils, "BleakScanner", DummyScanner)

    printers = asyncio.get_event_loop().run_until_complete(utils.scan_for_printers(False))
    assert len(printers) == 2
    assert any(getattr(p, "address", "") == "AA:BB:CC:DD:EE:01" for p in printers)
    assert any(getattr(p, "address", "") == "AA:BB:CC:DD:EE:02" for p in printers)
