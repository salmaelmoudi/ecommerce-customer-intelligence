# Power BI Dashboard Specification & Implementation Guide
## E-Commerce Operations & Customer Intelligence
**Author:** Salma El Moudi | Data Analyst & BI Consultant  
**Data Source:** Cleaned Olist Brazilian E-Commerce (`data/powerbi_exports/`)

---

## 1. Data Model Architecture (Star Schema)

In Power BI Desktop, connect to the CSV exports located in `data/powerbi_exports/`. Set up relationships as follows:

```
                  ┌──────────────────────────────┐
                  │      dim_rfm_segments        │
                  │ (customer_unique_id, segment)│
                  └──────────────┬───────────────┘
                                 │ 1
                                 │ *
┌─────────────────────────┐      │      ┌─────────────────────────────┐
│       dim_sellers       │      │      │        dim_products         │
│  (agg_seller_scorecard) │      │      │  (agg_category_performance) │
└───────────┬─────────────┘      │      └──────────────┬──────────────┘
            │ 1                  │                     │ 1
            │ *                  │                     │ *
┌───────────┴────────────────────┴─────────────────────┴──────────────┐
│                            fact_orders                              │
│ (order_id, customer_id, customer_unique_id, seller_id, product_id, │
│  price, freight_value, order_value, order_status, is_late, etc.)    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ *
                                  │ 1
                  ┌───────────────┴──────────────┐
                  │     agg_monthly_revenue      │
                  │   (year_month, date_key)     │
                  └──────────────────────────────┘
```

### Table Relationships
- `fact_orders[customer_unique_id]` (*:1) `dim_rfm_segments[customer_unique_id]`
- `fact_orders[seller_id]` (*:1) `agg_seller_scorecard[seller_id]`
- `fact_orders[product_category_name_english]` (*:1) `agg_category_performance[product_category_name_english]`
- `fact_orders[customer_state]` (*:1) `agg_delivery_by_state[customer_state]`

---

## 2. Core DAX Measures (Copy-Paste Ready)

Create a dedicated measure table called `_Measures` and add the following DAX calculations:

### 2.1 Revenue & Financial KPIs

```dax
Total Revenue = 
SUMX(
    FILTER(fact_orders, fact_orders[order_status] IN {"delivered", "shipped", "invoiced"}),
    fact_orders[order_value]
)
```

```dax
Total Orders = 
DISTINCTCOUNT(fact_orders[order_id])
```

```dax
Average Order Value (AOV) = 
DIVIDE([Total Revenue], [Total Orders], 0)
```

```dax
Total Freight Value = 
SUMX(
    FILTER(fact_orders, fact_orders[order_status] IN {"delivered", "shipped", "invoiced"}),
    fact_orders[freight_value]
)
```

```dax
Freight % of Revenue = 
DIVIDE([Total Freight Value], [Total Revenue], 0)
```

```dax
Previous Month Revenue = 
CALCULATE(
    [Total Revenue],
    DATEADD('Calendar'[Date], -1, MONTH)
)
```

```dax
MoM Revenue Growth % = 
VAR PrevRev = [Previous Month Revenue]
RETURN
DIVIDE([Total Revenue] - PrevRev, PrevRev, 0)
```

---

### 2.2 Operations & Delivery KPIs

```dax
Delivered Orders = 
CALCULATE(
    [Total Orders],
    fact_orders[order_status] = "delivered"
)
```

```dax
Late Orders = 
CALCULATE(
    [Total Orders],
    fact_orders[order_status] = "delivered",
    fact_orders[is_late] = 1
)
```

```dax
Late Delivery Rate % = 
DIVIDE([Late Orders], [Delivered Orders], 0)
```

```dax
On-Time Delivery Rate % = 
1 - [Late Delivery Rate %]
```

```dax
Average Delivery Days = 
AVERAGEX(
    FILTER(fact_orders, fact_orders[order_status] = "delivered" && fact_orders[delivery_days] > 0),
    fact_orders[delivery_days]
)
```

---

### 2.3 Customer & Quality KPIs

```dax
Total Unique Customers = 
DISTINCTCOUNT(fact_orders[customer_unique_id])
```

```dax
Average Review Score = 
AVERAGEX(
    FILTER(fact_orders, NOT(ISBLANK(fact_orders[review_score]))),
    fact_orders[review_score]
)
```

```dax
Repeat Customers Count = 
COUNTROWS(
    FILTER(
        VALUES(fact_orders[customer_unique_id]),
        CALCULATE(DISTINCTCOUNT(fact_orders[order_id])) > 1
    )
)
```

```dax
Repeat Customer % = 
DIVIDE([Repeat Customers Count], [Total Unique Customers], 0)
```

---

## 3. Power BI Report Layout & Visuals

### Page 1 — Executive Overview
- **Visual 1 (Top Cards Row):**
  - Card 1: `Total Revenue` (Formatted as Currency R$ Millions)
  - Card 2: `Total Orders` (Formatted as Whole Number: 99,441)
  - Card 3: `Average Order Value (AOV)` (Formatted as Currency: R$ 140.19)
  - Card 4: `On-Time Delivery Rate %` (Formatted as %: 92.1%)
  - Card 5: `Average Review Score` (Formatted as Decimal: 4.08 / 5)
- **Visual 2 (Main Chart - Line & Clustered Column):**
  - X-Axis: `agg_monthly_revenue[year_month]`
  - Column Values: `Total Revenue`
  - Line Values: `Total Orders`
- **Visual 3 (Bar Chart):**
  - Y-Axis: `agg_category_performance[product_category_name_english]` (Top 10 Filter)
  - X-Axis: `Total Revenue`
- **Visual 4 (Donut Chart):**
  - Legend: `fact_orders[payment_type]`
  - Values: `fact_orders[payment_value]`
- **Slicers:**
  - Date Range Slicer (Order Purchase Timestamp)
  - Order Status Dropdown

---

### Page 2 — Customer Intelligence (RFM)
- **Visual 1 (Column Chart):**
  - X-Axis: `dim_rfm_segments[segment]` (Champions, Loyal, Potential Loyalists, At Risk, Lost)
  - Y-Axis: `Total Unique Customers`
  - Data Labels: On
- **Visual 2 (Donut Chart):**
  - Legend: `dim_rfm_segments[segment]`
  - Values: `Total Unique Customers`
- **Visual 3 (Bar Chart):**
  - Y-Axis: `dim_rfm_segments[segment]`
  - X-Axis: `Average Spend (Monetary)`
- **Visual 4 (Filled Map / Horizontal Bar):**
  - Location / Y-Axis: `fact_orders[customer_state]`
  - Values / Tooltip: `Total Revenue`, `Total Orders`
- **Slicers:**
  - Segment Multi-select Slicer
  - State Slicer

---

### Page 3 — Operations & Delivery Deep Dive
- **Visual 1 (Bar Chart - State SLA Breach):**
  - Y-Axis: `agg_delivery_by_state[customer_state]` (Sorted by Late %)
  - X-Axis: `Late Delivery Rate %`
  - Conditional Formatting: Red (>15%), Amber (8-15%), Teal (<8%)
- **Visual 2 (Column Chart - Impact on Reviews):**
  - X-Axis: `fact_orders[review_score]` (1 to 5)
  - Y-Axis: `Average Delivery Days`
- **Visual 3 (Table - Seller Scorecard):**
  - Columns: `seller_id`, `seller_state`, `Total Orders`, `Total Revenue`, `Late Delivery Rate %`, `Average Review Score`
  - Conditional Formatting on `Late Delivery Rate %` (Red icon if > 20%)
- **Visual 4 (Predictive ML Feature Card):**
  - Display ROC-AUC score (0.6748) and top delay drivers (`estimated_delivery_days`, `freight_value`, `product_weight_g`)
