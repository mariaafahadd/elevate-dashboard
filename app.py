import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | Professional Rental Dash", layout="wide")

# --- ACCOUNTING ENGINES ---
def extract_natwest_pdf(file):
    reader = pypdf.PdfReader(file)
    txns = []
    for page in reader.pages:
        text = page.extract_text()
        matches = re.findall(r'(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\s+(.*?)\s+(-?£[\d,]+\.\d{2})', text)
        for m in matches:
            date_str, desc, amt_str = m
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
            dfs.append(tmp)
        elif file.name.endswith('.pdf'):
            dfs.append(extract_natwest_pdf(file))
    
    if not dfs: return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)

    def categorize_rental(row):
        text = (str(row['Counter Party']) + " " + str(row.get('Reference', ''))).upper()
        prop = "18 Honor Street" if "HONOR" in text else "74 Barnby Street" if "BARNBY" in text else "General Portfolio"
        
        # 1. INCOME
        if row['Amount'] > 0: 
            return pd.Series([prop, "Rental Income", "Income"])
        
        # 2. CAPITAL ASSETS (The £37k WTB payment and £44k JMW payment)
        if any(x in text for x in ["JMW", "WTB", "SOLICITOR", "ACQUISITION"]) and abs(row['Amount']) > 3000: 
            return pd.Series([prop, "Property Acquisition & Legal (Capital)", "Fixed Asset"])
        
        # 3. DETAILED HMRC EXPENSES (P&L)
        if any(x in text for x in ["MORTGAGE", "PRECISE", "CHARTER"]): 
            return pd.Series([prop, "Mortgage Interest & Financing", "Expense"])
        if any(x in text for x in ["REPAIRS", "SELCO", "PLASTER", "KHALID", "HAROUN", "MUHAMMAD AHMED"]): 
            return pd.Series([prop, "Maintenance, Repairs & Plastering", "Expense"])
        if any(x in text for x in ["AXA", "INSURANCE"]): 
            return pd.Series([prop, "Property Insurance", "Expense"])
        if any(x in text for x in ["EE", "UTILITIES", "WATER", "GAS"]): 
            return pd.Series([prop, "Utilities (Electric/Gas/Water)", "Expense"])
        if any(x in text for x in ["SALARY", "NAHEED", "DIRECTOR"]): 
            return pd.Series([prop, "Wages & Payroll Staff", "Expense"])
        if any(x in text for x in ["IONOS", "1 AND 1", "WEB", "COMPANIES HOUSE", "GPS FINANCIAL", "PROPERTY INFO", "DESIGN BY MARIA"]): 
            return pd.Series([prop, "Admin, Marketing & Professional Fees", "Expense"])
        if any(x in text for x in ["POST OFFICE", "CHARGES"]):
            return pd.Series([prop, "Bank & Post Office Charges", "Expense"])
        
        return pd.Series([prop, "Sundry Rental Expenses", "Expense"])

    df[['Property', 'HMRC_Category', 'Account_Type']] = df.apply(categorize_rental, axis=1)
    return df

# --- UI INTERFACE ---
st.title("🏠 Elevate Living Ltd. | Property Performance App")
uploaded_files = st.sidebar.file_uploader("Upload Starling/NatWest Data", accept_multiple_files=True)

if uploaded_files:
    data = process_data(uploaded_files)
    
    # Financial Stats
    income = data[data['Account_Type'] == "Income"]['Amount'].sum()
    opex = data[data['Account_Type'] == "Expense"]['Amount'].sum()
    capex = data[data['Account_Type'] == "Fixed Asset"]['Amount'].abs().sum()

    # 1. TOP LEVEL METRICS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gross Rents", f"£{income:,.2f}")
    c2.metric("Operating Costs", f"£{abs(opex):,.2f}")
    c3.metric("Net Profit", f"£{income + opex:,.2f}")
    c4.metric("Capital Invested", f"£{capex:,.2f}")

    # 2. DETAILED HMRC P&L TABLE
    st.subheader("Schedule E Property Income Breakdown")
    
    detailed_pl = data[data['Account_Type'] != "Fixed Asset"].groupby('HMRC_Category')['Amount'].sum().reset_index()
    detailed_pl.columns = ['HMRC Allowable Category', 'Total Amount (£)']
    st.table(detailed_pl.sort_values('Total Amount (£)').style.format({"Total Amount (£)": "£{:,.2f}"}))

    # 3. BALANCE SHEET
    st.subheader("Consolidated Balance Sheet")
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.info(f"**Fixed Assets (Land/Building Costs):** £{capex:,.2f}")
    with b_col2:
        st.success(f"**Current Cash (Net Inflow):** £{data['Amount'].sum():,.2f}")

    # 4. DATA LOGS
    with st.expander("View All Categorized Transactions"):
        st.dataframe(data.sort_values('Date', ascending=False))

else:
    st.info("Upload your statements (CSV or PDF) to generate the rental dashboard.")
