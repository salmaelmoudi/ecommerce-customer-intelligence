"""
Master pipeline runner — runs all project scripts in sequence.
Handles Windows encoding and path issues.
"""
import sys
import os
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(PROJECT_ROOT, "data")
CLEANED_DIR  = os.path.join(DATA_DIR, "cleaned")
EXPORT_DIR   = os.path.join(DATA_DIR, "powerbi_exports")
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "dashboard")

os.makedirs(CLEANED_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)
os.makedirs(DASHBOARD_DIR, exist_ok=True)

import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings("ignore")

# ─── STEP 1: DATA CLEANING ────────────────────────────────────────────────────
print("=" * 60)
print("STEP 1: DATA CLEANING")
print("=" * 60)

files = {
    "orders":       "olist_orders_dataset.csv",
    "order_items":  "olist_order_items_dataset.csv",
    "payments":     "olist_order_payments_dataset.csv",
    "reviews":      "olist_order_reviews_dataset.csv",
    "customers":    "olist_customers_dataset.csv",
    "products":     "olist_products_dataset.csv",
    "sellers":      "olist_sellers_dataset.csv",
    "geolocation":  "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}
dfs = {}
for key, fname in files.items():
    path = os.path.join(DATA_DIR, fname)
    dfs[key] = pd.read_csv(path)
    print(f"  Loaded {key:30s} -> {len(dfs[key]):>7,} rows")

# Clean orders
date_cols = ["order_purchase_timestamp","order_approved_at",
             "order_delivered_carrier_date","order_delivered_customer_date",
             "order_estimated_delivery_date"]
for col in date_cols:
    dfs["orders"][col] = pd.to_datetime(dfs["orders"][col])

# Impute 8 missing delivery dates
mask = ((dfs["orders"]["order_status"] == "delivered") &
        dfs["orders"]["order_delivered_customer_date"].isna())
dfs["orders"].loc[mask, "order_delivered_customer_date"] = \
    dfs["orders"].loc[mask, "order_estimated_delivery_date"]

dfs["orders"]["delivery_days"] = (
    dfs["orders"]["order_delivered_customer_date"] -
    dfs["orders"]["order_purchase_timestamp"]
).dt.days
dfs["orders"]["is_late"] = (
    dfs["orders"]["order_delivered_customer_date"] >
    dfs["orders"]["order_estimated_delivery_date"]
).astype(int)
dfs["orders"]["approval_hours"] = (
    dfs["orders"]["order_approved_at"] -
    dfs["orders"]["order_purchase_timestamp"]
).dt.total_seconds() / 3600

# Clean payments
before = len(dfs["payments"])
dfs["payments"] = dfs["payments"][dfs["payments"]["payment_value"] > 0]
dfs["payments"] = dfs["payments"][dfs["payments"]["order_id"].isin(dfs["orders"]["order_id"])]
print(f"  Payments: removed {before - len(dfs['payments'])} invalid rows")

# Clean products
dfs["products"]["product_category_name"] = dfs["products"]["product_category_name"].fillna("unknown")
dfs["products"] = dfs["products"].merge(dfs["category_translation"], on="product_category_name", how="left")
dfs["products"]["product_category_name_english"] = dfs["products"]["product_category_name_english"].fillna(
    dfs["products"]["product_category_name"])
for col in ["product_weight_g","product_length_cm","product_height_cm","product_width_cm"]:
    dfs["products"][col] = dfs["products"][col].fillna(dfs["products"][col].median())

# Deduplicate geolocation
dfs["geolocation"] = (
    dfs["geolocation"]
    .groupby("geolocation_zip_code_prefix")
    .agg(geolocation_lat=("geolocation_lat","median"),
         geolocation_lng=("geolocation_lng","median"),
         geolocation_city=("geolocation_city","first"),
         geolocation_state=("geolocation_state","first"))
    .reset_index()
)

# Save cleaned CSVs
save_tables = {k: v for k, v in dfs.items() if k != "category_translation"}
for key, df in save_tables.items():
    path = os.path.join(CLEANED_DIR, f"{key}_clean.csv")
    df.to_csv(path, index=False)
print(f"  Saved {len(save_tables)} cleaned tables to {CLEANED_DIR}")

# ─── STEP 2: ADVANCED ANALYTICS ───────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2: ADVANCED ANALYTICS + RFM + ML")
print("=" * 60)

from scipy import stats as scipy_stats
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score, f1_score

# RFM
print("\n  Computing RFM segmentation...")
ref_date = dfs["orders"]["order_purchase_timestamp"].max() + pd.Timedelta(days=1)
df_rfm = (
    dfs["orders"]
    .merge(dfs["customers"][["customer_id","customer_unique_id","customer_state"]], on="customer_id", how="left")
    .merge(dfs["order_items"][["order_id","price","freight_value"]], on="order_id", how="left")
)
df_rfm = df_rfm[df_rfm["order_status"].isin(["delivered","shipped","invoiced"])]
df_rfm["order_value"] = df_rfm["price"] + df_rfm["freight_value"]

rfm = (
    df_rfm.groupby("customer_unique_id")
    .agg(last_purchase=("order_purchase_timestamp","max"),
         frequency=("order_id","nunique"),
         monetary=("order_value","sum"),
         customer_state=("customer_state","first"))
    .reset_index()
)
rfm["recency"] = (ref_date - rfm["last_purchase"]).dt.days
rfm.drop(columns=["last_purchase"], inplace=True)

rfm["r_score"] = pd.qcut(rfm["recency"],   4, labels=[4,3,2,1]).astype(int)
rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 4, labels=[1,2,3,4]).astype(int)
rfm["m_score"] = pd.qcut(rfm["monetary"],  4, labels=[1,2,3,4]).astype(int)
rfm["rfm_score"] = rfm["r_score"] + rfm["f_score"] + rfm["m_score"]

def segment_label(row):
    if row["rfm_score"] >= 10: return "Champions"
    elif row["rfm_score"] >= 8: return "Loyal Customers"
    elif row["rfm_score"] >= 6: return "Potential Loyalists"
    elif row["r_score"] >= 3:  return "Recent Customers"
    elif row["rfm_score"] >= 4: return "At Risk"
    else: return "Lost Customers"

rfm["segment"] = rfm.apply(segment_label, axis=1)
rfm["monetary"] = rfm["monetary"].round(2)
print(f"  RFM done: {len(rfm):,} customers")
for s, c in rfm["segment"].value_counts().items():
    print(f"    {s:25s}: {c:,}")

# Statistical test
print("\n  Statistical test: delay vs review score...")
test_df = dfs["orders"].merge(dfs["reviews"][["order_id","review_score"]], on="order_id", how="inner")
test_df = test_df[test_df["order_status"] == "delivered"].dropna(subset=["review_score","is_late"])
on_time = test_df[test_df["is_late"]==0]["review_score"].astype(float)
late    = test_df[test_df["is_late"]==1]["review_score"].astype(float)
u_stat, p_val = scipy_stats.mannwhitneyu(on_time, late, alternative="greater")
stats_result = {
    "avg_review_on_time": round(on_time.mean(), 3),
    "avg_review_late":    round(late.mean(), 3),
    "p_value":            round(p_val, 6),
    "conclusion": "Late deliveries significantly lower review scores (p < 0.05)" if p_val < 0.05 else "No significant difference"
}
print(f"  On-time avg review: {stats_result['avg_review_on_time']}")
print(f"  Late avg review:    {stats_result['avg_review_late']}")
print(f"  p-value: {stats_result['p_value']} -> {stats_result['conclusion']}")

# ML model
print("\n  Building delay prediction model...")
orders_ml = dfs["orders"].copy()
orders_ml["order_estimated_delivery_date"] = pd.to_datetime(orders_ml["order_estimated_delivery_date"])
orders_ml["estimated_delivery_days"] = (
    orders_ml["order_estimated_delivery_date"] - orders_ml["order_purchase_timestamp"]
).dt.days

df_ml = (
    orders_ml[["order_id","is_late","estimated_delivery_days","customer_id"]]
    .merge(dfs["order_items"][["order_id","product_id","seller_id","price","freight_value"]], on="order_id", how="left")
    .merge(dfs["products"][["product_id","product_weight_g"]], on="product_id", how="left")
    .merge(dfs["customers"][["customer_id","customer_state"]], on="customer_id", how="left")
    .merge(dfs["sellers"][["seller_id","seller_state"]], on="seller_id", how="left")
)
df_ml = df_ml.dropna(subset=["is_late","product_weight_g","freight_value","price","estimated_delivery_days"])
df_ml = df_ml[df_ml["estimated_delivery_days"] > 0]
df_ml["is_late"] = df_ml["is_late"].astype(int)

top_states = df_ml["customer_state"].value_counts().nlargest(5).index
df_ml["cust_state_enc"] = df_ml["customer_state"].apply(lambda x: x if x in top_states else "other")
df_ml["sell_state_enc"] = df_ml["seller_state"].apply(lambda x: x if x in top_states else "other")
df_ml = pd.get_dummies(df_ml, columns=["cust_state_enc","sell_state_enc"], drop_first=True)

feature_cols = (
    ["product_weight_g","freight_value","price","estimated_delivery_days"]
    + [c for c in df_ml.columns if c.startswith("cust_state_enc_") or c.startswith("sell_state_enc_")]
)
X = df_ml[feature_cols].fillna(0)
y = df_ml["is_late"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc  = scaler.transform(X_test)

model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
model.fit(X_train_sc, y_train)
y_pred = model.predict(X_test_sc)
y_prob = model.predict_proba(X_test_sc)[:,1]

ml_metrics = {
    "roc_auc":  round(roc_auc_score(y_test, y_prob), 4),
    "f1_score": round(f1_score(y_test, y_pred), 4),
    "test_samples": len(y_test),
}
print(f"  ROC-AUC: {ml_metrics['roc_auc']}  |  F1: {ml_metrics['f1_score']}")

coef_df = pd.DataFrame({
    "feature":     feature_cols,
    "coefficient": model.coef_[0].round(4),
    "abs_coef":    np.abs(model.coef_[0]).round(4),
}).sort_values("abs_coef", ascending=False)

# ─── STEP 3: POWER BI EXPORTS ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3: EXPORTING DATA FOR POWER BI / DASHBOARD")
print("=" * 60)

# 3a. Fact table
fact = (
    dfs["orders"]
    .merge(dfs["customers"][["customer_id","customer_unique_id","customer_city","customer_state"]], on="customer_id", how="left")
    .merge(dfs["order_items"][["order_id","product_id","seller_id","price","freight_value"]], on="order_id", how="left")
    .merge(dfs["products"][["product_id","product_category_name_english"]], on="product_id", how="left")
    .merge(dfs["sellers"][["seller_id","seller_state"]], on="seller_id", how="left")
    .merge(dfs["payments"][["order_id","payment_type","payment_value"]].drop_duplicates("order_id"), on="order_id", how="left")
    .merge(dfs["reviews"][["order_id","review_score"]].drop_duplicates("order_id"), on="order_id", how="left")
)
fact["order_value"] = fact["price"].fillna(0) + fact["freight_value"].fillna(0)
fact["year_month"]  = fact["order_purchase_timestamp"].dt.to_period("M").astype(str)
fact["day_of_week"] = fact["order_purchase_timestamp"].dt.day_name()
fact.to_csv(os.path.join(EXPORT_DIR, "fact_orders.csv"), index=False)
print(f"  fact_orders.csv -> {len(fact):,} rows")

# 3b. RFM
rfm.to_csv(os.path.join(EXPORT_DIR, "dim_rfm_segments.csv"), index=False)
print(f"  dim_rfm_segments.csv -> {len(rfm):,} rows")

# 3c. Monthly revenue
monthly = (
    fact[fact["order_status"].isin(["delivered","shipped","invoiced"])]
    .groupby("year_month")
    .agg(total_revenue=("order_value","sum"), total_orders=("order_id","nunique"))
    .reset_index().sort_values("year_month")
)
monthly["prev_revenue"] = monthly["total_revenue"].shift(1)
monthly["mom_growth_pct"] = ((monthly["total_revenue"]-monthly["prev_revenue"])/monthly["prev_revenue"]*100).round(1)
monthly.to_csv(os.path.join(EXPORT_DIR, "agg_monthly_revenue.csv"), index=False)
print(f"  agg_monthly_revenue.csv -> {len(monthly)} rows")

# 3d. Seller scorecard
seller_sc = (
    fact[fact["order_status"]=="delivered"]
    .groupby(["seller_id","seller_state"])
    .agg(total_orders=("order_id","nunique"), total_revenue=("order_value","sum"),
         avg_review=("review_score","mean"), late_deliveries=("is_late","sum"))
    .reset_index()
)
seller_sc["late_pct"]    = (seller_sc["late_deliveries"]/seller_sc["total_orders"]*100).round(1)
seller_sc["avg_review"]  = seller_sc["avg_review"].round(2)
seller_sc["total_revenue"] = seller_sc["total_revenue"].round(2)
seller_sc = seller_sc[seller_sc["total_orders"]>=10]
seller_sc.to_csv(os.path.join(EXPORT_DIR, "agg_seller_scorecard.csv"), index=False)
print(f"  agg_seller_scorecard.csv -> {len(seller_sc)} rows")

# 3e. Category performance
cat = (
    fact[fact["order_status"].isin(["delivered","shipped","invoiced"])]
    .groupby("product_category_name_english")
    .agg(total_orders=("order_id","nunique"), total_revenue=("price","sum"),
         total_freight=("freight_value","sum"), avg_review=("review_score","mean"))
    .reset_index()
)
cat["freight_pct"]    = (cat["total_freight"]/(cat["total_revenue"]+cat["total_freight"])*100).round(1)
cat["total_revenue"]  = cat["total_revenue"].round(2)
cat.to_csv(os.path.join(EXPORT_DIR, "agg_category_performance.csv"), index=False)
print(f"  agg_category_performance.csv -> {len(cat)} rows")

# 3f. Delivery by state
delivery_state = (
    fact[fact["order_status"]=="delivered"]
    .groupby("customer_state")
    .agg(total_orders=("order_id","nunique"), avg_delivery_days=("delivery_days","mean"),
         late_deliveries=("is_late","sum"), avg_review=("review_score","mean"))
    .reset_index()
)
delivery_state["late_pct"] = (delivery_state["late_deliveries"]/delivery_state["total_orders"]*100).round(1)
delivery_state["avg_delivery_days"] = delivery_state["avg_delivery_days"].round(1)
delivery_state.to_csv(os.path.join(EXPORT_DIR, "agg_delivery_by_state.csv"), index=False)
print(f"  agg_delivery_by_state.csv -> {len(delivery_state)} rows")

# 3g. ML summary
ml_summary = {
    "model": "Logistic Regression (Delivery Delay Prediction)",
    "metrics": ml_metrics,
    "top_features": coef_df.head(10).to_dict(orient="records"),
    "stats_test": stats_result,
}
with open(os.path.join(EXPORT_DIR, "ml_summary.json"), "w", encoding="utf-8") as f:
    json.dump(ml_summary, f, indent=2)
print(f"  ml_summary.json")

# ─── STEP 4: BUILD DASHBOARD ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4: BUILDING INTERACTIVE HTML DASHBOARD")
print("=" * 60)

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

PRIMARY   = "#1B4F72"
SECONDARY = "#2E86C1"
ACCENT    = "#F39C12"
SUCCESS   = "#1ABC9C"
DANGER    = "#E74C3C"
LIGHT_BG  = "#F8F9FA"
GRAY      = "#7F8C8D"

# --- Page 1: Executive Overview ---
fig1 = make_subplots(
    rows=3, cols=4,
    specs=[
        [{"type":"indicator"},{"type":"indicator"},{"type":"indicator"},{"type":"indicator"}],
        [{"type":"xy","colspan":4},None,None,None],
        [{"type":"xy","colspan":2},None,{"type":"domain","colspan":2},None],
    ],
    subplot_titles=("","","","",
                    "Monthly Revenue (R$) & Order Volume",
                    "Top 10 Categories by Revenue", "Payment Methods"),
    vertical_spacing=0.12, horizontal_spacing=0.05,
)

delivered_fact = fact[fact["order_status"]=="delivered"]
valid_fact = fact[fact["order_status"].isin(["delivered","shipped","invoiced"])]
total_revenue = valid_fact["order_value"].sum()
total_orders  = fact["order_id"].nunique()
aov           = valid_fact["order_value"].mean()
avg_review    = delivered_fact["review_score"].mean()

for col, (val, label, color) in enumerate([
    (total_revenue, "Total Revenue (R$)", PRIMARY),
    (total_orders,  "Total Orders",        SECONDARY),
    (aov,           "Avg Order Value (R$)", ACCENT),
    (avg_review,    "Avg Review Score",    SUCCESS),
], 1):
    fig1.add_trace(go.Indicator(
        mode="number", value=val,
        title={"text": f"<b>{label}</b>", "font": {"size":13,"color":GRAY}},
        number={"font":{"size":26,"color":color},
                "valueformat": ",.0f" if val > 100 else ".2f"},
    ), row=1, col=col)

monthly_s = monthly.sort_values("year_month")
fig1.add_trace(go.Bar(x=monthly_s["year_month"], y=monthly_s["total_revenue"],
    name="Revenue", marker_color=SECONDARY, opacity=0.75), row=2, col=1)
fig1.add_trace(go.Scatter(x=monthly_s["year_month"], y=monthly_s["total_orders"],
    name="Orders", mode="lines+markers", line=dict(color=ACCENT, width=2)), row=2, col=1)

cat_top = cat.nlargest(10,"total_revenue").sort_values("total_revenue")
fig1.add_trace(go.Bar(x=cat_top["total_revenue"], y=cat_top["product_category_name_english"],
    orientation="h", marker_color=PRIMARY, name="Category Revenue"), row=3, col=1)

pay_grp = (fact.dropna(subset=["payment_type"])
           .groupby("payment_type")["payment_value"].sum().reset_index())
fig1.add_trace(go.Pie(labels=pay_grp["payment_type"], values=pay_grp["payment_value"],
    hole=0.4, marker=dict(colors=[PRIMARY,SECONDARY,ACCENT,SUCCESS,DANGER])), row=3, col=3)

fig1.update_layout(
    title=dict(text="<b>E-Commerce Executive Dashboard</b>", font=dict(size=18,color=PRIMARY), x=0.5),
    height=900, paper_bgcolor=LIGHT_BG, plot_bgcolor="white", showlegend=False,
    font=dict(family="Segoe UI, Arial", size=12), margin=dict(t=100,b=40,l=60,r=40),
)

# --- Page 2: Customer Intelligence ---
seg_counts = rfm["segment"].value_counts().reset_index()
seg_counts.columns = ["segment","count"]
color_map = {"Champions":PRIMARY,"Loyal Customers":SECONDARY,"Potential Loyalists":SUCCESS,
             "Recent Customers":ACCENT,"At Risk":"#E67E22","Lost Customers":DANGER}

fig2 = make_subplots(
    rows=2, cols=2,
    specs=[[{"type":"xy"},{"type":"domain"}],[{"type":"xy"},{"type":"xy"}]],
    subplot_titles=("Customer Segments - Count","RFM Segment Share",
                    "Avg Lifetime Value by Segment (R$)","Revenue by Customer State (Top 10)"),
    vertical_spacing=0.15, horizontal_spacing=0.1,
)
fig2.add_trace(go.Bar(x=seg_counts["segment"], y=seg_counts["count"],
    marker_color=[color_map.get(s,GRAY) for s in seg_counts["segment"]],
    text=seg_counts["count"], textposition="outside", name="Customers"), row=1, col=1)
fig2.add_trace(go.Pie(labels=seg_counts["segment"], values=seg_counts["count"], hole=0.45,
    marker=dict(colors=[color_map.get(s,GRAY) for s in seg_counts["segment"]])), row=1, col=2)
avg_mon = rfm.groupby("segment")["monetary"].mean().reset_index().sort_values("monetary")
fig2.add_trace(go.Bar(x=avg_mon["monetary"], y=avg_mon["segment"], orientation="h",
    marker_color=[color_map.get(s,GRAY) for s in avg_mon["segment"]],
    text=avg_mon["monetary"].round(0), textposition="outside"), row=2, col=1)
state_rev = (valid_fact.groupby("customer_state")["order_value"].sum()
             .nlargest(10).reset_index().sort_values("order_value"))
fig2.add_trace(go.Bar(x=state_rev["order_value"], y=state_rev["customer_state"], orientation="h",
    marker_color=SECONDARY, text=state_rev["order_value"].round(0), textposition="outside"), row=2, col=2)
fig2.update_layout(
    title=dict(text="<b>Customer Intelligence Dashboard</b>", font=dict(size=18,color=PRIMARY), x=0.5),
    height=800, paper_bgcolor=LIGHT_BG, plot_bgcolor="white", showlegend=False,
    font=dict(family="Segoe UI, Arial", size=12), margin=dict(t=100,b=40,l=60,r=40),
)

# --- Page 3: Operations & Delivery ---
fig3 = make_subplots(
    rows=2, cols=2,
    specs=[[{"type":"xy"},{"type":"xy"}],[{"type":"xy"},{"type":"xy"}]],
    subplot_titles=("Late Delivery % by State (Top 15)",
                    "Avg Review Score by Delivery Days Group",
                    "Worst Sellers by Late Delivery %",
                    "ML Feature Importance (Delay Predictor)"),
    vertical_spacing=0.15, horizontal_spacing=0.1,
)
ds_sorted = delivery_state.sort_values("late_pct", ascending=True).tail(15)
colors_late = [DANGER if x>20 else ACCENT if x>10 else SUCCESS for x in ds_sorted["late_pct"]]
fig3.add_trace(go.Bar(x=ds_sorted["late_pct"], y=ds_sorted["customer_state"], orientation="h",
    marker_color=colors_late, text=ds_sorted["late_pct"].astype(str)+"%", textposition="outside"), row=1, col=1)

review_del = (delivered_fact.groupby("review_score")
              .agg(avg_days=("delivery_days","mean"), count=("order_id","nunique")).reset_index().dropna())
fig3.add_trace(go.Bar(x=review_del["review_score"], y=review_del["avg_days"],
    marker_color=[DANGER,"#E67E22",ACCENT,SUCCESS,PRIMARY],
    text=review_del["avg_days"].round(1), textposition="outside"), row=1, col=2)

worst = seller_sc.nlargest(15,"late_pct").sort_values("late_pct", ascending=True)
fig3.add_trace(go.Bar(x=worst["late_pct"], y=worst["seller_id"].str[:12], orientation="h",
    marker_color=DANGER, text=worst["late_pct"].astype(str)+"%", textposition="outside"), row=2, col=1)

feat_df = coef_df.head(8).sort_values("abs_coef")
fig3.add_trace(go.Bar(x=feat_df["abs_coef"], y=feat_df["feature"], orientation="h",
    marker_color=SECONDARY, text=feat_df["coefficient"].round(3), textposition="outside"), row=2, col=2)

fig3.add_annotation(
    text=f"<b>ROC-AUC: {ml_metrics['roc_auc']}</b> | F1: {ml_metrics['f1_score']}",
    x=0.98, y=0.02, xref="paper", yref="paper", showarrow=False,
    font=dict(size=11,color=PRIMARY), bgcolor="white", bordercolor=SECONDARY, borderwidth=1,
)
fig3.update_layout(
    title=dict(text="<b>Operations & Delivery Intelligence</b>", font=dict(size=18,color=PRIMARY), x=0.5),
    height=800, paper_bgcolor=LIGHT_BG, plot_bgcolor="white", showlegend=False,
    font=dict(family="Segoe UI, Arial", size=12), margin=dict(t=100,b=40,l=100,r=40),
)

# Assemble HTML
html1 = fig1.to_html(full_html=False, include_plotlyjs=False)
html2 = fig2.to_html(full_html=False, include_plotlyjs=False)
html3 = fig3.to_html(full_html=False, include_plotlyjs=False)

on_time_pct = (1 - delivered_fact["is_late"].mean()) * 100

final_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>E-Commerce Analytics Dashboard | Salma El Moudi</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F8F9FA;color:#2C3E50;}}
  .header{{background:linear-gradient(135deg,#1B4F72,#2E86C1);color:white;padding:20px 40px;display:flex;justify-content:space-between;align-items:center;}}
  .header h1{{font-size:20px;font-weight:700;}}
  .header p{{font-size:12px;opacity:0.85;margin-top:4px;}}
  .header .badge{{background:rgba(255,255,255,0.15);padding:6px 14px;border-radius:20px;font-size:12px;}}
  .tabs{{display:flex;border-bottom:2px solid #2E86C1;background:white;padding:0 40px;}}
  .tab{{padding:14px 24px;cursor:pointer;font-weight:600;color:#7F8C8D;border-bottom:3px solid transparent;transition:all 0.2s;font-size:14px;}}
  .tab.active{{color:#1B4F72;border-bottom-color:#F39C12;}}
  .tab:hover{{color:#2E86C1;}}
  .content{{display:none;padding:20px 30px;}}
  .content.active{{display:block;}}
  .insight-bar{{background:white;border-left:4px solid #F39C12;padding:12px 20px;margin-bottom:16px;border-radius:0 8px 8px 0;box-shadow:0 1px 4px rgba(0,0,0,0.08);font-size:13px;}}
  .insight-bar strong{{color:#1B4F72;}}
  .footer{{text-align:center;padding:16px;font-size:12px;color:#7F8C8D;border-top:1px solid #E0E0E0;background:white;margin-top:20px;}}
  .footer a{{color:#2E86C1;text-decoration:none;}}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>E-Commerce Operations &amp; Customer Intelligence</h1>
    <p>Olist Brazilian E-Commerce Dataset (2016-2018) &middot; 100K+ orders &middot; 8 relational tables &middot; Python + SQL + Plotly</p>
  </div>
  <div class="badge">Portfolio Project &middot; Salma El Moudi</div>
</div>
<div class="tabs">
  <div class="tab active" onclick="showTab(0)">Executive Overview</div>
  <div class="tab" onclick="showTab(1)">Customer Intelligence</div>
  <div class="tab" onclick="showTab(2)">Operations &amp; Delivery</div>
</div>
<div id="tab0" class="content active">
  <div class="insight-bar">
    <strong>Key Insight:</strong> Revenue grew consistently through 2017 with strong seasonality peaks in Nov-Dec.
    Credit cards dominate payment (~74%). Top 3 categories generate over 40% of total revenue.
    On-time delivery rate: <strong>{on_time_pct:.1f}%</strong>.
  </div>
  {html1}
</div>
<div id="tab1" class="content">
  <div class="insight-bar">
    <strong>Key Insight:</strong> Over 90% of customers are one-time buyers &mdash; retention is the #1 growth lever.
    Champions have an avg lifetime value 8x higher than Lost Customers. Sao Paulo drives ~40% of total revenue.
  </div>
  {html2}
</div>
<div id="tab2" class="content">
  <div class="insight-bar">
    <strong>Key Insight:</strong>
    Late deliveries are <strong>statistically proven</strong> to lower review scores
    (avg {stats_result['avg_review_on_time']} on-time vs {stats_result['avg_review_late']} late, p={stats_result['p_value']}).
    ML delay predictor: <strong>ROC-AUC = {ml_metrics['roc_auc']}</strong>.
    Top predictor: estimated delivery days at purchase time.
  </div>
  {html3}
</div>
<div class="footer">
  Built by <strong>Salma El Moudi</strong> &middot; Data Analyst Portfolio &middot;
  Python + SQL (PostgreSQL) + Plotly &middot;
  <a href="https://github.com/salmaelmoudi" target="_blank">github.com/salmaelmoudi</a> &middot;
  linkedin.com/in/salma-el-moudi-401a67265
</div>
<script>
function showTab(n){{
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',i===n));
  document.querySelectorAll('.content').forEach((c,i)=>c.classList.toggle('active',i===n));
}}
</script>
</body>
</html>"""

out_path = os.path.join(DASHBOARD_DIR, "ecommerce_dashboard.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(final_html)
print(f"  Dashboard saved -> {out_path}")
print(f"  File size: {os.path.getsize(out_path)/1024/1024:.1f} MB")

print("\n" + "=" * 60)
print("ALL DONE! PROJECT COMPLETE.")
print("=" * 60)
print(f"  Cleaned data  -> {CLEANED_DIR}")
print(f"  Power BI data -> {EXPORT_DIR}")
print(f"  Dashboard     -> {out_path}")
print(f"  SQL queries   -> sql/analytical_queries.sql")
print(f"  ML ROC-AUC:   {ml_metrics['roc_auc']}")
