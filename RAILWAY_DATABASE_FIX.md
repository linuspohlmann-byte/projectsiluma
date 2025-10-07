# Railway Database Schema Fix

## Issue
The Railway PostgreSQL database is missing the `word_hash` column in the `user_word_familiarity` table, causing errors when trying to ensure user databases.

## Solution
Run the database fix script on Railway to correct the table schema.

## Steps to Fix

### Option 1: Run the Python Script (Recommended)
1. SSH into your Railway deployment or use Railway CLI
2. Run the fix script:
   ```bash
   python fix_railway_database.py
   ```

### Option 2: Run the SQL Script
1. Connect to your Railway PostgreSQL database using a database client
2. Execute the SQL commands from `fix_database_schema.sql`

## What the Fix Does
- Checks the current table structure
- Drops and recreates the `user_word_familiarity` table with the correct schema
- Adds the missing `word_hash` column
- Creates proper indexes for performance
- Ensures the table has all required columns:
  - `id` (SERIAL PRIMARY KEY)
  - `user_id` (INTEGER NOT NULL)
  - `word_hash` (VARCHAR(32) NOT NULL) ← **This was missing**
  - `native_language` (VARCHAR(10) NOT NULL)
  - `familiarity` (INTEGER NOT NULL DEFAULT 0)
  - `seen_count` (INTEGER NOT NULL DEFAULT 0)
  - `correct_count` (INTEGER NOT NULL DEFAULT 0)
  - `last_seen` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
  - `created_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
  - `updated_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)

## Verification
After running the fix, the custom level group word familiarity functionality should work without the "column word_hash does not exist" errors.

## Files Added
- `fix_railway_database.py` - Python script to fix the schema
- `fix_database_schema.sql` - SQL script with the fix commands
- `RAILWAY_DATABASE_FIX.md` - This instruction file
