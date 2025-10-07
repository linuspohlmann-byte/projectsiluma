#!/usr/bin/env python3
"""
Script to fix the Railway PostgreSQL database schema
This script should be run on Railway where DATABASE_URL is available
"""

import os
import sys
from urllib.parse import urlparse

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ psycopg2 not available. Please install it: pip install psycopg2-binary")
    sys.exit(1)

def fix_database_schema():
    """Fix the user_word_familiarity table schema in PostgreSQL"""
    
    # Get DATABASE_URL from environment (Railway sets this automatically)
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        print("Available environment variables:")
        for key, value in os.environ.items():
            if 'DATABASE' in key.upper() or 'POSTGRES' in key.upper():
                print(f"  {key}: {value[:50]}...")
        return False
    
    try:
        # Parse DATABASE_URL
        parsed = urlparse(database_url)
        
        print(f"🔧 Connecting to PostgreSQL database: {parsed.hostname}:{parsed.port}/{parsed.path[1:]}")
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password,
            cursor_factory=RealDictCursor
        )
        
        cursor = conn.cursor()
        
        print("🔍 Checking current table structure...")
        
        # Check if table exists and what columns it has
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'user_word_familiarity' 
            ORDER BY ordinal_position
        """)
        
        existing_columns = cursor.fetchall()
        
        if existing_columns:
            print("📋 Current table structure:")
            for col in existing_columns:
                print(f"  - {col['column_name']}: {col['data_type']} {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
            
            # Check if word_hash column exists
            has_word_hash = any(col['column_name'] == 'word_hash' for col in existing_columns)
            
            if has_word_hash:
                print("✅ word_hash column already exists - no fix needed")
                return True
            else:
                print("⚠️ word_hash column missing - need to recreate table")
        else:
            print("⚠️ user_word_familiarity table doesn't exist - will create it")
        
        print("🔧 Recreating user_word_familiarity table with correct schema...")
        
        # Drop the table if it exists (this will also drop any data, but the schema is wrong anyway)
        cursor.execute("DROP TABLE IF EXISTS user_word_familiarity CASCADE")
        
        # Create the table with the correct schema
        cursor.execute("""
            CREATE TABLE user_word_familiarity (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                word_hash VARCHAR(32) NOT NULL,
                native_language VARCHAR(10) NOT NULL,
                familiarity INTEGER NOT NULL DEFAULT 0 CHECK (familiarity >= 0 AND familiarity <= 5),
                seen_count INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, word_hash, native_language)
            )
        """)
        
        # Create indexes
        print("🔧 Creating indexes...")
        cursor.execute("""
            CREATE INDEX idx_user_word_familiarity_user_hash 
            ON user_word_familiarity(user_id, word_hash)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_user_word_familiarity_native_lang 
            ON user_word_familiarity(native_language)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_user_word_familiarity_familiarity 
            ON user_word_familiarity(familiarity)
        """)
        
        # Commit the changes
        conn.commit()
        
        print("✅ Database schema fixed successfully!")
        
        # Verify the table was created correctly
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'user_word_familiarity' 
            ORDER BY ordinal_position
        """)
        
        new_columns = cursor.fetchall()
        print("📋 New table structure:")
        for col in new_columns:
            print(f"  - {col['column_name']}: {col['data_type']} {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing database schema: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Fixing Railway PostgreSQL database schema...")
    success = fix_database_schema()
    if success:
        print("🎉 Database schema fix completed successfully!")
    else:
        print("💥 Database schema fix failed!")
        sys.exit(1)
