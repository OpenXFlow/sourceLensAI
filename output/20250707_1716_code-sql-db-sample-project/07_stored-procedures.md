> Previously, we looked at [Relationships (Foreign Keys)](06_relationships-foreign-keys.md).

# Chapter 7: Stored Procedures
Let's begin exploring this concept. In this chapter, we'll dive into stored procedures, which are precompiled SQL code blocks stored within the database itself. These procedures offer a way to encapsulate and reuse complex business logic.
**Why Stored Procedures?**
Think of a stored procedure like a mini-program residing inside your database. Instead of sending multiple SQL queries from your application to perform a complex task, you can call a single stored procedure. This offers several advantages:
*   **Performance:** Stored procedures are precompiled, meaning the database has already parsed and optimized the code. This can lead to faster execution compared to sending multiple individual queries.
*   **Security:** By granting users permission to execute stored procedures, you can control access to the underlying data and prevent direct manipulation of tables.
*   **Maintainability:** Complex business logic is centralized within the stored procedure. If the logic needs to change, you only need to modify the stored procedure, rather than updating code in multiple applications.
*   **Reduced Network Traffic:** Instead of sending multiple SQL statements over the network, you send only the call to the stored procedure.
**Key Concepts:**
*   **Procedure Definition:** The SQL code that defines the stored procedure, including its name, input parameters, and the SQL statements it executes.
*   **Parameters:** Input values that you pass to the stored procedure. These allow you to customize the procedure's behavior.
*   **Return Values:** Stored procedures can return values, indicating success, failure, or specific data resulting from the procedure's execution.
*   **Transaction Management:** Stored procedures often encompass multiple operations that should be treated as a single unit of work. Transaction management ensures that either all operations succeed or none do, maintaining data consistency.
**How They Work:**
A stored procedure is defined using SQL statements and stored in the database. When you need to execute the procedure, you call it by name, providing any required input parameters. The database then executes the precompiled code block within the procedure.
Consider the `place_order` procedure in our project. It handles the complex process of creating a new order, checking product stock, updating inventory, and calculating the total order amount. Without a stored procedure, this would require multiple round trips between the application and the database.
```python
--- File: schema/04_procedures.sql ---
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
```
The `place_order` stored procedure takes the `user_id`, an array of `product_ids` and an array of the respective `quantities` as input.
It performs several steps:
1.  Creates a new order record in the `orders` table.
2.  Iterates through the list of products to be added to the order.
3.  For each product, it checks the available stock. If there's enough stock, it creates a new record in the `order_items` table, updates the product's stock quantity, and accumulates the total order amount.
4.  Finally, it updates the `orders` table with the calculated total amount.
The following diagram illustrates the flow of the `place_order` stored procedure.
```mermaid
sequenceDiagram
    participant App as Application
    participant SP as Stored Procedure (place_order)
    participant Orders as orders Table
    participant OrderItems as order_items Table
    participant Products as products Table
    App->>SP: Call place_order(user_id, product_ids, quantities)
    activate SP
    SP->>Orders: INSERT INTO orders
    activate Orders
    Orders-->>SP: order_id
    deactivate Orders
    loop For each product
        SP->>Products: SELECT price, stock_quantity FROM products WHERE product_id = product_ids[i]
        activate Products
        Products-->>SP: price, stock_quantity
        deactivate Products
        alt available_stock < quantity
            SP->>App: RAISE EXCEPTION 'Not enough stock'
            deactivate SP
            App->>App: Handle exception
        else
            SP->>OrderItems: INSERT INTO order_items
            activate OrderItems
            OrderItems-->>SP: OK
            deactivate OrderItems
            SP->>Products: UPDATE products SET stock_quantity = stock_quantity - quantity WHERE product_id = product_ids[i]
            activate Products
            Products-->>SP: OK
            deactivate Products
            SP->>SP: Accumulate total amount
        end
    end
    SP->>Orders: UPDATE orders SET total_amount = total_amount WHERE order_id = new_order_id
    activate Orders
    Orders-->>SP: OK
    deactivate Orders
    SP-->>App: new_order_id
    deactivate SP
```
This diagram shows how the application calls the `place_order` stored procedure, which then interacts with several database tables to complete the order process.
You may find it useful to review the sections on [Database Tables](01_database-tables.md), [User Management](07_user-management.md) and [Views](08_views.md) for additional context.
This concludes our look at this topic.

> Next, we will examine [User Management](08_user-management.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*