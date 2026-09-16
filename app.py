import io
import os
import pandas as pd
import streamlit as st

# Direct local imports inside the ocr directory
from dpi import DPINormalizer
from schema import InvoiceDataResponse
from ocr import preprocess_file_bytes, extract_with_gemini


def create_excel_bytes(data: InvoiceDataResponse) -> bytes:
    """Generates Excel workbook in memory for user download."""
    summary_df = pd.DataFrame([{
        "ACID Number": data.acid_number,
        "Importer Tax ID": data.importer_tax_id,
        "Invoice Number": data.invoice_number,
        "Invoice Date": data.invoice_date,
        "Currency": data.currency,
        "Origin Port": data.origin_port,
        "Destination Port": data.destination_port,
        "Exporter Address": data.exporter_address,
        "Printed Total": data.bill_total,
        "Calculated Total": data.calculated_total,
        "Totals Match": data.totals_match,
    }])

    items_list = []
    for idx, item in enumerate(data.items, start=1):
        items_list.append({
            "Item #": idx,
            "Description": item.item_description,
            "HS Code": item.hs_code,
            "UOM": item.unit_of_measure,
            "Quantity": item.quantity,
            "Unit Price": item.unit_price,
            "Total Price": item.total_price,
            "Country of Origin": item.country_of_origin,
        })
    items_df = pd.DataFrame(items_list)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Invoice Summary", index=False)
        items_df.to_excel(writer, sheet_name="Line Items", index=False)
    
    return output.getvalue()


# ------------------- Streamlit UI Configuration -------------------

st.set_page_config(page_title="Nafeza OCR Tester", page_icon="🧾", layout="wide")

st.title("🧾 Nafeza Customs Invoice Extraction Testing Workbench")
st.markdown("Upload any commercial invoice **PDF** or **Image** to test extraction accuracy.")

# Sidebar API Key Setup
st.sidebar.header("Configuration")
env_api_key = os.environ.get("GEMINI_API_KEY", "")
api_key = st.sidebar.text_input("Gemini API Key", value=env_api_key, type="password")

if not api_key:
    st.warning("⚠️ Please provide a valid Gemini API Key in the sidebar or export GEMINI_API_KEY in your terminal.")

# File Uploader
uploaded_file = st.file_uploader(
    "Choose an Invoice File (PDF, PNG, JPG, JPEG, TIFF)", 
    type=["pdf", "png", "jpg", "jpeg", "tiff"]
)

if uploaded_file and api_key:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📄 Document Preview")
        file_bytes = uploaded_file.read()
        
        normalizer = DPINormalizer()
        with st.spinner("Preprocessing document at 300 DPI with CLAHE vision enhancement..."):
            pages = preprocess_file_bytes(file_bytes, uploaded_file.type, normalizer)
        
        for idx, page in enumerate(pages, start=1):
            st.image(page, caption=f"Page {idx} (Enhanced for Vision)", use_container_width=True)

    with col2:
        st.subheader("⚡ Extraction Results")
        if st.button("Run OCR Extraction", type="primary"):
            with st.spinner("Extracting structured fields with Gemini..."):
                try:
                    extracted_data = extract_with_gemini(pages, api_key)

                    # Reconciliation Logic
                    if extracted_data.items:
                        calc_sum = sum(
                            (item.total_price or (item.quantity * item.unit_price)) 
                            for item in extracted_data.items
                        )
                        extracted_data.calculated_total = round(calc_sum, 2)
                        if extracted_data.bill_total:
                            extracted_data.totals_match = abs(
                                extracted_data.calculated_total - extracted_data.bill_total
                            ) < 0.05

                    # Summary Status Indicators
                    m1, m2, m3 = st.columns(3)
                    
                    acid_len = len(extracted_data.acid_number or "")
                    m1.metric(
                        "ACID Number Status", 
                        extracted_data.acid_number or "Not Found",
                        delta="19 Digits Valid" if acid_len == 19 else f"Invalid ({acid_len} chars)",
                        delta_color="normal" if acid_len == 19 else "inverse"
                    )

                    m2.metric(
                        "Printed vs Calculated", 
                        f"{extracted_data.bill_total} {extracted_data.currency or 'USD'}",
                        delta=f"Calc: {extracted_data.calculated_total}"
                    )

                    m3.metric(
                        "Totals Reconciled", 
                        "MATCH ✅" if extracted_data.totals_match else "MISMATCH ❌"
                    )

                    st.divider()

                    # Result Tabs
                    tab1, tab2, tab3 = st.tabs(["📌 Header Summary", "📦 Line Items Table", "🔍 Raw JSON"])

                    with tab1:
                        st.json({
                            "acid_number": extracted_data.acid_number,
                            "importer_tax_id": extracted_data.importer_tax_id,
                            "invoice_number": extracted_data.invoice_number,
                            "invoice_date": extracted_data.invoice_date,
                            "currency": extracted_data.currency,
                            "origin_port": extracted_data.origin_port,
                            "destination_port": extracted_data.destination_port,
                            "exporter_address": extracted_data.exporter_address,
                            "bill_total": extracted_data.bill_total,
                            "calculated_total": extracted_data.calculated_total,
                            "totals_match": extracted_data.totals_match,
                        })

                    with tab2:
                        if extracted_data.items:
                            items_data = [item.model_dump() for item in extracted_data.items]
                            st.dataframe(pd.DataFrame(items_data), use_container_width=True)
                        else:
                            st.info("No line items extracted.")

                    with tab3:
                        st.code(extracted_data.model_dump_json(indent=2), language="json")

                    # Excel Export Button
                    excel_bytes = create_excel_bytes(extracted_data)
                    st.download_button(
                        label="📥 Download Results as Excel (.xlsx)",
                        data=excel_bytes,
                        file_name=f"extraction_{os.path.splitext(uploaded_file.name)[0]}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                except Exception as e:
                    st.error(f"Extraction failed: {str(e)}")