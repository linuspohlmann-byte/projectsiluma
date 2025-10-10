#!/usr/bin/env python3
"""
Database Schema Migration Script
Fixes missing columns and schema issues in PostgreSQL database
"""

import os
import sys
from server import postgres as psycopg2
from server.postgres import RealDictCursor

def get_database_connection():
    """Get PostgreSQL database connection"""
    try:
        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL environment variable not set")
            return None
        
        # Parse database URL
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return None

def check_column_exists(conn, table_name, column_name):
    """Check if a column exists in a table"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = %s AND column_name = %s
            );
        """, (table_name, column_name))
        exists = cursor.fetchone()[0]
        cursor.close()
        return exists
    except Exception as e:
        print(f"❌ Error checking column {column_name} in {table_name}: {e}")
        return False

def add_column_if_not_exists(conn, table_name, column_name, column_definition):
    """Add a column to a table if it doesn't exist"""
    try:
        if not check_column_exists(conn, table_name, column_name):
            cursor = conn.cursor()
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition};")
            conn.commit()
            cursor.close()
            print(f"✅ Added column {column_name} to {table_name}")
            return True
        else:
            print(f"ℹ️ Column {column_name} already exists in {table_name}")
            return True
    except Exception as e:
        print(f"❌ Error adding column {column_name} to {table_name}: {e}")
        conn.rollback()
        return False

def fix_user_word_familiarity_table(conn):
    """Fix user_word_familiarity table schema"""
    print("🔧 Fixing user_word_familiarity table schema...")
    
    # Add word_hash column if missing
    if not add_column_if_not_exists(conn, 'user_word_familiarity', 'word_hash', 'VARCHAR(64)'):
        return False
    
    # Add native_language column if missing
    if not add_column_if_not_exists(conn, 'user_word_familiarity', 'native_language', 'VARCHAR(10)'):
        return False
    
    # Create index on word_hash if it doesn't exist
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_user_hash 
            ON user_word_familiarity(user_id, word_hash);
        """)
        conn.commit()
        cursor.close()
        print("✅ Created index on user_word_familiarity(user_id, word_hash)")
    except Exception as e:
        print(f"❌ Error creating index: {e}")
        conn.rollback()
        return False
    
    return True

def fix_level_runs_table(conn):
    """Fix level_runs table schema and queries"""
    print("🔧 Fixing level_runs table schema...")
    
    # Check if level_runs table exists
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'level_runs'
            );
        """)
        table_exists = cursor.fetchone()[0]
        cursor.close()
        
        if not table_exists:
            print("ℹ️ level_runs table does not exist, creating it...")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE level_runs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    score DECIMAL(5,2),
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            cursor.close()
            print("✅ Created level_runs table")
        else:
            print("ℹ️ level_runs table already exists")
            
    except Exception as e:
        print(f"❌ Error checking/creating level_runs table: {e}")
        conn.rollback()
        return False
    
    return True

def populate_word_hash_values(conn):
    """Populate word_hash values for existing records"""
    print("🔧 Populating word_hash values for existing records...")
    
    try:
        cursor = conn.cursor()
        
        # Get all records without word_hash
        cursor.execute("""
            SELECT uwf.id, w.word, uwf.native_language
            FROM user_word_familiarity uwf
            JOIN words w ON uwf.word_id = w.id
            WHERE uwf.word_hash IS NULL;
        """)
        
        records = cursor.fetchall()
        print(f"📊 Found {len(records)} records without word_hash")
        
        if records:
            # Update records with word_hash
            for record_id, word, native_language in records:
                # Generate hash (simple hash for now)
                import hashlib
                word_hash = hashlib.sha256(f"{word}_{native_language}".encode()).hexdigest()
                
                cursor.execute("""
                    UPDATE user_word_familiarity 
                    SET word_hash = %s, native_language = %s
                    WHERE id = %s;
                """, (word_hash, native_language, record_id))
            
            conn.commit()
            print(f"✅ Updated {len(records)} records with word_hash")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"❌ Error populating word_hash values: {e}")
        conn.rollback()
        return False

def verify_schema_fixes(conn):
    """Verify that all schema fixes are working"""
    print("🔍 Verifying schema fixes...")
    
    try:
        cursor = conn.cursor()
        
        # Check user_word_familiarity table structure
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_word_familiarity'
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        print("📋 user_word_familiarity table columns:")
        for col_name, col_type in columns:
            print(f"  - {col_name}: {col_type}")
        
        # Check if indexes exist
        cursor.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'user_word_familiarity' 
            AND indexname LIKE '%word_hash%';
        """)
        indexes = cursor.fetchall()
        print(f"📋 Indexes on user_word_familiarity: {[idx[0] for idx in indexes]}")
        
        # Test a query that was failing
        cursor.execute("""
            SELECT COUNT(*) FROM user_word_familiarity 
            WHERE word_hash IS NOT NULL;
        """)
        count = cursor.fetchone()[0]
        print(f"📊 Records with word_hash: {count}")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verifying schema fixes: {e}")
        return False

def main():
    """Main migration function"""
    print("🚀 Starting database schema migration...")
    
    # Get database connection
    conn = get_database_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        # Fix user_word_familiarity table
        if not fix_user_word_familiarity_table(conn):
            print("❌ Failed to fix user_word_familiarity table")
            return False
        
        # Fix level_runs table
        if not fix_level_runs_table(conn):
            print("❌ Failed to fix level_runs table")
            return False
        
        # Populate word_hash values
        if not populate_word_hash_values(conn):
            print("❌ Failed to populate word_hash values")
            return False
        
        # Verify fixes
        if not verify_schema_fixes(conn):
            print("❌ Schema verification failed")
            return False
        
        print("✅ Database schema migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
