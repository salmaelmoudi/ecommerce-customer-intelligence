"""
Day 3 & 4 — Advanced Analytics + RFM Segmentation + ML Model
===============================================================
Author: Salma El Moudi
Project: E-Commerce Operations & Customer Intelligence

This script produces:
  - RFM customer segmentation (with labeled segments)
  - Delivery delay prediction (Logistic Regression)
  - Statistical correlation test (delivery delay vs review score)
  - Exports for Power BI dashboard
"""

import pandas as pd
import numpy as np
import os
import json
import warnings
warnings.filterwarnings("ignore")

from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, f1_score
)

# ─── CONFIGURATION ──────────────────────────────────────────────────────────
DATA_DIR    = os.path.join(os.path.dirname(__file__), "..", "data")
CLEANED_DIR = os.path.join(DATA_DIR, "cleaned")
EXPORT_DIR  = os.path.join(DATA_DIR, "powerbi_exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# ─── LOAD CLEANED DATA ───────────────────────────────────────────────────────
def load_cleaned(cleaned_dir: str) -> dict:
    tables = ["orders", "order_items", "payments", "reviews",
              "customers", "products", "sellers", "geolocation"]
    dfs = {}
    for t in tables:
        path = os.path.join(cleaned_dir, f"{t}_clean.csv")
        if os.path.exists(path):
            dfs[t] = pd.read_csv(path, low_memory=False)
    return dfs


# ─── PART 1: RFM SEGMENTATION ────────────────────────────────────────────────
def compute_rfm(orders: pd.DataFrame, order_items: pd.DataFrame,
                customers: pd.DataFrame) -> pd.DataFrame:
    """
    RFM = Recency, Frequency, Monetary
    Computed at customer_unique_id level.
    Reference date: max order date + 1 day (simulate 'today')
    """
    orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"])
    ref_date = orders["order_purchase_timestamp"].max() + pd.Timedelta(days=1)

    # Merge to get customer unique IDs and revenue
    df = (
        orders
        .merge(customers[["customer_id", "customer_unique_id", "customer_state"]],
               on="customer_id", how="left")
        .merge(order_items[["order_id", "price", "freight_value"]],
               on="order_id", how="left")
    )
    df = df[df["order_status"].isin(["delivered", "shipped", "invoiced"])]
    df["order_value"] = df["price"] + df["freight_value"]

    rfm = (
        df.groupby("customer_unique_id")
        .agg(
            last_purchase=("order_purchase_timestamp", "max"),
            frequency=("order_id", "nunique"),
            monetary=("order_value", "sum"),
            customer_state=("customer_state", "first"),
        )
        .reset_index()
    )
    rfm["recency"] = (ref_date - rfm["last_purchase"]).dt.days
    rfm.drop(columns=["last_purchase"], inplace=True)

    # Score each dimension 1-4 (quartile-based)
    rfm["r_score"] = pd.qcut(rfm["recency"],   4, labels=[4, 3, 2, 1]).astype(int)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["m_score"] = pd.qcut(rfm["monetary"],  4, labels=[1, 2, 3, 4]).astype(int)

    rfm["rfm_score"] = rfm["r_score"] + rfm["f_score"] + rfm["m_score"]

    # Segment labels
    def label(row):
        if row["rfm_score"] >= 10:
            return "Champions"
        elif row["rfm_score"] >= 8:
            return "Loyal Customers"
        elif row["rfm_score"] >= 6:
            return "Potential Loyalists"
        elif row["r_score"] >= 3:
            return "Recent Customers"
        elif row["rfm_score"] >= 4:
            return "At Risk"
        else:
            return "Lost Customers"

    rfm["segment"] = rfm.apply(label, axis=1)
    rfm["monetary"] = rfm["monetary"].round(2)
    return rfm


# ─── PART 2: STATISTICAL TEST — Delay vs Review Score ───────────────────────
def delivery_vs_review_test(orders: pd.DataFrame, reviews: pd.DataFrame):
    """
    Hypothesis: Late deliveries lead to lower review scores.
    Test: Point-biserial correlation + Mann-Whitney U test
    """
    df = orders.merge(reviews[["order_id", "review_score"]], on="order_id", how="inner")
    df = df[df["order_status"] == "delivered"].dropna(subset=["review_score", "is_late"])
    df["is_late"] = df["is_late"].astype(int)
    df["review_score"] = df["review_score"].astype(float)

    # Mann-Whitney U: non-parametric test (doesn't assume normality)
    on_time = df[df["is_late"] == 0]["review_score"]
    late    = df[df["is_late"] == 1]["review_score"]
    u_stat, p_val = stats.mannwhitneyu(on_time, late, alternative="greater")

    result = {
        "avg_review_on_time":   round(on_time.mean(), 3),
        "avg_review_late":      round(late.mean(), 3),
        "mann_whitney_u":       round(u_stat, 0),
        "p_value":              round(p_val, 6),
        "statistically_significant": p_val < 0.05,
        "conclusion": (
            "Late deliveries significantly lower review scores (p < 0.05)"
            if p_val < 0.05
            else "No significant difference found"
        )
    }
    return result, df


# ─── PART 3: ML — DELIVERY DELAY PREDICTION ─────────────────────────────────
def build_delay_model(orders: pd.DataFrame, order_items: pd.DataFrame,
                      products: pd.DataFrame, customers: pd.DataFrame,
                      sellers: pd.DataFrame, geolocation: pd.DataFrame):
    """
    Predict is_late (0/1) at order placement time using:
    - product_weight_g
    - freight_value
    - price
    - estimated_delivery_days (at time of order)
    - customer_state → encoded
    - seller_state → encoded
    """
    orders["order_purchase_timestamp"]      = pd.to_datetime(orders["order_purchase_timestamp"])
    orders["order_estimated_delivery_date"] = pd.to_datetime(orders["order_estimated_delivery_date"])
    orders["estimated_delivery_days"] = (
        orders["order_estimated_delivery_date"] - orders["order_purchase_timestamp"]
    ).dt.days

    df = (
        orders[["order_id", "is_late", "estimated_delivery_days", "customer_id"]]
        .merge(order_items[["order_id", "product_id", "seller_id", "price", "freight_value"]],
               on="order_id", how="left")
        .merge(products[["product_id", "product_weight_g"]], on="product_id", how="left")
        .merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left")
        .merge(sellers[["seller_id", "seller_state"]], on="seller_id", how="left")
    )
    df = df.dropna(subset=["is_late", "product_weight_g", "freight_value", "price",
                            "estimated_delivery_days"])
    df = df[df["estimated_delivery_days"] > 0]
    df["is_late"] = df["is_late"].astype(int)

    # Simple encoding: use top 5 states, rest = 'other'
    top_states = df["customer_state"].value_counts().nlargest(5).index
    df["cust_state_enc"] = df["customer_state"].apply(lambda x: x if x in top_states else "other")
    df["sell_state_enc"] = df["seller_state"].apply(lambda x: x if x in top_states else "other")
    df = pd.get_dummies(df, columns=["cust_state_enc", "sell_state_enc"], drop_first=True)

    feature_cols = (
        ["product_weight_g", "freight_value", "price", "estimated_delivery_days"]
        + [c for c in df.columns if c.startswith("cust_state_enc_") or c.startswith("sell_state_enc_")]
    )
    X = df[feature_cols].fillna(0)
    y = df["is_late"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc  = scaler.transform(X_test)

    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_train_sc, y_train)

    y_pred = model.predict(X_test_sc)
    y_prob = model.predict_proba(X_test_sc)[:, 1]

    metrics = {
        "roc_auc":      round(roc_auc_score(y_test, y_prob), 4),
        "f1_score":     round(f1_score(y_test, y_pred), 4),
        "test_samples": len(y_test),
        "pct_late_actual":    round(y_test.mean() * 100, 1),
        "pct_late_predicted": round(y_pred.mean() * 100, 1),
    }

    # Feature importance (absolute coefficients)
    coef_df = pd.DataFrame({
        "feature":     feature_cols,
        "coefficient": model.coef_[0].round(4),
        "abs_coef":    np.abs(model.coef_[0]).round(4),
    }).sort_values("abs_coef", ascending=False).head(10)

    return metrics, coef_df, classification_report(y_test, y_pred)


# ─── POWER BI EXPORTS ────────────────────────────────────────────────────────
def export_for_powerbi(dfs: dict, rfm: pd.DataFrame, stats_result: dict,
                       ml_metrics: dict, coef_df: pd.DataFrame, export_dir: str):
    """Create clean, joined flat tables that Power BI will connect to directly."""

    orders = dfs["orders"].copy()
    orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"])
    orders["order_delivered_customer_date"] = pd.to_datetime(
        orders["order_delivered_customer_date"], errors="coerce"
    )
    orders["order_estimated_delivery_date"] = pd.to_datetime(
        orders["order_estimated_delivery_date"], errors="coerce"
    )

    # 1. Fact Table: orders enriched
    fact = (
        orders
        .merge(dfs["customers"][["customer_id", "customer_unique_id",
                                  "customer_city", "customer_state"]], on="customer_id", how="left")
        .merge(dfs["order_items"][["order_id", "product_id", "seller_id",
                                    "price", "freight_value"]], on="order_id", how="left")
        .merge(dfs["products"][["product_id", "product_category_name_english"]],
               on="product_id", how="left")
        .merge(dfs["sellers"][["seller_id", "seller_state"]], on="seller_id", how="left")
        .merge(dfs["payments"][["order_id", "payment_type", "payment_value"]].drop_duplicates("order_id"),
               on="order_id", how="left")
        .merge(dfs["reviews"][["order_id", "review_score"]].drop_duplicates("order_id"),
               on="order_id", how="left")
    )
    fact["order_value"]  = fact["price"].fillna(0) + fact["freight_value"].fillna(0)
    fact["year_month"]   = fact["order_purchase_timestamp"].dt.to_period("M").astype(str)
    fact["day_of_week"]  = fact["order_purchase_timestamp"].dt.day_name()
    fact.to_csv(os.path.join(export_dir, "fact_orders.csv"), index=False)
    print(f"  ✓ fact_orders.csv        → {len(fact):,} rows")

    # 2. RFM table
    rfm.to_csv(os.path.join(export_dir, "dim_rfm_segments.csv"), index=False)
    print(f"  ✓ dim_rfm_segments.csv   → {len(rfm):,} rows")

    # 3. Monthly Revenue summary
    monthly = (
        fact[fact["order_status"].isin(["delivered", "shipped", "invoiced"])]
        .groupby("year_month")
        .agg(
            total_revenue=("order_value", "sum"),
            total_orders=("order_id", "nunique"),
        )
        .reset_index()
        .sort_values("year_month")
    )
    monthly["prev_revenue"] = monthly["total_revenue"].shift(1)
    monthly["mom_growth_pct"] = (
        (monthly["total_revenue"] - monthly["prev_revenue"])
        / monthly["prev_revenue"] * 100
    ).round(1)
    monthly.to_csv(os.path.join(export_dir, "agg_monthly_revenue.csv"), index=False)
    print(f"  ✓ agg_monthly_revenue.csv → {len(monthly)} rows")

    # 4. Seller scorecard
    seller_sc = (
        fact[fact["order_status"] == "delivered"]
        .groupby(["seller_id", "seller_state"])
        .agg(
            total_orders=("order_id", "nunique"),
            total_revenue=("order_value", "sum"),
            avg_review=("review_score", "mean"),
            late_deliveries=("is_late", "sum"),
        )
        .reset_index()
    )
    seller_sc["late_pct"] = (seller_sc["late_deliveries"] / seller_sc["total_orders"] * 100).round(1)
    seller_sc["avg_review"] = seller_sc["avg_review"].round(2)
    seller_sc["total_revenue"] = seller_sc["total_revenue"].round(2)
    seller_sc = seller_sc[seller_sc["total_orders"] >= 10]
    seller_sc.to_csv(os.path.join(export_dir, "agg_seller_scorecard.csv"), index=False)
    print(f"  ✓ agg_seller_scorecard.csv → {len(seller_sc)} rows")

    # 5. Category performance
    cat = (
        fact[fact["order_status"].isin(["delivered", "shipped", "invoiced"])]
        .groupby("product_category_name_english")
        .agg(
            total_orders=("order_id", "nunique"),
            total_revenue=("price", "sum"),
            total_freight=("freight_value", "sum"),
            avg_review=("review_score", "mean"),
        )
        .reset_index()
    )
    cat["freight_pct"] = (cat["total_freight"] / (cat["total_revenue"] + cat["total_freight"]) * 100).round(1)
    cat["total_revenue"] = cat["total_revenue"].round(2)
    cat.to_csv(os.path.join(export_dir, "agg_category_performance.csv"), index=False)
    print(f"  ✓ agg_category_performance.csv → {len(cat)} rows")

    # 6. Delivery by state
    delivery_state = (
        fact[fact["order_status"] == "delivered"]
        .groupby("customer_state")
        .agg(
            total_orders=("order_id", "nunique"),
            avg_delivery_days=("delivery_days", "mean"),
            late_deliveries=("is_late", "sum"),
            avg_review=("review_score", "mean"),
        )
        .reset_index()
    )
    delivery_state["late_pct"] = (
        delivery_state["late_deliveries"] / delivery_state["total_orders"] * 100
    ).round(1)
    delivery_state["avg_delivery_days"] = delivery_state["avg_delivery_days"].round(1)
    delivery_state.to_csv(os.path.join(export_dir, "agg_delivery_by_state.csv"), index=False)
    print(f"  ✓ agg_delivery_by_state.csv → {len(delivery_state)} rows")

    # 7. ML results
    ml_summary = {
        "model": "Logistic Regression (Delivery Delay Prediction)",
        "metrics": ml_metrics,
        "top_features": coef_df.to_dict(orient="records"),
        "stats_test": stats_result,
    }
    with open(os.path.join(export_dir, "ml_summary.json"), "w") as f:
        json.dump(ml_summary, f, indent=2)
    print(f"  ✓ ml_summary.json")


# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  E-COMMERCE ANALYTICS — DAY 3 & 4: ADVANCED ANALYTICS")
    print("=" * 60)

    print("\n[1/5] Loading cleaned data...")
    dfs = load_cleaned(CLEANED_DIR)
    if not dfs:
        print("  ✗ No cleaned data found. Run data_cleaning.py first.")
        return

    print("\n[2/5] Computing RFM segmentation...")
    rfm = compute_rfm(dfs["orders"], dfs["order_items"], dfs["customers"])
    print(f"  ✓ RFM computed for {len(rfm):,} unique customers")
    print("\n  Segment distribution:")
    seg_dist = rfm["segment"].value_counts()
    for seg, cnt in seg_dist.items():
        print(f"    {seg:25s}: {cnt:,} customers ({cnt/len(rfm)*100:.1f}%)")

    print("\n[3/5] Statistical test: Delivery delay vs Review score...")
    stats_result, test_df = delivery_vs_review_test(dfs["orders"], dfs["reviews"])
    print(f"  ✓ Avg review — On-time: {stats_result['avg_review_on_time']}")
    print(f"  ✓ Avg review — Late:    {stats_result['avg_review_late']}")
    print(f"  ✓ p-value: {stats_result['p_value']} → {stats_result['conclusion']}")

    print("\n[4/5] Building delivery delay ML model...")
    ml_metrics, coef_df, report = build_delay_model(
        dfs["orders"], dfs["order_items"], dfs["products"],
        dfs["customers"], dfs["sellers"], dfs["geolocation"]
    )
    print(f"  ✓ ROC-AUC: {ml_metrics['roc_auc']}")
    print(f"  ✓ F1 Score: {ml_metrics['f1_score']}")
    print(f"\n  Classification Report:\n{report}")
    print(f"\n  Top 5 predictors of late delivery:")
    print(coef_df[["feature", "coefficient"]].head(5).to_string(index=False))

    print("\n[5/5] Exporting data for Power BI...")
    export_for_powerbi(dfs, rfm, stats_result, ml_metrics, coef_df, EXPORT_DIR)

    print("\n✓ All done! Files ready in:", EXPORT_DIR)
    print("  Open Power BI Desktop and connect to those CSVs.")
    print("=" * 60)


if __name__ == "__main__":
    main()
