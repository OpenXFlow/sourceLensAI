-- 04_procedures.sql
-- Defines stored procedures for common business logic.

CREATE OR REPLACE FUNCTION place_order(
    p_user_id INT,
    p_product_ids INT[],
    p_quantities INT[]
) RETURNS INT AS $$
DECLARE
    new_order_id INT;
    total_order_amount DECIMAL(10, 2) := 0;
    product_price DECIMAL(10, 2);
    available_stock INT;
    i INT;
BEGIN
    -- Create a new order
    INSERT INTO orders (user_id, status, total_amount)
    VALUES (p_user_id, 'pending', 0)
    RETURNING order_id INTO new_order_id;

    -- Loop through products to add to the order
    FOR i IN 1..array_length(p_product_ids, 1)
    LOOP
        -- Check stock and get price
        SELECT price, stock_quantity INTO product_price, available_stock
        FROM products WHERE product_id = p_product_ids[i];

        IF available_stock < p_quantities[i] THEN
            RAISE EXCEPTION 'Not enough stock for product ID %', p_product_ids[i];
        END IF;

        -- Add to order_items
        INSERT INTO order_items (order_id, product_id, quantity, price_per_unit)
        VALUES (new_order_id, p_product_ids[i], p_quantities[i], product_price);

        -- Update stock
        UPDATE products SET stock_quantity = stock_quantity - p_quantities[i]
        WHERE product_id = p_product_ids[i];

        -- Accumulate total amount
        total_order_amount := total_order_amount + (p_quantities[i] * product_price);
    END LOOP;

    -- Update the total amount on the order
    UPDATE orders SET total_amount = total_order_amount
    WHERE order_id = new_order_id;

    RETURN new_order_id;
END;
$$ LANGUAGE plpgsql;