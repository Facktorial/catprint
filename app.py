import streamlit as st
import asyncio
import catprint
import PIL.Image
from time import gmtime, strftime
import importlib.resources
from catprint import utils
from catprint.templates import list_templates, get_template
from bleak import BleakScanner
import pdf2image
import io

TEMPLATE_KEYS = list_templates()


async def scan_printers():
    """Scan for available MX06 printers (delegates to shared utils)."""
    return await utils.scan_for_printers(st.session_state.mock_printers)


def refresh_printers():
    """Refresh the list of available printers."""
    with st.spinner("Scanning for printers..."):
        printers = asyncio.run(scan_printers())
        st.session_state.available_printers = printers
        if printers and not st.session_state.selected_printer:
            st.session_state.selected_printer = printers[0].address


st.set_page_config(
    page_title="🐈🖨️",
    page_icon="🖨️",
    initial_sidebar_state="expanded",
)

if "blocks" not in st.session_state:
    st.session_state.blocks = []


if "available_printers" not in st.session_state:
    st.session_state.available_printers = []

if "selected_printer" not in st.session_state:
    st.session_state.selected_printer = None


if "mock_printers" not in st.session_state:
    st.session_state.mock_printers = False

if "selected_template" not in st.session_state:
    st.session_state.selected_template = TEMPLATE_KEYS[0] if TEMPLATE_KEYS else None

col_left, col_right = st.columns([6, 2])
with col_left:
    st.title("Gutenberg 🖨️")
with col_right:
    if TEMPLATE_KEYS:
        tpl_index = TEMPLATE_KEYS.index(st.session_state.selected_template) if st.session_state.selected_template in TEMPLATE_KEYS else 0
        tpl_choice = st.selectbox(
            "",
            options=TEMPLATE_KEYS,
            index=tpl_index,
            key="selected_template",
            label_visibility="collapsed",
        )
        # show small logo preview
        tpl = get_template(st.session_state.selected_template) if st.session_state.selected_template else None
        if tpl:
            try:
                st.image(PIL.Image.open(tpl.logo_path()), width=200)
            except Exception:
                pass

# Printer selection in sidebar
with st.sidebar:
    st.header("🖨️ Printer Settings")

    # Mock mode toggle
    mock_mode = st.checkbox(
        "🧪 Mock Mode (Testing)",
        value=st.session_state.mock_printers,
        help="Enable to simulate printers without real hardware",
    )
    if mock_mode != st.session_state.mock_printers:
        st.session_state.mock_printers = mock_mode
        st.session_state.available_printers = []
        st.session_state.selected_printer = None

    

    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🔄 Scan Printers", use_container_width=True):
            refresh_printers()
            if st.session_state.available_printers:
                st.success(
                    f"Found {len(st.session_state.available_printers)} printer(s)"
                )
            else:
                st.error("No printers found")

    if st.session_state.available_printers:
        printer_options = {
            f"{p.name} ({p.address})": p.address
            for p in st.session_state.available_printers
        }

        selected_label = st.selectbox(
            "Select Printer",
            options=list(printer_options.keys()),
            index=0 if st.session_state.selected_printer else 0,
        )
        st.session_state.selected_printer = printer_options[selected_label]

        if st.session_state.mock_printers:
            st.warning("⚠️ Mock mode - prints will be simulated")
        else:
            st.success(f"✓ Printer ready")
    else:
        st.info("Click 'Scan Printers' to find available printers")

    st.divider()

# st.subheader("📄 Print PDF")
# pdf_file = st.file_uploader(
#     "Upload PDF to print",
#     type=["pdf"],
#     help="PDF will be converted to images and printed page by page",
# )
#
# with st.expander("⚙️ PDF Quality Settings"):
#     col1, col2, col3 = st.columns(3)
#     with col1:
#         pdf_dpi = st.slider(
#             "DPI", 100, 300, 150, 25, help="Higher = better quality but slower"
#         )
#     with col2:
#         pdf_contrast = st.slider(
#             "Contrast", 1.0, 2.0, 1.5, 0.1, help="Higher = darker text"
#         )
#     with col3:
#         pdf_brightness = st.slider(
#             "Brightness", 0.5, 1.5, 1.0, 0.1, help="Adjust if too dark/light"
#         )

# if pdf_file is not None:
#     try:
#         # Convert PDF to images
#         pdf_bytes = pdf_file.read()
#         images = pdf2image.convert_from_bytes(pdf_bytes, dpi=150)
#
#         st.info(f"PDF loaded: {len(images)} page(s)")
#
#         # Show preview of first page
#         with st.expander("Preview first page"):
#             st.image(images[0], caption="Page 1", use_container_width=True)
#
#         if st.button("🖨️ Print PDF", type="primary", use_container_width=True):
#             if not st.session_state.selected_printer:
#                 st.error("Please select a printer first!")
#             else:
#                 selected_device = next(
#                     (
#                         p
#                         for p in st.session_state.available_printers
#                         if p.address == st.session_state.selected_printer
#                     ),
#                     None,
#                 )
#
#                 if selected_device:
#                     progress_bar = st.progress(0)
#                     status_text = st.empty()
#
#                     for i, page_img in enumerate(images):
#                         status_text.text(f"Printing page {i+1}/{len(images)}...")
#                         progress_bar.progress((i + 1) / len(images))
#
#                         # Resize to printer width while maintaining aspect ratio
#                         aspect_ratio = page_img.height / page_img.width
#                         new_height = int(384 * aspect_ratio)
#                         resized_img = page_img.resize(
#                             (384, new_height), PIL.Image.Resampling.LANCZOS
#                         )
#                         resized_img = catprint.render.pdf_page(resized_img)
#
#                         if st.session_state.mock_printers:
#                             import time
#
#                             time.sleep(0.5)
#                             st.write(
#                                 f"[MOCK] Printed page {i+1} to {selected_device.address}"
#                             )
#                         else:
#                             asyncio.run(
#                                 catprint.printer.print(
#                                     resized_img, device=selected_device
#                                 )
#                             )
#
#                     status_text.empty()
#                     progress_bar.empty()
#                     st.success(f"✅ PDF printed successfully! ({len(images)} pages)")
#                 else:
#                     st.error("Selected printer not found. Please scan again.")
#     except Exception as e:
#         st.error(f"Error processing PDF: {e}")
#
# st.divider()

# Receipt Builder Section
st.subheader("🧾 Receipt Builder")

st.checkbox(
    "Include company template (logo + header + footer)",
    value=True,
    key="include_company_template",
)

if not st.session_state.blocks:
    st.info("Use the buttons below to add content blocks.")

for i, block in enumerate(st.session_state.blocks):
    with st.container():
        col_content, col_actions = st.columns([4, 1], vertical_alignment="center")

        with col_content:
            if block["type"] == "image":
                uploaded_file = st.file_uploader(
                    f"Image Block #{i+1}",
                    type=["png", "jpg", "jpeg", "gif", "bmp", "webp"],
                    key=f"image_{block['id']}",
                )
                if uploaded_file is not None:
                    try:
                        st.session_state.blocks[i]["data"] = catprint.render.image_page(
                            PIL.Image.open(uploaded_file)
                        )
                    except Exception as e:
                        st.error(f"Error loading image: {e}")

            elif block["type"] == "text":
                widget_key = f"text_{block['id']}"
                if widget_key in st.session_state:
                    current_value = st.session_state[widget_key]
                else:
                    current_value = block["data"]

                text_content = st.text_area(
                    f"Text Block #{i+1}",
                    value=current_value,
                    height=100,
                    key=widget_key,
                )
                st.session_state.blocks[i]["data"] = text_content

            elif block["type"] == "banner":
                widget_key = f"banner_{block['id']}"
                if widget_key in st.session_state:
                    current_value = st.session_state[widget_key]
                else:
                    current_value = block["data"]

                banner_content = st.text_input(
                    f"Banner Block #{i+1}", value=current_value, key=widget_key
                )
                st.session_state.blocks[i]["data"] = banner_content
            elif block["type"] == "pdf":
                uploaded_file = st.file_uploader(
                    f"PDF Block #{i+1}",
                    type=["pdf"],
                    key=f"pdf_{block['id']}",
                )
                # Quality controls
                with st.expander("⚙️ PDF Quality Settings"):
                    col1, col2 = st.columns(2)
                    with col1:
                        pdf_contrast = st.slider(
                            "Contrast",
                            min_value=1.0,
                            max_value=2.5,
                            value=1.5,
                            step=0.1,
                            key=f"pdf_contrast_{block['id']}",
                            help="Higher = darker text (1.0-2.5)",
                        )
                    with col2:
                        pdf_threshold = st.slider(
                            "Threshold",
                            min_value=100,
                            max_value=230,
                            value=212,
                            step=5,
                            key=f"pdf_threshold_{block['id']}",
                            help="Lower = more black pixels (100-230)",
                        )
                if uploaded_file is not None:
                    try:
                        pdf_bytes = uploaded_file.read()
                        images = pdf2image.convert_from_bytes(pdf_bytes, dpi=150)
                        st.info(f"PDF: {len(images)} page(s)")

                        # Store all converted pages
                        converted_pages = []
                        for page_img in images:
                            aspect_ratio = page_img.height / page_img.width
                            new_height = int(384 * aspect_ratio)
                            resized_img = page_img.resize(
                                (384, new_height), PIL.Image.Resampling.LANCZOS
                            )
                            resized_img = catprint.render.pdf_page(
                                resized_img,
                                contrast=pdf_contrast,
                                threshold=pdf_threshold,
                            )
                            converted_pages.append(resized_img)

                        st.session_state.blocks[i]["data"] = converted_pages
                    except Exception as e:
                        st.error(f"Error loading PDF: {e}")

        with col_actions:
            if st.button("🗑️", key=f"delete_{block['id']}", help="Delete this block"):
                st.session_state.blocks.pop(i)
                st.rerun()

            if i > 0:
                if st.button("⬆️", key=f"up_{block['id']}", help="Move up"):
                    st.session_state.blocks[i], st.session_state.blocks[i - 1] = (
                        st.session_state.blocks[i - 1],
                        st.session_state.blocks[i],
                    )
                    st.rerun()

            if i < len(st.session_state.blocks) - 1:
                if st.button("⬇️", key=f"down_{block['id']}", help="Move down"):
                    st.session_state.blocks[i], st.session_state.blocks[i + 1] = (
                        st.session_state.blocks[i + 1],
                        st.session_state.blocks[i],
                    )
                    st.rerun()

        st.divider()

col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

with col1:
    if st.button("➕ Image", use_container_width=True):
        st.session_state.blocks.append(
            {"id": len(st.session_state.blocks), "type": "image", "data": None}
        )
        st.rerun()

with col2:
    if st.button("➕ Text", use_container_width=True):
        st.session_state.blocks.append(
            {"id": len(st.session_state.blocks), "type": "text", "data": ""}
        )
        st.rerun()

with col3:
    if st.button("➕ Banner", use_container_width=True):
        st.session_state.blocks.append(
            {"id": len(st.session_state.blocks), "type": "banner", "data": ""}
        )
        st.rerun()

with col4:
    if st.button("➕ PDF", use_container_width=True):
        st.session_state.blocks.append(
            {"id": len(st.session_state.blocks), "type": "pdf", "data": None}
        )
        st.rerun()

def _selected_template():
    if st.session_state.get("selected_template"):
        return get_template(st.session_state["selected_template"])
    return None


from catprint import receipt

tpl = _selected_template() if st.session_state.get("include_company_template", True) else None
rendered_blocks = receipt.render_blocks(st.session_state.blocks, include_template=st.session_state.get("include_company_template", True), template=tpl)
preview_img = catprint.render.stack(*rendered_blocks) if rendered_blocks else None

if preview_img is not None:
    st.sidebar.image(preview_img, caption="Live Preview", use_container_width=True)

    print_disabled = not st.session_state.selected_printer
    if st.button(
        "🖨️ Print Receipt",
        type="primary",
        use_container_width=True,
        disabled=print_disabled,
        help="Select a printer first" if print_disabled else None,
    ):
        # Find the selected printer device
        selected_device = next(
            (
                p
                for p in st.session_state.available_printers
                if p.address == st.session_state.selected_printer
            ),
            None,
        )

        if selected_device:
            with st.spinner(
                f"Printing to {selected_device.name} ({selected_device.address})..."
            ):
                if st.session_state.mock_printers:
                    # Mock print
                    import time

                    time.sleep(1)
                    st.write(f"[MOCK] Printed receipt to {selected_device.address}")
                else:
                    asyncio.run(
                        catprint.printer.print(preview_img, device=selected_device)
                    )
            st.success("✅ Printing done!")
        else:
            st.error("Selected printer not found. Please scan again.")
