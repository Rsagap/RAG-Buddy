---
source: https://portswigger.net/web-security/sql-injection/examining-the-database
topic: sql-injection
type: THEORY
---

- Web Security Academy
- SQL injection
- Examining the database

# Examining the database in SQL injection attacks

To exploit SQL injection vulnerabilities, it's often necessary to find information about the database. This includes:

- The type and version of the database software.
- The tables and columns that the database contains.

## Querying the database type and version

You can potentially identify both the database type and version by injecting provider-specific queries to see if one works

The following are some queries to determine the database version for some popular database types:

| Database type | Query |
| --- | --- |
| Microsoft, MySQL | SELECT @@version |
| Oracle | SELECT * FROM v$version |
| PostgreSQL | SELECT version() |

For example, you could use a UNION attack with the following input:

This might return the following output. In this case, you can confirm that the database is Microsoft SQL Server and see the version used:

## Listing the contents of the database

Most database types (except Oracle) have a set of views called the information schema. This provides information about the database.

For example, you can query information_schema.tables to list the tables in the database:

This returns output like the following:

This output indicates that there are three tables, called Products , Users , and Feedback .

You can then query information_schema.columns to list the columns in individual tables:

This returns output like the following:

This output shows the columns in the specified table and the data type of each column.

### Listing the contents of an Oracle database

On Oracle, you can find the same information as follows:

- You can list tables by querying all_tables : SELECT * FROM all_tables
- You can list columns by querying all_tab_columns : SELECT * FROM all_tab_columns WHERE table_name = 'USERS'