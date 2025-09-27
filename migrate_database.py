#!/usr/bin/env python3
"""
Database migration script to add missing columns to level_runs table
"""
import sqlite3
import os
import sys
from datetime import datetime

def migrate_level_runs_table(db_path):
    """Add missing columns to level_runs table"""
    print(f"🔄 Migrating database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if level_runs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='level_runs'")
        if not cursor.fetchone():
            print(f"⚠️ Table level_runs not found in {db_path}")
            return False
        
        # Check current table structure
        cursor.execute("PRAGMA table_info(level_runs)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Current columns: {columns}")
        
        # Add missing columns
        missing_columns = []
        if 'target_lang' not in columns:
            missing_columns.append('target_lang')
        if 'native_lang' not in columns:
            missing_columns.append('native_lang')
        
        if not missing_columns:
            print(f"✅ All columns already exist in {db_path}")
            return True
        
        print(f"🔧 Adding missing columns: {missing_columns}")
        
        # Add columns one by one
        for column in missing_columns:
            try:
                cursor.execute(f"ALTER TABLE level_runs ADD COLUMN {column} TEXT")
                print(f"✅ Added column: {column}")
            except sqlite3.Error as e:
                print(f"❌ Failed to add column {column}: {e}")
                return False
        
        conn.commit()
        
        # Verify the changes
        cursor.execute("PRAGMA table_info(level_runs)")
        new_columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 New columns: {new_columns}")
        
        print(f"✅ Successfully migrated {db_path}")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        if conn:
            conn.close()

def main():
    """Main migration function"""
    print("🚀 Starting database migration...")
    print(f"⏰ Timestamp: {datetime.now()}")
    
    # List of databases to migrate
    databases = [
        "/Users/Air/Documents/ProjectSiluma/polo.db",
        "/Users/Air/Documents/ProjectSiluma/server/siluma.db",
        "/Users/Air/Documents/ProjectSiluma/data/siluma.db"
    ]
    
    success_count = 0
    total_count = 0
    
    for db_path in databases:
        if os.path.exists(db_path):
            total_count += 1
            if migrate_level_runs_table(db_path):
                success_count += 1
        else:
            print(f"⚠️ Database not found: {db_path}")
    
    print(f"\n📊 Migration Summary:")
    print(f"✅ Successful: {success_count}")
    print(f"📁 Total databases: {total_count}")
    
    if success_count == total_count:
        print("🎉 All databases migrated successfully!")
        return 0
    else:
        print("❌ Some migrations failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
