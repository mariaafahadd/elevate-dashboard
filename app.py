import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf
from datetime import datetime

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | Interactive Dashboard", layout="wide")

# --- ACCOUNTING ENGINES ---
def extract_natwest_pdf(file):
    reader = pypdf.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
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

    def categorize_logic(row):
        text = (str(row['Counter Party']) + " " + str(row.get('Reference', ''))).upper()
        prop = "18 Honor Street" if "HONOR" in text else "74 Barnby Street" if "BARNBY" in text else "General Portfolio"
        if row['Amount'] > 0:
            itype = "Standard Rent"
            if "TODD" in text: itype = "Legal Settlement"
            if "MUSTAFA" in text: itype = "Company Let"
            return pd.Series([prop, "Income", "Rental Income", itype])
        if any(x in text for x in ["JMW", "WTB", "SOLICITOR"]) and abs(row['Amount']) > 3000:
            return pd.Series([prop, "Fixed Asset", "Property Asset", "N/A"])
        repair_keys = ["REPAIR", "MAINTENANCE", "SELCO", "PLASTER", "KHALID", "HAROUN", "MUHAMMAD"]
        if any(x in text for x in repair_keys):
            return pd.Series([prop, "Expense", "Repairs & Maintenance", "N/A"])
        if any(x in text for x in ["MORTGAGE", "PRECISE", "CHARTER"]):
            return pd.Series([prop, "Expense", "Mortgage Interest", "N/A"])
        return pd.Series([prop, "Expense", "Other Operating Costs", "N/A"])

    df[['Property', 'Type', 'HMRC_Cat', 'Income_Type']] = df.apply(categorize_logic, axis=1)
    return df

# --- UI INTERFACE ---
st.title("🏠 Elevate Living Ltd. | Clickable Property Intelligence")
uploaded_files = st.sidebar.file_uploader("Upload Statements", accept_multiple_files=True)

if uploaded_files:
    data = process_data(uploaded_files)
    income_df = data[data['Type'] == "Income"]
    
    # Clickable Navigation Tabs
    tab1, tab2, tab3 = st.tabs(["📋 P&L Summary", "💰 Income Deep-Dive", "🔨 Repairs Audit"])

    with tab1:
        st.subheader("Profit & Loss Summary")
        pl_data = data[data['Type'] != "Fixed Asset"].groupby('HMRC_Cat')['Amount'].sum().reset_index()
        st.table(pl_data.style.format({"Amount": "£{:,.2f}"}))
        st.plotly_chart(px.bar(pl_data, x='HMRC_Cat', y='Amount', color='HMRC_Cat'))

    with tab2:
        st.subheader("Income Deep-Dive: Click to Inspect")
        st.write("Below is a breakdown of every payment received. Click any header to sort.")
        col_pie, col_table = st.columns([1, 2])
        with col_pie:
            st.plotly_chart(px.pie(income_df, values='Amount', names='Income_Type', hole=0.4))
        with col_table:
            st.dataframe(income_df[['Date', 'Counter Party', 'Income_Type', 'Amount']].sort_values('Amount', ascending=False), use_container_width=True)

    with tab3:
        st.subheader("Repairs Audit Trail")
        repairs = data[data['HMRC_Cat'] == "Repairs & Maintenance"]
        st.write("The following transactions were moved from 'Sundry' to 'Repairs' for tax optimization:")
        st.dataframe(repairs[['Date', 'Counter Party', 'Amount', 'Property']], use_container_width=True)

else:
    st.info("Please upload your CSV or PDF statements to activate the clickable dashboard.")
