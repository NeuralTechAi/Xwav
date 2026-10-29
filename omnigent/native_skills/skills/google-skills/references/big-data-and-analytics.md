# big-data-and-analytics

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## bigquery-basics
Manages datasets, tables, and jobs in BigQuery. Use when you need to interact with BigQuery, run SQL queries, manage BigQuery resources (datasets, tables, views), or perform basic data ingestion and analysis.

Read: `library/cloud/bigquery-basics/INSTRUCTIONS.md`

## bigquery-bigframes
Generates Python code using BigQuery DataFrames (BigFrames). Use by default for any Python data task involving BigQuery, including data processing, analysis, and machine learning. Don't use for SQL-first workflows or the google-cloud-bigquery client library — use bigquery-basics.

Read: `library/cloud/bigquery-bigframes/INSTRUCTIONS.md`

## bigquery-migration-sql-translator
Translates SQL queries, DDL schemas, and stored procedures from legacy database dialects (Teradata, Oracle, Redshift, Snowflake, SparkSQL, HiveQL) to BigQuery GoogleSQL using the BigQuery Migration Service (BQMS) MCP server. Use when translating legacy SQL queries, migrating schemas or metadata zip archives, or configuring BigQuery Migration Service (BQMS) YAML translation settings. Don't use for executing BigQuery queries or managing datasets and tables (use bigquery-basics), diagnosing runtime job errors (use bigquery-troubleshooting), or tuning slot reservations (use bigquery-optimization).

Read: `library/cloud/bigquery-migration-sql-translator/INSTRUCTIONS.md`

## bigquery-observability
Provides data-retrieval best practices, tool selection guidance, and performant SQL query syntax for BigQuery telemetry across INFORMATION_SCHEMA, Cloud Monitoring, and the REST API. Use when the telemetry to fetch is already known, selecting telemetry tools, writing performant INFORMATION_SCHEMA queries, retrieving telemetry for diagnosing single-job performance bottlenecks, investigating slot contention, job concurrency and queue latency, analyzing reservation capacity, utilization and autoscaling saturation, or auditing capacity-based and on-demand compute and storage resource billable usage. Don't use for root-cause diagnosis or symptom troubleshooting when the cause is unknown (use bigquery-troubleshooting first), or for writing or optimizing business logic SQL (use bigquery-optimization).

Read: `library/cloud/bigquery-observability/INSTRUCTIONS.md`

## bigquery-optimization
Provides workflows to optimize BigQuery environments (capacity planning, editions), storage assets (partitioning, clustering, storage lifecycles, billing models), and SQL queries. Use when optimizing cost, modeling Edition migrations, rightsizing reservations, evaluating logical vs. physical storage, designing table partitioning/clustering, generating table DDL, migrating unpartitioned tables, managing partition expiration, optimizing individual SQL queries, or evaluating acceleration structures (search indexes, materialized views, BI Engine). Do not use for raw usage reporting (use bigquery-observability), query execution plan analysis, error troubleshooting, or diagnosing why a specific job was slow (use bigquery-troubleshooting).

Read: `library/cloud/bigquery-optimization/INSTRUCTIONS.md`

## bigquery-troubleshooting
Provides diagnostic workflows and step-by-step root-cause analysis procedures for actively broken, failing, or slow BigQuery jobs, execution graph and query plan stage bottlenecks, system performance issues, or unexpectedly expensive workloads. Use when interpreting symptoms, isolating bottlenecks, diagnosing cost spikes (on-demand query spend, capacity slot autoscaling, storage growth), execution graph stages or substep variables, identifying root causes, and determining remediation steps. Don't use for writing or optimizing SQL, proactive capacity planning, or storage layout design (use bigquery-optimization), or when the user already knows which telemetry they want and just needs the query (use bigquery-observability).

Read: `library/cloud/bigquery-troubleshooting/INSTRUCTIONS.md`

## bigquery-udfs
Creates, deploys, and troubleshoots BigQuery User-Defined Functions (UDFs) and Remote Functions across SQL, JavaScript, Python, and Cloud Run endpoints. Use when writing custom scalar or aggregate functions in BigQuery, installing PyPI packages or Cloud Storage libraries in a Python or JavaScript UDF, or calling Google Cloud and external APIs from a Python UDF (WITH CONNECTION) or Remote Function. Don't use for standard BigQuery table/dataset CRUD (use bigquery-basics), DataFrames client workflows (use bigquery-bigframes), or BigQuery ML models (use bigquery-ai-ml).

Read: `library/cloud/bigquery-udfs/INSTRUCTIONS.md`

## datalineage-bigquery-asset-impact-analysis
Analyzes the downstream impact (blast radius) using data lineage on Google Cloud when a BigQuery table or view is broken, stale, or modified. Identifies all downstream tables, dashboards, and processes that will be affected. Use when: - Performing a blast radius or impact analysis for a BigQuery table or view. - Assessing the consequences of modifying, deleting, or pausing updates to a BigQuery asset. - Identifying downstream dependencies (tables, dashboards, processes) of a BigQuery asset. Don't use for: - General BigQuery querying or data analysis (use BigQuery-related tools instead). - Non-BigQuery assets (e.g., Cloud Storage files) unless they are part of the BigQuery lineage. - Creating or modifying lineage links directly.

Read: `library/cloud/datalineage-bigquery-asset-impact-analysis/INSTRUCTIONS.md`

## datalineage-summary
Summarizes data lineage graphs on Google Cloud to help users debug data quality issues and understand data provenance for BigQuery and Cloud Storage. Use when summarizing upstream and downstream data flows, and presenting complex lineage data as an intuitive Markdown report. Don't use for generic BigQuery queries, editing lineage relationships, or downstream deprecation. Don't use for downstream blast-radius impact analysis (use datalineage-bigquery-asset-impact-analysis skill instead).

Read: `library/cloud/datalineage-summary/INSTRUCTIONS.md`

## dbt-sf-to-bq-translator
Translates Snowflake dbt SQL models to Standardized BigQuery SQL. Handles SQL compilation, Jinja macro placeholder masking, BigQuery Translation Service migration workflows, AST-based config transformations, explicit type casting, JSON extraction standardization, and deduplication. Use when migrating Snowflake dbt pipelines or models to BigQuery on Google Cloud. Don't use for generic BigQuery queries or non-Snowflake SQL migrations.

Read: `library/cloud/dbt-sf-to-bq-translator/INSTRUCTIONS.md`

## managed-airflow-dag-authoring
Provides guidance for authoring Apache Airflow DAGs in Managed Service for Apache Airflow (MSAA; formerly Cloud Composer). Covers environment context discovery, Airflow 2 vs 3 compatibility, authoring best practices, and local/remote validation processes. Use when creating or extending an Airflow DAG. Don't use when authoring Python code unrelated to Airflow DAGs.

Read: `library/cloud/managed-airflow-dag-authoring/INSTRUCTIONS.md`

## managed-airflow-dag-troubleshooting
Provides guidance for troubleshooting Apache Airflow DAGs (failed DAG runs and task instances) in Managed Service for Apache Airflow (MSAA; formerly Cloud Composer). Use when figuring out reasons for DAG run or task instance failures. Don't use when looking for overall recommendations for Managed Airflow environment performance.

Read: `library/cloud/managed-airflow-dag-troubleshooting/INSTRUCTIONS.md`

## managed-airflow-migrations
Provides guidance for migrating Apache Airflow DAGs in Managed Service for Apache Airflow (MSAA; formerly Cloud Composer). Covers migration to Airflow 2.11.1 (MSAA Gen 2 and 3) and Airflow 3 (MSAA Gen 3), including environment inspection, GCS download/upload and scanning patterns for breaking changes. Use when migrating the DAG code to newer Airflow version. Don't use when checking DAG run failures unrelated to code migration.

Read: `library/cloud/managed-airflow-migrations/INSTRUCTIONS.md`

## managed-airflow-recommendations
Provides recommendations and best practices for creating, configuring, tuning and optimizing Managed Service for Apache Airflow (MSAA; formerly Cloud Composer) environments. Use when the user asks for guidance, recommendations, or best practices on configuring Managed Airflow environments, scaling Airflow environments, preventing workload restarts, or analyzing system health. Don't use for troubleshooting individual DAG or task run failures, authoring DAGs, or migrating DAGs to newer Airflow versions.

Read: `library/cloud/managed-airflow-recommendations/INSTRUCTIONS.md`
