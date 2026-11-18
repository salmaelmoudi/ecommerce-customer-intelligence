-- ============================================================
-- E-COMMERCE ANALYTICS — ANALYTICAL SQL QUERIES
-- Author: Salma El Moudi
-- Database: ecommerce_analytics (PostgreSQL)
-- ============================================================
-- Run these after the data_cleaning.py script has loaded
-- all tables into the ecommerce_analytics database.
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- Q1. MONTHLY REVENUE TREND WITH MoM GROWTH (Window Function)
-- ─────────────────────────────────────────────────────────────
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
        ROUND(SUM(oi.price + oi.freight_value)::NUMERIC, 2) AS total_revenue,
        COUNT(DISTINCT o.order_id) AS total_orders
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY 1
),
revenue_with_lag AS (
    SELECT
        month,
        total_revenue,
        total_orders,
        LAG(total_revenue) OVER (ORDER BY month) AS prev_month_revenue
    FROM monthly_revenue
)
SELECT
    TO_CHAR(month, 'YYYY-MM')                                   AS month,
    total_revenue,
    total_orders,
    prev_month_revenue,
    ROUND(
        ((total_revenue - prev_month_revenue) / NULLIF(prev_month_revenue, 0) * 100)::NUMERIC,
        1
    )                                                            AS mom_growth_pct
FROM revenue_with_lag
ORDER BY month;


-- ─────────────────────────────────────────────────────────────
-- Q2. TOP 10 PRODUCT CATEGORIES BY REVENUE
-- ─────────────────────────────────────────────────────────────
SELECT
    COALESCE(p.product_category_name_english, p.product_category_name) AS category,
    COUNT(DISTINCT oi.order_id)                                          AS total_orders,
    ROUND(SUM(oi.price)::NUMERIC, 2)                                     AS total_revenue,
    ROUND(SUM(oi.freight_value)::NUMERIC, 2)                             AS total_freight,
    ROUND(AVG(oi.price)::NUMERIC, 2)                                     AS avg_item_price,
    ROUND(
        (SUM(oi.freight_value) / NULLIF(SUM(oi.price + oi.freight_value), 0) * 100)::NUMERIC,
        1
    )                                                                    AS freight_pct_revenue
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN orders o   ON oi.order_id   = o.order_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY 1
ORDER BY total_revenue DESC
LIMIT 10;


-- ─────────────────────────────────────────────────────────────
-- Q3. DELIVERY PERFORMANCE — OVERALL KPIs
-- ─────────────────────────────────────────────────────────────
SELECT
    COUNT(*)                                                          AS total_delivered,
    ROUND(AVG(delivery_days)::NUMERIC, 1)                             AS avg_delivery_days,
    PERCENTILE_CONT(0.5)
        WITHIN GROUP (ORDER BY delivery_days)                         AS median_delivery_days,
    SUM(is_late)                                                      AS late_deliveries,
    ROUND((SUM(is_late) / COUNT(*)::NUMERIC * 100), 1)                AS late_delivery_pct,
    ROUND(AVG(CASE WHEN is_late = 0 THEN delivery_days END)::NUMERIC, 1) AS avg_days_on_time,
    ROUND(AVG(CASE WHEN is_late = 1 THEN delivery_days END)::NUMERIC, 1) AS avg_days_late
FROM orders
WHERE order_status = 'delivered'
  AND delivery_days IS NOT NULL
  AND delivery_days > 0;


-- ─────────────────────────────────────────────────────────────
-- Q4. DELIVERY PERFORMANCE BY STATE (Geographic Analysis)
-- ─────────────────────────────────────────────────────────────
SELECT
    c.customer_state                                                   AS state,
    COUNT(DISTINCT o.order_id)                                         AS total_orders,
    ROUND(AVG(o.delivery_days)::NUMERIC, 1)                            AS avg_delivery_days,
    SUM(o.is_late)                                                     AS late_deliveries,
    ROUND((SUM(o.is_late)::NUMERIC / COUNT(*) * 100), 1)               AS late_pct,
    ROUND(AVG(CASE WHEN o.is_late = 1
        THEN (o.delivery_days - EXTRACT(EPOCH FROM
            (o.order_estimated_delivery_date - o.order_purchase_timestamp)
        ) / 86400)
    END)::NUMERIC, 1)                                                  AS avg_days_overdue
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered'
  AND o.delivery_days > 0
GROUP BY 1
ORDER BY late_pct DESC
LIMIT 15;


-- ─────────────────────────────────────────────────────────────
-- Q5. SELLER PERFORMANCE SCORECARD (Window Functions + RANK)
-- ─────────────────────────────────────────────────────────────
WITH seller_stats AS (
    SELECT
        oi.seller_id,
        s.seller_state,
        COUNT(DISTINCT oi.order_id)                                   AS total_orders,
        ROUND(SUM(oi.price + oi.freight_value)::NUMERIC, 2)           AS total_revenue,
        ROUND(AVG(r.review_score)::NUMERIC, 2)                        AS avg_review_score,
        SUM(o.is_late)                                                AS late_deliveries,
        ROUND((SUM(o.is_late)::NUMERIC / COUNT(DISTINCT oi.order_id) * 100), 1) AS late_pct
    FROM order_items oi
    JOIN orders  o  ON oi.order_id  = o.order_id
    JOIN sellers s  ON oi.seller_id = s.seller_id
    LEFT JOIN reviews r ON o.order_id = r.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY oi.seller_id, s.seller_state
    HAVING COUNT(DISTINCT oi.order_id) >= 10  -- at least 10 orders to be meaningful
)
SELECT
    seller_id,
    seller_state,
    total_orders,
    total_revenue,
    avg_review_score,
    late_deliveries,
    late_pct,
    RANK() OVER (ORDER BY late_pct DESC)        AS late_rank,
    RANK() OVER (ORDER BY avg_review_score DESC) AS quality_rank,
    RANK() OVER (ORDER BY total_revenue DESC)    AS revenue_rank
FROM seller_stats
ORDER BY late_pct DESC
LIMIT 20;


-- ─────────────────────────────────────────────────────────────
-- Q6. PARETO ANALYSIS — Do 20% of products generate 80% revenue?
-- ─────────────────────────────────────────────────────────────
WITH product_revenue AS (
    SELECT
        oi.product_id,
        ROUND(SUM(oi.price)::NUMERIC, 2) AS revenue
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY 1
),
ranked AS (
    SELECT
        product_id,
        revenue,
        SUM(revenue) OVER ()                              AS total_revenue,
        SUM(revenue) OVER (ORDER BY revenue DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_revenue,
        ROW_NUMBER() OVER (ORDER BY revenue DESC)         AS rank_num,
        COUNT(*) OVER ()                                   AS total_products
    FROM product_revenue
)
SELECT
    rank_num,
    product_id,
    revenue,
    ROUND((cumulative_revenue / total_revenue * 100)::NUMERIC, 2)  AS cumulative_revenue_pct,
    ROUND((rank_num::NUMERIC / total_products * 100), 2)            AS product_pct
FROM ranked
WHERE rank_num <= 100
ORDER BY rank_num;


-- ─────────────────────────────────────────────────────────────
-- Q7. CUSTOMER RETENTION — Repeat vs One-Time Buyers
-- ─────────────────────────────────────────────────────────────
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_count,
        MIN(o.order_purchase_timestamp) AS first_purchase,
        MAX(o.order_purchase_timestamp) AS last_purchase,
        ROUND(SUM(oi.price + oi.freight_value)::NUMERIC, 2) AS total_spent
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY c.customer_unique_id
)
SELECT
    CASE
        WHEN order_count = 1  THEN 'One-Time Buyer'
        WHEN order_count <= 3 THEN 'Occasional Buyer (2-3 orders)'
        ELSE 'Loyal Buyer (4+ orders)'
    END                                              AS customer_segment,
    COUNT(*)                                         AS customer_count,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER () * 100, 1) AS pct_of_customers,
    ROUND(AVG(total_spent)::NUMERIC, 2)              AS avg_lifetime_value,
    ROUND(AVG(order_count)::NUMERIC, 1)              AS avg_order_count
FROM customer_orders
GROUP BY 1
ORDER BY avg_lifetime_value DESC;


-- ─────────────────────────────────────────────────────────────
-- Q8. COHORT RETENTION — Monthly Cohort Analysis
-- ─────────────────────────────────────────────────────────────
WITH first_purchase AS (
    SELECT
        c.customer_unique_id,
        DATE_TRUNC('month', MIN(o.order_purchase_timestamp)) AS cohort_month
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY c.customer_unique_id
),
all_purchases AS (
    SELECT
        c.customer_unique_id,
        DATE_TRUNC('month', o.order_purchase_timestamp) AS purchase_month
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
),
cohort_data AS (
    SELECT
        fp.cohort_month,
        ap.purchase_month,
        EXTRACT(EPOCH FROM (ap.purchase_month - fp.cohort_month)) / 2592000 AS period_number,
        COUNT(DISTINCT ap.customer_unique_id) AS customer_count
    FROM first_purchase fp
    JOIN all_purchases ap USING (customer_unique_id)
    GROUP BY 1, 2, 3
),
cohort_sizes AS (
    SELECT cohort_month, customer_count AS cohort_size
    FROM cohort_data WHERE period_number = 0
)
SELECT
    TO_CHAR(cd.cohort_month, 'YYYY-MM')     AS cohort,
    cs.cohort_size,
    cd.period_number::INT                   AS month_number,
    cd.customer_count,
    ROUND((cd.customer_count::NUMERIC / cs.cohort_size * 100), 1) AS retention_rate_pct
FROM cohort_data cd
JOIN cohort_sizes cs ON cd.cohort_month = cs.cohort_month
WHERE cd.period_number BETWEEN 0 AND 6
ORDER BY cd.cohort_month, cd.period_number;


-- ─────────────────────────────────────────────────────────────
-- Q9. AVERAGE TIME TO APPROVE ORDERS (Date Math)
-- ─────────────────────────────────────────────────────────────
SELECT
    DATE_TRUNC('month', order_purchase_timestamp)   AS month,
    COUNT(*)                                         AS total_orders,
    ROUND(AVG(approval_hours)::NUMERIC, 1)           AS avg_approval_hours,
    ROUND(PERCENTILE_CONT(0.5)
        WITHIN GROUP (ORDER BY approval_hours)::NUMERIC, 1) AS median_approval_hours,
    COUNT(*) FILTER (WHERE approval_hours > 24)      AS orders_slow_approval,
    ROUND(
        COUNT(*) FILTER (WHERE approval_hours > 24)::NUMERIC / COUNT(*) * 100, 1
    )                                                AS pct_slow_approval
FROM orders
WHERE order_status NOT IN ('canceled', 'unavailable')
  AND approval_hours IS NOT NULL
  AND approval_hours >= 0
GROUP BY 1
ORDER BY 1;


-- ─────────────────────────────────────────────────────────────
-- Q10. PAYMENT METHOD ANALYSIS
-- ─────────────────────────────────────────────────────────────
SELECT
    payment_type,
    COUNT(DISTINCT order_id)                          AS total_orders,
    ROUND(SUM(payment_value)::NUMERIC, 2)             AS total_revenue,
    ROUND(AVG(payment_value)::NUMERIC, 2)             AS avg_payment_value,
    ROUND(AVG(payment_installments)::NUMERIC, 1)      AS avg_installments,
    ROUND(COUNT(DISTINCT order_id)::NUMERIC /
        SUM(COUNT(DISTINCT order_id)) OVER () * 100, 1) AS pct_orders
FROM payments
WHERE payment_value > 0
GROUP BY payment_type
ORDER BY total_revenue DESC;


-- ─────────────────────────────────────────────────────────────
-- Q11. REVIEW SCORE DISTRIBUTION vs DELIVERY PERFORMANCE
-- ─────────────────────────────────────────────────────────────
SELECT
    r.review_score,
    COUNT(*)                                              AS order_count,
    ROUND(AVG(o.delivery_days)::NUMERIC, 1)               AS avg_delivery_days,
    ROUND(AVG(CASE WHEN o.is_late = 1 THEN 1.0 ELSE 0.0 END) * 100, 1) AS late_pct
FROM reviews r
JOIN orders o ON r.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.delivery_days > 0
GROUP BY r.review_score
ORDER BY r.review_score;


-- ─────────────────────────────────────────────────────────────
-- Q12. REVENUE BY DAY OF WEEK (Operational Insight)
-- ─────────────────────────────────────────────────────────────
SELECT
    TO_CHAR(order_purchase_timestamp, 'Day')           AS day_of_week,
    EXTRACT(ISODOW FROM order_purchase_timestamp)      AS dow_num,
    COUNT(DISTINCT o.order_id)                         AS total_orders,
    ROUND(AVG(oi.price + oi.freight_value)::NUMERIC, 2) AS avg_order_value
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY 1, 2
ORDER BY 2;


-- ─────────────────────────────────────────────────────────────
-- Q13. TOP REVENUE STATES (Customer Geography)
-- ─────────────────────────────────────────────────────────────
SELECT
    c.customer_state,
    COUNT(DISTINCT c.customer_unique_id)              AS unique_customers,
    COUNT(DISTINCT o.order_id)                        AS total_orders,
    ROUND(SUM(oi.price + oi.freight_value)::NUMERIC, 2) AS total_revenue,
    ROUND(AVG(oi.price + oi.freight_value)::NUMERIC, 2) AS avg_order_value
FROM customers c
JOIN orders o      ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY 1
ORDER BY total_revenue DESC
LIMIT 10;


-- ─────────────────────────────────────────────────────────────
-- Q14. SELLER CATEGORY RANK (RANK per category)
-- ─────────────────────────────────────────────────────────────
WITH seller_category AS (
    SELECT
        oi.seller_id,
        COALESCE(p.product_category_name_english, p.product_category_name) AS category,
        ROUND(SUM(oi.price)::NUMERIC, 2)              AS revenue,
        COUNT(DISTINCT oi.order_id)                   AS orders
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    JOIN orders o   ON oi.order_id   = o.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY 1, 2
)
SELECT
    category,
    seller_id,
    revenue,
    orders,
    RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS rank_in_category
FROM seller_category
WHERE rank_in_category <= 3
ORDER BY category, rank_in_category;


-- ─────────────────────────────────────────────────────────────
-- Q15. POWER BI MASTER VIEW — Flattened fact table for BI tool
-- (Save as a VIEW for direct Power BI connection)
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_orders_master AS
SELECT
    o.order_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    o.delivery_days,
    o.is_late,
    o.approval_hours,
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    s.seller_id,
    s.seller_city,
    s.seller_state,
    p.product_id,
    COALESCE(p.product_category_name_english, p.product_category_name) AS category,
    p.product_weight_g,
    oi.price,
    oi.freight_value,
    oi.price + oi.freight_value                                         AS order_value,
    pay.payment_type,
    pay.payment_installments,
    pay.payment_value,
    r.review_score
FROM orders o
LEFT JOIN customers  c   ON o.customer_id   = c.customer_id
LEFT JOIN order_items oi ON o.order_id      = oi.order_id
LEFT JOIN products   p   ON oi.product_id   = p.product_id
LEFT JOIN sellers    s   ON oi.seller_id    = s.seller_id
LEFT JOIN payments   pay ON o.order_id      = pay.order_id
LEFT JOIN reviews    r   ON o.order_id      = r.order_id;
