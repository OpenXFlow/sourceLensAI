> Previously, we looked at [Views](09_views.md).

# Chapter 10: Architecture Diagrams
## Class Diagram
Key classes and their relationships in **20250707_1716_code-sql-db-sample-project**.
```mermaid
classDiagram
    class SQLTable {
        +tableName: str
        +columns: List[str]
        +constraints: List[str]
    }
    class SQLView {
        +viewName: str
        +definition: str
    }
    class SQLProcedure {
        +procedureName: str
        +parameters: List[str]
        +body: str
    }
```
## Package Dependencies
High-level module and package structure of **20250707_1716_code-sql-db-sample-project**.
```mermaid
graph TD
    A["README.md"]
    B["data/01_seed_data.sql"]
    C["schema/01_tables.sql"]
    D["schema/02_constraints_and_indexes.sql"]
    E["schema/03_views.sql"]
    F["schema/04_procedures.sql"]
    A --> B
    A --> C
    C --> D
    D --> E
    E --> F
```
## Sequence Diagrams
These diagrams illustrate various interaction scenarios, showcasing operations between components for specific use cases.
### User logs in, authenticates against the database, and views the product catalog.
```mermaid
sequenceDiagram
    participant User
    participant WebApp
    participant AuthServer
    participant Database
    User->>WebApp: Login request
    activate WebApp
    WebApp->>AuthServer: Authenticate request
    activate AuthServer
    AuthServer->>Database: Verify credentials
    activate Database
    Database-->>AuthServer: Credentials verified
    deactivate Database
    AuthServer-->>WebApp: Authentication token
    deactivate AuthServer
    WebApp->>WebApp: Store authentication token
    WebApp-->>User: Login successful
    WebApp->>WebApp: Request product catalog
    WebApp->>Database: Retrieve product catalog
    activate Database
    Database-->>WebApp: Product catalog data
    deactivate Database
    WebApp-->>User: Display product catalog
    deactivate WebApp
```
### User adds a product to their shopping cart, triggering database updates for inventory.
```mermaid
sequenceDiagram
    participant User
    participant API
    participant Database
    User->>API: Add product to cart
    activate API
    API->>Database: Check inventory
    activate Database
    Database-->>API: Inventory count
    alt Inventory available
        API->>Database: Update inventory
        Database-->>API: Inventory updated
        API-->>User: Product added to cart
    else Inventory unavailable
        API-->>User: Product out of stock
    end
    deactivate Database
    deactivate API
```
### A stored procedure is executed to calculate and apply discounts to an order.
```mermaid
sequenceDiagram
    participant User
    participant Application
    participant Database
    User->>Application: Initiate Order Discount Calculation
    activate Application
    Application->>Database: Execute Stored Procedure to Apply Discounts
    activate Database
    alt Success
        Database-->>Application: Discount Applied Successfully
        Application-->>User: Order Updated with Discounts
    else Failure
        Database-->>Application: Error Applying Discounts
        Application-->>User: Error: Discount Application Failed
    end
    deactivate Database
    deactivate Application
```
### The system attempts to insert a new product with invalid data, violating database constraints.
```mermaid
sequenceDiagram
    participant User
    participant API
    participant Database
    participant Logger
    User->>API: Attempt to create product with invalid data
    activate API
    API->>Database: Insert new product
    activate Database
    alt Insert fails due to constraint violation
        Database-->>API: Constraint violation error
        API->>Logger: Log error
        activate Logger
        Logger-->>API: Logged error
        deactivate Logger
        API-->>User: Error: Invalid product data
    else Insert succeeds (unexpected)
        Database-->>API: Success (unexpected)
        API->>Logger: Log unexpected success
        activate Logger
        Logger-->>API: Logged unexpected success
        deactivate Logger
        API-->>User: Success (unexpected)
    end
    deactivate Database
    deactivate API
```
### An administrator seeds the database with initial product catalog data upon application startup.
```mermaid
sequenceDiagram
    participant Administrator
    participant Application
    participant Database
    Administrator->>Application: Start application
    activate Application
    Application->>Application: Check if database is empty
    Application->>Database: Query for product count
    activate Database
    Database-->>Application: Product count (e.g., 0)
    deactivate Database
    alt Database is empty
        Application->>Application: Seed database with initial data
        Application->>Database: Insert initial product data
        activate Database
        Database-->>Application: Data insertion complete
        deactivate Database
    else Database is not empty
        Application->>Application: Database already seeded
    end
    Application-->>Administrator: Application started successfully
    deactivate Application
```

> Next, we will examine [Code Inventory](11_code_inventory.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*