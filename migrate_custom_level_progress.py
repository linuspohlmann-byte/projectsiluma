#!/usr/bin/env python3
"""
Migration script to add score, status, and completed_at columns to custom_level_progress table
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from server.db_config import get_database_config, get_db_connection, execute_query

def migrate_custom_level_progress_table():
    """Add missing columns to custom_level_progress table"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            print("🔄 Migrating PostgreSQL custom_level_progress table...")
            cursor = conn.cursor()
            
            # Check if columns exist
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'custom_level_progress'
            """)
            
            existing_columns = {row[0] for row in cursor.fetchall()}
            print(f"📋 Existing columns: {existing_columns}")
            
            # Add score column if missing
            if 'score' not in existing_columns:
                print("➕ Adding 'score' column...")
                cursor.execute("""
                    ALTER TABLE custom_level_progress 
                    ADD COLUMN score REAL
                """)
                print("✅ Added 'score' column")
            else:
                print("ℹ️  'score' column already exists")
            
            # Add status column if missing
            if 'status' not in existing_columns:
                print("➕ Adding 'status' column...")
                cursor.execute("""
                    ALTER TABLE custom_level_progress 
                    ADD COLUMN status VARCHAR(50) DEFAULT 'not_started'
                """)
                print("✅ Added 'status' column")
            else:
                print("ℹ️  'status' column already exists")
            
            # Add completed_at column if missing
            if 'completed_at' not in existing_columns:
                print("➕ Adding 'completed_at' column...")
                cursor.execute("""
                    ALTER TABLE custom_level_progress 
                    ADD COLUMN completed_at TIMESTAMP
                """)
                print("✅ Added 'completed_at' column")
            else:
                print("ℹ️  'completed_at' column already exists")
            
            conn.commit()
            print("✅ PostgreSQL migration completed successfully")
            
        else:
            print("🔄 Migrating SQLite custom_level_progress table...")
            cursor = conn.cursor()
            
            # Check if columns exist
            cursor.execute("PRAGMA table_info(custom_level_progress)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            print(f"📋 Existing columns: {existing_columns}")
            
            # Add score column if missing
            if 'score' not in existing_columns:
                print("➕ Adding 'score' column...")
                cursor.execute("""
                    ALTER TABLE custom_level_progress 
                    ADD COLUMN score REAL
                """)
                print("✅ Added 'score' column")
            else:
                print("ℹ️  'score' column already exists")
            
            # Add status column if missing
            if 'status' not in existing_columns:
                print("➕ Adding 'status' column...")
                cursor.execute("""
                    ALTER TABLE custom_level_progress 
                    ADD COLUMN status TEXT DEFAULT 'not_started'
                """)
                print("✅ Added 'status' column")
            else:
                print("ℹ️  'status' column already exists")
            
            # Add completed_at column if missing
            if 'completed_at' not in existing_columns:
                print("➕ Adding 'completed_at' column...")
                cursor.execute("""
                    ALTER TABLE custom_level_progress 
                    ADD COLUMN completed_at TEXT
                """)
                print("✅ Added 'completed_at' column")
            else:
                print("ℹ️  'completed_at' column already exists")
            
            conn.commit()
            print("✅ SQLite migration completed successfully")
            
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn.rollback()
        except:
            pass
        return False
    finally:
        conn.close()
    
    return True

if __name__ == '__main__':
    print("🚀 Starting custom_level_progress table migration...")
    success = migrate_custom_level_progress_table()
    
    if success:
        print("✅ Migration completed successfully!")
        sys.exit(0)
    else:
        print("❌ Migration failed!")
        sys.exit(1)

