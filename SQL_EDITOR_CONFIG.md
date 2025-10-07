# SQL Editor Configuration

## Issue
The SQL files in this project are written for **PostgreSQL**, but your editor is interpreting them as **Microsoft SQL Server (MSSQL)** syntax, which causes syntax errors.

## Solution
Configure your editor to use PostgreSQL syntax highlighting and validation.

### For VS Code:
1. Install the "PostgreSQL" extension by Chris Kolkman
2. Or install the "SQLTools" extension with PostgreSQL driver
3. Set the file association for `.sql` files to PostgreSQL

### For Cursor:
1. Install the PostgreSQL extension
2. Add this to your settings.json:
```json
{
    "files.associations": {
        "*.sql": "postgresql"
    }
}
```

### For other editors:
- Look for PostgreSQL syntax highlighting extensions
- Configure the SQL dialect to PostgreSQL instead of SQL Server

## Files Affected
- `fix_database_schema.sql` - PostgreSQL syntax (correct)
- `fix_database_schema_postgresql.sql` - PostgreSQL syntax (correct)
- `create_user_word_familiarity_table.sql` - PostgreSQL syntax (correct)

## Note
The syntax errors you're seeing are false positives because the editor is using the wrong SQL dialect. The SQL code is correct for PostgreSQL and will work fine when executed on Railway's PostgreSQL database.
