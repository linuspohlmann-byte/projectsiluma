#!/usr/bin/env python3
"""
Simple script to create the user_word_familiarity table
"""

import os
import sys
from urllib.parse import urlparse

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_table():
    """Create the user_word_familiarity table"""
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        if config['type'] != 'postgresql':
            print("❌ Not using PostgreSQL")
            return False
        
        conn = get_db_connection()
        
        print("🔧 Creating user_word_familiarity table...")
        
        # Create the table
        execute_query(conn, """
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
        
        # Create indexes
        execute_query(conn, """
            CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_user_hash 
            ON user_word_familiarity(user_id, word_hash)
        """)
        
        execute_query(conn, """
            CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_native_lang 
            ON user_word_familiarity(native_language)
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ user_word_familiarity table created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    create_table()
