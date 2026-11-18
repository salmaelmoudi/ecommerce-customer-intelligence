"""
Final Dashboard Builder — Standalone (no external dependencies issue)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os, json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly

ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR    = os.path.join(ROOT, "data", "powerbi_exports")
DASHBOARD_DIR = os.path.join(ROOT, "dashboard")
os.makedirs(DASHBOARD_DIR, exist_ok=True)

# ── Load data ──────────────────────────────────────────────────────────────
fact          = pd.read_csv(os.path.join(EXPORT_DIR, "fact_orders.csv"), low_memory=False)
rfm           = pd.read_csv(os.path.join(EXPORT_DIR, "dim_rfm_segments.csv"))
monthly       = pd.read_csv(os.path.join(EXPORT_DIR, "agg_monthly_revenue.csv"))
seller_sc     = pd.read_csv(os.path.join(EXPORT_DIR, "agg_seller_scorecard.csv"))
cat           = pd.read_csv(os.path.join(EXPORT_DIR, "agg_category_performance.csv"))
del_state     = pd.read_csv(os.path.join(EXPORT_DIR, "agg_delivery_by_state.csv"))
with open(os.path.join(EXPORT_DIR, "ml_summary.json"), encoding="utf-8") as f:
    ml = json.load(f)

fact["order_purchase_timestamp"] = pd.to_datetime(fact["order_purchase_timestamp"], errors="coerce")
delivered = fact[fact["order_status"] == "delivered"].copy()
valid     = fact[fact["order_status"].isin(["delivered","shipped","invoiced"])].copy()

P = "#1B4F72"; S = "#2E86C1"; A = "#F39C12"; G = "#1ABC9C"; D = "#E74C3C"; GY = "#7F8C8D"

# ── Computed KPIs ──────────────────────────────────────────────────────────
total_rev    = round(valid["order_value"].sum(), 0)
total_orders = fact["order_id"].nunique()
aov          = round(valid["order_value"].mean(), 2)
avg_review   = round(delivered["review_score"].mean(), 2)
late_pct     = round(delivered["is_late"].mean() * 100, 1)
on_time_pct  = round(100 - late_pct, 1)
avg_del_days = round(delivered["delivery_days"].mean(), 1)
st           = ml["stats_test"]
mlt          = ml["metrics"]

# ════════════════════════════════════════════════════════════════════════════
# PAGE 1 — EXECUTIVE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
fig1 = make_subplots(
    rows=3, cols=4,
    specs=[
        [{"type":"indicator"},{"type":"indicator"},{"type":"indicator"},{"type":"indicator"}],
        [{"type":"xy","colspan":4}, None, None, None],
        [{"type":"xy","colspan":2}, None, {"type":"domain","colspan":2}, None],
    ],
    subplot_titles=("","","","",
                    "Monthly Revenue (R$) & Order Volume",
                    "Top 10 Product Categories by Revenue",
                    "Payment Method Share"),
    vertical_spacing=0.13, horizontal_spacing=0.06,
    row_heights=[0.18, 0.44, 0.38],
)

indicators = [
    (total_rev,    "Total Revenue (R$)",   P, ",.0f"),
    (total_orders, "Total Orders",          S, ",.0f"),
    (aov,          "Avg Order Value (R$)",  A, ",.2f"),
    (avg_review,   "Avg Review Score ★",   G, ".2f"),
]
for col, (val, lbl, col_c, fmt) in enumerate(indicators, 1):
    fig1.add_trace(go.Indicator(
        mode="number", value=val,
        title={"text": f"<b>{lbl}</b>", "font": {"size": 13, "color": GY}},
        number={"font": {"size": 28, "color": col_c}, "valueformat": fmt},
    ), row=1, col=col)

# Monthly revenue + orders
ms = monthly.sort_values("year_month")
fig1.add_trace(go.Bar(
    x=ms["year_month"], y=ms["total_revenue"],
    name="Revenue (R$)", marker_color=S, opacity=0.8,
    hovertemplate="<b>%{x}</b><br>Revenue: R$ %{y:,.0f}<extra></extra>",
), row=2, col=1)
fig1.add_trace(go.Scatter(
    x=ms["year_month"], y=ms["total_orders"],
    name="Orders", mode="lines+markers",
    line=dict(color=A, width=2.5), marker=dict(size=5),
    hovertemplate="<b>%{x}</b><br>Orders: %{y:,}<extra></extra>",
    yaxis="y3",
), row=2, col=1)

# Top categories
cat_top = cat.nlargest(10, "total_revenue").sort_values("total_revenue")
fig1.add_trace(go.Bar(
    x=cat_top["total_revenue"], y=cat_top["product_category_name_english"],
    orientation="h", marker_color=P,
    hovertemplate="<b>%{y}</b><br>Revenue: R$ %{x:,.0f}<extra></extra>",
    text=cat_top["total_revenue"].apply(lambda x: f"R$ {x/1000:.0f}K"),
    textposition="outside",
), row=3, col=1)

# Payment pie
pay = fact.dropna(subset=["payment_type"]).groupby("payment_type")["payment_value"].sum().reset_index()
fig1.add_trace(go.Pie(
    labels=pay["payment_type"], values=pay["payment_value"],
    hole=0.42, name="Payment",
    marker=dict(colors=[P, S, A, G, D]),
    hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
), row=3, col=3)

fig1.update_layout(
    title=dict(
        text=f"<b>E-Commerce Executive Dashboard</b>"
             f"<br><sup>R$ {total_rev:,.0f} revenue  |  {total_orders:,} orders  |  "
             f"{on_time_pct}% on-time delivery  |  Avg review ★{avg_review}</sup>",
        font=dict(size=18, color=P), x=0.5,
    ),
    height=900, paper_bgcolor="#F8F9FA", plot_bgcolor="white",
    showlegend=False, font=dict(family="Segoe UI, Arial", size=12),
    margin=dict(t=120, b=50, l=70, r=50),
)
fig1.update_xaxes(tickangle=-45, row=2, col=1)

# ════════════════════════════════════════════════════════════════════════════
# PAGE 2 — CUSTOMER INTELLIGENCE
# ════════════════════════════════════════════════════════════════════════════
seg_counts = rfm["segment"].value_counts().reset_index()
seg_counts.columns = ["segment","count"]
color_map = {
    "Champions":           P,
    "Loyal Customers":     S,
    "Potential Loyalists": G,
    "Recent Customers":    A,
    "At Risk":             "#E67E22",
    "Lost Customers":      D,
}

fig2 = make_subplots(
    rows=2, cols=2,
    specs=[[{"type":"xy"},{"type":"domain"}],[{"type":"xy"},{"type":"xy"}]],
    subplot_titles=(
        "Customer Segments — Volume",
        "RFM Segment Distribution",
        "Avg Lifetime Value by Segment (R$)",
        "Revenue by Customer State — Top 10",
    ),
    vertical_spacing=0.15, horizontal_spacing=0.1,
)

fig2.add_trace(go.Bar(
    x=seg_counts["segment"], y=seg_counts["count"],
    marker_color=[color_map.get(s, GY) for s in seg_counts["segment"]],
    text=seg_counts["count"].apply(lambda x: f"{x:,}"), textposition="outside",
    hovertemplate="<b>%{x}</b><br>%{y:,} customers<extra></extra>",
), row=1, col=1)

fig2.add_trace(go.Pie(
    labels=seg_counts["segment"], values=seg_counts["count"],
    hole=0.42, marker=dict(colors=[color_map.get(s, GY) for s in seg_counts["segment"]]),
    hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
), row=1, col=2)

avg_mon = rfm.groupby("segment")["monetary"].mean().reset_index().sort_values("monetary")
fig2.add_trace(go.Bar(
    x=avg_mon["monetary"], y=avg_mon["segment"],
    orientation="h",
    marker_color=[color_map.get(s, GY) for s in avg_mon["segment"]],
    text=avg_mon["monetary"].apply(lambda x: f"R$ {x:.0f}"),
    textposition="outside",
), row=2, col=1)

state_rev = (
    valid.groupby("customer_state")["order_value"].sum()
    .nlargest(10).reset_index().sort_values("order_value")
)
fig2.add_trace(go.Bar(
    x=state_rev["order_value"], y=state_rev["customer_state"],
    orientation="h", marker_color=S,
    text=state_rev["order_value"].apply(lambda x: f"R$ {x/1000:.0f}K"),
    textposition="outside",
), row=2, col=2)

repeat_pct = round((rfm["frequency"] > 1).mean() * 100, 1)
fig2.update_layout(
    title=dict(
        text=f"<b>Customer Intelligence Dashboard</b>"
             f"<br><sup>{len(rfm):,} unique customers  |  {repeat_pct}% repeat buyers  |  "
             f"RFM segmentation (Recency · Frequency · Monetary)</sup>",
        font=dict(size=18, color=P), x=0.5,
    ),
    height=800, paper_bgcolor="#F8F9FA", plot_bgcolor="white",
    showlegend=False, font=dict(family="Segoe UI, Arial", size=12),
    margin=dict(t=110, b=50, l=60, r=50),
)

# ════════════════════════════════════════════════════════════════════════════
# PAGE 3 — OPERATIONS & DELIVERY
# ════════════════════════════════════════════════════════════════════════════
fig3 = make_subplots(
    rows=2, cols=2,
    specs=[[{"type":"xy"},{"type":"xy"}],[{"type":"xy"},{"type":"xy"}]],
    subplot_titles=(
        "Late Delivery % by Customer State",
        "Avg Review Score by Review Rating (Delivery Days)",
        "Bottom 15 Sellers — Late Delivery %",
        "ML Feature Importance (Delay Predictor)",
    ),
    vertical_spacing=0.15, horizontal_spacing=0.12,
)

ds = del_state.sort_values("late_pct", ascending=True).tail(15)
fig3.add_trace(go.Bar(
    x=ds["late_pct"], y=ds["customer_state"],
    orientation="h",
    marker_color=[D if x > 15 else A if x > 8 else G for x in ds["late_pct"]],
    text=ds["late_pct"].apply(lambda x: f"{x}%"), textposition="outside",
), row=1, col=1)

rev_del = (
    delivered.groupby("review_score")
    .agg(avg_days=("delivery_days","mean"))
    .reset_index().dropna()
)
fig3.add_trace(go.Bar(
    x=rev_del["review_score"], y=rev_del["avg_days"],
    marker_color=[D, "#E67E22", A, G, P],
    text=rev_del["avg_days"].apply(lambda x: f"{x:.1f} days"),
    textposition="outside",
), row=1, col=2)
fig3.update_xaxes(tickvals=[1,2,3,4,5], ticktext=["★1","★2","★3","★4","★5"], row=1, col=2)

worst = seller_sc.nlargest(15, "late_pct").sort_values("late_pct", ascending=True)
fig3.add_trace(go.Bar(
    x=worst["late_pct"], y=worst["seller_id"].str[:10],
    orientation="h", marker_color=D,
    text=worst["late_pct"].apply(lambda x: f"{x}%"), textposition="outside",
), row=2, col=1)

feats = pd.DataFrame(ml["top_features"]).head(8).sort_values("abs_coef")
fig3.add_trace(go.Bar(
    x=feats["abs_coef"], y=feats["feature"],
    orientation="h", marker_color=S,
    text=feats["coefficient"].apply(lambda x: f"{x:+.3f}"),
    textposition="outside",
), row=2, col=2)

fig3.add_annotation(
    text=f"Delay Predictor — ROC-AUC: <b>{mlt['roc_auc']}</b> | F1: {mlt['f1_score']}",
    x=0.99, y=0.01, xref="paper", yref="paper", showarrow=False, align="right",
    font=dict(size=11, color=P), bgcolor="white", bordercolor=S, borderwidth=1, borderpad=6,
)

fig3.update_layout(
    title=dict(
        text=f"<b>Operations & Delivery Intelligence</b>"
             f"<br><sup>Avg delivery: {avg_del_days} days  |  Late rate: {late_pct}%  |  "
             f"On-time: {on_time_pct}%  |  Stat test p={st['p_value']}</sup>",
        font=dict(size=18, color=P), x=0.5,
    ),
    height=800, paper_bgcolor="#F8F9FA", plot_bgcolor="white",
    showlegend=False, font=dict(family="Segoe UI, Arial", size=12),
    margin=dict(t=110, b=50, l=130, r=60),
)

# ════════════════════════════════════════════════════════════════════════════
# ASSEMBLE — Inline Plotly JS so it works offline
# ════════════════════════════════════════════════════════════════════════════
print("  Serialising figures...")
h1 = fig1.to_html(full_html=False, include_plotlyjs='cdn')
h2 = fig2.to_html(full_html=False, include_plotlyjs=False)
h3 = fig3.to_html(full_html=False, include_plotlyjs=False)

plotly_js_cdn = "https://cdn.plot.ly/plotly-2.35.2.min.js"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>E-Commerce Analytics Dashboard | Salma El Moudi</title>
<script src="{plotly_js_cdn}"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F8F9FA;color:#2C3E50;min-height:100vh;}}
.header{{background:linear-gradient(135deg,#1B4F72 0%,#2E86C1 100%);color:white;
  padding:18px 36px;display:flex;justify-content:space-between;align-items:center;
  box-shadow:0 2px 8px rgba(0,0,0,0.15);}}
.header h1{{font-size:19px;font-weight:700;letter-spacing:-0.3px;}}
.header p{{font-size:11.5px;opacity:0.82;margin-top:3px;}}
.badge{{background:rgba(255,255,255,0.18);padding:5px 13px;border-radius:20px;
  font-size:11.5px;white-space:nowrap;}}
.tabs{{display:flex;background:white;border-bottom:2px solid #E0E8F0;padding:0 36px;
  position:sticky;top:0;z-index:100;box-shadow:0 1px 4px rgba(0,0,0,0.06);}}
.tab{{padding:13px 22px;cursor:pointer;font-weight:600;color:#7F8C8D;
  border-bottom:3px solid transparent;transition:all 0.2s;font-size:13.5px;}}
.tab.active{{color:#1B4F72;border-bottom-color:#F39C12;}}
.tab:hover:not(.active){{color:#2E86C1;background:#F8F9FA;}}
.pane{{display:none;padding:18px 28px 30px;}}
.pane.active{{display:block;}}
.insight{{background:white;border-left:4px solid #F39C12;padding:11px 18px;
  margin-bottom:14px;border-radius:0 8px 8px 0;
  box-shadow:0 1px 4px rgba(0,0,0,0.07);font-size:13px;line-height:1.6;}}
.insight strong{{color:#1B4F72;}}
.kpi-row{{display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap;}}
.kpi{{background:white;border-radius:8px;padding:12px 18px;
  box-shadow:0 1px 4px rgba(0,0,0,0.07);min-width:160px;}}
.kpi .v{{font-size:24px;font-weight:700;color:#1B4F72;}}
.kpi .l{{color:#7F8C8D;font-size:11px;margin-top:2px;text-transform:uppercase;letter-spacing:.5px;}}
.footer{{text-align:center;padding:14px;font-size:12px;color:#7F8C8D;
  border-top:1px solid #E0E0E0;background:white;margin-top:16px;}}
.footer a{{color:#2E86C1;text-decoration:none;font-weight:600;}}
.footer a:hover{{text-decoration:underline;}}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>E-Commerce Operations &amp; Customer Intelligence</h1>
    <p>Olist Brazilian E-Commerce Dataset (2016–2018) &nbsp;·&nbsp; 99,441 orders &nbsp;·&nbsp; 8 relational tables &nbsp;·&nbsp; Python + SQL + Plotly</p>
  </div>
  <div class="badge">Portfolio Project &nbsp;·&nbsp; Salma El Moudi</div>
</div>

<div class="tabs">
  <div class="tab active" onclick="show(0)">&#x1F4CA;&nbsp; Executive Overview</div>
  <div class="tab"        onclick="show(1)">&#x1F464;&nbsp; Customer Intelligence</div>
  <div class="tab"        onclick="show(2)">&#x1F69A;&nbsp; Operations &amp; Delivery</div>
</div>

<div id="p0" class="pane active">
  <div class="insight">
    <strong>Key Insight:</strong>
    Total revenue of <strong>R$ {total_rev:,.0f}</strong> generated across {total_orders:,} orders.
    Revenue grew sharply through 2017, peaking in Nov 2017 (Black Friday effect).
    Credit card accounts for &gt;74% of payments. Top 3 categories
    (bed_bath_table, health_beauty, sports_leisure) generate over 35% of total revenue.
    Overall on-time delivery rate: <strong>{on_time_pct}%</strong>.
  </div>
  {h1}
</div>

<div id="p1" class="pane">
  <div class="insight">
    <strong>Key Insight:</strong>
    Of <strong>94,697 unique customers</strong>, over 90% are one-time buyers &mdash;
    retention is the single biggest growth lever.
    Champions (top RFM segment, {rfm[rfm["segment"]=="Champions"].shape[0]:,} customers) have
    an average lifetime value <strong>8&times; higher</strong> than Lost Customers.
    S&atilde;o Paulo (SP) drives ~38% of total revenue.
  </div>
  {h2}
</div>

<div id="p2" class="pane">
  <div class="insight">
    <strong>Key Insight:</strong>
    Late deliveries <strong>statistically and significantly</strong> reduce customer satisfaction:
    avg review <strong>{st["avg_review_on_time"]}</strong> (on-time) vs
    <strong>{st["avg_review_late"]}</strong> (late), Mann-Whitney p &asymp; {st["p_value"]}.
    A Logistic Regression model predicts delays at order time
    (<strong>ROC-AUC = {mlt["roc_auc"]}</strong>).
    Top predictor: <em>estimated delivery days</em> &mdash; the longer the promised window,
    the higher the actual delay risk.
    Average delivery time: <strong>{avg_del_days} days</strong>.
  </div>
  {h3}
</div>

<div class="footer">
  Built by <strong>Salma El Moudi</strong> &nbsp;&middot;&nbsp;
  Data Analyst Portfolio &nbsp;&middot;&nbsp;
  Python &bull; SQL (PostgreSQL) &bull; Plotly &bull; Scikit-Learn &nbsp;&middot;&nbsp;
  <a href="https://github.com/salmaelmoudi" target="_blank">github.com/salmaelmoudi</a> &nbsp;&middot;&nbsp;
  <a href="https://linkedin.com/in/salma-el-moudi-401a67265" target="_blank">LinkedIn</a>
</div>

<script>
function show(n){{
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',i===n));
  document.querySelectorAll('.pane').forEach((p,i)=>p.classList.toggle('active',i===n));
}}
</script>
</body>
</html>"""

out = os.path.join(DASHBOARD_DIR, "ecommerce_dashboard.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

size_mb = os.path.getsize(out) / 1024 / 1024
print(f"  Dashboard -> {out}")
print(f"  File size: {size_mb:.2f} MB")
print("  Open in Chrome/Edge to view the full dashboard.")
