import streamlit as st
import fitz  # PyMuPDF
import zipfile
import tempfile
import os
import re
import pandas as pd
import io
import json
from PIL import Image
import pdfplumber
import docx2txt
import easyocr
import pytesseract
import numpy as np

# Initialize EasyOCR reader (English only)
easyocr_reader = easyocr.Reader(['en'], gpu=False)

def pdf_to_text_per_page(pdf_path):
    doc = fitz.open(pdf_path)
    page_texts = []
    for page in doc:
        text = page.get_text()
        if not text.strip():
            # If no text, convert page to image and OCR with pytesseract
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img)
        page_texts.append(text)
    doc.close()
    return page_texts

def extract_tables(pdf_path):
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            for table in page_tables:
                df = pd.DataFrame(table)
                tables.append((i+1, df))
    return tables

def extract_images(pdf_path):
    images = []
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        img_list = page.get_images(full=True)
        for img_index, img in enumerate(img_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            images.append({
                "page": i+1,
                "image": image_bytes,
                "extension": image_ext,
                "name": f"page_{i+1}_img_{img_index+1}.{image_ext}"
            })
    doc.close()
    return images

def extract_fields(text, document_type):
    fields = {}

    # Common fields found in most documents
    fields["Email ID"] = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    fields["Date"] = re.search(
        r"\b(?:\d{1,2}[-/\s\.]*)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t)?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[-/\s\.]*\d{1,4}\b|\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
        text,
    )
    fields["Phone Number"] = re.search(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b", text)
    fields["GST Number"] = re.search(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b", text)

    if document_type == "Commercial Invoice":
        fields["Invoice Number"] = re.search(r"Invoice\s*No\.?:?\s*(\S+)", text, re.IGNORECASE)
        fields["Exporter Name"] = re.search(r"Exporter\s*Name\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Importer Name"] = re.search(r"Importer\s*Name\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Buyer"] = re.search(r"Buyer\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Description of Goods"] = re.search(r"Description\s*of\s*Goods\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Unit Price"] = re.search(r"Unit\s*Price\s*:\s*([\d.,]+)", text, re.IGNORECASE)
        fields["Total Price"] = re.search(r"Total\s*Price\s*:\s*([\d.,]+)", text, re.IGNORECASE)
        fields["Currency"] = re.search(r"Currency\s*:\s*(\w{3})", text, re.IGNORECASE)
        fields["Payment Terms"] = re.search(r"Payment\s*Terms\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Incoterms"] = re.search(r"Incoterms\s*:\s*(.*)", text, re.IGNORECASE)
        fields["HS Code"] = re.search(r"HS\s*Code\s*:\s*(\w+)", text, re.IGNORECASE)
        fields["Country of Origin"] = re.search(r"Country\s*of\s*Origin\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Exporter Signature"] = re.search(r"Signature\s*of\s*Exporter\s*:\s*(.*)", text, re.IGNORECASE)

    elif document_type == "Bill of Lading":
        fields["Bill of Lading Number"] = re.search(r"Bill\s*of\s*Lading\s*No\.?:?\s*(\S+)", text, re.IGNORECASE)
        fields["Consignor"] = re.search(r"Consignor\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Consignee"] = re.search(r"Consignee\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Notify Party"] = re.search(r"Notify\s*Party\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Description of Goods"] = re.search(r"Description\s*of\s*Goods\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Voyage Details"] = re.search(r"Voyage\s*Details\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Port of Loading"] = re.search(r"Port\s*of\s*Loading\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Port of Discharge"] = re.search(r"Port\s*of\s*Discharge\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Carrier Details"] = re.search(r"Carrier\s*Details\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Freight Terms"] = re.search(r"Freight\s*Terms\s*:\s*(Prepaid|Collect)", text, re.IGNORECASE)
        fields["Container Numbers"] = re.search(r"Container\s*Numbers\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Carrier Signature"] = re.search(r"Signature\s*of\s*Carrier\s*:\s*(.*)", text, re.IGNORECASE)

    elif document_type == "Packing List":
        fields["Exporter Details"] = re.search(r"Exporter\s*Details\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Importer Details"] = re.search(r"Importer\s*Details\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Invoice Reference"] = re.search(r"Invoice\s*Reference\s*:\s*(\S+)", text, re.IGNORECASE)
        fields["Description of Goods per Box"] = re.search(r"Description\s*of\s*Goods\s*per\s*Box\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Number of Boxes"] = re.search(r"Number\s*of\s*Boxes\s*:\s*(\d+)", text, re.IGNORECASE)
        fields["Gross Weight"] = re.search(r"Gross\s*Weight\s*:\s*([\d.]+\s*(?:kg|g|lbs|tons)?)", text, re.IGNORECASE)
        fields["Net Weight"] = re.search(r"Net\s*Weight\s*:\s*([\d.]+\s*(?:kg|g|lbs|tons)?)", text, re.IGNORECASE)
        fields["Dimensions"] = re.search(r"Dimensions\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Marks and Numbers"] = re.search(r"Marks\s*and\s*Numbers\s*:\s*(.*)", text, re.IGNORECASE)

    elif document_type == "Certificate of Origin":
        fields["Exporter Details"] = re.search(r"Exporter\s*Details\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Consignee Details"] = re.search(r"Consignee\s*Details\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Description of Goods"] = re.search(r"Description\s*of\s*Goods\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Country of Origin"] = re.search(r"Country\s*of\s*Origin\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Certifying Authority"] = re.search(r"Certifying\s*Authority\s*Stamp\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Certifying Signature"] = re.search(r"Signature\s*:\s*(.*)", text, re.IGNORECASE)

    elif document_type == "Shipping Instructions":
        fields["Pick-up Instructions"] = re.search(r"Pick-?up\s*Instructions\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Delivery Instructions"] = re.search(r"Delivery\s*Instructions\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Document Handling"] = re.search(r"Document\s*Handling\s*Preferences\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Special Instructions"] = re.search(r"Special\s*Instructions\s*:\s*(.*)", text, re.IGNORECASE)

    elif document_type == "Insurance Certificate":
        fields["Type of Coverage"] = re.search(r"Type\s*of\s*Coverage\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Insured Value"] = re.search(r"Insured\s*Value\s*:\s*([\d.,]+)", text, re.IGNORECASE)
        fields["Goods Description"] = re.search(r"Goods\s*Description\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Shipment Route"] = re.search(r"Shipment\s*Route\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Policy Number"] = re.search(r"Insurance\s*Policy\s*Number\s*:\s*(.*)", text, re.IGNORECASE)

    else:
        # Default fallback fields
        fields["Consignor"] = re.search(r"Consignor\s*:\s*(.*)", text, re.IGNORECASE)
        fields["Consignee"] = re.search(r"Consignee\s*:\s*(.*)", text, re.IGNORECASE)

    # Address fallback - common field
    address_match = re.search(r"Address\s*:\s*(.+)", text, re.IGNORECASE)
    if not address_match:
        address_match = re.search(
            r"\b\d{1,4}.*(Street|St\.|Road|Rd\.|Avenue|Ave\.|Lane|Ln\.|Block|Sector).*\b", text, re.IGNORECASE
        )
    fields["Address"] = address_match

    # Clean the extracted results (convert Match objects to strings or None)
    cleaned = {}
    for key, match in fields.items():
        if match:
            # For common fields like Email, Date, Phone, GST keep full match
            if key in ["Email ID", "Date", "Phone Number", "GST Number", "Insured Value", "Unit Price", "Total Price"]:
                cleaned[key] = match.group(0).strip()
            else:
                cleaned[key] = match.group(1).strip()
        else:
            cleaned[key] = None

    return cleaned

def extract_text_from_txt(file):
    file.seek(0)
    return file.read().decode("utf-8")

def extract_text_from_docx(file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name
    return docx2txt.process(tmp_path)

def extract_text_from_image(file):
    file.seek(0)
    image = Image.open(file).convert("RGB")
    img_np = np.array(image)
    result = easyocr_reader.readtext(img_np, detail=0, paragraph=True)
    return "\n".join(result)

st.title("📄 Document Text Extractor")

uploaded_zip = st.file_uploader("Upload ZIP file with PDF docs (optional)", type=["zip"])
uploaded_files = st.file_uploader(
    "Or upload individual files (PDF, TXT, DOCX, PNG, JPG, JPEG)",
    type=["pdf", "txt", "docx", "png", "jpg", "jpeg"],
    accept_multiple_files=True
)

# Define document types for selection
document_types = ["Commercial Invoice", "Bill of Lading", "Packing List", "Certificate of Origin", "Shipping Instructions", "Insurance Certificate"]
selected_document_type = st.selectbox("Select Document Type:", document_types)
st.write(f"You selected: {selected_document_type}")

all_data = []

def detect_document_type(text):
    """
    Basic heuristic to detect document type based on keywords in the text.
    Returns one of the known document types or None if no match.
    """
    text_lower = text.lower()

    if any(keyword in text_lower for keyword in ["invoice", "invoice no", "buyer", "unit price", "total price"]):
        return "Commercial Invoice"
    elif any(keyword in text_lower for keyword in ["bill of lading", "consignor", "consignee", "notify party"]):
        return "Bill of Lading"
    elif any(keyword in text_lower for keyword in ["packing list", "number of boxes", "gross weight", "net weight"]):
        return "Packing List"
    elif any(keyword in text_lower for keyword in ["certificate of origin", "certifying authority", "country of origin"]):
        return "Certificate of Origin"
    elif any(keyword in text_lower for keyword in ["shipping instructions", "pickup instructions", "delivery instructions"]):
        return "Shipping Instructions"
    elif any(keyword in text_lower for keyword in ["insurance certificate", "type of coverage", "insured value", "policy number"]):
        return "Insurance Certificate"
    else:
        return None

def process_pdf_file(file_bytes, file_name):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(file_bytes)
            tmp_pdf_path = tmp_pdf.name

        page_texts = pdf_to_text_per_page(tmp_pdf_path)

        for i, text in enumerate(page_texts):
            detected_type = detect_document_type(text)
            document_type = detected_type if detected_type else selected_document_type
            fields = extract_fields(text, document_type)
            fields["File Name"] = file_name
            fields["Page Number"] = i + 1
            fields["Extracted Text"] = text
            all_data.append(fields)

            st.subheader(f"📁 {file_name} - Page {i + 1}")
            st.write(f"**Document Type**: {document_type}")
            for k, v in fields.items():
                if k not in ["File Name", "Extracted Text", "Page Number"]:
                    st.write(f"**{k}**: {v}")

            with st.expander("Show Text"):
                st.text(text)

        tables = extract_tables(tmp_pdf_path)
        if tables:
            st.markdown("**📊 Extracted Tables:**")
            for page_num, df in tables:
                st.markdown(f"**Table from Page {page_num}**")
                st.dataframe(df)

        images = extract_images(tmp_pdf_path)
        if images:
            st.markdown("**🖼️ Extracted Images:**")
            for img in images:
                st.image(img["image"], caption=f"{img['name']}", use_column_width=True)

    except Exception as e:
        st.warning(f"⚠️ Could not process {file_name}: {e}")

if uploaded_zip:
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "uploaded.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.read())
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
        for root, _, files in os.walk(tmpdir):
            for file_name in files:
                if file_name.lower().endswith(".pdf"):
                    full_path = os.path.join(root, file_name)
                    with open(full_path, "rb") as pdf_file:
                        process_pdf_file(pdf_file.read(), file_name)

if uploaded_files:
    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name.lower()
        try:
            if file_name.endswith(".pdf"):
                process_pdf_file(uploaded_file.read(), uploaded_file.name)
            elif file_name.endswith(".txt"):
                text = extract_text_from_txt(uploaded_file)
                file_type = "TXT"
            elif file_name.endswith(".docx"):
                text = extract_text_from_docx(uploaded_file)
                file_type = "DOCX"
            elif file_name.endswith((".png", ".jpg", ".jpeg")):
                text = extract_text_from_image(uploaded_file)
                file_type = "Image"
            else:
                continue

            if file_name.endswith((".txt", ".docx", ".png", ".jpg", ".jpeg")):
                document_type = selected_document_type  # Use the selected document type
                fields = extract_fields(text, document_type)
                fields.update({
                    "File Name": file_name,
                    "Page Number": 1,
                    "Extracted Text": text
                })
                all_data.append(fields)

                st.subheader(f"📄 {uploaded_file.name} ({file_type})")
                st.write(f"**Document Type**: {document_type}")
                for k, v in fields.items():
                    if k != "Extracted Text":
                        st.write(f"**{k}**: {v}")
                with st.expander("Show Text"):
                    st.text(text)

        except Exception as e:
            st.warning(f"⚠️ Could not process {uploaded_file.name}: {e}")

if all_data:
    df_all = pd.DataFrame([{k: v for k, v in item.items() if k != "Extracted Text"} for item in all_data])
    
    # CSV download
    csv_buffer = io.StringIO()
    df_all.to_csv(csv_buffer, index=False)
    st.subheader("⬇️ Download Extracted Structured Data")
    st.download_button(
        label="Download combined CSV",
        data=csv_buffer.getvalue(),
        file_name="extracted_data.csv",
        mime="text/csv"
    )
    
    # JSON download
    json_data = json.dumps(all_data, indent=2)
    st.subheader("⬇️ Download Extracted Structured Data (JSON)")
    st.download_button(
        label="Download combined JSON",
        data=json_data,
        file_name="extracted_data.json",
        mime="application/json"
    )
    
    st.subheader("⬇️ Download Extracted Raw Texts")
    with tempfile.TemporaryDirectory() as text_dir:
        text_zip_path = os.path.join(text_dir, "extracted_texts.zip")
        with zipfile.ZipFile(text_zip_path, "w") as zipf:
            for item in all_data:
                file_txt_name = os.path.splitext(item["File Name"])[0] + f"_page_{item['Page Number']}.txt"
                file_txt_path = os.path.join(text_dir, file_txt_name)
                with open(file_txt_path, "w", encoding="utf-8") as f:
                    f.write(item["Extracted Text"])
                zipf.write(file_txt_path, arcname=file_txt_name)

        with open(text_zip_path, "rb") as zipf:
            st.download_button(
                label="Download All Extracted Texts (.zip)",
                data=zipf,
                file_name="extracted_texts.zip",
                mime="application/zip"
            )

elif not uploaded_zip and not uploaded_files:
    st.info("Please upload a ZIP file or individual files to get started.")

