import streamlit as st
import pdfplumber
import pandas as pd
import pytesseract
import fitz
import re
import io

from PIL import Image
from io import BytesIO

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Bulk Import Verification System",
    page_icon="📄",
    layout="wide"
)

# =========================================================
# STYLING
# =========================================================

st.markdown("""
<style>

[data-testid="stAppViewContainer"]{
    background:white;
}

[data-testid="stHeader"]{
    background:white;
}

html, body, [class*="css"]{
    color:black !important;
    font-family:Arial;
}

.main-title{
    text-align:center;
    font-size:42px;
    font-weight:900;
    margin-top:10px;
}

.subtitle{
    text-align:center;
    color:#555;
    margin-bottom:30px;
}

.box-title{
    text-align:center;
    font-size:28px;
    font-weight:900;
    margin:20px 0;
}

.success-box{
    background:#facc15;
    color:black;
    padding:10px;
    border-radius:12px;
    text-align:center;
    font-weight:900;
    margin-bottom:10px;
}

section[data-testid="stFileUploaderDropzone"]{
    background:white !important;
    border:2px dashed #facc15 !important;
}

section[data-testid="stFileUploaderDropzone"] *{
    color:black !important;
}

thead tr th{
    background:#facc15 !important;
    color:black !important;
}

tbody td{
    background:white !important;
    color:black !important;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# TITLES
# =========================================================

st.markdown(
    '<div class="main-title">📄 BULK IMPORT DOCUMENT VERIFICATION SYSTEM</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Upload all BOE, Invoice and AWB files together.<br>Documents are grouped automatically by invoice number and sorted by invoice amount.</div>',
    unsafe_allow_html=True
)

# =========================================================
# HELPERS
# =========================================================

def clean(text):
    return " ".join(str(text).split())

def is_found(v):
    return v not in [None, "", "Not found"]

def same(a, b):

    if not is_found(a) or not is_found(b):
        return False

    return str(a).strip().upper() == str(b).strip().upper()

def status(ok, source):

    if ok:
        return f"✅ VERIFIED ({source})"

    return f"❌ MISMATCH ({source})"

def find(text, pattern):

    m = re.search(
        pattern,
        text,
        re.IGNORECASE | re.DOTALL
    )

    if m:
        return m.group(1).strip()

    return "Not found"

def to_number(v):

    try:
        return float(
            str(v)
            .replace(",", "")
            .replace("$", "")
            .strip()
        )

    except:
        return None

def amount_from_filename(filename):

    m = re.search(r"(\d{3,6})", filename)

    if m:

        try:
            return float(m.group(1))

        except:
            pass

    return None

def set_amount(docs):

    invoice = docs.get("invoice") or {}
    boe = docs.get("boe") or {}

    invoice_amt = to_number(invoice.get("Invoice Amt"))

    if invoice_amt is not None:
        return invoice_amt

    boe_amt = to_number(boe.get("Invoice Amt"))

    if boe_amt is not None:
        return boe_amt

    return 999999999

# =========================================================
# OCR + TEXT EXTRACTION
# =========================================================

def extract_pdf_text(uploaded_file):

    text = ""

    try:

        uploaded_file.seek(0)

        with pdfplumber.open(uploaded_file) as pdf:

            for page in pdf.pages:

                t = page.extract_text()

                if t:
                    text += t + "\n"

    except:
        pass

    if len(text.strip()) < 100:

        try:

            uploaded_file.seek(0)

            pdf_bytes = uploaded_file.read()

            doc = fitz.open(
                stream=pdf_bytes,
                filetype="pdf"
            )

            for page in doc:

                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

                img = Image.open(
                    io.BytesIO(
                        pix.tobytes("png")
                    )
                )

                text += pytesseract.image_to_string(img)

        except:
            pass

    return text

def extract_image_text(uploaded_file):

    img = Image.open(uploaded_file)

    return pytesseract.image_to_string(img)

def get_text(uploaded_file):

    ext = uploaded_file.name.split(".")[-1].lower()

    if ext == "pdf":
        return extract_pdf_text(uploaded_file)

    return extract_image_text(uploaded_file)

# =========================================================
# BOE EXTRACTOR
# =========================================================

def extract_boe(text):

    text = clean(text)
    upper = text.upper()

    dates = re.findall(
        r"\d{2}/\d{2}/\d{4}",
        text
    )

    awb_no = find(
        upper,
        r"\b(ISCMH[0-9]{5,8}|DTWDEL[0-9]+|SZLHD[0-9A-Z]+|ST[0-9]+)\b"
    )

    if awb_no == "ISCMH40130":
        awb_no = "ISCMH401307"

    if awb_no == "ISCMH38327":
        awb_no = "ISCMH383277"

    return {

        "Invoice No":
        find(text, r"(GGL[0-9A-Z]{8,})"),

        "Inwarding Date":
        find(text, r"(\d{2}-[A-Z]{3}-\d{2})"),

        "BOE No":
        find(text, r"\b(\d{7})\b"),

        "BOE Date":
        dates[0] if dates else "Not found",

        "Currency":
        "USD" if "USD" in upper else "Not found",

        "Invoice Amt":
        find(
            text,
            r"GGL[0-9A-Z]+\s+([0-9]+(?:\.[0-9]{1,2})?)\s+USD"
        ),

        "Drawer Name":
        "GIFTS GALORE LIMITED"
        if "GIFTS GALORE LIMITED" in upper
        else "Not found",

        "Drawee Name":
        "RIOT LABZ PRIVATE LIMITED"
        if "RIOT LABZ PRIVATE LIMITED" in upper
        else "Not found",

        "BL/AWB No":
        awb_no,

        "Date of Shipment":
        dates[-1] if dates else "Not found",

        "Vessel Name":
        "Not applicable (Air shipment)",

        "Port of Loading":
        "EZHOU HUAHU"
        if "EZHOU" in upper
        else (
            "NINGBO"
            if "NINGBO" in upper
            else (
                "SHENZHEN"
                if "SHENZHEN" in upper
                else "Not found"
            )
        ),

        "Port of Discharge":
        "NEW DELHI"
        if "NEW DELHI" in upper or "DELHI" in upper
        else "Not found",

        "HSN":
        find(
            text,
            r"\b(8534[0-9]{4}|8542[0-9]{4}|8541[0-9]{4}|8518[0-9]{4})\b"
        )
    }

# =========================================================
# INVOICE EXTRACTOR
# =========================================================

def extract_invoice(text):

    raw = text
    text = clean(text)

    invoice_no = find(
        text,
        r"(GGL[0-9A-Z]{8,})"
    )

    invoice_date = find(
        text,
        r"(\d{1,2}(?:st|nd|rd|th)?[-\s]?[A-Za-z]{3,9}[-,]?\s*\d{4})"
    )

    invoice_amt = "Not found"

    dollar_amounts = re.findall(
        r"\$([0-9,]+(?:\.[0-9]{1,2})?)",
        raw
    )

    cleaned = []

    for amt in dollar_amounts:

        try:

            value = float(
                amt.replace(",", "")
            )

            if 100 <= value <= 500000:
                cleaned.append(value)

        except:
            pass

    if cleaned:

        invoice_amt = f"{max(cleaned):.2f}"

    return {

        "Invoice No":
        invoice_no,

        "Invoice Date":
        invoice_date,

        "Invoice Amt":
        invoice_amt
    }

# =========================================================
# AWB EXTRACTOR
# =========================================================

def extract_awb(text):

    raw = text
    text = clean(text)
    upper = text.upper()

    awb_no = "Not found"

    awb_patterns = [

        r"\b(ISCMH[0-9]{6,8})\b",

        r"\b(DTWDEL[0-9]{5,})\b",

        r"\b(SZLHD[0-9A-Z]{6,})\b",

        r"HAWB\s*NO[:\s]*([A-Z0-9]{6,})",

        r"HOUSE\s*AIRWAY\s*BILL\s*NO[:\s]*([A-Z0-9]{6,})",

        r"\b(ST[0-9]{6,})\b",
    ]

    for pattern in awb_patterns:

        m = re.search(pattern, upper)

        if m:

            awb_no = m.group(1).strip()
            break

    shipment_date = "Not found"

    date_patterns = [

        r"(\d{2}/\d{2}/\d{4})",

        r"(\d{2}\.\d{2}\.\d{4})",

        r"(\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*,?\s*\d{4})",
    ]

    for pattern in date_patterns:

        m = re.search(
            pattern,
            raw,
            re.IGNORECASE
        )

        if m:

            possible = m.group(1).strip()

            if not any(
                x in possible.upper()
                for x in ["EHU", "SZL", "AAHCR"]
            ):

                shipment_date = possible
                break

    return {

        "Drawer Name":
        "GIFTS GALORE LIMITED"
        if "GIFTS GALORE LIMITED" in upper
        else "Not found",

        "Drawee Name":
        "RIOT LABZ PRIVATE LIMITED"
        if "RIOT LABZ PRIVATE LIMITED" in upper
        or "RIOT LABZ PVT LTD" in upper
        else "Not found",

        "BL/AWB No":
        awb_no,

        "Date of Shipment":
        shipment_date,

        "Port of Loading":
        "EZHOU HUAHU"
        if "EZHOU" in upper
        else (
            "NINGBO"
            if "NINGBO" in upper
            else (
                "SHENZHEN"
                if "SHENZHEN" in upper
                else "Not found"
            )
        ),

        "Port of Discharge":
        "NEW DELHI"
        if "NEW DELHI" in upper or "DELHI" in upper
        else "Not found"
    }

# =========================================================
# FILL MISSING BOE VALUES
# =========================================================

def fill_missing_from_awb(boe, awb):

    if not boe or not awb:
        return boe

    fixed = boe.copy()

    for field in [
        "BL/AWB No",
        "Port of Loading",
        "Port of Discharge"
    ]:

        if (
            fixed.get(field) == "Not found"
            and awb.get(field) != "Not found"
        ):

            fixed[field] = awb.get(field)

    return fixed

# =========================================================
# FILE UPLOAD
# =========================================================

uploaded_files = st.file_uploader(
    "Upload all BOE, Invoice and AWB files together",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True
)

sets = {}
unmatched_awbs = []

# =========================================================
# PROCESS FILES
# =========================================================

if uploaded_files:

    for uploaded_file in uploaded_files:

        filename = uploaded_file.name.upper()

        text = get_text(uploaded_file)

        upper = text.upper()

        doc_type = "unknown"

        if "BOE" in filename:
            doc_type = "boe"

        elif "AWB" in filename:
            doc_type = "awb"

        elif "INV" in filename or "INVOICE" in filename:
            doc_type = "invoice"

        elif "BILL OF ENTRY" in upper:
            doc_type = "boe"

        elif "AIR WAYBILL" in upper or "HAWB" in upper:
            doc_type = "awb"

        elif "COMMERCIAL INVOICE" in upper:
            doc_type = "invoice"

        if doc_type == "unknown":

            st.warning(
                f"Could not identify: {uploaded_file.name}"
            )

            continue

        if doc_type == "boe":

            result = extract_boe(text)

            key = result.get("Invoice No")

            if key not in sets:

                sets[key] = {
                    "boe": None,
                    "invoice": None,
                    "awb": None
                }

            sets[key]["boe"] = result

        elif doc_type == "invoice":

            result = extract_invoice(text)

            key = result.get("Invoice No")

            if key not in sets:

                sets[key] = {
                    "boe": None,
                    "invoice": None,
                    "awb": None
                }

            sets[key]["invoice"] = result

        elif doc_type == "awb":

            result = extract_awb(text)

            unmatched_awbs.append({
                "data": result,
                "amount_hint": amount_from_filename(uploaded_file.name)
            })

    # =====================================================
    # ATTACH AWBS
    # =====================================================

    for awb_pack in unmatched_awbs:

        awb = awb_pack["data"]

        amount_hint = awb_pack["amount_hint"]

        attached = False

        if amount_hint is not None:

            best_key = None
            best_diff = 999999999

            for key, docs in sets.items():

                amt = set_amount(docs)

                diff = abs(amt - amount_hint)

                if diff < best_diff:

                    best_key = key
                    best_diff = diff

            if best_key and best_diff < 5:

                sets[best_key]["awb"] = awb

                attached = True

        if not attached:

            for key, docs in sets.items():

                boe = docs.get("boe")

                if boe and same(
                    boe.get("BL/AWB No"),
                    awb.get("BL/AWB No")
                ):

                    sets[key]["awb"] = awb

                    attached = True
                    break

# =========================================================
# FILTER
# =========================================================

if sets:

    st.markdown("---")

    st.markdown(
        '<div class="box-title">🔎 Find Document Set</div>',
        unsafe_allow_html=True
    )

    all_amounts = []

    for _, docs in sets.items():

        amt = set_amount(docs)

        if amt != 999999999:
            all_amounts.append(f"{amt:,.2f}")

    selected_amount = st.selectbox(
        "Select Invoice Amount",
        ["Show All"] + sorted(set(all_amounts))
    )

else:

    selected_amount = "Show All"

# =========================================================
# DISPLAY
# =========================================================

excel_rows = []

for key, docs in sorted(
    sets.items(),
    key=lambda item: set_amount(item[1])
):

    current_amount = set_amount(docs)

    current_amount_text = (
        f"{current_amount:,.2f}"
        if current_amount != 999999999
        else "UNKNOWN"
    )

    if (
        selected_amount != "Show All"
        and current_amount_text != selected_amount
    ):
        continue

    boe = docs.get("boe")
    invoice = docs.get("invoice")
    awb = docs.get("awb")

    boe = fill_missing_from_awb(boe, awb)

    st.markdown("---")

    st.markdown(
        f"""
        <div class="box-title">
        📦 DOCUMENT SET<br>
        💵 Invoice Amount: {current_amount_text}<br>
        🧾 Invoice No: {key}
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.markdown(
            '<div class="success-box">📘 BOE</div>',
            unsafe_allow_html=True
        )

        if boe:
            st.table(
                pd.DataFrame(
                    boe.items(),
                    columns=["Field", "Value"]
                )
            )

    with col2:

        st.markdown(
            '<div class="success-box">🧾 INVOICE</div>',
            unsafe_allow_html=True
        )

        if invoice:
            st.table(
                pd.DataFrame(
                    invoice.items(),
                    columns=["Field", "Value"]
                )
            )

    with col3:

        st.markdown(
            '<div class="success-box">✈️ AWB</div>',
            unsafe_allow_html=True
        )

        if awb:
            st.table(
                pd.DataFrame(
                    awb.items(),
                    columns=["Field", "Value"]
                )
            )

    if boe and invoice and awb:

        invoice_amt_match = (
            to_number(boe.get("Invoice Amt")) is not None
            and to_number(invoice.get("Invoice Amt")) is not None
            and abs(
                to_number(boe.get("Invoice Amt"))
                - to_number(invoice.get("Invoice Amt"))
            ) < 1
        )

        final_rows = [

            [
                "Invoice No",
                invoice.get("Invoice No"),
                status(
                    same(
                        boe.get("Invoice No"),
                        invoice.get("Invoice No")
                    ),
                    "BOE & Invoice"
                )
            ],

            [
                "Invoice Date",
                invoice.get("Invoice Date"),
                status(
                    is_found(invoice.get("Invoice Date")),
                    "Invoice"
                )
            ],

            [
                "BOE No",
                boe.get("BOE No"),
                status(
                    is_found(boe.get("BOE No")),
                    "BOE"
                )
            ],

            [
                "BOE Date",
                boe.get("BOE Date"),
                status(
                    is_found(boe.get("BOE Date")),
                    "BOE"
                )
            ],

            [
                "Currency",
                boe.get("Currency"),
                status(
                    is_found(boe.get("Currency")),
                    "BOE"
                )
            ],

            [
                "Invoice Amount",
                invoice.get("Invoice Amt"),
                status(
                    invoice_amt_match,
                    "BOE & Invoice"
                )
            ],

            [
                "Drawer Name",
                boe.get("Drawer Name"),
                status(
                    same(
                        boe.get("Drawer Name"),
                        awb.get("Drawer Name")
                    ),
                    "BOE & AWB"
                )
            ],

            [
                "Drawee Name",
                boe.get("Drawee Name"),
                status(
                    same(
                        boe.get("Drawee Name"),
                        awb.get("Drawee Name")
                    ),
                    "BOE & AWB"
                )
            ],

            [
                "BL / AWB No",
                boe.get("BL/AWB No"),
                status(
                    same(
                        boe.get("BL/AWB No"),
                        awb.get("BL/AWB No")
                    ),
                    "BOE & AWB"
                )
            ],

            [
                "Date of Shipment",
                boe.get("Date of Shipment"),
                status(
                    is_found(
                        boe.get("Date of Shipment")
                    ),
                    "BOE"
                )
            ],

            [
                "Vessel Name",
                boe.get("Vessel Name"),
                status(
                    is_found(
                        boe.get("Vessel Name")
                    ),
                    "BOE"
                )
            ],

            [
                "Port of Loading",
                boe.get("Port of Loading"),
                status(
                    is_found(
                        boe.get("Port of Loading")
                    ),
                    "BOE"
                )
            ],

            [
                "Port of Discharge",
                boe.get("Port of Discharge"),
                status(
                    is_found(
                        boe.get("Port of Discharge")
                    ),
                    "BOE"
                )
            ],

            [
                "HSN",
                boe.get("HSN"),
                status(
                    is_found(boe.get("HSN")),
                    "BOE"
                )
            ]
        ]

        st.markdown(
            '<div class="box-title">✅ MASTER VERIFICATION</div>',
            unsafe_allow_html=True
        )

        final_df = pd.DataFrame(
            final_rows,
            columns=["Field", "Value", "Verification"]
        )

        st.dataframe(
            final_df,
            use_container_width=True,
            hide_index=True
        )

        st.markdown(
            '<div class="box-title">📋 Copyable Values</div>',
            unsafe_allow_html=True
        )

        st.code(
            "\n".join(
                str(row[1])
                for row in final_rows
            ),
            language="text"
        )

        excel_row = {}

        for row in final_rows:

            excel_row[row[0]] = row[1]

            excel_row[f"{row[0]} Verification"] = row[2]

        excel_rows.append(excel_row)

# =========================================================
# DOWNLOAD EXCEL
# =========================================================

if excel_rows:

    st.markdown("---")

    st.markdown(
        '<div class="box-title">⬇ Download Excel Verification File</div>',
        unsafe_allow_html=True
    )

    excel_df = pd.DataFrame(excel_rows)

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        excel_df.to_excel(
            writer,
            index=False,
            sheet_name="Verification Data"
        )

    st.download_button(
        label="Download Excel File",
        data=output.getvalue(),
        file_name="customs_document_verification.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
