#!/usr/bin/env python3

# based on: https://github.com/amber-sixel/gb01print/blob/main/gb01print.py

import asyncio
import enum
import itertools
import sys
import typing

from bleak import BleakClient, BleakScanner
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

    def format(self: typing.Self, data: bytes | int) -> bytes:
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
    print("Scanning for printers...")
    devices = await BleakScanner.discover()
    printers = [d for d in devices if d.name == "MX06"]

    if not printers:
        print("No printers found. Make sure the printer is powered on and in range.")
        sys.exit(1)

    if len(printers) == 1:
        print(f"Found 1 printer: {printers[0].name} ({printers[0].address})")
        return printers[0]

    # Multiple printers found - let user choose
    print(f"\nFound {len(printers)} printers:")
    for i, printer in enumerate(printers, 1):
        print(f"{i}. {printer.name} - {printer.address}")

    while True:
        try:
            choice = input("\nSelect printer number (or 'q' to quit): ").strip()
            if choice.lower() == "q":
                sys.exit(0)

            idx = int(choice) - 1
            if 0 <= idx < len(printers):
                return printers[idx]
            else:
                print(f"Please enter a number between 1 and {len(printers)}")
        except ValueError:
            print("Please enter a valid number")
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            sys.exit(0)


async def print(img: PIL.Image.Image, device=None) -> None:
    assert img.width == PRINTER_WIDTH, f"Image width must be {PRINTER_WIDTH} pixels"

    data = b"".join(
        (
            Command.SET_QUALITY.format(b"\x33"),
            Command.CONTROL_LATTICE.format(Command.Lattice.PRINT.value),
            Command.SET_ENERGY.format(17500),
            Command.DRAWING_MODE.format(b"\x00"),
            Command.OTHER_FEED_PAPER.format(Command.PrintSpeed.IMAGE.value),
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
            Command.CONTROL_LATTICE.format(Command.Lattice.FINISH.value),
            Command.FEED_PAPER.format(50),
        )
    )

    if device is None:
        device = await select_printer()
    # try:
    #     # device = next((d for d in (await BleakScanner.discover()) if d.name == "MX06"))
    #     device = await select_printer()
    print(f"\nConnecting to {device.name} ({device.address})...")
    # except StopIteration:
    #     __builtins__.print("Printer not found. Make sure it is powered on and in range.")
    #     sys.exit(1)

    async with BleakClient(device) as client:
        print("Connected! Printing...")
        for chunk in itertools.batched(data, n=64):
            # service UUID: 0000ae30-0000-1000-8000-00805f9b34fb
            await client.write_gatt_char(
                "0000AE01-0000-1000-8000-00805F9B34FB", bytearray(chunk)
            )
            await asyncio.sleep(0.025)
        print("Print job sent successfully!")
