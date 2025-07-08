-- 01_seed_data.sql
-- Populates the database with some initial sample data.

INSERT INTO users (email, password_hash, first_name, last_name) VALUES
('john.doe@example.com', 'hashed_pw_1', 'John', 'Doe'),
('jane.smith@example.com', 'hashed_pw_2', 'Jane', 'Smith');

INSERT INTO products (sku, name, description, price, stock_quantity) VALUES
('LPTP-001', 'Pro Laptop', 'A high-performance laptop for professionals.', 1200.00, 50),
('SMT-002', 'Smart Mouse', 'An ergonomic wireless mouse.', 75.50, 200),
('KBD-003', 'Mechanical Keyboard', 'A backlit mechanical keyboard for typing enthusiasts.', 150.00, 100);

-- Note: Orders would typically be placed via the stored procedure.
-- This is a manual insertion for demonstration.
INSERT INTO orders (user_id, status, total_amount) VALUES
(1, 'shipped', 1275.50);

INSERT INTO order_items (order_id, product_id, quantity, price_per_unit) VALUES
(1, 1, 1, 1200.00),
(1, 2, 1, 75.50);

INSERT INTO product_reviews (product_id, user_id, rating, comment) VALUES
(1, 2, 5, 'Absolutely fantastic laptop! Fast and reliable.'),
(3, 1, 4, 'Great keyboard, very clicky. A bit loud but feels great.');