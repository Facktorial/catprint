import streamlit as st
import asyncio
import catprint
import PIL.Image
from time import gmtime, strftime
import importlib.resources
from catprint import utils
from catprint.templates import list_templates, get_template
from catprint import receipt
from bleak import BleakScanner
import pdf2image
import io
import time
from pathlib import Path


# Safe access to Streamlit secrets to avoid exceptions when no secrets file exists
def safe_secret_get(key: str, default=None):
    try:
        # Using st.secrets.get may raise StreamlitSecretNotFoundError when no secrets file exists
        return st.secrets.get(key, default)
    except Exception:
        return default


# Safe rerun helper for Streamlit versions without experimental_rerun
def safe_rerun():
    try:
        # Preferred API when available
        if hasattr(st, "experimental_rerun"):
            return st.experimental_rerun()
    except Exception:
        pass

    # Best effort: change query params to induce a rerun
    try:
        # Read current params using the new property
        params = dict(st.query_params) if hasattr(st, "query_params") else {}
        params["_r"] = [str(int(time.time()))]
        # Prefer the non-experimental setter if available
        if hasattr(st, "set_query_params"):
            st.set_query_params(**params)
        elif hasattr(st, "experimental_set_query_params"):
            st.experimental_set_query_params(**params)
        return
    except Exception:
        pass

    # Final fallback: set a flag and stop execution (user can refresh the page)
    st.session_state["_need_reload"] = True
    st.stop()

# ID password (simple equality check). Can be overridden in Streamlit secrets under key 'id_password'.
# Read admin password from secrets safely (returns None when missing)
ID_PASSWORD = safe_secret_get("id_password", None)
if not ID_PASSWORD:
    ID_PASSWORD = "catprint"  # default simple password (change via secrets if needed)


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

# Initialize template selections per context
try:
    receipt_options = [k for k in TEMPLATE_KEYS if get_template(k).supports_receipt]
except Exception:
    receipt_options = TEMPLATE_KEYS
if "receipt_selected_template" not in st.session_state:
    st.session_state.receipt_selected_template = receipt_options[0] if receipt_options else (TEMPLATE_KEYS[0] if TEMPLATE_KEYS else None)

try:
    id_options = [k for k in TEMPLATE_KEYS if get_template(k).supports_id_card]
except Exception:
    id_options = TEMPLATE_KEYS
if "id_selected_template" not in st.session_state:
    st.session_state.id_selected_template = id_options[0] if id_options else (TEMPLATE_KEYS[0] if TEMPLATE_KEYS else None)

# Receipt template include toggles
if "receipt_include_logo" not in st.session_state:
    st.session_state.receipt_include_logo = True
if "receipt_include_header_footer" not in st.session_state:
    st.session_state.receipt_include_header_footer = True

col_left, col_right = st.columns([6, 2])
with col_left:
    st.title("Gutenberg 🖨️")
with col_right:
    st.empty()  # Reserve space for layout consistency

# Printer selection in sidebar
with st.sidebar:
    st.header("🖨️ Printer Settings")

    # # Admin: Import people JSON to populate people DB
    # with st.expander("📥 Import People JSON (admin)"):
    #     imported_file = st.file_uploader("Upload JSON file", type=["json"], key="people_json_upload")
    #     admin_btn_col1, admin_btn_col2 = st.columns([3,1])
    #     with admin_btn_col2:
    #         if st.button("Import", key="import_people_btn"):
    #             if not imported_file:
    #                 st.error("Please choose a JSON file to import")
    #             else:
    #                 try:
    #                     inserted = utils.populate_people_db_from_json(imported_file)
    #                     st.success(f"Imported {inserted} records into people DB (password set to 'admin' by default)")
    #                     # clear cached session ID data so next load will fetch updated DB
    #                     st.session_state.pop("id_images", None)
    #                     st.session_state.pop("id_image", None)
    #                 except Exception as e:
    #                     st.error(f"Import failed: {e}")

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
            # Start keep-alive heartbeat for the selected printer
            if st.session_state.selected_printer and not st.session_state.get('keepalive_task'):
                st.session_state['keepalive_task'] = True
                st.info("🔄 Printer keep-alive enabled - periodic heartbeat active")
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

# Helper functions for tabs
def clear_db_filter():
    """Clear DB filter for refresh button."""
    st.session_state["db_filter"] = ""


# Builder Tabs
tab_receipt, tab_id, tab_db = st.tabs(["🧾 Receipt Builder", "🆔 Card Builder", "🗄️ DB Viewer"])

with tab_receipt:
    st.subheader("🧾 Receipt Builder")

    # Template selector at top of receipt builder (filter to templates supporting receipts)
    col_tpl, col_chk = st.columns([2, 2])
    with col_tpl:
        if receipt_options:
            tpl_index = receipt_options.index(st.session_state.receipt_selected_template) if st.session_state.receipt_selected_template in receipt_options else 0
            st.selectbox(
                "Select template",
                options=receipt_options,
                index=tpl_index,
                key="receipt_selected_template",
                label_visibility="visible",
            )
            # show small logo preview
            tpl = get_template(st.session_state.receipt_selected_template) if st.session_state.receipt_selected_template else None
            if tpl:
                try:
                    st.image(PIL.Image.open(tpl.logo_path()), width=150)
                except Exception:
                    pass
    with col_chk:
        st.checkbox("Include logo", value=st.session_state.receipt_include_logo, key="receipt_include_logo")
        st.checkbox("Include header + footer", value=st.session_state.receipt_include_header_footer, key="receipt_include_header_footer")

    if not st.session_state.blocks:
        st.info("Use the buttons below to add content blocks.")

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        if st.button("➕ Image", use_container_width=True):
            st.session_state.blocks.append(
                {"id": len(st.session_state.blocks), "type": "image", "data": None}
            )

    with col2:
        if st.button("➕ Text", use_container_width=True):
            st.session_state.blocks.append(
                {"id": len(st.session_state.blocks), "type": "text", "data": ""}
            )

    with col3:
        if st.button("➕ Banner", use_container_width=True):
            st.session_state.blocks.append(
                {"id": len(st.session_state.blocks), "type": "banner", "data": ""}
            )

    with col4:
        if st.button("➕ PDF", use_container_width=True):
            st.session_state.blocks.append(
                {"id": len(st.session_state.blocks), "type": "pdf", "data": None}
            )

    # Print control for receipts (kept in Receipt tab; preview is shown in the sidebar)
    # Use the same preview calculation as sidebar to ensure consistency
    try:
        tpl_local = get_template(st.session_state.receipt_selected_template) if st.session_state.get("receipt_selected_template") else None
    except Exception:
        tpl_local = None
    try:
        rendered_blocks = receipt.render_blocks(
            st.session_state.blocks,
            include_logo=st.session_state.get("receipt_include_logo", True),
            include_header_footer=st.session_state.get("receipt_include_header_footer", True),
            template=tpl_local,
        )
        preview_img_local = catprint.render.stack(*rendered_blocks) if rendered_blocks else None
    except Exception:
        preview_img_local = None

    print_disabled = not st.session_state.selected_printer or (preview_img_local is None and not (st.session_state.get("receipt_include_logo", True) or st.session_state.get("receipt_include_header_footer", True)))
    if st.button(
        "🖨️ Print Receipt",
        type="primary",
        use_container_width=True,
        disabled=print_disabled,
        help="Select a printer and add content to print" if print_disabled else None,
    ):
        if preview_img_local is None:
            st.error("Nothing to print; add some blocks first.")
        else:
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
                        import time

                        time.sleep(1)
                        st.write(f"[MOCK] Printed receipt to {selected_device.address}")
                    else:
                        asyncio.run(catprint.printer.print(preview_img_local, device=selected_device))
                st.success("✅ Printing done!")
            else:
                st.error("Selected printer not found. Please scan again.")

    # Block editor (moved here from after DB viewer where it was accidentally placed)
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
                            pdf_pages = catprint.receipt._convert_pdf_bytes(uploaded_file.read())
                            st.session_state.blocks[i]["data"] = (pdf_pages, pdf_contrast, pdf_threshold)
                        except Exception as e:
                            st.error(f"Error loading PDF: {e}")

            with col_actions:
                if st.button("🗑️", key=f"delete_{block['id']}"):
                    st.session_state.blocks = [
                        b for b in st.session_state.blocks if b["id"] != block["id"]
                    ]
                    st.rerun()


with tab_id:
    st.subheader("🆔 ID Card Builder")

    # ID lookup and selection
    id_col1, id_col2 = st.columns([3, 1])
    with id_col1:
        id_input = st.text_input("ID", value=st.session_state.get("id_input", ""), key="id_input")
        id_password = st.text_input("Password", type="password", value="", key="id_password")
    with id_col2:
        if st.button("Load", key="load_id"):
            # Basic checks
            if not id_input:
                st.error("Please enter an ID first")
            elif not id_password:
                st.error("Please enter the password")
            else:
                rec = utils.get_person_by_id(id_input)
                if not rec:
                    st.error("ID not found in DB")
                    st.session_state["id_authenticated"] = False
                    st.session_state["id_loaded"] = False
                else:
                    expected_pw = rec.get('password') or ID_PASSWORD
                    # Allow admin override via global ID_PASSWORD
                    if id_password != expected_pw and id_password != ID_PASSWORD:
                        st.error("Invalid password for this ID")
                        # DEBUG helper: show expected password only if explicitly enabled via secrets
                        if safe_secret_get("debug_show_password"):
                            st.info(f"[debug] Expected password for this ID: {expected_pw}")
                        st.session_state["id_authenticated"] = False
                        st.session_state["id_loaded"] = False
                    else:
                        st.session_state["id_name"] = rec["name"]
                        st.session_state["id_max_clearance"] = rec["max_clearance"]
                        st.session_state["id_images"] = rec.get("images", [])
                        # set default selected image if present
                        if rec.get("images"):
                            st.session_state["id_image"] = rec.get("images")[0]
                        st.session_state["id_authenticated"] = True
                        st.session_state["id_loaded"] = True
                        st.session_state["id_current"] = id_input
                        # Prefill main form with DB values
                        st.session_state["id_name"] = rec["name"]
                        st.session_state["id_images"] = rec.get("images", [])
                        # set default selected image
                        if rec.get("images"):
                            st.session_state["id_image"] = rec.get("images")[0]
                        # store admin flag for UI enforcement, pokeball count and jobs
                        st.session_state["id_is_admin"] = bool(rec.get("is_admin", False))
                        st.session_state["id_pokeball_count"] = int(rec.get("pokeball_count", 0)) if rec.get("pokeball_count") is not None else 0
                        st.session_state["id_jobs"] = rec.get("jobs", [])
                        # default position (if stored) and default clearance to highest available
                        st.session_state["id_position"] = rec.get("position", st.session_state.get("id_position", ""))
                        clear_opts = utils.build_clearance_options(rec.get("max_clearance", 3))
                        st.session_state["id_clearance"] = clear_opts[-1] if clear_opts else ""                        # auto-select first available printer if none selected
                        if st.session_state.get("available_printers") and not st.session_state.get("selected_printer"):
                            first_dev = st.session_state.get("available_printers")[0]
                            try:
                                st.session_state["selected_printer"] = first_dev.address
                            except Exception:
                                st.session_state["selected_printer"] = None
                        st.success(f"Loaded ID {rec['id']}: {rec['name']} (max clearance {rec['max_clearance']})")


    # Defaults to avoid NameError and give preview sensible fallbacks
    id_tpl = st.session_state.get("id_selected_template", id_options[0] if id_options else (TEMPLATE_KEYS[0] if TEMPLATE_KEYS else None))
    id_name = st.session_state.get("id_name", "")
    id_position = st.session_state.get("id_position", "")
    id_clearance = st.session_state.get("id_clearance", "")
    id_images = st.session_state.get("id_images", [])
    id_image = st.session_state.get("id_image") if id_images else None
    id_photo_file = st.session_state.get("id_photo_upload") if st.session_state.get("id_photo_upload") else None

    # Load template early so tpl_obj is available throughout the section
    tpl_obj = get_template(id_tpl) if id_tpl else None
    logo_img = PIL.Image.open(tpl_obj.logo_path()) if tpl_obj else None
    preview_desc = f"{st.session_state.get('id_position','')}\nClearance level: {st.session_state.get('id_clearance','')}"

    # Load pokeball icon early so it's available for preview
    pokeball_icon = None
    try:
        p_icon = utils.PUBLICS.joinpath('pokeball.png')
        if p_icon.exists():
            pokeball_icon = PIL.Image.open(p_icon)
    except Exception:
        pokeball_icon = None

    # The form is available even before loading/authenticating an ID — users wanted the ability to edit fields first.
#    if not st.session_state.get("id_loaded") or not st.session_state.get("id_authenticated"):
#        st.info("You can edit the card fields below without loading an existing ID. Printing is enabled only after successful authentication.")

    # Simple ID form (hidden until authenticated)
    # If user has not loaded+authenticated an ID we don't reveal editable form fields
    if not (st.session_state.get("id_loaded") and st.session_state.get("id_authenticated")):
        # st.info("Please load and authenticate an ID to edit card fields.")
        # Provide safe defaults so later code can reference variables without error
        id_tpl = st.session_state.get("id_selected_template", id_options[0] if id_options else (TEMPLATE_KEYS[0] if TEMPLATE_KEYS else None))
        id_name = st.session_state.get("id_name", "")
        id_position = st.session_state.get("id_position", "")
        id_clearance = st.session_state.get("id_clearance", "")
        id_images = st.session_state.get("id_images", [])
        id_image = st.session_state.get("id_image") if id_images else None
        id_photo_file = None
        id_photo_img = None
    else:
        # Refresh jobs/companies from DB to ensure we have latest data (in case changes were made in DB Viewer)
        if st.session_state.get("id_current"):
            fresh_rec = utils.get_person_by_id(st.session_state.get("id_current"))
            if fresh_rec:
                st.session_state["id_jobs"] = fresh_rec.get("jobs", [])
                st.session_state["id_companies"] = fresh_rec.get("companies", {})
        
        # Build template options
        if st.session_state.get("id_is_admin", False):
            # Admins see ALL templates
            id_template_options = TEMPLATE_KEYS
        else:
            # Non-admins: show ONLY companies where they have non-empty position list AND template.supports_id_card is true
            rec_id = st.session_state.get("id_current")
            rec_data = utils.get_person_by_id(rec_id) if rec_id else None
            companies_dict = rec_data.get("companies", {}) if rec_data else {}
            id_template_options = [
                k for k in TEMPLATE_KEYS 
                if get_template(k).supports_id_card and len(companies_dict.get(k, [])) > 0
            ]
        
        # Calculate index for currently selected template
        # Let the widget control its own value - don't override with index
        current_selection = st.session_state.get("id_selected_template")
        if current_selection and current_selection in id_template_options:
            tpl_index = id_template_options.index(current_selection)
        elif id_template_options:
            # No valid selection - default to first option
            tpl_index = 0
            # But don't force it - let the widget update naturally
        else:
            tpl_index = 0
        
        # Don't pass index parameter - let Streamlit manage the widget state
        st.selectbox("Template", options=id_template_options, key="id_selected_template")
        
        # Read template value and detect changes
        id_tpl = st.session_state.get("id_selected_template", id_template_options[tpl_index] if id_template_options else None)
        
        # Admin-only: Allow choosing a different company for the card display
        use_different_company = False
        display_tpl = id_tpl  # Default: use same template for display
        display_tpl_obj = None
        display_logo_img = None
        
        if st.session_state.get("id_is_admin", False):
            use_different_company = st.checkbox(
                "Use different company for card display", 
                value=st.session_state.get("id_use_different_company", False),
                key="id_use_different_company",
                help="Check this to show a different company logo/name on the card while using positions from the selected template above"
            )
            
            if use_different_company:
                # Show second template selector for display company
                st.selectbox("Display company on card", options=TEMPLATE_KEYS, key="id_display_template", help="The company shown on the printed card")
                display_tpl = st.session_state.get("id_display_template", TEMPLATE_KEYS[0] if TEMPLATE_KEYS else None)
                display_tpl_obj = get_template(display_tpl) if display_tpl else None
                display_logo_img = PIL.Image.open(display_tpl_obj.logo_path()) if display_tpl_obj else None
        
        # Detect template change by comparing to previous value
        prev_template = st.session_state.get("id_prev_template")
        if prev_template != id_tpl:
            # Template changed! Reset position
            st.session_state["id_position"] = ""
            st.session_state["id_prev_template"] = id_tpl
        
        # Use display template if different company is selected, otherwise use regular template
        tpl_obj = display_tpl_obj if use_different_company and display_tpl_obj else get_template(id_tpl) if id_tpl else None
        logo_img = display_logo_img if use_different_company and display_logo_img else (PIL.Image.open(tpl_obj.logo_path()) if tpl_obj else None)
        
        # Refresh jobs from DB when template changes to avoid stale state
        if st.session_state.get("id_current"):
            fresh_rec = utils.get_person_by_id(st.session_state.get("id_current"))
            if fresh_rec:
                st.session_state["id_jobs"] = fresh_rec.get("jobs", [])
        
        # Disable editing of name for non-admins when a DB record is loaded and authenticated
        name_disabled = not bool(st.session_state.get("id_is_admin", False))
        id_name = st.text_input("Full name", value=st.session_state.get("id_name", ""), key="id_name", disabled=name_disabled)

        # Position selection: admins choose from all template positions; non-admins from their assigned companies' positions
        # Always re-fetch fresh data from DB to avoid stale companies dict
        rec_id = st.session_state.get("id_current")
        fresh_rec_data = utils.get_person_by_id(rec_id) if rec_id else None
        fresh_companies_dict = fresh_rec_data.get("companies", {}) if fresh_rec_data else {}
        
        all_template_positions = None
        if id_tpl:
            try:
                all_template_positions = get_template(id_tpl).positions
            except Exception:
                all_template_positions = None
        all_template_positions = all_template_positions or utils.POSITIONS

        if st.session_state.get("id_is_admin", False):
            # Admins can choose ANY position from the selected template (regardless of assigned companies)
            # When position is reset (""), use first position from current template
            current_pos = st.session_state.get("id_position", "")
            if not current_pos or current_pos not in all_template_positions:
                current_pos = all_template_positions[0] if all_template_positions else ""
            id_position = st.selectbox("Position", options=all_template_positions, index=all_template_positions.index(current_pos) if current_pos in all_template_positions else 0, key="id_position", help="Admins can select any position from any company")
        else:
            # Non-admins: get allowed positions from the freshly-loaded companies dict for the selected template
            # Positions allowed for this template = what's in their companies[id_tpl]
            allowed_positions = fresh_companies_dict.get(id_tpl, []) if id_tpl else []
            if not allowed_positions:
                allowed_positions = [all_template_positions[0]] if all_template_positions else ["Unassigned"]
            current = st.session_state.get("id_position", "")
            if not current or current not in allowed_positions:
                current = allowed_positions[0] if allowed_positions else ""
            id_position = st.selectbox("Position", options=allowed_positions, index=allowed_positions.index(current) if current in allowed_positions else 0, key="id_position")

        # Clearance options based on DB max value (or default to 3)
        max_clear = st.session_state.get("id_max_clearance", 3)
        clearance_opts = utils.build_clearance_options(max_clear)
        id_clearance = st.selectbox("Clearance level", options=clearance_opts, index=clearance_opts.index(st.session_state.get("id_clearance")) if st.session_state.get("id_clearance") in clearance_opts else 0, key="id_clearance")

        # Image selection: either choose from DB-provided images; only admins can upload new photos
        id_images = st.session_state.get("id_images", [])
        id_image = None
        if id_images:
            id_image = st.selectbox("Choose image from DB", options=id_images, index=0, key="id_image")

        # Allow upload only for admins
        if st.session_state.get("id_is_admin", False):
            id_photo_file = st.file_uploader("Photo (png/jpg)", type=["png", "jpg", "jpeg"], key="id_photo_upload")
        else:
            id_photo_file = None
        id_photo_img = None

        # Pokeball count (stored in DB) - displayed and editable by admins only
        cur_pok = int(st.session_state.get("id_pokeball_count", 0))
        if st.session_state.get("id_is_admin", False):
            # immediate save on slider change
            new_pok = st.slider("Pokeball count", min_value=0, max_value=6, value=cur_pok, key="id_pokeball_slider")
            if new_pok != cur_pok:
                try:
                    utils.update_person(st.session_state.get("id_current"), pokeball_count=int(new_pok))
                    st.session_state["id_pokeball_count"] = int(new_pok)
                    st.success("Pokeball count updated")
                except Exception as e:
                    st.error(f"Failed to update pokeball count: {e}")
        else:
            st.write(f"Pokeballs: {cur_pok}")
    if id_photo_file is not None:
        try:
            id_photo_img = PIL.Image.open(id_photo_file)
        except Exception as e:
            st.error(f"Error loading photo: {e}")

    # Resolve photo: prefer uploaded file, then DB-selected image
    resolved_photo = id_photo_img
    if resolved_photo is None and st.session_state.get('id_image'):
        try:
            asset_path = importlib.resources.files("catprint").joinpath("assets", st.session_state.get('id_image'))
            if asset_path.exists():
                resolved_photo = PIL.Image.open(asset_path)
            else:
                photos_path = utils.PUBLIC_PHOTOS.joinpath(st.session_state.get('id_image'))
                if photos_path.exists():
                    resolved_photo = PIL.Image.open(photos_path)
                else:
                    try:
                        resolved_photo = PIL.Image.open(st.session_state.get('id_image'))
                    except Exception:
                        resolved_photo = None
        except Exception:
            resolved_photo = None

    preview_desc = f"{st.session_state.get('id_position','')}\nClearance level: {st.session_state.get('id_clearance','')}"

    preview_card = None
    try:
        preview_card = catprint.render.id_card(
            company=(tpl_obj.name if tpl_obj else ""),
            name=id_name or "(name)",
            photo=resolved_photo,
            logo=logo_img,
            description=preview_desc,
            pokeball_count=int(st.session_state.get('id_pokeball_count', 0)),
            pokeball_icon=pokeball_icon,
        )
        st.image(preview_card, caption="Preview", use_container_width=False)

        if st.session_state.get("id_authenticated"):
            st.success("Authenticated — preview is ready. Select a printer and press '🖨️ Print ID Card'.")
        
    except Exception as e:
        st.error(f"Preview unavailable: {e}")

    preview_exists = preview_card is not None
    selected_printer = st.session_state.get("selected_printer")
    print_disabled = not preview_exists or not st.session_state.get("id_authenticated") or not selected_printer
    if st.button(
        "🖨️ Print ID Card",
        type="primary",
        use_container_width=True,
        disabled=print_disabled,
        help=("Preview unavailable" if not preview_exists else ("Select a printer first" if not selected_printer else ("Authenticate with the correct password to enable printing" if not st.session_state.get("id_authenticated") else None))),
    ):
        selected_device = next((p for p in st.session_state.get("available_printers", []) if p.address == selected_printer), None)
        if selected_device:
            img = preview_card.rotate(-90, expand=True)
            PRINTER_WIDTH = catprint.printer.PRINTER_WIDTH
            new_h = int(img.height * PRINTER_WIDTH / img.width)
            img = img.resize((PRINTER_WIDTH, new_h), PIL.Image.Resampling.LANCZOS)

            canvas = PIL.Image.new("RGB", (PRINTER_WIDTH, img.height), color=(255, 255, 255))
            xoff = max(0, (PRINTER_WIDTH - img.width) // 2)
            canvas.paste(img, (xoff, 0))

            if st.session_state.mock_printers:
                import time

                time.sleep(0.5)
                st.write(f"[MOCK] Printed ID card to {selected_device.address}")
            else:
                with st.spinner(f"Printing ID card to {selected_device.name} ({selected_device.address})..."):
                    asyncio.run(catprint.printer.print(catprint.render.image_page(canvas), device=selected_device))
            st.success("✅ ID card printed")
        else:
            st.error("Selected printer not found. Please scan again.")


# --- DB Viewer (moved below the ID builder and print controls) ---
with tab_db:
    st.subheader("🗄️ DB Viewer")

    DB = utils.ensure_people_db()
    import sqlite3, json

    col_f1, col_f2, col_f3 = st.columns([3, 1, 2])
    with col_f1:
        db_filter = st.text_input("Filter (id or name)", value=st.session_state.get("db_filter", ""), key="db_filter")
    with col_f2:
        if st.button("Refresh", key="db_refresh", on_click=clear_db_filter):
            pass
    with col_f3:
        # Choose a company/template context to filter allowed positions
        tpl_keys = list_templates()
        db_tpl_index = tpl_keys.index(st.session_state.get("db_template")) if st.session_state.get("db_template") in tpl_keys else 0
        db_template = st.selectbox("Company template", options=tpl_keys, index=db_tpl_index, key="db_template")
        try:
            tpl_positions = get_template(db_template).positions or None
        except Exception:
            tpl_positions = None
        DB_POSITIONS = tpl_positions or utils.POSITIONS

    # Query DB (include position, is_admin, pokeball_count, jobs, companies)
    conn = sqlite3.connect(DB)
    params = ()
    sql = "SELECT id, name, max_clearance, images, password, position, is_admin, pokeball_count, jobs, companies FROM people"
    if db_filter:
        sql = sql + " WHERE id LIKE ? OR name LIKE ?"
        params = (f"%{db_filter}%", f"%{db_filter}%")
    rows = conn.execute(sql, params).fetchall()
    people = []
    # Collect known company keys from templates to define table columns
    company_keys = list_templates()
    for r in rows:
        # Extract companies dict to populate company columns
        companies_dict = {}
        try:
            companies_dict = json.loads(r[9]) if r[9] else {}
        except Exception:
            companies_dict = {}

        # Base record (removed jobs column - it's derived from companies)
        person_rec = {
            "id": r[0],
            "name": r[1],
            "max_clearance": r[2],
            "images": r[3],
            "password": r[4],
            "is_admin": bool(r[6]),
            "pokeball_count": int(r[7]) if r[7] is not None else 0,
        }

        # Add per-company columns with positions joined as strings
        for comp in company_keys:
            positions = companies_dict.get(comp) or []
            person_rec[comp] = ", ".join(positions) if positions else ""

        people.append(person_rec)
    conn.close()

    # Show a compact table with key columns
    st.table(people)

    # Select a person to view details and edit
    if people:
        choices = [f"{p['id']} — {p['name']}" for p in people]
        sel = st.selectbox("Select person", options=choices, index=0, key="db_select")
        selected_id = sel.split(" — ")[0]

        rec = utils.get_person_by_id(selected_id)
        if rec:
            st.write(f"**ID:** {rec['id']}")

            # Editable fields
            col_n, col_m = st.columns([3, 1])
            with col_n:
                new_name = st.text_input("Name", value=rec['name'], key=f"edit_name_{rec['id']}")
            with col_m:
                new_max = st.number_input("Max clearance", min_value=1, max_value=20, value=rec.get('max_clearance', 3), step=1, key=f"edit_max_{rec['id']}")

            if st.button("Save changes", key=f"save_person_{rec['id']}"):
                ok = utils.update_person(rec['id'], name=new_name, max_clearance=int(new_max))
                if ok:
                    st.success("Person updated")
                    safe_rerun()

            st.write(f"**Images ({len(rec.get('images', []))}):**")
            imgs = rec.get('images', [])
            if imgs:
                for idx, img in enumerate(imgs):
                    # Attempt to load image (filesystem path or package asset)
                    col_img, col_act = st.columns([3, 1])
                    try:
                        from pathlib import Path
                        img_obj = None
                        p = Path(img)
                        if p.exists():
                            img_obj = PIL.Image.open(p)
                        else:
                            # try public/photos folder
                            try:
                                photos_path = utils.PUBLIC_PHOTOS.joinpath(img)
                                if photos_path.exists():
                                    img_obj = PIL.Image.open(photos_path)
                            except Exception:
                                pass
                            
                            # try package asset
                            if img_obj is None:
                                try:
                                    asset_path = importlib.resources.files("catprint").joinpath("assets", img)
                                    if asset_path.exists():
                                        img_obj = PIL.Image.open(asset_path)
                                except Exception:
                                    img_obj = None

                        if img_obj:
                            col_img.image(img_obj, width=160)
                        else:
                            col_img.write(img)
                    except Exception:
                        col_img.write(img)

                    if col_act.button("Remove", key=f"removeimg_{rec['id']}_{idx}"):
                        removed = utils.remove_image_for_person(rec['id'], img)
                        if removed:
                            st.success("Image removed")
                            safe_rerun()
                        else:
                            st.error("Failed to remove image")
            else:
                st.write("(no images)")

            st.divider()

            st.write(f"**Position:** {rec.get('position','')}  **Admin:** {'Yes' if rec.get('is_admin') else 'No'}")
            st.write(f"**Jobs:** {', '.join(rec.get('jobs', [])) if rec.get('jobs') else '(none)'}")

            # Admin-only controls to change position / admin status (requires current UI user be admin)
            POSITIONS = DB_POSITIONS
            if st.session_state.get('id_is_admin', False):
                new_pos = st.selectbox("Set position", options=POSITIONS, index=POSITIONS.index(rec.get('position')) if rec.get('position') in POSITIONS else 0, key=f"db_setpos_{rec['id']}")
                new_admin = st.checkbox("Is admin", value=bool(rec.get('is_admin')), key=f"db_setadmin_{rec['id']}")
                # immediate save for pokeball slider changes
                new_pok = st.slider("Pokeball count", 0, 6, value=int(rec.get('pokeball_count', 0)), key=f"db_setpok_{rec['id']}")
                if new_pok != int(rec.get('pokeball_count', 0)):
                    okp = utils.update_person(rec['id'], pokeball_count=int(new_pok))
                    if okp:
                        st.success("Pokeball count updated")
                        safe_rerun()
                if st.button("Save record", key=f"db_save_{rec['id']}"):
                    ok = utils.update_person(rec['id'], position=new_pos, is_admin=1 if new_admin else 0)
                    if ok:
                        st.success("Record updated")
                        safe_rerun()
                    else:
                        st.error("Failed to update record")

            st.divider()

            # Company management form - visible to:
            # 1. Non-admin users managing their own companies
            # 2. Admin users managing ANY user's companies
            show_company_form = (not rec.get('is_admin') and not st.session_state.get('id_is_admin', False)) or st.session_state.get('id_is_admin', False)
            
            if show_company_form:
                st.subheader("📋 Manage Companies & Positions")
                current_companies = rec.get("companies", {}) or {}
                
                all_company_keys = company_keys
                new_companies = {}
                
                for company_key in all_company_keys:
                    tpl = get_template(company_key)
                    if not tpl:
                        continue
                    available_positions = tpl.positions if tpl.positions else utils.POSITIONS
                    current_positions = current_companies.get(company_key, [])
                    
                    selected_positions = st.multiselect(
                        f"**{company_key.title()}** — Select positions",
                        options=available_positions,
                        default=[p for p in current_positions if p in available_positions],
                        key=f"self_db_companies_{rec['id']}_{company_key}"
                    )
                    # Store all selected positions (even if empty list)
                    new_companies[company_key] = selected_positions
                
                if st.button("💾 Save companies and positions", key=f"self_db_save_companies_{rec['id']}"):
                    if new_companies != current_companies:
                        ok = utils.update_person(rec['id'], companies=new_companies)
                        if ok:
                            # Read directly from DB to verify save
                            import sqlite3, json
                            fresh_conn = sqlite3.connect(str(utils.DEFAULT_PEOPLE_DB))
                            fresh_c = fresh_conn.cursor()
                            fresh_c.execute("SELECT jobs, companies FROM people WHERE id = ?", (rec['id'],))
                            fresh_row = fresh_c.fetchone()
                            fresh_conn.close()
                            if fresh_row:
                                fresh_jobs = json.loads(fresh_row[0]) if fresh_row[0] else []
                                fresh_companies = json.loads(fresh_row[1]) if fresh_row[1] else {}
                                # Show derived jobs
                                st.success(f"✅ Saved! Jobs derived from positions: **{', '.join(fresh_jobs)}**")
                            else:
                                st.success("✅ Companies and positions saved!")
                            safe_rerun()
                        else:
                            st.error("❌ Failed to save changes")
                    else:
                        st.info("No changes to save")

            st.divider()

            # Attach image from public/photos; admins see all photos, others see a subset
            
            photo_files = utils.list_public_photos()
            available_photos = sorted(photo_files)

            sel_photo = st.selectbox("Choose image from public/photos", options=["(none)"] + available_photos, key=f"db_photosel_{rec['id']}")
            if st.button("Attach selected photo", key=f"db_attach_{rec['id']}"):
                if not sel_photo or sel_photo == "(none)":
                    st.error("Choose a photo first")
                else:
                    try:
                        ok = utils.attach_existing_image(rec['id'], sel_photo)
                        if ok:
                            st.success(f"Image attached: {sel_photo}")
                            safe_rerun()
                        else:
                            st.error("Failed to attach image to person (ensure file exists in public/photos)")
                    except Exception as e:
                        st.error(f"Failed to attach image: {e}")

            st.divider()

            # Delete person (require explicit confirm)
            if 'db_delete_pending' not in st.session_state:
                st.session_state['db_delete_pending'] = None

            if st.button("Delete person", key=f"db_delete_{rec['id']}"):
                st.session_state['db_delete_pending'] = rec['id']

            if st.session_state.get('db_delete_pending') == rec['id']:
                st.warning("Click Confirm to permanently delete this person")
                if st.button("Confirm delete", key=f"db_delete_confirm_{rec['id']}"):
                    ok = utils.delete_person(rec['id'])
                    if ok:
                        st.success("Person deleted")
                        st.session_state['db_delete_pending'] = None
                        st.experimental_rerun()
                    else:
                        st.error("Failed to delete person")

    # Admin: Add new person
    with st.expander("➕ Add new person (admin)"):
        new_id = st.text_input("ID", value="", key="new_person_id")
        new_name = st.text_input("Name", value="", key="new_person_name")
        new_pos = st.selectbox("Position", options=DB_POSITIONS, key="new_person_pos")
        new_max = st.number_input("Max clearance", min_value=1, max_value=20, value=3, key="new_person_max")
        new_pw = st.text_input("Password", value="admin", key="new_person_pw")
        new_admin = st.checkbox("Is admin", value=False, key="new_person_admin")
        new_img = st.file_uploader("Initial image (optional)", type=["png", "jpg", "jpeg"], key="new_person_img")
        if st.button("Add person", key="new_person_add"):
            if not new_id:
                st.error("ID is required")
            else:
                try:
                    utils.add_person(new_id, name=new_name, max_clearance=int(new_max), images=[], password=new_pw, position=new_pos, is_admin=bool(new_admin))
                    if new_img:
                        utils.add_image_for_person(new_id, new_img, filename=new_img.name)
                    st.success("Person added")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Failed to add person: {e}")
from catprint import receipt

# Sidebar live preview for receipts (visible regardless of active tab)
try:
    tpl_sidebar = get_template(st.session_state.receipt_selected_template) if st.session_state.get("receipt_selected_template") else None
except Exception:
    tpl_sidebar = None
rendered_blocks_sidebar = receipt.render_blocks(
    st.session_state.blocks,
    include_logo=st.session_state.get("receipt_include_logo", True),
    include_header_footer=st.session_state.get("receipt_include_header_footer", True),
    template=tpl_sidebar,
)
preview_img = catprint.render.stack(*rendered_blocks_sidebar) if rendered_blocks_sidebar else None
if preview_img is not None:
    st.sidebar.image(preview_img, caption="Live Preview", use_container_width=True)


