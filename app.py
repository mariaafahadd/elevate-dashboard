import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf
from datetime import datetime

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | Statutory Accounts", layout="wide")

# --- DATA EXTRACTION ENGINES ---
def extract_natwest_pdf(file):
    reader = pypdf.PdfReader(file)
    txns = []
    # NatWest PDF structure logic [cite: 13, 16]
    for page in reader.pages:
        text = page.extract_text()
        matches = re.findall(r'(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\s+(.*?)\s+(-?£[\d,]+\.\d{2})', text)
        for m in matches:
            date_str, desc, amt_str = m
            # Handle Year Logic for the 22/23 statements
            year = "2023" if any(x in date_str for x in ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]) else "2022"
            txns.append({
                "Date": pd.to_datetime(f"{date_str} {year}"),
                "Counter Party": desc,
                "Amount": float(amt_str.replace('£', '').replace(',', '')),
                "Category": "Uncategorized"
            })
    return pd.DataFrame(txns)

def process_data(uploaded_files):
    dfs = []
    for file in uploaded_files:
        if file.name.endswith('.csv'):
            tmp = pd.read_csv(file)
            tmp['Date'] = pd.to_datetime(tmp['Date'], dayfirst=True)
            tmp = tmp.rename(columns={'Amount (GBP)': 'Amount', 'Spending Category': 'Category'})
            dfs.append(tmp)
        elif file.name.endswith('.pdf'):
            dfs.append(extract_natwest_pdf(file))
    
    if not dfs: return pd.DataFrame()
    full_df = pd.concat(dfs, ignore_index=True)

    # PROPERTY & HMRC CATEGORY MAPPING [cite: 1, 2, 3, 13, 16]
    def map_accounting(row):
        text = (str(row['Counter Party']) + " " + str(row.get('Reference', ''))).upper()
        # Property Tagging
        prop = "18 Honor Street" if "HONOR" in text else "74 Barnby Street" if "BARNBY" in text else "General"
        
        # HMRC Category Mapping
        cat = "Operating Charge"
        if any(x in text for x in ["SALARY", "NAHEED"]): cat = "Staff Costs"
        elif any(x in text for x in ["MORTGAGE", "PRECISE", "CHARTER"]): cat = "Interest Payable"
        elif any(x in text for x in ["REPAIRS", "SELCO", "PLASTER"]): cat = "Raw Materials"
        elif any(x in text for x in ["JMW", "WTB", "SOLICITOR"]) and abs(row['Amount']) > 5000: cat = "Fixed Asset"
        
        return pd.Series([prop, cat])

    full_df[['Property', 'HMRC_Cat']] = full_df.apply(map_accounting, axis=1)
    return full_df

# --- APP UI ---
st.title("🏠 Elevate Living Ltd. | Statutory Financial Statements")
files = st.sidebar.file_uploader("Upload CSV/PDF Bank Statements", accept_multiple_files=True)

if files:
    df = process_data(files)
    
    # Financial Calculations
    turnover = df[df['Amount'] > 0]['Amount'].sum()
    staff_costs = df[df['HMRC_Cat'] == 'Staff Costs']['Amount'].sum()
    raw_materials = df[df['HMRC_Cat'] == 'Raw Materials']['Amount'].sum()
    other_charges = df[df['HMRC_Cat'] == 'Operating Charge' & (df['Amount'] < 0)]['Amount'].sum()
    interest = df[df['HMRC_Cat'] == 'Interest Payable']['Amount'].sum()
    fixed_assets = df[df['HMRC_Cat'] == 'Fixed Asset']['Amount'].abs().sum()

    # --- TAB 1: HMRC PROFIT AND LOSS ---
    st.header("Profit and Loss Account")
    st.subheader("Period ending 30 June 2023")
    
    pl_data = {
        "Description": ["Turnover", "Cost of Raw Materials", "Staff Costs", "Other Operating Charges", "Interest Payable"],
        "Amount (£)": [turnover, raw_materials, staff_costs, other_charges, interest]
    }
    pl_df = pd.DataFrame(pl_data)
    st.table(pl_df.style.format({"Amount (£)": "£{:,.2f}"}))
    
    net_profit = turnover + raw_materials + staff_costs + other_charges + interest
    st.metric("Profit / (Loss) before Taxation", f"£{net_profit:,.2f}")

    # --- TAB 2: MICRO-ENTITY BALANCE SHEET ---
    st.header("Balance Sheet")
    
    
    bs_col1, bs_col2 = st.columns(2)
    with bs_col1:
        st.write("### Assets")
        st.write(f"**Fixed Assets:** £{fixed_assets:,.2f}")
        st.write(f"**Current Assets (Bank Balance):** £{df['Amount'].sum():,.2f}")
    with bs_col2:
        st.write("### Capital & Reserves")
        st.write(f"**Called up share capital:** £100.00")
        st.write(f"**Retained Earnings:** £{net_profit:,.2f}")

    # --- TAB 3: PROPERTY PERFORMANCE ---
    st.header("Performance by Property")
    prop_perf = df.groupby('Property')['Amount'].sum().reset_index()
    fig = px.bar(prop_perf, x='Property', y='Amount', color='Property', title="Net Cash Flow by Property")
    st.plotly_chart(fig)

else:
    st.info("Please upload your statements to generate the statutory accounts.")
