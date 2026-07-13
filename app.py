"""
app.py
--------------------------------
Yeh main entry file hai. Isi ko run karenge:
    streamlit run app.py

Streamlit automatically 'pages/' folder ki files ko sidebar me
alag pages ki tarah dikha dega. User jis page pe click karega,
usi page ka code chalega aur uska data load hoga.
"""

import streamlit as st
from utils.styling import inject_custom_css

st.set_page_config(
    page_title="Business Dashboard",
    page_icon="📊",
    layout="wide",
)

inject_custom_css()

st.title("📊 Business Dashboard")

st.markdown(
    """
    Welcome! Left sidebar se koi bhi dashboard select karein:

    - **Health Sales Dashboard**
    - **Client Analytics**
    - **Calling Dashboard**
    - **Leads Utilisation**

    Har page apna data Google Sheet se khud-ba-khud load karega.
    """
)

st.info("👈 Sidebar se ek dashboard chuniye shuru karne ke liye.")
