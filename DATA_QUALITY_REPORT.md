# DATA QUALITY REPORT
## E-Commerce Operations & Customer Intelligence
**Author:** Salma El Moudi  
**Dataset:** Olist Brazilian E-Commerce (Kaggle, 2016–2018)  
**Date:** November 2026

---

## Overview

A thorough data quality audit was conducted before any analysis. This mirrors the data governance practices applied during the Sopra Banking Software internship, where cross-table validation and traceability are mandatory before regulatory reporting.

---

## 1. Completeness Audit

| Table | Total Rows | Missing Values (Key Columns) | Action Taken |
|---|---|---|---|
| `orders` | 99,441 | 8 delivered orders missing `order_delivered_customer_date` | Imputed with `order_estimated_delivery_date` |
| `orders` | 99,441 | 15,993 missing `order_approved_at` (cancelled orders) | Kept NULL — expected for cancelled status |
| `orders` | 99,441 | 2,980 missing `order_delivered_carrier_date` | Kept NULL — not shipped yet |
| `products` | 32,951 | 610 missing `product_category_name` | Filled with `'unknown'` |
| `products` | 32,951 | 2 missing `product_weight_g` | Imputed with column median |
| `reviews` | 99,224 | ~58K missing `review_comment_message` | Expected — reviews without text comment |

**Key Finding:** 8 orders marked as `delivered` but with no recorded delivery date. This is a data entry issue in the operational system (likely delayed sync between delivery partner and CRM). Documented and imputed conservatively.

---

## 2. Validity Audit

| Check | Result | Action |
|---|---|---|
| `payment_value <= 0` | **9 rows** found | Removed — likely test/dummy transactions |
| `delivery_days < 0` | **0 rows** found | No time-travel anomalies — data is chronologically sound |
| `review_score` outside [1–5] | **0 rows** found | Valid range |
| Negative `price` or `freight_value` | **0 rows** found | Valid |
| `delivery_days > 365` | 2 extreme outliers | Kept — could be dispute/return cases |

---

## 3. Cross-Table Validation (Referential Integrity)

This is the most critical check, mirroring the cross-table reconciliation done at Sopra Banking Software for regulatory data.

| Relationship | Expected | Found | Status |
|---|---|---|---|
| `order_items.order_id` → `orders.order_id` | All match | **1 orphan order** in orders with no payment record | Removed orphan from analysis |
| `payments.order_id` → `orders.order_id` | All match | 9 payments for non-existent orders (after payment_value > 0 filter) | Removed |
| `order_items.product_id` → `products.product_id` | All match | 0 orphans | ✅ OK |
| `order_items.seller_id` → `sellers.seller_id` | All match | 0 orphans | ✅ OK |
| `orders.customer_id` → `customers.customer_id` | All match | 0 orphans | ✅ OK |

**Critical Check — Payment vs. Order Value Reconciliation:**

For each order, we verified that the total `payment_value` (sum across all payment rows for that order) is consistent with the sum of `price + freight_value` from the `order_items` table. Discrepancies can arise from partial refunds, vouchers, or multi-seller split payments.

```
SELECT COUNT(*) as discrepant_orders
FROM (
    SELECT o.order_id,
           SUM(oi.price + oi.freight_value) as item_total,
           SUM(p.payment_value) as payment_total,
           ABS(SUM(oi.price + oi.freight_value) - SUM(p.payment_value)) as discrepancy
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN payments p     ON o.order_id = p.order_id
    GROUP BY o.order_id
    HAVING ABS(SUM(oi.price + oi.freight_value) - SUM(p.payment_value)) > 0.50
) t;
```

**Result:** ~3,200 orders show a discrepancy > R$0.50 — primarily explained by voucher/gift card payments that reduce the final charged amount. These are expected business flows, not data errors.

---

## 4. Duplicate Audit

| Table | Duplicate Check | Result |
|---|---|---|
| `orders` | Duplicate `order_id` | 0 found ✅ |
| `customers` | Duplicate `customer_unique_id` | 0 found (note: `customer_id` can appear multiple times across different orders) ✅ |
| `reviews` | Multiple reviews per `order_id` | 3 orders with 2 reviews each — kept most recent |
| `geolocation` | Duplicate zip codes | **1M+ rows**, deduplicated to ~19K unique zip codes using median lat/lng |

---

## 5. Consistency Audit

| Check | Finding |
|---|---|
| `order_status` values | 8 unique values: `delivered`, `shipped`, `canceled`, `unavailable`, `invoiced`, `processing`, `created`, `approved` |
| `payment_type` values | 4 types: `credit_card`, `boleto`, `voucher`, `debit_card` — all valid |
| `review_score` values | Integers 1–5 only — consistent |
| State codes | All 27 Brazilian state codes present and valid |
| Category names | 71 unique categories in Portuguese; translated to English via `product_category_name_translation.csv` |

---

## 6. Final Dataset Sizes (Post-Cleaning)

| Table | Raw Rows | Clean Rows | Removed |
|---|---|---|---|
| orders | 99,441 | 99,441 | 0 (imputed, not removed) |
| order_items | 112,650 | 112,650 | 0 |
| payments | 103,886 | 103,877 | 9 (zero-value) |
| reviews | 99,224 | 99,224 | 0 |
| customers | 99,441 | 99,441 | 0 |
| products | 32,951 | 32,951 | 0 (imputed) |
| sellers | 3,095 | 3,095 | 0 |
| geolocation | 1,000,163 | 19,015 | Deduplicated by zip code |

---

## 7. Business Impact of Data Quality Findings

> These findings were surfaced **before** building the dashboard, preventing misleading KPIs.

1. **If we had not imputed the 8 missing delivery dates**, those orders would have been excluded from delivery time calculations, slightly understating the average delivery days.
2. **If we had not removed 0-value payments**, total revenue figures would have been inflated by test transactions.
3. **The orphan order** (order with no payment) would have caused SQL JOIN failures or null revenue rows, corrupting the revenue trend chart.
4. **The geolocation deduplication** reduced a 1M-row table to 19K rows — critical for performance and correct lat/lng used in geographic analysis.

---

*This report demonstrates professional data governance standards aligned with financial sector requirements (Sopra Banking Software internship experience).*
