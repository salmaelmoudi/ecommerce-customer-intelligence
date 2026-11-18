-- ============================================================
-- TABLE SCHEMAS — PostgreSQL DDL
-- E-Commerce Analytics Project
-- Author: Salma El Moudi
-- ============================================================

CREATE TABLE IF NOT EXISTS customers (
    customer_id             VARCHAR PRIMARY KEY,
    customer_unique_id      VARCHAR NOT NULL,
    customer_zip_code_prefix VARCHAR,
    customer_city           VARCHAR,
    customer_state          CHAR(2)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id                        VARCHAR PRIMARY KEY,
    customer_id                     VARCHAR REFERENCES customers(customer_id),
    order_status                    VARCHAR NOT NULL,
    order_purchase_timestamp        TIMESTAMP,
    order_approved_at               TIMESTAMP,
    order_delivered_carrier_date    TIMESTAMP,
    order_delivered_customer_date   TIMESTAMP,
    order_estimated_delivery_date   TIMESTAMP,
    delivery_days                   NUMERIC,
    is_late                         SMALLINT,
    approval_hours                  NUMERIC
);

CREATE TABLE IF NOT EXISTS products (
    product_id                      VARCHAR PRIMARY KEY,
    product_category_name           VARCHAR,
    product_category_name_english   VARCHAR,
    product_name_length             INTEGER,
    product_description_length      INTEGER,
    product_photos_qty              INTEGER,
    product_weight_g                NUMERIC,
    product_length_cm               NUMERIC,
    product_height_cm               NUMERIC,
    product_width_cm                NUMERIC
);

CREATE TABLE IF NOT EXISTS sellers (
    seller_id               VARCHAR PRIMARY KEY,
    seller_zip_code_prefix  VARCHAR,
    seller_city             VARCHAR,
    seller_state            CHAR(2)
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id            VARCHAR REFERENCES orders(order_id),
    order_item_id       INTEGER,
    product_id          VARCHAR REFERENCES products(product_id),
    seller_id           VARCHAR REFERENCES sellers(seller_id),
    shipping_limit_date TIMESTAMP,
    price               NUMERIC NOT NULL,
    freight_value       NUMERIC NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS payments (
    order_id                VARCHAR REFERENCES orders(order_id),
    payment_sequential      INTEGER,
    payment_type            VARCHAR,
    payment_installments    INTEGER,
    payment_value           NUMERIC,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id               VARCHAR PRIMARY KEY,
    order_id                VARCHAR REFERENCES orders(order_id),
    review_score            SMALLINT CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS geolocation (
    geolocation_zip_code_prefix VARCHAR PRIMARY KEY,
    geolocation_lat             NUMERIC,
    geolocation_lng             NUMERIC,
    geolocation_city            VARCHAR,
    geolocation_state           CHAR(2)
);
