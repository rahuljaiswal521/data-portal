# Glossary

Key terms used throughout the Data Platform Portal and the Medallion Architecture.

---

## A

**Append mode**
A CDC mode where every incoming record is inserted as a new row, with no updates or history tracking. Used for immutable records like event logs.

**Attribute-level source priority**
A Silver layer feature where multiple Bronze sources can contribute different attributes to the same canonical entity. If two sources have the same attribute, the one with the lower priority number wins (1 = highest priority).

**Audit log**
A Delta Table (`dev.bronze_meta.ingestion_audit_log`) that records every pipeline run: start time, end time, records loaded, records quarantined, status. Queried by the portal's Runs tab.

---

## B

**Bronze layer**
The first layer in the Medallion Architecture. Stores raw data as-is from source systems, with SCD2 history tracking and data quality quarantine. Bronze tables are in the `dev.bronze` schema.

**Business key**
One or more columns that uniquely identify a record in a Silver entity. Used as the join key when merging data from multiple Bronze sources. Example: `customer_id` for a `customer` entity.

---

## C

<a id="canonical-entity"></a>
**Canonical entity**
A single, authoritative representation of a business object (customer, policy, payment) in the Silver layer. Combines data from multiple Bronze sources with attribute-level source priority. Also referred to as an **entity**.

**Catalog**
The top-level namespace in Unity Catalog (e.g. `dev`, `prod`). All Bronze, Silver, and Gold schemas live within a catalog.

**CDC (Change Data Capture)**
The technique of detecting which records have changed since the last pipeline run. The Bronze framework supports watermark-based CDC (using a timestamp column) and flag-based CDC (using a `_cdc_operation` column).

**Cluster**
A Databricks compute resource that runs notebooks and jobs. The portal uses the existing cluster `1225-063853-8un63us8` (DBR 17.3, Standard_D4s_v3).

**Consumer group**
A Kafka concept — a named group of consumers that collectively read from a topic. Each consumer group maintains its own read offset.

---

## D

**Databricks**
The cloud data platform (Azure Databricks) where all pipeline code runs and where Delta Tables are stored.

**Dead letter table**
A Delta Table that stores records rejected by data quality rules. Named `dev.bronze_meta.dead_letter_{table_name}`. Records here never reach the main Bronze table. See [Data Quality](../bronze/quality.md).

**Delta Lake**
An open-source storage layer that brings ACID transactions to Apache Spark and big data workloads. All tables in the Lakehouse are Delta Tables.

**Delta Table**
A table stored in Delta Lake format on Azure Data Lake Storage. Supports ACID transactions, time travel, schema enforcement, and SCD2 merge.

**Deploy**
The act of uploading a source or entity configuration to Databricks and creating/updating the associated job. See [Deploy to Databricks](../bronze/deploy.md).

**Domain**
A business subject area. Silver entities are grouped by domain: `customer`, `policy`, `payment`, `interaction`. Each domain has its own schema (e.g. `dev.slv_customer`).

---

## E

**Entity**
See [Canonical entity](#canonical-entity).

---

## F

**Foreign key**
A reference from one Silver entity to another (e.g. `customer_interaction.customer_id` references `customer.customer_id`). Shown as edges in the [Entity Diagram](../silver/diagram.md).

**Framework**
The Bronze Framework and Silver Framework — Python libraries that contain all the pipeline execution logic (SCD2 merge SQL, quality checks, audit logging). The portal is a UI that configures and deploys these frameworks.

---

## G

**Gold layer**
The third layer in the Medallion Architecture. Contains analytics-ready star schema tables (fact and dimension tables) optimised for BI tools. Planned for v2.0.

---

## J

**JDBC (Java Database Connectivity)**
A standard interface for connecting to relational databases. The portal uses JDBC to read from PostgreSQL, MySQL, SQL Server, Oracle, and other databases.

---

## L

**Lakehouse**
An architecture that combines the flexibility of a data lake (cheap object storage, any file format) with the reliability and performance of a data warehouse (ACID transactions, schema enforcement, SQL access). The Data Platform Portal manages a Lakehouse on Azure Databricks with Unity Catalog.

**Landing volume**
A Unity Catalog Volume (`/Volumes/dev/bronze/landing_data/`) where upstream systems drop files for the portal to ingest. Used by File-type sources.

---

## M

**Medallion Architecture**
A data design pattern organising data into three layers: Bronze (raw), Silver (cleansed/canonical), Gold (analytics). See [Architecture Overview](../overview.md).

**Merge**
The operation that compares incoming source data with existing Delta Table data and writes new records, updates changed records (as new SCD2 versions), and marks deleted records. At the heart of both Bronze and Silver pipelines.

**MoSCoW**
A prioritisation framework: Must Have, Should Have, Could Have, Won't Have. Used in the project's PRD.

---

## N

**3NF (Third Normal Form)**
A relational database design principle where data is not repeated — each fact is stored once. Silver entities follow 3NF design: related concepts are separate entities linked by foreign keys.

---

## P

**Pipeline**
The complete data processing flow for one source: extract from source → apply quality checks → merge into Delta Table → write to audit log.

**Primary key**
The column(s) that uniquely identify a record in a source table (e.g. `order_id`). Used in SCD2 merge to match incoming records with existing ones.

---

## R

**RAG (Retrieval-Augmented Generation)**
The AI technique used by the portal's AI Assistant. The assistant retrieves relevant context (existing source configs, framework documentation) before generating a response, making answers specific to your setup.

---

## S

**SCD2 (Slowly Changing Dimension Type 2)**
A data warehousing technique that preserves the full history of changes to a record. Instead of overwriting the old value, a new row is inserted with `_valid_from` / `_valid_to` timestamps. The most recent version has `_is_current = true`. Used by default for both Bronze and Silver layers.

**Schema**
A namespace within a catalog (e.g. `bronze`, `slv_customer`). Analogous to a database in traditional SQL.

**Secret**
A Databricks secret — a securely stored credential (password, API key, token) referenced by key name. The portal never stores credentials directly; it stores the secret key name only.

**Silver layer**
The second layer in the Medallion Architecture. Contains canonical business entities merged from multiple Bronze sources. Silver tables are in domain-specific schemas (`dev.slv_{domain}`).

**Source**
A Bronze-layer pipeline configuration. One source = one raw table in Databricks.

**Star schema**
A data model used in the Gold layer, with one central fact table surrounded by dimension tables. Optimised for BI query performance.

**Structured Streaming**
Apache Spark's framework for continuous, fault-tolerant stream processing. Used by the portal's Stream source type to process Kafka / Event Hub messages.

---

## U

**Unity Catalog**
Databricks' data governance layer. Provides a unified namespace for all data assets (catalogs, schemas, tables, volumes) with centralised access control.

---

## W

**Watermark column**
A timestamp or sequence column in a source table that increases monotonically (e.g. `updated_at`, `created_date`). The Bronze framework reads only records where this column is greater than the last processed value, enabling efficient incremental loads.

**YAML**
A human-readable configuration file format. The Bronze and Silver frameworks use YAML files to define source and entity configurations. The portal generates these files automatically — you should not need to edit them directly.

---

## Z

**Z-order**
A Databricks Delta Lake optimisation technique that co-locates related rows in the same data files, improving query performance when filtering on the Z-order columns (e.g. `customer_id`). Configured optionally in the portal's Target step.
