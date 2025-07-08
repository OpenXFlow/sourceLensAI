> Previously, we looked at [Product Catalog](05_product-catalog.md).

# Chapter 6: Relationships (Foreign Keys)
Let's begin exploring this concept. This chapter focuses on relationships between tables in our database, specifically how to establish and understand foreign key constraints. Foreign keys are essential for maintaining data integrity and creating meaningful connections between related data.
**Why Relationships?**
Imagine you're building a social media application. You have a table for `users` and a table for `posts`. Each post is associated with a specific user. How do you represent this association in your database? This is where relationships come in. A foreign key in the `posts` table would point to the `user_id` in the `users` table, indicating which user created that post.
Think of it like a family tree. Each person is a record, and relationships (parent-child, sibling-sibling) link them together. Without these links, you'd just have a bunch of individuals without any context.
**Key Concepts: Foreign Keys**
A *foreign key* is a column (or set of columns) in one table that refers to the *primary key* of another table. It establishes a link between the two tables. The table containing the foreign key is called the *child table* or *referencing table*, and the table containing the primary key is called the *parent table* or *referenced table*.
**How Foreign Keys Work in `20250707_1716_code-sql-db-sample-project`**
In our project, several tables have foreign key relationships:
*   `orders` table: `user_id` (foreign key) references `users(user_id)`
*   `order_items` table: `order_id` (foreign key) references `orders(order_id)` and `product_id` (foreign key) references `products(product_id)`
*   `product_reviews` table: `product_id` (foreign key) references `products(product_id)` and `user_id` (foreign key) references `users(user_id)`
Let's look at the SQL that creates these relationships. This code snippet is from the `schema/02_constraints_and_indexes.sql` file, which we explored earlier when discussing [Constraints (Primary Keys, Checks)](02_constraints-primary-keys-checks.md).
```python
--- File: schema/02_constraints_and_indexes.sql ---
-- Foreign Keys
ALTER TABLE orders ADD CONSTRAINT fk_orders_user_id
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;
ALTER TABLE order_items ADD CONSTRAINT fk_order_items_order_id
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE;
ALTER TABLE order_items ADD CONSTRAINT fk_order_items_product_id
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE RESTRICT;
ALTER TABLE product_reviews ADD CONSTRAINT fk_reviews_product_id
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE;
ALTER TABLE product_reviews ADD CONSTRAINT fk_reviews_user_id
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;
```
*   `ALTER TABLE ... ADD CONSTRAINT`:  This SQL command adds a new constraint to an existing table.
*   `FOREIGN KEY (column_name)`:  Specifies the column(s) in the current table that will act as the foreign key.
*   `REFERENCES table_name(column_name)`: Specifies the table and column that the foreign key references.
*   `ON DELETE CASCADE` and `ON DELETE RESTRICT`: These clauses define what happens when a record in the parent table is deleted.
    *   `ON DELETE CASCADE`: If a record in the parent table is deleted, all related records in the child table are also deleted.  For example, if a user is deleted from the `users` table, all their orders in the `orders` table will also be deleted.
    *   `ON DELETE RESTRICT`:  The deletion is prevented if there are any related records in the child table.  For example, you cannot delete a product from the `products` table if there are any order items referencing that product in the `order_items` table.
**Why `ON DELETE CASCADE` and `ON DELETE RESTRICT`?**
These options are critical for maintaining *referential integrity*. Referential integrity ensures that relationships between tables remain consistent and valid.  Without it, you could end up with "orphaned" records in the child table that refer to non-existent records in the parent table.
Here's a simple sequence diagram illustrating a successful order creation, highlighting the foreign key relationship between `orders` and `users`:
```mermaid
sequenceDiagram
    participant User
    participant Application
    participant Database
    User->>Application: Submits order request
    activate Application
    Application->>Database:  Insert order (user_id=X)
    activate Database
    Database->>Database: Verify user_id exists in users table (FK check)
    alt user_id exists
        Database-->>Application: OK
        deactivate Database
        Application->>Database: Insert order items (order_id=Y, product_id=Z)
        activate Database
        Database->>Database: Verify order_id & product_id exist (FK check)
        Database-->>Application: OK
        deactivate Database
        Application-->>User: Order confirmation
    else user_id does not exist
        Database-->>Application: Error: Invalid user_id
        deactivate Database
        Application-->>User: Error: Order creation failed
    end
    deactivate Application
```
This diagram shows the application creating an order. Notice how the database verifies the `user_id` during the order creation process. If the `user_id` doesn't exist in the `users` table (meaning there is no user with that ID), the database will reject the insertion, thus preserving referential integrity. We will cover the data insertion process in more detail in the chapter on [Data Seeding](05_data-seeding.md).
Understanding and properly implementing foreign keys is crucial for building robust and reliable database applications. Without them, data can become inconsistent and difficult to manage.
This concludes our look at this topic.

> Next, we will examine [Stored Procedures](07_stored-procedures.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*