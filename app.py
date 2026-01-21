import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | HMRC Accounts", layout="wide")

# --- ACCOUNTING ENGINES ---
def extract_natwest_pdf(file):
    reader = pypdf.PdfReader(file)
    txns = []
    for page in reader.pages:
        text = page.extract_text()
        # [cite_start]Regex to capture Date, Description, and Amount from NatWest PDF [cite: 13, 16]
        matches = re.findall(r'(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\s+(.*?)\s+(-?£[\d,]+\.\d{2})', text)
        for m in matches:
            date_str, desc, amt_str = m
            # [cite_start]Handle Year Logic: July-Dec is 2022, Jan-June is 2023 [cite: 9]
            year = "2023" if any(x in date_str for x in ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]) else "2022"
            txns.append({
                "Date": pd.to_datetime(f"{date_str} {year}"),
                "Counter Party": desc,
                "Amount": float(amt_str.replace('£', '').replace(',', '')),
                "Source": "NatWest PDF"
            })
    return pd.DataFrame(txns)

def process_data(uploaded_files):
    dfs = []
    for file in uploaded_files:
        if file.name.endswith('.csv'):
            tmp = pd.read_csv(file)
            tmp['Date'] = pd.to_datetime(tmp['Date'], dayfirst=True)
            tmp = tmp.rename(columns={'Amount (GBP)': 'Amount', 'Spending Category': 'Category'})
            tmp['Source'] = "Starling CSV"
            dfs.append(tmp)
        elif file.name.endswith('.pdf'):
            dfs.append(extract_natwest_pdf(file))
    
    if not dfs: return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)

    # HMRC & PROPERTY MAPPING LOGIC
    def categorize(row):
        text = (str(row['Counter Party']) + " " + str(row.get('Reference', ''))).upper()
        # [cite_start]Property Tagging [cite: 1, 13, 16]
        prop = "18 Honor Street" if "HONOR" in text else "74 Barnby Street" if "BARNBY" in text else "General"
        
        # [cite_start]HMRC FRS 105 Mapping [cite: 1, 13]
        cat = "Other Operating Charges"
        if row['Amount'] > 0: cat = "Turnover"
        elif any(x in text for x in ["SALARY", "NAHEED", "DIRECTOR"]): cat = "Staff Costs"
        elif any(x in text for x in ["MORTGAGE", "PRECISE", "CHARTER"]): cat = "Interest Payable"
        elif any(x in text for x in ["REPAIRS", "SELCO", "PLASTER"]): cat = "Raw Materials"
        elif any(x in text for x in ["JMW", "WTB", "SOLICITOR"]) and abs(row['Amount']) > 5000: cat = "Fixed Asset"
        
        return pd.Series([prop, cat])

    df[['Property', 'HMRC_Cat']] = df.apply(categorize, axis=1)
    return df

# --- UI INTERFACE ---
st.title("🏠 Elevate Living Ltd. | Statutory Accounts Portal")
uploaded_files = st.sidebar.file_uploader("Upload Statements (CSV/PDF)", accept_multiple_files=True)

if uploaded_files:
    data = process_data(uploaded_files)
    
    # Financial Summaries
    turnover = data[data['HMRC_Cat'] == 'Turnover']['Amount'].sum()
    staff = data[data['HMRC_Cat'] == 'Staff Costs']['Amount'].sum()
    materials = data[data['HMRC_Cat'] == 'Raw Materials']['Amount'].sum()
    interest = data[data['HMRC_Cat'] == 'Interest Payable']['Amount'].sum()
    other = data[data['HMRC_Cat'] == 'Other Operating Charges']['Amount'].sum()
    fixed_assets = data[data['HMRC_Cat'] == 'Fixed Asset']['Amount'].abs().sum()

    # --- HMRC PROFIT & LOSS ---
    st.header("Profit and Loss Account (FRS 105)")
    
    
    pl_table = pd.DataFrame({
        "HMRC Classification": ["Turnover", "Cost of Raw Materials", "Staff Costs", "Other Operating Charges", "Interest Payable"],
        "Amount (£)": [turnover, materials, staff, other, interest]
    })
    st.table(pl_table.style.format({"Amount (£)": "£{:,.2f}"}))
    
    net_profit = turnover + materials + staff + other + interest
    st.metric("Profit / (Loss) for the Year", f"£{net_profit:,.2f}")

    # --- BALANCE SHEET ---
    st.header("Balance Sheet")
    
    
    bs_left, bs_right = st.columns(2)
    with bs_left:
        st.subheader("Assets")
        st.write(f"**Fixed Assets (Properties):** £{fixed_assets:,.2f}")
        st.write(f"**Current Assets (Cash):** £{data['Amount'].sum():,.2f}")
    with bs_right:
        st.subheader("Capital and Reserves")
        st.write(f"**Retained Earnings:** £{net_profit:,.2f}")
        [cite_start]st.write(f"**Director Loan Account:** (£12,000.00)") # Based on historical transfers [cite: 13]

    # --- PROPERTY BREAKDOWN ---
    st.header("Breakdown by Address")
    prop_fig = px.bar(data[data['Amount'] > 0], x='Property', y='Amount', title="Rental Income by Property")
    st.plotly_chart(prop_fig)

else:
    st.info("Upload your 2021-2023 statements to generate statutory accounts.")
