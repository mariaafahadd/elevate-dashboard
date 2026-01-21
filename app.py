import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Elevate Living Dashboard", layout="wide")

st.title("🏠 Elevate Living Ltd. | Financial App")
st.sidebar.header("Upload New Statements")
uploaded_file = st.sidebar.file_uploader("Upload Starling or NatWest CSV", type="csv")

# 1. Dashboard Metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Portfolio Value", "£81,372", "+£37,184 YoY")
with col2:
    st.metric("Annual Rental Income", "£52,809", "210% Growth")
with col3:
    st.metric("Operating Margin", "-1.9%", "Warning: High Repairs")

# 2. Income vs Expense Chart
st.subheader("Monthly Performance Trend")
# Data sourced from processed statements 
chart_data = pd.DataFrame({
    'Month': ['Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
    'Income': [1450, 850, 850, 850, 1450, 15880, 1500, 1500, 1500, 1500, 1500, 1500],
    'Expenses': [982, 1120, 1340, 38184, 1200, 1400, 2100, 3200, 1500, 1200, 1400, 1600]
})
fig = px.bar(chart_data, x='Month', y=['Income', 'Expenses'], barmode='group')
st.plotly_chart(fig, use_container_width=True)

# 3. Expense Breakdown
st.subheader("Where is the money going?")
# Category analysis based on NatWest and Starling data [cite: 1, 13]
exp_pie = px.pie(values=[12690, 9216, 11009, 15082], 
                 names=['Mortgage Interest', 'Repairs/Maintenance', 'Salaries', 'Professional Fees'])
st.plotly_chart(exp_pie)
