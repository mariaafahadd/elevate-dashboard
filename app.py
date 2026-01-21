import streamlit as st
import pandas as pd
import plotly.express as px

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Elevate Living | Finance App", layout="wide")

st.title("🏠 Elevate Living Ltd. Dashboard")
st.markdown("### Rental Property Portfolio: Profit & Loss and Balance Sheet")

# --- SIDEBAR: FILE UPLOAD ---
st.sidebar.header("Data Management")
uploaded_files = st.sidebar.file_uploader("Upload Starling/NatWest CSVs", accept_multiple_files=True)

# --- ACCOUNTING LOGIC FUNCTIONS ---
def process_data(files):
    all_data = []
    for file in files:
        df = pd.read_csv(file)
        # Standardizing columns based on Starling/NatWest format
        if 'Amount (GBP)' in df.columns:
            df = df.rename(columns={'Amount (GBP)': 'Amount', 'Spending Category': 'Category'})
        all_data.append(df)
    
    if not all_data:
        return pd.DataFrame()
        
    full_df = pd.concat(all_data)
    full_df['Date'] = pd.to_datetime(full_df['Date'], dayfirst=True)
    return full_df

# --- LOAD DATA ---
df = process_data(uploaded_files)

if not df.empty:
    # 1. CAPITALIZATION LOGIC
    # Automatically moving large legal fees to the Balance Sheet
    solicitor_keywords = ['JMW', 'WTB', 'SOLICITORS']
    is_solicitor = df['Counter Party'].str.contains('|'.join(solicitor_keywords), case=False, na=False)
    
    # Define Assets (Capitalized) vs Operating Expenses
    assets_df = df[is_solicitor & (df['Amount'].abs() > 5000)]
    p_and_l_df = df[~(is_solicitor & (df['Amount'].abs() > 5000))]

    # 2. CALCULATE METRICS
    total_income = p_and_l_df[p_and_l_df['Amount'] > 0]['Amount'].sum()
    operating_exp = p_and_l_df[p_and_l_df['Amount'] < 0]['Amount'].sum()
    net_profit = total_income + operating_exp
    total_assets = assets_df['Amount'].abs().sum()

    # --- DASHBOARD LAYOUT ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Revenue", f"£{total_income:,.2f}")
    m2.metric("Net Operating Profit", f"£{net_profit:,.2f}")
    m3.metric("Capitalized Assets", f"£{total_assets:,.2f}")

    # --- TABBED INTERFACE ---
    tab1, tab2, tab3 = st.tabs(["📊 Profit & Loss", "🏛️ Balance Sheet", "🧾 Transaction Logs"])

    with tab1:
        st.subheader("Profit & Loss Account")
        pl_summary = p_and_l_df.groupby('Category')['Amount'].sum().reset_index()
        
        col_left, col_right = st.columns(2)
        with col_left:
            st.table(pl_summary.style.format({'Amount': '£{:.2f}'}))
        with col_right:
            fig_pl = px.pie(pl_summary[pl_summary['Amount'] < 0], values='Amount', names='Category', title="Expense Distribution")
            st.plotly_chart(fig_pl)

    with tab2:
        st.subheader("Balance Sheet")
        st.markdown(f"""
        | Item | Value |
        | :--- | :--- |
        | **Fixed Assets (Properties)** | **£{total_assets:,.2f}** |
        | *Current Cash at Bank* | *£{df['Balance (GBP)'].iloc[-1] if 'Balance (GBP)' in df.columns else 0:,.2f}* |
        | **Total Assets** | **£{total_assets + (df['Balance (GBP)'].iloc[-1] if 'Balance (GBP)' in df.columns else 0):,.2f}** |
        | --- | --- |
        | **Equity (Retained Earnings)** | **£{net_profit:,.2f}** |
        """)

    with tab3:
        st.subheader("Full Transaction History")
        st.dataframe(df.sort_values(by='Date', ascending=False))

else:
    st.info("Please upload your CSV statements in the sidebar to view the accounts.")
