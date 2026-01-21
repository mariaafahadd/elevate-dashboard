import streamlit as st
import pandas as pd
import plotly.express as px
import re
import pypdf

st.set_page_config(page_title="Elevate Living | Multi-Property Dash", layout="wide")

# --- DATA EXTRACTION ENGINES ---
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
                "Reference": desc, # NatWest often puts details in the description
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
    
    full_df = pd.concat(dfs, ignore_index=True)
    
    # PROPERTY TAGGING LOGIC
    def tag_property(row):
        text = str(row['Counter Party']) + " " + str(row.get('Reference', '')) + " " + str(row.get('Notes', ''))
        if 'HONOR' in text.upper(): return '18 Honor Street'
        if 'BARNBY' in text.upper() or '74 B' in text.upper(): return '74 Barnby Street'
        return 'General / Unallocated'
    
    full_df['Property'] = full_df.apply(tag_property, axis=1)
    return full_df

# --- APP UI ---
st.title("🏠 Elevate Living Ltd. Property Portfolio")
files = st.sidebar.file_uploader("Upload Statements", accept_multiple_files=True)

if files:
    df = process_data(files)
    
    # Sidebar Filters
    selected_property = st.sidebar.selectbox("Select Property View", ["All Properties", "18 Honor Street", "74 Barnby Street"])
    
    view_df = df if selected_property == "All Properties" else df[df['Property'] == selected_property]

    # ACCOUNTING CALCULATIONS
    is_asset = view_df['Counter Party'].str.contains('JMW|WTB|SOLICITOR', case=False, na=False)
    assets_val = view_df[is_asset]['Amount'].abs().sum()
    p_and_l = view_df[~is_asset]
    
    revenue = p_and_l[p_and_l['Amount'] > 0]['Amount'].sum()
    expenses = p_and_l[p_and_l['Amount'] < 0]['Amount'].sum()

    # DASHBOARD
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Revenue ({selected_property})", f"£{revenue:,.2f}")
    c2.metric("Operating Profit", f"£{revenue + expenses:,.2f}")
    c3.metric("Asset Investment", f"£{assets_val:,.2f}")

    # VISUALS
    st.subheader("Profit & Loss Analysis")
    fig = px.bar(p_and_l, x='Date', y='Amount', color='Property', barmode='group')
    st.plotly_chart(fig, use_container_width=True)

    tab_pl, tab_bs, tab_tx = st.tabs(["P&L Table", "Balance Sheet", "Transactions"])
    with tab_pl:
        st.dataframe(p_and_l.sort_values('Date', ascending=False))
    with tab_bs:
        st.write(f"**Property Value (at cost):** £{assets_val:,.2f}")
        st.write(f"**Retained Earnings:** £{revenue + expenses:,.2f}")
    with tab_tx:
        st.write(view_df)
else:
    st.info("Upload your statements to see the property breakdown.")
