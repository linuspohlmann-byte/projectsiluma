#!/usr/bin/env python3
"""
Script to create the user_word_familiarity table in Railway PostgreSQL database
This script will be deployed to Railway and run there
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

def create_user_word_familiarity_table():
    """Create the user_word_familiarity table in PostgreSQL"""
    
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
        
        print("🔧 Creating user_word_familiarity table...")
        
        # Create the table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_word_familiarity (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                word_hash TEXT NOT NULL,
                native_language TEXT NOT NULL,
                familiarity INTEGER DEFAULT 0,
                seen_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, word_hash, native_language)
            )
        """)
        
        print("🔧 Creating indexes...")
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_user_hash 
            ON user_word_familiarity(user_id, word_hash)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_native_lang 
            ON user_word_familiarity(native_language)
        """)
        
        # Commit the changes
        conn.commit()
        
        print("✅ user_word_familiarity table created successfully!")
        
        # Verify the table exists
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'user_word_familiarity'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        print(f"📋 Table structure:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']} {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Creating user_word_familiarity table in Railway PostgreSQL...")
    success = create_user_word_familiarity_table()
    if success:
        print("🎉 Table creation completed successfully!")
    else:
        print("💥 Table creation failed!")
        sys.exit(1)
