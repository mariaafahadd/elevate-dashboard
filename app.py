import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf
from datetime import datetime

# --- ACCOUNTANT'S CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | UK Accountant Portal", layout="wide")

# --- ACCOUNTING ENGINE: DATA EXTRACTION ---
def extract_natwest_pdf(file):
    reader = pypdf.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    
    # Extract Statement Period to fix the DateParseError
    year_match = re.search(r'From\s+\d{2}/\d{2}/(\d{4})', text)
    base_year = int(year_match.group(1)) if year_match else 2022
    
    months_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 
                  'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
    
    txns = []
    matches = re.findall(r'(\d{1,2})\s(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(.*?)\s+(-?£[\d,]+\.\d{2})', text)
    
    for m in matches:
        day, month_str, desc, amt_str = m
        month_num = months_map[month_str]
        year = base_year if month_num >= 7 else base_year + 1
        
        txns.append({
            "Date": datetime(year, month_num, int(day)),
            "Counter Party": desc.strip(),
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
            if 'Amount (GBP)' in tmp.columns:
                tmp = tmp.rename(columns={'Amount (GBP)': 'Amount', 'Spending Category': 'Category'})
            dfs.append(tmp)
        elif file.name.endswith('.pdf'):
            dfs.append(extract_natwest_pdf(file))
    
    if not dfs: return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)

    # --- ADVANCED ACCOUNTING CLASSIFICATION ---
    def categorize_statutory(row):
        text = (str(row['Counter Party']) + " " + str(row.get('Reference', ''))).upper()
        prop = "18 Honor Street" if "HONOR" in text else "74 Barnby Street" if "BARNBY" in text else "General Portfolio"
        
        # 1. Revenue Segmentation
        if row['Amount'] > 0:
            rtype = "Standard Rent"
            if "TODD" in text: rtype = "Legal Settlement"
            if "MUSTAFA" in text: rtype = "Company Let"
            if "PARVEZ" in text and row['Amount'] > 2000: rtype = "Director Capital Injection"
            return pd.Series([prop, "Turnover", "Income", rtype])
        
        # 2. Capital Assets (Balance Sheet Only)
        if any(x in text for x in ["JMW", "WTB", "SOLICITOR"]) and abs(row['Amount']) > 3000: 
            return pd.Series([prop, "Fixed Assets: Property Cost", "Capital", "N/A"])
        
        # 3. Director Loan Account (Drawings)
        if any(x in text for x in ["ADNAN", "AIZA"]) and abs(row['Amount']) > 500:
            return pd.Series([prop, "Director Loan Account (DLA)", "Liability", "N/A"])
        
        # 4. HMRC Allowable Expenses (P&L)
        if any(x in text for x in ["MORTGAGE", "PRECISE", "CHARTER"]): return pd.Series([prop, "Loan Interest", "Expense", "N/A"])
        if any(x in text for x in ["REPAIR", "PLASTER", "KHALID", "HAROUN", "MUHAMMAD", "SELCO"]): return pd.Series([prop, "Repairs & Maintenance", "Expense", "N/A"])
        if any(x in text for x in ["SALARY", "NAHEED"]): return pd.Series([prop, "Wages & Salaries", "Expense", "N/A"])
        if any(x in text for x in ["AXA", "INSURANCE"]): return pd.Series([prop, "Insurance", "Expense", "N/A"])
        
        return pd.Series([prop, "Other Operating Charges", "Expense", "N/A"])

    df[['Property', 'HMRC_Cat', 'Type', 'Income_Type']] = df.apply(categorize_statutory, axis=1)
    return df

# --- UI INTERFACE ---
st.title("🏛️ Elevate Living Ltd. | Statutory Financial Controller")
st.markdown("---")

files = st.sidebar.file_uploader("Upload Statements (CSV/PDF)", accept_multiple_files=True)

if files:
    data = process_data(files)
    
    # --- TOP LEVEL PERFORMANCE ---
    income_df = data[data['Type'] == "Income"]
    expense_df = data[data['Type'] == "Expense"]
    net_profit = income_df['Amount'].sum() + expense_df['Amount'].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Annual Turnover", f"£{income_df['Amount'].sum():,.2f}")
    col2.metric("Allowable Expenses", f"£{abs(expense_df['Amount'].sum()):,.2f}")
    col3.metric("Net Taxable Profit", f"£{net_profit:,.2f}")
    col4.metric("Capital Portfolio", f"£{data[data['Type'] == 'Capital']['Amount'].abs().sum():,.2f}")

    # --- THE INTERACTIVE DASHBOARD ---
    tabs = st.tabs(["📊 Profit & Loss", "💰 Income Deep-Dive", "🔨 Repairs Audit", "🏛️ Balance Sheet"])

    with tabs[0]:
        st.subheader("HMRC Micro-Entity Profit & Loss")
        
        pl_table = data[data['Type'].isin(["Income", "Expense"])].groupby('HMRC_Cat')['Amount'].sum().reset_index()
        st.table(pl_table.style.format({"Amount": "£{:,.2f}"}))
        st.plotly_chart(px.bar(data[data['Amount'] < 0], x='HMRC_Cat', y='Amount', color='Property', title="Expense Distribution"))

    with tabs[1]:
        st.subheader("Detailed Income Analysis")
        col_in1, col_in2 = st.columns([1, 2])
        with col_in1:
            st.plotly_chart(px.pie(income_df, values='Amount', names='Income_Type', hole=0.5))
        with col_in2:
            st.dataframe(income_df[['Date', 'Counter Party', 'Property', 'Income_Type', 'Amount']].sort_values('Amount', ascending=False))

    with tabs[2]:
        st.subheader("Property Maintenance Audit")
        repairs = data[data['HMRC_Cat'] == "Repairs & Maintenance"]
        st.write("These items are fully deductible for Corporation Tax purposes:")
        st.dataframe(repairs[['Date', 'Counter Party', 'Property', 'Amount']])

    with tabs[3]:
        st.subheader("Micro-Entity Balance Sheet (FRS 105)")
        
        assets = data[data['Type'] == "Capital"]['Amount'].abs().sum()
        dla = data[data['HMRC_Cat'] == "Director Loan Account (DLA)"]['Amount'].sum()
        
        st.info(f"**Fixed Assets (Land & Buildings):** £{assets:,.2f}")
        st.warning(f"**Director Loan Account (Net Position):** £{dla:,.2f}")
        st.success(f"**Net Assets / Shareholders Equity:** £{assets + net_profit + dla:,.2f}")

else:
    st.info("Upload your statements to launch the Statutory Financial Dashboard.")
