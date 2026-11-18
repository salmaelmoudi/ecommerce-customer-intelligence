"""
Generate high-resolution PNG visuals for README, portfolio and LinkedIn.
Author: Salma El Moudi
"""
import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_DIR = os.path.join(ROOT, "data", "powerbi_exports")
IMG_DIR = os.path.join(ROOT, "images")
os.makedirs(IMG_DIR, exist_ok=True)

# Styling palette
PRIMARY = "#1B4F72"
SECONDARY = "#2E86C1"
ACCENT = "#F39C12"
SUCCESS = "#1ABC9C"
DANGER = "#E74C3C"
DARK = "#2C3E50"
GRAY = "#7F8C8D"
LIGHT_BG = "#F8F9FA"

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#BDC3C7"
plt.rcParams["axes.linewidth"] = 0.8

# Load export data
fact = pd.read_csv(os.path.join(EXPORT_DIR, "fact_orders.csv"), low_memory=False)
rfm = pd.read_csv(os.path.join(EXPORT_DIR, "dim_rfm_segments.csv"))
monthly = pd.read_csv(os.path.join(EXPORT_DIR, "agg_monthly_revenue.csv"))
seller_sc = pd.read_csv(os.path.join(EXPORT_DIR, "agg_seller_scorecard.csv"))
cat = pd.read_csv(os.path.join(EXPORT_DIR, "agg_category_performance.csv"))
del_state = pd.read_csv(os.path.join(EXPORT_DIR, "agg_delivery_by_state.csv"))
with open(os.path.join(EXPORT_DIR, "ml_summary.json"), encoding="utf-8") as f:
    ml = json.load(f)

# ── 1. EXECUTIVE OVERVIEW VISUAL ──────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(15, 10), facecolor=LIGHT_BG)
fig.suptitle("E-Commerce Executive Overview — Revenue & Growth Trends", fontsize=18, fontweight="bold", color=PRIMARY, y=0.98)

# 1a. Monthly Revenue
ax = axes[0, 0]
ax.set_facecolor("white")
ms = monthly.sort_values("year_month")
ax.bar(ms["year_month"], ms["total_revenue"] / 1e6, color=SECONDARY, alpha=0.85, label="Revenue (M R$)")
ax.plot(ms["year_month"], ms["total_orders"] / 5000, color=ACCENT, marker="o", linewidth=2.5, label="Orders (scaled)")
ax.set_title("Monthly Revenue (Million R$) & Order Volume", fontsize=13, fontweight="bold", color=DARK)
ax.set_ylabel("Revenue (Million R$)", fontsize=11, color=DARK)
ax.set_xticks(range(len(ms)))
ax.set_xticklabels(ms["year_month"], rotation=45, ha="right", fontsize=9)
ax.legend(loc="upper left")
ax.grid(axis="y", linestyle="--", alpha=0.5)

# 1b. Top 10 Product Categories
ax = axes[0, 1]
ax.set_facecolor("white")
top_cat = cat.nlargest(10, "total_revenue").sort_values("total_revenue")
ax.barh(top_cat["product_category_name_english"], top_cat["total_revenue"] / 1e3, color=PRIMARY, alpha=0.9)
ax.set_title("Top 10 Product Categories by Revenue (k R$)", fontsize=13, fontweight="bold", color=DARK)
ax.set_xlabel("Revenue (Thousand R$)", fontsize=11, color=DARK)
ax.grid(axis="x", linestyle="--", alpha=0.5)

# 1c. Payment Methods
ax = axes[1, 0]
ax.set_facecolor("white")
pay = fact.dropna(subset=["payment_type"]).groupby("payment_type")["payment_value"].sum().reset_index()
colors = [PRIMARY, SECONDARY, ACCENT, SUCCESS, DANGER][:len(pay)]
wedges, texts, autotexts = ax.pie(pay["payment_value"], labels=pay["payment_type"], autopct="%1.1f%%",
                                  startangle=140, colors=colors, textprops={"fontsize": 10},
                                  wedgeprops=dict(width=0.45, edgecolor="w", linewidth=2))
for at in autotexts:
    at.set_color("white")
    at.set_weight("bold")
ax.set_title("Payment Method Revenue Share", fontsize=13, fontweight="bold", color=DARK)

# 1d. Top States Revenue
ax = axes[1, 1]
ax.set_facecolor("white")
valid = fact[fact["order_status"].isin(["delivered", "shipped", "invoiced"])]
top_states = valid.groupby("customer_state")["order_value"].sum().nlargest(10).sort_values()
ax.barh(top_states.index, top_states.values / 1e6, color=SUCCESS, alpha=0.9)
ax.set_title("Top 10 States by Revenue (Million R$)", fontsize=13, fontweight="bold", color=DARK)
ax.set_xlabel("Revenue (Million R$)", fontsize=11, color=DARK)
ax.grid(axis="x", linestyle="--", alpha=0.5)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.savefig(os.path.join(IMG_DIR, "executive_overview.png"), dpi=200)
plt.close()
print("Saved images/executive_overview.png")

# ── 2. CUSTOMER INTELLIGENCE & RFM ────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(15, 6), facecolor=LIGHT_BG)
fig.suptitle("Customer Intelligence — RFM Segmentation Analysis", fontsize=18, fontweight="bold", color=PRIMARY, y=1.02)

# 2a. Segment Distribution
ax = axes[0]
ax.set_facecolor("white")
seg_counts = rfm["segment"].value_counts()
seg_colors = [PRIMARY, SECONDARY, SUCCESS, ACCENT, "#E67E22", DANGER][:len(seg_counts)]
bars = ax.bar(seg_counts.index, seg_counts.values, color=seg_colors, alpha=0.88)
ax.set_title("Customer Volume by RFM Segment", fontsize=13, fontweight="bold", color=DARK)
ax.set_ylabel("Number of Customers", fontsize=11, color=DARK)
ax.set_xticklabels(seg_counts.index, rotation=30, ha="right", fontsize=10)
for b in bars:
    height = b.get_height()
    ax.text(b.get_x() + b.get_width() / 2., height + 400, f"{int(height):,}", ha="center", va="bottom", fontsize=9, fontweight="bold")
ax.grid(axis="y", linestyle="--", alpha=0.5)

# 2b. Average Spend by Segment
ax = axes[1]
ax.set_facecolor("white")
avg_mon = rfm.groupby("segment")["monetary"].mean().reindex(seg_counts.index)
bars = ax.barh(avg_mon.index, avg_mon.values, color=seg_colors, alpha=0.88)
ax.set_title("Average Customer Lifetime Value (R$)", fontsize=13, fontweight="bold", color=DARK)
ax.set_xlabel("Average Spend (R$)", fontsize=11, color=DARK)
for b in bars:
    width = b.get_width()
    ax.text(width + 10, b.get_y() + b.get_height() / 2., f"R$ {width:.0f}", ha="left", va="center", fontsize=9, fontweight="bold")
ax.grid(axis="x", linestyle="--", alpha=0.5)

plt.tight_layout()
plt.savefig(os.path.join(IMG_DIR, "customer_intelligence_rfm.png"), dpi=200, bbox_inches="tight")
plt.close()
print("Saved images/customer_intelligence_rfm.png")

# ── 3. OPERATIONS & ML DELAY PREDICTION ────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), facecolor=LIGHT_BG)
fig.suptitle("Operations, Delivery Performance & Predictive Analytics", fontsize=18, fontweight="bold", color=PRIMARY, y=1.03)

# 3a. Delivery vs Review Score
ax = axes[0]
ax.set_facecolor("white")
delivered = fact[fact["order_status"] == "delivered"]
review_del = delivered.groupby("review_score")["delivery_days"].mean().dropna()
rev_colors = [DANGER, "#E67E22", ACCENT, SUCCESS, PRIMARY]
ax.bar([str(int(i)) + " Stars" for i in review_del.index], review_del.values, color=rev_colors, alpha=0.9)
ax.set_title("Delivery Days vs Review Score\n(p < 0.001, Mann-Whitney)", fontsize=12, fontweight="bold", color=DARK)
ax.set_ylabel("Average Delivery Days", fontsize=11, color=DARK)
for i, v in enumerate(review_del.values):
    ax.text(i, v + 0.3, f"{v:.1f} d", ha="center", fontsize=9, fontweight="bold")
ax.grid(axis="y", linestyle="--", alpha=0.5)

# 3b. Late Delivery % by State
ax = axes[1]
ax.set_facecolor("white")
ds = del_state.sort_values("late_pct", ascending=True).tail(10)
late_colors = [DANGER if x > 15 else ACCENT if x > 8 else SUCCESS for x in ds["late_pct"]]
ax.barh(ds["customer_state"], ds["late_pct"], color=late_colors, alpha=0.88)
ax.set_title("Worst 10 States by Late Delivery %", fontsize=12, fontweight="bold", color=DARK)
ax.set_xlabel("Late Delivery Rate (%)", fontsize=11, color=DARK)
for i, (state, v) in enumerate(zip(ds["customer_state"], ds["late_pct"])):
    ax.text(v + 0.3, i, f"{v:.1f}%", ha="left", va="center", fontsize=9, fontweight="bold")
ax.grid(axis="x", linestyle="--", alpha=0.5)

# 3c. ML Feature Importance
ax = axes[2]
ax.set_facecolor("white")
feats = pd.DataFrame(ml["top_features"]).head(7).sort_values("abs_coef", ascending=True)
ax.barh(feats["feature"], feats["coefficient"], color=SECONDARY, alpha=0.88)
ax.set_title(f"Logistic Regression Feature Importance\n(ROC-AUC = {ml['metrics']['roc_auc']})", fontsize=12, fontweight="bold", color=DARK)
ax.set_xlabel("Regression Coefficient (Log-Odds Impact)", fontsize=11, color=DARK)
ax.axvline(0, color="gray", linestyle="--", linewidth=0.8)
ax.grid(axis="x", linestyle="--", alpha=0.5)

plt.tight_layout()
plt.savefig(os.path.join(IMG_DIR, "operations_delivery_ml.png"), dpi=200, bbox_inches="tight")
plt.close()
print("Saved images/operations_delivery_ml.png")
