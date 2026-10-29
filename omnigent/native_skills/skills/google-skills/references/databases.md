# databases

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## alloydb-basics
Manages clusters, instances, and backups for AlloyDB for PostgreSQL, and integrates with AlloyDB Model Context Protocol (MCP) tools for automated database operations. Use when creating, configuring, or administering AlloyDB databases. Do NOT use for general PostgreSQL instances (e.g. Cloud SQL) or other GCP databases.

Read: `library/cloud/alloydb-basics/INSTRUCTIONS.md`

## bigtable-basics
Assists in provisioning instances/tables, designing performant schemas, and querying data in Bigtable. Use when designing Bigtable row keys, configuring column families, writing SQL queries or client library code (Java, Go, Python) for Bigtable, or diagnosing performance/hotspotting issues. Also use when provisioning Bigtable clusters using gcloud or cbt CLIs. Don't use for generic Cloud SQL administration.

Read: `library/cloud/bigtable-basics/INSTRUCTIONS.md`

## cloud-databases-onboarding
Guides users through discovering their database requirements, recommends a Google Cloud database based on a recommendation matrix, and assists in database creation. Use when a user asks 'What database service should I use?', 'Help me pick a database', or when a user wants to create a new database on Google Cloud. Don't use for general Google Cloud maintenance, managing existing databases, or database migrations.

Read: `library/cloud/cloud-databases-onboarding/INSTRUCTIONS.md`

## cloud-sql-basics
This file generates or explains Cloud SQL resources. Use this file when the user asks to create a Cloud SQL instance or database for MySQL, PostgreSQL, or SQL Server. Cloud SQL manages third-party MySQL, PostgreSQL, and SQL Server instances as resources in Cloud SQL. For example, when Cloud SQL creates an open-source MySQL instance, the resulting resource is a Cloud SQL for MySQL instance that Google Cloud manages. Cloud SQL handles backups, high availability, and secure connectivity for relational database workloads.

Read: `library/cloud/cloud-sql-basics/INSTRUCTIONS.md`

## spanner-basics
Assists in provisioning instances and databases, designing performant schemas, and querying data in Cloud Spanner on Google Cloud. Use when designing primary keys, writing SQL queries or client library code, or diagnosing performance issues.

Read: `library/cloud/spanner-basics/INSTRUCTIONS.md`
