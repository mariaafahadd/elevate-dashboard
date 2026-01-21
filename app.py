import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | Property Intelligence", layout="wide")

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
            if 'Amount (GBP)' in tmp.columns:
                tmp = tmp.rename(columns={'Amount (GBP)': 'Amount', 'Spending Category': 'Category'})
            dfs.append(tmp)
        elif file.name.endswith('.pdf'):
            dfs.append(extract_natwest_pdf(file))
    
    if not dfs: return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)

    def categorize_rental(row):
        text = (str(row['Counter Party']) + " " + str(row.get('Reference', '')) + " " + str(row.get('Notes', ''))).upper()
        prop = "18 Honor Street" if "HONOR" in text else "74 Barnby Street" if "BARNBY" in text else "General Portfolio"
        
        # 1. INCOME TYPES (Detailed)
        if row['Amount'] > 0:
            income_type = "Standard Rent"
            if "TODD" in text or "SETTLEMENT" in text: income_type = "Legal Settlement"
            if "DEPOSIT" in text: income_type = "Tenant Deposit"
            if "MUSTAFA" in text: income_type = "Company Let"
            return pd.Series([prop, "Rental Income", "Income", income_type])
        
        # 2. CAPITAL ASSETS
        if any(x in text for x in ["JMW", "WTB", "SOLICITOR"]) and abs(row['Amount']) > 3000: 
            return pd.Series([prop, "Property Acquisition & Legal", "Fixed Asset", "N/A"])
        
        # 3. REPAIRS (Catching names like Muhammad, Khalid, Haroun)
        repair_keywords = ["REPAIR", "MAINTENANCE", "SELCO", "PLASTER", "KHALID", "HAROUN", "MUHAMMAD", "PLUMBING", "BOILER"]
        if any(x in text for x in repair_keywords): 
            return pd.Series([prop, "Property Repairs & Maintenance", "Expense", "N/A"])
        
        # 4. OTHER CATEGORIES
        if any(x in text for x in ["MORTGAGE", "PRECISE", "CHARTER"]): 
            return pd.Series([prop, "Loan Interest & Financing", "Expense", "N/A"])
        if any(x in text for x in ["SALARY", "NAHEED"]): 
            return pd.Series([prop, "Wages & Payroll Staff", "Expense", "N/A"])
        
        return pd.Series([prop, "Sundry Rental Expenses", "Expense", "N/A"])

    df[['Property', 'HMRC_Category', 'Account_Type', 'Income_Type']] = df.apply(categorize_rental, axis=1)
    return df

# --- UI INTERFACE ---
st.title("🏠 Elevate Living Ltd. | Property Dashboard")
uploaded_files = st.sidebar.file_uploader("Upload Statements", accept_multiple_files=True)

if uploaded_files:
    data = process_data(uploaded_files)
    
    # Financial Stats
    income_df = data[data['Account_Type'] == "Income"]
    
    # --- METRICS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Gross Rents", f"£{income_df['Amount'].sum():,.2f}")
    m2.metric("Net Profit", f"£{data[data['Account_Type'] != 'Fixed Asset']['Amount'].sum():,.2f}")
    m3.metric("Property Assets", f"£{data[data['Account_Type'] == 'Fixed Asset']['Amount'].abs().sum():,.2f}")

    # --- THE INTERACTIVE TABS ---
    tab_summary, tab_income, tab_repairs = st.tabs(["📋 P&L Summary", "💰 Income Deep-Dive", "🔨 Repairs Audit"])

    with tab_summary:
        st.subheader("HMRC Statutory Breakdown")
        pl_summary = data[data['Account_Type'] != "Fixed Asset"].groupby('HMRC_Category')['Amount'].sum().reset_index()
        st.table(pl_summary.style.format({"Amount": "£{:,.2f}"}))

    with tab_income:
        st.subheader("Income Details: What's inside the numbers?")
        col_in1, col_in2 = st.columns([1, 2])
        with col_in1:
            # Breakdown Pie Chart
            fig_pie = px.pie(income_df, values='Amount', names='Income_Type', hole=0.4, title="Income Sources")
            st.plotly_chart(fig_pie)
        with col_in2:
            # Detailed View Table
            st.write("**Detailed Income Log:**")
            st.dataframe(income_df[['Date', 'Counter Party', 'Property', 'Income_Type', 'Amount']], use_container_width=True)

    with tab_repairs:
        st.subheader("Repairs & Maintenance Audit")
        repair_data = data[data['HMRC_Category'] == "Property Repairs & Maintenance"]
        st.write("The following items were identified as repairs (not sundry):")
        st.dataframe(repair_data[['Date', 'Counter Party', 'Property', 'Amount']], use_container_width=True)

else:
    st.info("Upload your bank statements (CSV or PDF) to activate the interactive dashboard.")
