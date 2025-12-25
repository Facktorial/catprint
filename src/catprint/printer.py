#!/usr/bin/env python3

# based on: https://github.com/amber-sixel/gb01print/blob/main/gb01print.py

import asyncio
import enum
import itertools
import sys
import typing
import logging
import builtins

try:
    from bleak import BleakClient, BleakScanner
    from bleak.exc import BleakDBusError
except Exception:  # pragma: no cover - tests may not have bleak
    BleakClient = None
    BleakScanner = None

    class BleakDBusError(Exception):
        pass

_LOG = logging.getLogger(__name__)

# serialize connect operations to avoid overlapping BlueZ connect requests
_connect_lock: asyncio.Lock | None = None


def _get_connect_lock() -> asyncio.Lock:
    global _connect_lock
    if _connect_lock is None:
        _connect_lock = asyncio.Lock()
    return _connect_lock
import crc8

import PIL.Image
from catprint.compat import batched, FLIP_LEFT_RIGHT

PRINTER_WIDTH = 384


class Command(enum.Enum):
    RETRACT_PAPER = b"\xa0"  # Data: Number of steps to go back
    FEED_PAPER = b"\xa1"  # Data: Number of steps to go forward
    DRAW_BITMAP = (
        b"\xa2"  # Data: Line to draw. 0 bit -> don't draw pixel, 1 bit -> draw pixel
    )
    GET_DEV_STATE = b"\xa3"  # Data: 0
    CONTROL_LATTICE = b"\xa6"  # Data: Eleven bytes, all constants. One set used before printing, one after.
    GET_DEV_INFO = b"\xa8"  # Data: 0
    OTHER_FEED_PAPER = b"\xbd"  # Data: one byte, set to a device-specific "Speed" value before printing, and to 0x19 before feeding blank paper
    DRAWING_MODE = b"\xbe"  # Data: 1 for Text, 0 for Images
    SET_ENERGY = b"\xaf"  # Data: 1 - 0xFFFF
    SET_QUALITY = b"\xa4"  # Data: 0x31 - 0x35. APK always sets 0x33 for GB01

    class Lattice(enum.Enum):
        PRINT = b"\xaa\x55\x17\x38\x44\x5f\x5f\x5f\x44\x38\x2c"
        FINISH = b"\xaa\x55\x17\x00\x00\x00\x00\x00\x00\x00\x17"

    class PrintSpeed(enum.Enum):
        IMAGE = b"\0x23"
        BLANK = b"\0x19"

    def format(self, data: bytes | int) -> bytes:
        if isinstance(data, int):
            data = (data).to_bytes(2, byteorder="little")
        return (
            b"Qx"
            + self.value
            + b"\x00"
            + bytes([len(data)])
            + b"\x00"
            + data
            + crc8.crc8(bytes(data)).digest()
            + b"\x00"
        )


async def select_printer() -> typing.Any:
    """Scan for available printers and let the user choose one."""
    import builtins
    builtins.print("Scanning for printers...")
    devices = await BleakScanner.discover()
    printers = [d for d in devices if d.name == "MX06"]

    if not printers:
        builtins.print("No printers found. Make sure the printer is powered on and in range.")
        sys.exit(1)

    if len(printers) == 1:
        builtins.print(f"Found 1 printer: {printers[0].name} ({printers[0].address})")
        return printers[0]

    # Multiple printers found - let user choose
    builtins.print(f"\nFound {len(printers)} printers:")
    for i, printer in enumerate(printers, 1):
        builtins.print(f"{i}. {printer.name} - {printer.address}")

    while True:
        try:
            choice = input("\nSelect printer number (or 'q' to quit): ").strip()
            if choice.lower() == "q":
                sys.exit(0)

            idx = int(choice) - 1
            if 0 <= idx < len(printers):
                return printers[idx]
            else:
                builtins.print(f"Please enter a number between 1 and {len(printers)}")
        except ValueError:
            builtins.print("Please enter a valid number")
        except (KeyboardInterrupt, EOFError):
            builtins.print("\nCancelled.")
            sys.exit(0)


async def print(img: PIL.Image.Image, device=None, keep_alive_callback=None) -> None:
    """
    Print image to device.
    Args:
        img: PIL Image to print
        device: BLE device to print to
        keep_alive_callback: Optional async callback to periodically send keep-alive signals
    """
    assert img.width == PRINTER_WIDTH, f"Image width must be {PRINTER_WIDTH} pixels"

    data = b"".join(
        (
            Command.SET_QUALITY.format(b"\x33"),
            Command.CONTROL_LATTICE.format(b"\xaa\x55\x17\x38\x44\x5f\x5f\x5f\x44\x38\x2c"),
            Command.SET_ENERGY.format(17500),
            Command.DRAWING_MODE.format(b"\x00"),
            Command.OTHER_FEED_PAPER.format(b"\0x23"),
            *(
                Command.DRAW_BITMAP.format(bytes(reversed(chunk)))
                for chunk in batched(
                    img.convert("RGB")
                    .convert("1")
                    .point(lambda p: 255 - p)
                    .transpose(FLIP_LEFT_RIGHT if FLIP_LEFT_RIGHT is not None else PIL.Image.FLIP_LEFT_RIGHT)
                    .tobytes(),
                    PRINTER_WIDTH // 8,
                )
            ),
            Command.CONTROL_LATTICE.format(b"\xaa\x55\x17\x00\x00\x00\x00\x00\x00\x00\x17"),
            Command.FEED_PAPER.format(50),
        )
    )

    if device is None:
        device = await select_printer()
    builtins.print(f"\nConnecting to {device.name} ({device.address})...")

    lock = _get_connect_lock()
    # retry transient DBus failures
    retries = 3
    for attempt in range(retries):
        try:
            async with lock:
                async with BleakClient(device) as client:
                    _LOG.info("Connected to %s, printing...", device.address)

                    # Periodically call the keep-alive callback if provided
                    async def _keep_alive_task():
                        try:
                            while True:
                                try:
                                    if keep_alive_callback:
                                        await keep_alive_callback()
                                except Exception as e:
                                    _LOG.debug("Keep-alive callback failed: %s", e)
                                await asyncio.sleep(8)
                        except asyncio.CancelledError:
                            return

                    keepalive = asyncio.create_task(_keep_alive_task())
                    try:
                        for chunk in batched(data, n=64):
                            await client.write_gatt_char(
                                "0000AE01-0000-1000-8000-00805F9B34FB", bytearray(chunk)
                            )
                            await asyncio.sleep(0.025)
                        _LOG.info("Print job sent successfully!")
                    finally:
                        keepalive.cancel()
                        try:
                            await keepalive
                        except Exception:
                            pass
            break
        except BleakDBusError as e:
            _LOG.warning("BleakDBusError on connect: %s (attempt %s/%s)", e, attempt + 1, retries)
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            raise
