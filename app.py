import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

# regex to find emails in affiliation lines
EMAIL_RX = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')

def parse_medline_text(text: str):
    """
    Parse MEDLINE-format text and extract authors with emails,
    handling multi-line AD blocks.
    """
    records = []
    # split into individual records by 'PMID-' markers
    chunks = re.split(r'\n(?=PMID-\s)', text.strip())

    for chunk in chunks:
        lines = chunk.splitlines()
        pmid = None
        title = None

        # 1) Extract PMID and Title
        for line in lines:
            if line.startswith('PMID-'):
                pmid = line.split('-', 1)[1].strip()
            elif line.startswith('TI  -'):
                title = line.split('-', 1)[1].strip()

        # 2) For each FAU, look ahead for its AD block
        i = 0
        while i < len(lines):
            if lines[i].startswith('FAU -'):
                author = lines[i].split('-', 1)[1].strip()
                email = ''
                j = i + 1
                # look for the next AD line, including continuation lines
                while j < len(lines):
                    if lines[j].startswith('AD  -'):
                        aff_lines = [lines[j].split('-', 1)[1].strip()]
                        k = j + 1
                        while k < len(lines) and lines[k].startswith(' '):
                            aff_lines.append(lines[k].strip())
                            k += 1
                        aff_text = ' '.join(aff_lines)
                        m = EMAIL_RX.search(aff_text)
                        if m:
                            email = m.group(0)
                        break
                    elif lines[j].startswith('FAU -'):
                        break
                    j += 1

                if email:
                    records.append({
                        'PMID': pmid,
                        'Title': title,
                        'Author': author,
                        'Email': email
                    })
            i += 1

    return records

# --- Streamlit UI ---
st.title("MEDLINE Author Email Extractor")
st.write("Upload one or more MEDLINE-format `.txt` files to extract only authors with emails (no duplicates).")

uploaded_files = st.file_uploader("Choose `.txt` files", type="txt", accept_multiple_files=True)

if uploaded_files:
    all_records = []
    for uploaded in uploaded_files:
        raw_text = uploaded.read().decode('utf-8', errors='ignore')
        all_records.extend(parse_medline_text(raw_text))

    if all_records:
        # create DataFrame, drop duplicates
        df = pd.DataFrame(all_records).drop_duplicates(subset=['PMID', 'Author', 'Email']).reset_index(drop=True)
        st.success(f"Extracted {len(df)} unique authors with emails from {len(uploaded_files)} file(s).")
        st.dataframe(df)

        # CSV download
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name="authors_with_emails.csv",
            mime="text/csv"
        )

        # Excel download
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer) as writer:
            df.to_excel(writer, index=False, sheet_name='Authors')
        st.download_button(
            "Download Excel",
            data=excel_buffer.getvalue(),
            file_name="authors_with_emails.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Copy to clipboard button
        csv_str = df.to_csv(index=False)
        # JSON-encode to safely embed
        js_csv = json.dumps(csv_str)
        st.markdown(f"""
            <button id="copy-btn">Copy All Results to Clipboard</button>
            <script>
            const btn = document.getElementById("copy-btn");
            btn.onclick = () => {{
              navigator.clipboard.writeText({js_csv});
              btn.innerText = "Copied!";
            }};
            </script>
            """, unsafe_allow_html=True)

    else:
        st.warning("No authors with emails were found in the uploaded files.")
