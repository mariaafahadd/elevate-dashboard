import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf

st.set_page_config(page_title="Elevate Living | Property Dashboard", layout="wide")

# --- ACCOUNTING LOGIC ---
def extract_natwest_pdf(file):
    reader = pypdf.PdfReader(file)
    txns = []
    for page in reader.pages:
        text = page.extract_text()
        # Regex to find: Date (DD Mon) Description Type Amount
        matches = re.findall(r'(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\s+(.*?)\s+(-?£[\d,]+\.\d{2})', text)
        for m in matches:
            date_str, desc, amt_str = m
            # Handle year logic (Assuming files cover 2021-2023)
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
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --- APP UI ---
st.title("🏠 Elevate Living Ltd. Accounting App")
st.sidebar.header("Upload Center")
files = st.sidebar.file_uploader("Upload CSV or PDF Statements", accept_multiple_files=True)

if files:
    df = process_data(files)
    
    # Capitalization & Director Loan Logic
    # 1. Capital Assets (e.g., JMW Solicitors £44k, WTB Solicitors £37k) 
    is_asset = df['Counter Party'].str.contains('JMW|WTB|SOLICITOR', case=False, na=False)
    assets_val = df[is_asset]['Amount'].abs().sum()
    
    # 2. Revenue vs Expenses
    p_and_l = df[~is_asset]
    revenue = p_and_l[p_and_l['Amount'] > 0]['Amount'].sum()
    expenses = p_and_l[p_and_l['Amount'] < 0]['Amount'].sum()
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Gross Revenue", f"£{revenue:,.2f}")
    c2.metric("Operating Profit/Loss", f"£{revenue + expenses:,.2f}")
    c3.metric("Property Asset Value", f"£{assets_val:,.2f}")

    # Tabs for Accounts
    t1, t2 = st.tabs(["📊 Profit & Loss", "🏛️ Balance Sheet"])
    
    with t1:
        st.subheader("Profit & Loss Account")
        fig = px.bar(p_and_l, x='Date', y='Amount', color='Amount', title="Cash Flow Timeline")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(p_and_l.sort_values('Date', ascending=False))

    with t2:
        st.subheader("Balance Sheet")
        st.write(f"**Fixed Assets (Properties):** £{assets_val:,.2f}")
        st.write(f"**Current Assets (Cash):** £{df.sort_values('Date')['Amount'].sum():,.2f}")
        st.divider()
        st.write(f"**Total Equity:** £{revenue + expenses + assets_val:,.2f}")

else:
    st.info("Awaiting file uploads (CSV or PDF)...")
