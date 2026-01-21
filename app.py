import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | Rental Portfolio Dash", layout="wide")

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
        prop = "18 Honor Street" if "HONOR" in text else "74 Barnby Street" if "BARNBY" in text else "General"
        
        # 1. INCOME
        if row['Amount'] > 0: 
            return pd.Series([prop, "Rental Income", "Income"])
        
        # 2. CAPITAL ASSETS (NOT IN P&L)
        if any(x in text for x in ["JMW", "WTB", "SOLICITOR"]) and abs(row['Amount']) > 5000: 
            return pd.Series([prop, "Property Acquisition/Legal", "Fixed Asset"])
        
        # 3. HMRC PROPERTY EXPENSES (P&L)
        if any(x in text for x in ["MORTGAGE", "PRECISE", "CHARTER"]): 
            return pd.Series([prop, "Loan Interest & Bank Charges", "Expense"])
        if any(x in text for x in ["REPAIRS", "SELCO", "PLASTER", "KHALID", "HAROUN"]): 
            return pd.Series([prop, "Property Repairs & Maintenance", "Expense"])
        if any(x in text for x in ["AXA", "INSURANCE"]): 
            return pd.Series([prop, "Insurance", "Expense"])
        if any(x in text for x in ["EE", "UTILITIES", "WATER", "GAS"]): 
            return pd.Series([prop, "Utilities & Council Tax", "Expense"])
        if any(x in text for x in ["SALARY", "NAHEED", "DIRECTOR"]): 
            return pd.Series([prop, "Wages & Staff Costs", "Expense"])
        if any(x in text for x in ["IONOS", "1 AND 1", "COMPANIES HOUSE", "GPS FINANCIAL", "PROPERTY INFO"]): 
            return pd.Series([prop, "Professional Fees & Admin", "Expense"])
        
        return pd.Series([prop, "Other Allowable Expenses", "Expense"])

    df[['Property', 'Detailed_Cat', 'Accounting_Type']] = df.apply(categorize_rental, axis=1)
    return df

# --- UI INTERFACE ---
st.title("🏠 Elevate Living Ltd. | Rental Business Dashboard")
uploaded_files = st.sidebar.file_uploader("Upload Starling/NatWest Data", accept_multiple_files=True)

if uploaded_files:
    data = process_data(uploaded_files)
    
    # Financial Calculations
    income_total = data[data['Accounting_Type'] == "Income"]['Amount'].sum()
    expense_total = data[data['Accounting_Type'] == "Expense"]['Amount'].sum()
    net_profit = income_total + expense_total
    assets_total = data[data['Accounting_Type'] == "Fixed Asset"]['Amount'].abs().sum()

    # 1. SUMMARY CARDS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gross Rent", f"£{income_total:,.2f}")
    c2.metric("Total Expenses", f"£{abs(expense_total):,.2f}")
    c3.metric("Net Profit", f"£{net_profit:,.2f}")
    c4.metric("Property Assets", f"£{assets_total:,.2f}")

    # 2. STATUTORY PROFIT & LOSS (Detailed HMRC Categories)
    st.header("Rental Income Profit & Loss Account")
    pl_breakdown = data[data['Accounting_Type'] != "Fixed Asset"].groupby('Detailed_Cat')['Amount'].sum().reset_index()
    pl_breakdown.columns = ['HMRC Category', 'Amount (£)']
    st.table(pl_breakdown.style.format({"Amount (£)": "£{:,.2f}"}))

    # 3. BALANCE SHEET
    st.header("Balance Sheet")
    
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.write("### Assets")
        st.write(f"**Fixed Assets (Land & Buildings):** £{assets_total:,.2f}")
        st.write(f"**Current Assets (Bank):** £{data['Amount'].sum():,.2f}")
    with b_col2:
        st.write("### Equity")
        st.write(f"**Retained Earnings:** £{net_profit:,.2f}")
        st.write(f"**Capital Contributed:** £{assets_total:,.2f}")

    # 4. PROPERTY COMPARISON
    st.header("Portfolio Breakdown")
    prop_chart = px.bar(data[data['Accounting_Type'] == "Income"], x='Property', y='Amount', color='Property', title="Income per Property")
    st.plotly_chart(prop_chart)

else:
    st.info("Upload your statements to generate detailed rental accounts.")
