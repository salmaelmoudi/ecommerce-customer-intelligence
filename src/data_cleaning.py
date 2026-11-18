"""
Day 2 — Data Cleaning & PostgreSQL Load
========================================
Author: Salma El Moudi
Project: E-Commerce Operations & Customer Intelligence

This script:
1. Loads all 8 Olist raw CSVs
2. Applies data quality fixes found in the Day 1 audit
3. Loads the cleaned tables into PostgreSQL (ecommerce_analytics DB)
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import os
import json

# ─── CONFIGURATION ──────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
# Update with your actual Postgres credentials
DB_URL = "postgresql://postgres:postgres@localhost:5432/ecommerce_analytics"

# ─── LOAD RAW DATA ──────────────────────────────────────────────────────────
def load_raw_data(data_dir: str) -> dict:
    """Load all 8 Olist CSV files into a dictionary of DataFrames."""
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
        path = os.path.join(data_dir, fname)
        dfs[key] = pd.read_csv(path)
        print(f"  ✓ {key:25s} → {len(dfs[key]):>7,} rows")
    return dfs


# ─── CLEANING FUNCTIONS ──────────────────────────────────────────────────────
def clean_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Fix: 8 delivered orders with missing delivery date
         → impute with order_estimated_delivery_date (conservative, documented)
    Fix: parse all timestamp columns to datetime
    """
    date_cols = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    for col in date_cols:
        orders[col] = pd.to_datetime(orders[col])

    # Impute missing delivery dates for 'delivered' status orders
    mask = (orders["order_status"] == "delivered") & orders["order_delivered_customer_date"].isna()
    orders.loc[mask, "order_delivered_customer_date"] = orders.loc[mask, "order_estimated_delivery_date"]

    # Derived columns
    orders["delivery_days"] = (
        orders["order_delivered_customer_date"] - orders["order_purchase_timestamp"]
    ).dt.days
    orders["is_late"] = (
        orders["order_delivered_customer_date"] > orders["order_estimated_delivery_date"]
    ).astype(int)
    orders["approval_hours"] = (
        orders["order_approved_at"] - orders["order_purchase_timestamp"]
    ).dt.total_seconds() / 3600

    return orders


def clean_payments(payments: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """
    Fix: remove 0-value payments (9 rows — likely test/dummy records)
    Fix: remove payments for orders that don't exist in orders table (orphans)
    """
    before = len(payments)
    payments = payments[payments["payment_value"] > 0]
    payments = payments[payments["order_id"].isin(orders["order_id"])]
    print(f"  payments: removed {before - len(payments)} invalid rows")
    return payments


def clean_products(products: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    """
    Fix: missing category names → fill with 'unknown'
    Add English category translation
    """
    products["product_category_name"] = products["product_category_name"].fillna("unknown")
    products = products.merge(translation, on="product_category_name", how="left")
    products["product_category_name_english"] = products["product_category_name_english"].fillna(
        products["product_category_name"]
    )
    # Fill missing dimensions with median (needed for ML feature later)
    for col in ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]:
        products[col] = products[col].fillna(products[col].median())
    return products


def clean_geolocation(geo: pd.DataFrame) -> pd.DataFrame:
    """
    Geolocation table is very large (1M+ rows) with duplicate zip codes.
    Keep one representative lat/lng per zip code (median — avoids outlier bias).
    """
    geo_dedup = (
        geo.groupby("geolocation_zip_code_prefix")
        .agg(
            geolocation_lat=("geolocation_lat", "median"),
            geolocation_lng=("geolocation_lng", "median"),
            geolocation_city=("geolocation_city", "first"),
            geolocation_state=("geolocation_state", "first"),
        )
        .reset_index()
    )
    return geo_dedup


# ─── LOAD TO POSTGRES ────────────────────────────────────────────────────────
def load_to_postgres(dfs: dict, db_url: str):
    """Push all cleaned DataFrames to PostgreSQL using SQLAlchemy."""
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("\n  ✓ PostgreSQL connection successful\n")
    except Exception as e:
        print(f"\n  ✗ PostgreSQL connection failed: {e}")
        print("  → Saving cleaned CSVs instead (fallback mode)\n")
        return False, None

    table_map = {
        "orders":       "orders",
        "order_items":  "order_items",
        "payments":     "payments",
        "reviews":      "reviews",
        "customers":    "customers",
        "products":     "products",
        "sellers":      "sellers",
        "geolocation":  "geolocation",
    }
    for key, table in table_map.items():
        if key in dfs:
            dfs[key].to_sql(table, engine, if_exists="replace", index=False, chunksize=10000)
            print(f"  ✓ Loaded {len(dfs[key]):>7,} rows → table '{table}'")
    return True, engine


# ─── SAVE CLEANED CSVs (FALLBACK) ───────────────────────────────────────────
def save_cleaned_csvs(dfs: dict, out_dir: str):
    """Save cleaned DataFrames as CSVs into data/cleaned/ directory."""
    os.makedirs(out_dir, exist_ok=True)
    for key, df in dfs.items():
        path = os.path.join(out_dir, f"{key}_clean.csv")
        df.to_csv(path, index=False)
        print(f"  ✓ Saved {key:25s} → {path}")


# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  E-COMMERCE ANALYTICS — DAY 2: DATA CLEANING")
    print("=" * 60)

    print("\n[1/4] Loading raw data...")
    dfs = load_raw_data(DATA_DIR)

    print("\n[2/4] Cleaning data...")
    dfs["orders"]   = clean_orders(dfs["orders"])
    dfs["payments"] = clean_payments(dfs["payments"], dfs["orders"])
    dfs["products"] = clean_products(dfs["products"], dfs["category_translation"])
    dfs["geolocation"] = clean_geolocation(dfs["geolocation"])
    print("  ✓ All tables cleaned")

    print("\n[3/4] Attempting PostgreSQL load...")
    success, engine = load_to_postgres(dfs, DB_URL)

    if not success:
        print("[3b/4] Saving cleaned CSVs as fallback...")
        cleaned_dir = os.path.join(DATA_DIR, "cleaned")
        save_cleaned_csvs(
            {k: v for k, v in dfs.items() if k != "category_translation"},
            cleaned_dir
        )

    print("\n[4/4] Done! ✓")
    print("  Next step: Run sql/analytical_queries.sql in pgAdmin or DBeaver")
    print("=" * 60)
    return dfs


if __name__ == "__main__":
    main()
