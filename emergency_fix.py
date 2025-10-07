#!/usr/bin/env python3
"""
Emergency database fix that can be run directly on Railway
This script will fix the database schema issues immediately
"""

import os
import sys
from urllib.parse import urlparse

def emergency_database_fix():
    """Emergency fix for Railway PostgreSQL database schema"""
    
    print("🚨 EMERGENCY DATABASE SCHEMA FIX")
    print("=" * 50)
    
    # Get DATABASE_URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        print("Available environment variables:")
        for key, value in os.environ.items():
            if 'DATABASE' in key.upper() or 'POSTGRES' in key.upper():
                print(f"  {key}: {value[:50]}...")
        return False
    
    try:
        # Import psycopg2
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Parse DATABASE_URL
        parsed = urlparse(database_url)
        
        print(f"🔧 Connecting to PostgreSQL: {parsed.hostname}:{parsed.port}/{parsed.path[1:]}")
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            cursor_factory=RealDictCursor
        )
        
        cursor = conn.cursor()
        
        print("🔍 Checking current table structure...")
        
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'user_word_familiarity'
            )
        """)
        
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # Check current columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'user_word_familiarity' 
                ORDER BY ordinal_position
            """)
            
            existing_columns = cursor.fetchall()
            print("📋 Current table structure:")
            for col in existing_columns:
                print(f"  - {col['column_name']}: {col['data_type']}")
            
            # Check for missing columns
            column_names = [col['column_name'] for col in existing_columns]
            missing_columns = []
            
            required_columns = ['word_hash', 'native_language']
            for req_col in required_columns:
                if req_col not in column_names:
                    missing_columns.append(req_col)
            
            if missing_columns:
                print(f"⚠️ Missing columns: {missing_columns}")
                print("🔧 Recreating table with correct schema...")
                
                # Drop and recreate table
                cursor.execute("DROP TABLE IF EXISTS user_word_familiarity CASCADE")
                
                # Create table with correct schema
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
                
                conn.commit()
                print("✅ Table recreated successfully!")
                
            else:
                print("✅ All required columns exist - no fix needed")
        else:
            print("⚠️ Table doesn't exist - creating it...")
            
            # Create table
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
            
            conn.commit()
            print("✅ Table created successfully!")
        
        # Verify final structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'user_word_familiarity' 
            ORDER BY ordinal_position
        """)
        
        final_columns = cursor.fetchall()
        print("📋 Final table structure:")
        for col in final_columns:
            print(f"  - {col['column_name']}: {col['data_type']}")
        
        cursor.close()
        conn.close()
        
        print("🎉 Database fix completed successfully!")
        print("✅ The custom level group word familiarity functionality should now work!")
        return True
        
    except ImportError:
        print("❌ psycopg2 not available")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = emergency_database_fix()
    if not success:
        sys.exit(1)
