# Business Case Study: E-Commerce Operations & Customer Intelligence
### Turnaround Strategy for Marketplace Delivery SLAs and Customer Lifetime Value
**Prepared by:** Salma El Moudi — Data Analyst & BI Consultant  
**Target Audience:** Chief Operating Officer (COO), VP of Growth & E-Commerce Business Owners  
**Date:** November 2026

---

## 1. Executive Summary

A commercial marketplace processing **99,441 orders** and **R$ 15.67M in gross revenue** faced customer churn and declining review scores. Although top-line order volume increased by over 40% year-on-year, operating margins were pressured by freight inefficiencies and growing customer complaints.

This analytics case study established an automated end-to-end intelligence framework connecting raw transactional, customer, seller, and logistics data. 

### Key Findings at a Glance:
1. **Late Deliveries Destroy Customer Trust:** A non-parametric Mann-Whitney test confirmed that orders delivered late suffer an average rating drop from **4.29 to 2.57 stars** ($p < 0.001$).
2. **The 80/20 Seller Bottleneck:** Less than 12% of sellers generate over 75% of delivery delays.
3. **The Retention Deficit:** Over **90% of customers are one-time buyers**. The top RFM segment ("Champions") spends **8x more** than lost customers, yet receives the exact same retention marketing.
4. **Logistics Asymmetry:** Outlying states (Amazonas, Roraima, Amapá) experience late delivery rates exceeding **25%**, compared to just **5.4%** in São Paulo.

---

## 2. Business Objectives & Analytical Scope

| Objective | Target Metric | Business Stakeholder |
|---|---|---|
| Reduce late delivery churn | Cut late delivery rate from 7.9% to < 5.0% | Head of Logistics & Operations |
| Protect customer review ratings | Lift average review from 4.08 to > 4.35 | VP of Customer Experience |
| Increase customer lifetime value (LTV) | Increase repeat purchase rate from 9.2% to 15% | Chief Marketing Officer (CMO) |
| Seller performance governance | Enforce delivery SLAs across 3,000+ sellers | Marketplace Partner Manager |

---

## 3. Data Governance & Audit (The QA Foundation)

Before computing any KPIs, rigorous data quality controls were implemented based on banking-grade validation standards:
- **Missing Delivery Dates:** 8 delivered orders were missing timestamps; conservative imputation prevented systematic underestimation of average delivery durations.
- **Zero-Value Transactions:** 9 payment records with zero or negative amounts were purged.
- **Cross-Table Reconciliation:** Verified that total payments matched item costs plus freight values within 0.5% tolerance, identifying voucher-offset behaviors.
- **Geographic Normalization:** Deduplicated 1,000,000+ noisy geolocation coordinates into 19,015 distinct zip centroids.

---

## 4. Key Analytical Insights

### 4.1 Revenue Performance & Payment Dynamics
- **Total Revenue:** R$ 15,665,892 across 99,441 unique orders.
- **Average Order Value (AOV):** R$ 140.19.
- **Payment Split:** 
  - Credit Card: **74.1%** of revenue (with an average of 3.6 installment splits)
  - Boleto Bancário: **19.1%**
  - Voucher: **4.1%**
  - Debit Card: **2.7%**
- **Seasonality:** Strong November peak corresponding to Black Friday promotions, followed by post-holiday operational strain.

### 4.2 Customer RFM Segmentation
Using Recency (days since last purchase), Frequency (order count), and Monetary spend, 94,697 unique buyers were categorized:
- **Champions (16.3% / 15,471 buyers):** High frequency, recent, high spend. Average LTV is the highest across all tiers.
- **Loyal Customers (33.3% / 31,548 buyers):** Consistent purchasers across multiple categories.
- **Potential Loyalists (34.2% / 32,353 buyers):** Recent purchasers needing targeted incentives for second purchase.
- **At Risk (12.9% / 12,258 buyers):** High past spend, but inactive for > 180 days.
- **Lost Customers (1.6% / 1,546 buyers):** Long inactivity, low spend.

### 4.3 Operations & SLA Breach Drivers
- **Overall On-Time Rate:** 92.1% (7.9% late delivery rate).
- **Average Delivery Time:** 12.5 days for on-time orders vs. **28.3 days** for delayed orders.
- **Seller Scorecard:** A cohort of 15 persistent offenders generated late rates above 40%, degrading the entire platform reputation.

### 4.4 Machine Learning Predictive Model
A balanced **Logistic Regression** model was trained to predict order delays at checkout:
- **ROC-AUC:** `0.6748`
- **Primary Delay Driver:** `estimated_delivery_days` (promising longer windows correlates with chronic carrier delays).
- **Secondary Drivers:** `freight_value` (higher freight = complex rural routing) and `product_weight_g` (bulky freight bottlenecks).

---

## 5. Strategic Recommendations & Action Plan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ACTION ROADMAP (90 DAYS)                              │
├────────────────────────────────┬────────────────────────────────────────────┤
│ Phase 1: Operational Triage    │ • Terminate / sanction bottom 2% of sellers│
│ (Days 1–30)                    │   with chronic late delivery rates (>35%)  │
│                                │ • Implement automated Power BI SLA alerts  │
├────────────────────────────────┼────────────────────────────────────────────┤
│ Phase 2: CRM & Retention       │ • Trigger automated 15% discount voucher   │
│ (Days 31–60)                   │   to "Potential Loyalists" at Day 21       │
│                                │ • VIP concierge support for "Champions"    │
├────────────────────────────────┼────────────────────────────────────────────┤
│ Phase 3: Logistics Engineering │ • Implement checkout delay scoring model   │
│ (Days 61–90)                   │   to warn buyers in high-risk zip codes    │
│                                │ • Renegotiate regional carrier contracts   │
└────────────────────────────────┴────────────────────────────────────────────┘
```

---

## 6. Freelance Value Proposition & Offering

For small-to-medium e-commerce brands, this case study serves as a direct pitch:

> **"Turn Your Messy Transactional Data into an Automated Revenue & Logistics Dashboard in 7 Days."**
> 
> - **Client Need:** Founders have Shopify/WooCommerce stores but fly blind on customer churn and seller delays.
> - **Deliverable:** Automated data cleaning pipeline + PostgreSQL analytical layer + Interactive Power BI Executive Dashboard.
> - **Standard Retainer / Project Fee:** 10,000–25,000 MAD per implementation.
