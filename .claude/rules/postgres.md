---
paths:
  - "**/*.sql"
---
# SQL Dialect: PostgreSQL

Use PostgreSQL exclusively. NOT Snowflake, NOT Spark SQL.
- JSONB, LATERAL, ON CONFLICT, RETURNING
- CASE WHEN (not IFF), no QUALIFY
- ::type for casting, COALESCE/NULLIF
