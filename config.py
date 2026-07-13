"""
config.py
--------------------------------
Yahan aap apne Google Sheet ka URL aur har dashboard ke worksheet (tab)
ka naam ek hi jagah set kar dein. Pages isi ko import karke use karenge.

NOTE: Agar sabhi 4 dashboards EK HI Google Sheet ke alag-alag tabs (sheets)
me hain, to neeche sirf SHEET_URL change karna hoga aur har dashboard
ke liye tab ka sahi naam dena hoga.

Agar har dashboard ki sheet ALAG-ALAG Google Sheet file me hai,
to har ek ke liye alag URL bhi de sakte hain.
"""

# Apna Google Sheet ka sharing URL yahan paste karein
SHEET_URL = "https://docs.google.com/spreadsheets/d/1B_0fz04NJj6scqoPqHGHyvy4Gp_6OXVVYruCZ8rF4Q8/edit?gid=1775537042#gid=1775537042"

# Har dashboard page ka worksheet (tab) name
WORKSHEETS = {
    "health_sales": "Payments Raw",      # Sheet ke tab ka exact naam
    "client_analytics": "Booking Data",
    "calling": "Calling Dashboard",
    "leads_utilisation": "Leads Utilisation",
}

# Health Sales Dashboard ke actual column names (reference ke liye)
# Date, RM Name, YTD Premium, Policy Type, Insurer, Leader, Fresh/Port,
# Policy Tenure, P&L, Payment Mode, Policy Status, YTD Target, Month

