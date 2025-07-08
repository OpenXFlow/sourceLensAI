-- 03_views.sql
-- Creates simplified views for reporting and easier querying.

CREATE OR REPLACE VIEW recent_orders_summary AS
SELECT 
    o.order_id,
    o.order_date,
    u.email,
    o.total_amount,
    o.status
FROM orders o
JOIN users u ON o.user_id = u.user_id
WHERE o.order_date > (NOW() - INTERVAL '30 days')
ORDER BY o.order_date DESC;

CREATE OR REPLACE VIEW product_sales_report AS
SELECT 
    p.product_id,
    p.name AS product_name,
    SUM(oi.quantity) AS total_units_sold,
    SUM(oi.quantity * oi.price_per_unit) AS total_revenue
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
GROUP BY p.product_id, p.name
ORDER BY total_revenue DESC;