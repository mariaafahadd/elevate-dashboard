import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | Professional Dash", layout="wide")

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
        
        # 2. CAPITAL ASSETS (Large Solicitor/Acquisition costs)
        if any(x in text for x in ["JMW", "WTB", "SOLICITOR"]) and abs(row['Amount']) > 3000: 
            return pd.Series([prop, "Property Acquisition & Legal", "Fixed Asset"])
        
        # 3. HMRC REPAIRS (EXPANDED KEYWORDS)
        # This fixes the "Sundry" issue by catching names and specific trade terms
        repair_keywords = ["REPAIR", "MAINTENANCE", "SELCO", "PLASTER", "KHALID", "HAROUN", "MUHAMMAD", "PLUMBING", "GAS", "BOILER", "PAINTING", "DECORATING"]
        if any(x in text for x in repair_keywords): 
            return pd.Series([prop, "Property Repairs & Maintenance", "Expense"])
        
        # 4. OTHER HMRC CATEGORIES
        if any(x in text for x in ["MORTGAGE", "PRECISE", "CHARTER"]): 
            return pd.Series([prop, "Loan Interest & Financing", "Expense"])
        if any(x in text for x in ["AXA", "INSURANCE"]): 
            return pd.Series([prop, "Property Insurance", "Expense"])
        if any(x in text for x in ["SALARY", "NAHEED", "DIRECTOR"]): 
            return pd.Series([prop, "Wages & Payroll Staff", "Expense"])
        if any(x in text for x in ["IONOS", "1 AND 1", "COMPANIES HOUSE", "GPS", "PROPERTY INFO"]): 
            return pd.Series([prop, "Admin & Professional Fees", "Expense"])
        
        return pd.Series([prop, "Sundry Rental Expenses", "Expense"])

    df[['Property', 'HMRC_Category', 'Account_Type']] = df.apply(categorize_rental, axis=1)
    return df

# --- UI INTERFACE ---
st.title("🏠 Elevate Living Ltd. | Rental Business App")
uploaded_files = st.sidebar.file_uploader("Upload Statements (CSV/PDF)", accept_multiple_files=True)

if uploaded_files:
    data = process_data(uploaded_files)
    
    # Financial Stats
    income = data[data['Account_Type'] == "Income"]['Amount'].sum()
    opex = data[data['Account_Type'] == "Expense"]['Amount'].sum()
    capex = data[data['Account_Type'] == "Fixed Asset"]['Amount'].abs().sum()

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gross Rents", f"£{income:,.2f}")
    c2.metric("Operating Costs", f"£{abs(opex):,.2f}")
    c3.metric("Net Profit", f"£{income + opex:,.2f}")
    c4.metric("Capital Assets", f"£{capex:,.2f}")

    # Detailed Table
    st.subheader("HMRC Property Income Breakdown")
    detailed_pl = data[data['Account_Type'] != "Fixed Asset"].groupby('HMRC_Category')['Amount'].sum().reset_index()
    st.table(detailed_pl.style.format({"Amount": "£{:,.2f}"}))

    # Property Charts
    st.subheader("Performance by Address")
    prop_chart = px.bar(data[data['Account_Type'] == "Income"], x='Property', y='Amount', color='Property')
    st.plotly_chart(prop_chart, use_container_width=True)

else:
    st.info("Upload your bank statements to update the dashboard.")
