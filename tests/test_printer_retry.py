import asyncio


class DummyClient:
    def __init__(self, device):
        self.device = device
        self._entered = False

    async def __aenter__(self):
        # simulate successful connect after being created
        self._entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def write_gatt_char(self, uuid, data):
        await asyncio.sleep(0)


class FlakyClientFactory:
    def __init__(self):
        self.calls = 0

    def __call__(self, device):
        self.calls += 1
        if self.calls == 1:
            # on first call, produce a context manager that raises BleakDBusError on enter
            class BadClient:
                async def __aenter__(self_inner):
                    from bleak.exc import BleakDBusError

                    raise BleakDBusError("[org.bluez.Error.Failed] Operation already in progress")

                async def __aexit__(self_inner, exc_type, exc, tb):
                    return False

            return BadClient()
        return DummyClient(device)


def test_printer_retries(monkeypatch):
    import sys
    import types

    # Provide a dummy crc8 module if missing so printer import succeeds
    if "crc8" not in sys.modules:
        sys.modules["crc8"] = types.SimpleNamespace(crc8=lambda b: types.SimpleNamespace(digest=lambda: b"\x00"))

    from catprint import printer

    # If bleak isn't installed, patch-in a dummy BleakClient attribute we can replace
    if getattr(printer, "BleakClient", None) is None:
        printer.BleakClient = None

    # Create a Flaky client factory that raises printer.BleakDBusError on first connect, then succeeds
    class FlakyClientFactoryLocal:
        def __init__(self):
            self.calls = 0

        def __call__(self, device):
            self.calls += 1
            if self.calls == 1:
                class BadClient:
                    async def __aenter__(self_inner):
                        raise printer.BleakDBusError("[org.bluez.Error.Failed] Operation already in progress")

                    async def __aexit__(self_inner, exc_type, exc, tb):
                        return False

                return BadClient()
            return DummyClient(device)

    monkeypatch.setattr(printer, "BleakClient", FlakyClientFactoryLocal())

    # fake image that satisfies width
    from PIL import Image

    img = Image.new("1", (printer.PRINTER_WIDTH, 100))

    # run print - should retry once and then succeed
    asyncio.get_event_loop().run_until_complete(printer.print(img, device=type("D", (), {"name": "MX06", "address": "AA:BB"})()))
