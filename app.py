import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf
from datetime import datetime

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | Statutory Dashboard", layout="wide")

# --- ACCOUNTING ENGINES ---
def extract_natwest_pdf(file):
    reader = pypdf.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    
    # Detect Statement Start Year (e.g., "From 01/07/2022")
    year_match = re.search(r'From\s+\d{2}/\d{2}/(\d{4})', text)
    base_year = int(year_match.group(1)) if year_match else 2022
    
    months_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 
                  'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
    
    txns = []
    # Regex: Matches Date, Description, and Amount (handling commas/signs)
    matches = re.findall(r'(\d{1,2})\s(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(.*?)\s+(-?£[\d,]+\.\d{2})', text)
    
    for m in matches:
        day, month_str, desc, amt_str = m
        month_num = months_map[month_str]
        # Logic: If month is Jul-Dec, it's the base year. If Jan-Jun, it's the next year.
        year = base_year if month_num >= 7 else base_year + 1
        
        try:
            clean_date = datetime(year, month_num, int(day))
            txns.append({
                "Date": clean_date,
                "Counter Party": desc.strip(),
                "Amount": float(amt_str.replace('£', '').replace(',', '')),
                "Source": "NatWest PDF"
            })
        except:
            continue
            
    return pd.DataFrame(txns)

def process_data(uploaded_files):
    dfs = []
    for file in uploaded_files:
        if file.name.endswith('.csv'):
            tmp = pd.read_csv(file)
            tmp['Date'] = pd.to_datetime(tmp['Date'], dayfirst=True)
            if 'Amount (GBP)' in tmp.columns:
                tmp = tmp.rename(columns={'Amount (GBP)': 'Amount', 'Spending Category': 'Category'})
            tmp['Source'] = "Starling CSV"
            dfs.append(tmp)
        elif file.name.endswith('.pdf'):
            dfs.append(extract_natwest_pdf(file))
    
    if not dfs: return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)

    def categorize_hmrc(row):
        text = (str(row['Counter Party']) + " " + str(row.get('Reference', ''))).upper()
        prop = "18 Honor Street" if "HONOR" in text else "74 Barnby Street" if "BARNBY" in text else "General Portfolio"
        
        # 1. Income Details
        if row['Amount'] > 0:
            income_type = "Standard Rent"
            if "TODD" in text: income_type = "Legal Settlement"
            if "MUSTAFA" in text: income_type = "Company Let"
            return pd.Series([prop, "Rent and other income", "Income", income_type])
        
        # 2. Capital Assets (Solicitors over £3k)
        if any(x in text for x in ["JMW", "WTB", "SOLICITOR"]) and abs(row['Amount']) > 3000: 
            return pd.Series([prop, "Property Acquisition & Legal (Capital)", "Fixed Asset", "N/A"])
        
        # 3. Proper HMRC Repairs & Maintenance
        repair_keywords = ["REPAIR", "MAINTENANCE", "SELCO", "PLASTER", "KHALID", "HAROUN", "MUHAMMAD", "PLUMBING", "BOILER", "PAINTING"]
        if any(x in text for x in repair_keywords): 
            return pd.Series([prop, "Property repairs and maintenance", "Expense", "N/A"])
        
        # 4. Other HMRC Categories
        if any(x in text for x in ["MORTGAGE", "PRECISE", "CHARTER"]): return pd.Series([prop, "Loan interest and financial costs", "Expense", "N/A"])
        if any(x in text for x in ["SALARY", "NAHEED", "DIRECTOR"]): return pd.Series([prop, "Wages and staff costs", "Expense", "N/A"])
        if any(x in text for x in ["AXA", "INSURANCE"]): return pd.Series([prop, "Insurance", "Expense", "N/A"])
        if any(x in text for x in ["GPS", "PROPERTY INFO", "IONOS", "COMPANIES HOUSE"]): return pd.Series([prop, "Legal, management and professional fees", "Expense", "N/A"])
        
        return pd.Series([prop, "Other allowable property expenses", "Expense", "N/A"])

    df[['Property', 'HMRC_Category', 'Account_Type', 'Income_Detail']] = df.apply(categorize_hmrc, axis=1)
    return df

# --- UI INTERFACE ---
st.title("🏠 Elevate Living Ltd. | Property Finance App")
files = st.sidebar.file_uploader("Upload Starling/NatWest Statements", accept_multiple_files=True)

if files:
    data = process_data(files)
    
    # Financial Totals
    income_df = data[data['Account_Type'] == "Income"]
    exp_df = data[data['Account_Type'] == "Expense"]
    capex = data[data['Account_Type'] == "Fixed Asset"]['Amount'].abs().sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gross Revenue", f"£{income_df['Amount'].sum():,.2f}")
    m2.metric("Operating Costs", f"£{abs(exp_df['Amount'].sum()):,.2f}")
    m3.metric("Net Profit/Loss", f"£{income_df['Amount'].sum() + exp_df['Amount'].sum():,.2f}")
    m4.metric("Capital Assets", f"£{capex:,.2f}")

    tab_pl, tab_income, tab_repairs, tab_bs = st.tabs(["📋 HMRC P&L", "💰 Income Deep-Dive", "🔨 Repairs Audit", "🏛️ Balance Sheet"])

    with tab_pl:
        st.subheader("Profit and Loss (Statutory Categories)")
        pl_data = data[data['Account_Type'] != "Fixed Asset"].groupby('HMRC_Category')['Amount'].sum().reset_index()
        st.table(pl_data.style.format({"Amount": "£{:,.2f}"}))
        st.plotly_chart(px.line(data.groupby(data['Date'].dt.strftime('%Y-%m'))['Amount'].sum().reset_index(), x='Date', y='Amount', title="Monthly Cash Flow"))

    with tab_income:
        st.subheader("Rental Income Detail")
        col_i1, col_i2 = st.columns([1, 2])
        with col_i1:
            st.plotly_chart(px.pie(income_df, values='Amount', names='Income_Detail', hole=0.4))
        with col_i2:
            st.dataframe(income_df[['Date', 'Counter Party', 'Property', 'Income_Detail', 'Amount']].sort_values('Date', ascending=False), use_container_width=True)

    with tab_repairs:
        st.subheader("Repairs & Maintenance Deep-Dive")
        rep_data = data[data['HMRC_Category'] == "Property repairs and maintenance"]
        st.write("These costs are fully tax-deductible in the current year:")
        st.dataframe(rep_data[['Date', 'Counter Party', 'Property', 'Amount']], use_container_width=True)

    with tab_bs:
        st.subheader("Statement of Financial Position")
        st.info(f"**Fixed Assets (Land & Buildings):** £{capex:,.2f}")
        st.success(f"**Current Cash Position:** £{data['Amount'].sum():,.2f}")
        st.write("---")
        st.write(f"**Retained Earnings:** £{income_df['Amount'].sum() + exp_df['Amount'].sum():,.2f}")

else:
    st.info("Upload your statements to see your detailed rental dashboard.")
