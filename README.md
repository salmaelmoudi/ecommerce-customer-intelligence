# E-Commerce Operations & Customer Intelligence
### End-to-End Data Analytics Portfolio Project
**Author:** Salma El Moudi | Data Analyst | [LinkedIn](https://linkedin.com/in/salma-el-moudi-401a67265) | [GitHub](https://github.com/salmaelmoudi)

---

## Business Context

A fast-growing online marketplace is experiencing an internal data quality crisis: order volume is up 40% YoY, but customer complaints about late deliveries are rising, and marketing cannot identify which customer segments are actually profitable. The operations team has 2 years of raw transactional data spread across 8 database tables but no analytics layer.

**Mission:** Audit the data, build a central analytical layer, uncover the root causes of declining satisfaction, and deliver an executive dashboard to drive operational decisions.

---

## Key Business Insights Discovered

| Insight | Finding | Business Action |
|---------|---------|-----------------|
| **Delivery impact on reviews** | Late deliveries cut avg review from **4.29 → 2.57** (p ≈ 0, statistically significant) | Prioritise SLA enforcement with bottom 10% of sellers |
| **Revenue concentration** | Top 3 categories (bed_bath_table, health_beauty, sports_leisure) = 35%+ of revenue | Focus supplier negotiation on these 3 categories |
| **Customer retention crisis** | 90%+ of customers are one-time buyers | Launch a loyalty/retention programme |
| **Late delivery rate** | **7.9%** of delivered orders arrive late | Implement seller SLA monitoring dashboard |
| **Payment dominance** | Credit card = 74% of transactions | Instalment plans (avg 3.6 instalments) drive high-ticket purchases |
| **Geographic bottleneck** | Northern/NE states (AM, RR, AP) have 2× the late delivery rate of SP | Work with regional logistics partners |
| **ML delay predictor** | Logistic Regression predicts delays at order time — **ROC-AUC 0.6748** | Flag high-risk orders at checkout for proactive customer communication |

---

## Project Architecture

```
Raw CSVs (Kaggle)
      │
      ▼
[Python — data_quality_audit]
      │  ✓ 8 missing delivery dates found & imputed
      │  ✓ 9 zero-value payments removed
      │  ✓ 1 orphan order removed
      │  ✓ Geolocation deduplicated (1M → 19K rows)
      ▼
[Python — data_cleaning_and_load]
      │  ✓ Cleaned DataFrames
      │  ✓ Loaded to PostgreSQL (ecommerce_analytics)
      │  ✓ Saved as cleaned CSVs (data/cleaned/)
      ▼
[SQL — analytical_queries.sql] (15 queries)
      │  ✓ Monthly MoM revenue (LAG window function)
      │  ✓ Seller scorecard (RANK, PARTITION BY)
      │  ✓ Customer cohort retention (CTEs)
      │  ✓ Pareto analysis (SUM OVER)
      │  ✓ Delivery SLA breach (CASE WHEN + date math)
      ▼
[Python — advanced_analytics.py]
      │  ✓ RFM Customer Segmentation (94,697 customers)
      │  ✓ Mann-Whitney statistical test (delay → review)
      │  ✓ Logistic Regression delay predictor
      │  ✓ Feature importance extraction
      ▼
[Plotly HTML Dashboard] ← [Power BI .pbix]
      ✓ 3-page interactive dashboard
      ✓ Executive Overview | Customer Intelligence | Operations
```

---

## Dashboard Preview

**Page 1 — Executive Overview**
> R\$ 15,665,892 total revenue · 99,441 orders · 4.08 avg review · 92.1% on-time delivery

**Page 2 — Customer Intelligence (RFM)**
> 94,697 unique customers · 15,471 Champions · 90%+ one-time buyers

**Page 3 — Operations & Delivery**
> Late rate 7.9% · Avg 12.5 days delivery · ML ROC-AUC 0.67

📊 **[Open Dashboard](dashboard/ecommerce_dashboard.html)**

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| **Python 3.13** | Data cleaning, RFM segmentation, ML model, pipeline |
| **Pandas / NumPy** | Data manipulation |
| **Scikit-Learn** | Logistic Regression delay predictor |
| **SciPy** | Mann-Whitney statistical test |
| **Plotly** | Interactive 3-page HTML dashboard |
| **PostgreSQL** | Relational data model, 15 analytical SQL queries |
| **SQLAlchemy** | Python → PostgreSQL pipeline |
| **Power BI** | Executive dashboard (connect to `data/powerbi_exports/`) |

---

## Repository Structure

```
ecommerce-customer-intelligence/
├── data/
│   ├── [raw CSVs — not committed, .gitignored]
│   ├── cleaned/              ← 8 cleaned tables (CSV)
│   └── powerbi_exports/      ← Flat tables for Power BI / dashboard
│       ├── fact_orders.csv           (113K rows)
│       ├── dim_rfm_segments.csv      (94K rows)
│       ├── agg_monthly_revenue.csv   (24 rows)
│       ├── agg_seller_scorecard.csv  (1,238 rows)
│       ├── agg_category_performance.csv
│       ├── agg_delivery_by_state.csv
│       └── ml_summary.json
│
├── notebooks/
│   └── 01_data_quality_audit.ipynb   ← Day 1: Data quality checks
│
├── sql/
│   ├── table_schemas.sql             ← PostgreSQL DDL
│   └── analytical_queries.sql        ← 15 business SQL queries
│
├── src/
│   ├── data_cleaning.py              ← Cleaning module
│   └── advanced_analytics.py         ← RFM + ML + Stats module
│
├── dashboard/
│   └── ecommerce_dashboard.html      ← Interactive Plotly dashboard
│
├── images/                           ← Screenshots for README/LinkedIn
├── run_pipeline.py                   ← Run the full project pipeline
├── build_dashboard_final.py          ← Build the HTML dashboard
├── DATA_QUALITY_REPORT.md            ← Full DQ audit documentation
├── requirements.txt
└── README.md
```

---

## SQL Highlights

The `sql/analytical_queries.sql` file contains 15 business queries demonstrating:

```sql
-- MoM Revenue Growth using LAG() window function
WITH monthly_revenue AS (
    SELECT DATE_TRUNC('month', order_purchase_timestamp) AS month,
           SUM(price + freight_value) AS total_revenue
    FROM orders JOIN order_items USING (order_id)
    WHERE order_status NOT IN ('canceled','unavailable')
    GROUP BY 1
)
SELECT month, total_revenue,
       LAG(total_revenue) OVER (ORDER BY month) AS prev_month,
       ROUND(((total_revenue - LAG(total_revenue) OVER (ORDER BY month))
           / LAG(total_revenue) OVER (ORDER BY month) * 100), 1) AS mom_growth_pct
FROM monthly_revenue ORDER BY month;
```

Other queries: Seller RANK per category, Cohort retention (CTEs), Pareto 80/20 analysis, Delivery SLA breach by state, Payment method analysis, RFM data prep.

---

## RFM Segmentation Results

| Segment | Customers | % | Avg Lifetime Value (R$) |
|---------|-----------|---|------------------------|
| Champions | 15,471 | 16.3% | Highest |
| Loyal Customers | 31,548 | 33.3% | High |
| Potential Loyalists | 32,353 | 34.2% | Medium |
| Recent Customers | 1,521 | 1.6% | Low (new) |
| At Risk | 12,258 | 12.9% | Medium (declining) |
| Lost Customers | 1,546 | 1.6% | Very Low |

---

## Data Quality Audit Summary

See [`DATA_QUALITY_REPORT.md`](DATA_QUALITY_REPORT.md) for the full audit.

| Check | Result |
|-------|--------|
| Missing delivery dates (delivered orders) | 8 found → imputed with estimated date |
| Zero-value payments | 9 found → removed |
| Orphan orders (no payment) | 1 found → removed |
| Time-travel deliveries (delivered before purchase) | 0 — data is chronologically sound |
| Duplicate order IDs | 0 |
| Geolocation duplicates | 1M rows → 19K deduplicated by zip code |

---

## ML Model — Delivery Delay Predictor

**Goal:** Predict at order placement time whether a delivery will be late (`is_late = 1`).

**Model:** Logistic Regression (class_weight='balanced', interpretable by design)

**Features:** product_weight_g, freight_value, price, estimated_delivery_days, customer_state (encoded), seller_state (encoded)

**Results:**
- ROC-AUC: **0.6748** (significantly above 0.5 baseline)
- F1-Score: **0.21** (expected given 7.9% base rate — optimise precision for business use)
- **Top predictor:** `estimated_delivery_days` — longer promised windows have higher actual delay risk

**Business Use:** Flag high-risk orders at checkout for proactive customer communication (e.g., "Your order may take longer than usual — we'll keep you updated").

---

## How to Run

```bash
# 1. Clone and set up environment
git clone https://github.com/salmaelmoudi/ecommerce-customer-intelligence
cd ecommerce-customer-intelligence
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 2. Download dataset
# → https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
# → Extract all CSVs to data/

# 3. Run the full pipeline (cleaning + analytics + dashboard)
python run_pipeline.py

# 4. View the dashboard
start dashboard/ecommerce_dashboard.html

# 5. (Optional) Load to PostgreSQL
# Update DB_URL in src/data_cleaning.py then run:
python src/data_cleaning.py
```

---

## Freelance Case Study

> **Client:** E-commerce retailer (Shopify, WooCommerce, etc.)
> **Problem:** Cannot identify which products/delivery zones are killing their reviews and margins.
> **Deliverable:** This exact setup — data audit → SQL analytics → Power BI dashboard.
> **Value:** Actionable insights in 5–7 days. Sellers to penalise identified. Retention strategy defined.
> **Price range:** 5,000–15,000 MAD for setup + 1,000–3,000 MAD/month for maintenance.

---

## About

**Salma El Moudi** — Data Analyst | BI & Data Consultant

*Ingénieure d'État en Informatique & Réseaux — EMSI Casablanca (2026)*

Skills demonstrated in this project: SQL (CTEs, Window Functions, JOINs), Python (Pandas, Scikit-Learn, SciPy, Plotly), Data Quality & Governance, RFM Segmentation, Statistical Testing, ML (Logistic Regression), Power BI (data model design), Business Analytics & Storytelling.

📧 salmaelmoudi3@gmail.com | 🔗 [LinkedIn](https://linkedin.com/in/salma-el-moudi-401a67265) | ⭐ [GitHub](https://github.com/salmaelmoudi)
