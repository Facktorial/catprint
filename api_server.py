"""
Minimal FastAPI server for printing receipts.
Usage: uvicorn api_server:app --host 0.0.0.0 --port 5000
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import asyncio
import catprint
import PIL.Image
from bleak import BleakScanner
import io
import base64

# API
app = FastAPI(title="CatPrint Receipt API", version="1.0.0")

# Printer cache
printers_cache = []


from catprint import utils
from catprint.templates import get_template


class ReceiptBlock(BaseModel):
    type: str = Field(..., description="text, banner, image, or pdf")
    data: str
    meta: Optional[dict] = None


class PrintReceiptRequest(BaseModel):
    printer: str = Field(..., description="Printer MAC address")
    blocks: list[ReceiptBlock]
    include_template: bool = False
    template: Optional[str] = Field(None, description="Template key to use")
    mock: bool = False


# use utils.scan_for_printers directly via endpoint


@app.get("/")
async def root():
    return {
        "service": "CatPrint Receipt API",
        "endpoints": {
            "scan": "POST /scan",
            "printers": "GET /printers",
            "print": "POST /print",
        },
    }


@app.post("/scan")
async def scan(mock: bool = False):
    """Scan for printers."""
    global printers_cache
    try:
        printers_cache = await utils.scan_for_printers(mock)
        return {
            "success": True,
            "printers": [
                {"name": p.name, "address": p.address} for p in printers_cache
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/printers")
async def get_printers():
    """List cached printers."""
    return {
        "success": True,
        "printers": [{"name": p.name, "address": p.address} for p in printers_cache],
    }


@app.post("/print")
async def print_receipt(req: PrintReceiptRequest):
    """
    Print a receipt.

    Example:
    {
        "printer": "AA:BB:CC:DD:EE:01",
        "blocks": [
            {"type": "text", "data": "Hello World"},
            {"type": "banner", "data": "SALE"}
        ],
        "include_template": true,
        "mock": false
    }
    """
    # Find printer
    printer = utils.find_printer_by_address(printers_cache, req.printer)
    if not printer:
        raise HTTPException(
            status_code=404, detail="Printer not found. Run /scan first."
        )

    try:
        # Render blocks using shared helper (supports pdf, images, text, banners)
        from catprint import receipt

        tpl = get_template(req.template or "ikea") if req.include_template else None
        rendered_blocks = receipt.render_blocks(req.blocks, include_template=req.include_template, template=tpl)

        print(f"DEBUG: Rendered {len(rendered_blocks)} blocks")

        if not rendered_blocks:
            raise HTTPException(status_code=400, detail="No valid blocks")

        # Print
        receipt_img = catprint.render.stack(*rendered_blocks)

        if req.mock:
            await asyncio.sleep(0.5)
            message = f"[MOCK] Printed to {printer.address}"
        else:
            await catprint.printer.print(receipt_img, device=printer)
            message = f"Printed to {printer.address}"

        return {"success": True, "message": message}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
