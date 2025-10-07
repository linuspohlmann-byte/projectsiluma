#!/usr/bin/env python3
"""
Migration script to populate word_count column for existing custom levels
"""

import os
import sys
import json
from datetime import datetime, UTC

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.db_config import get_database_config, get_db_connection, execute_query
from server.services.custom_levels import get_custom_levels_for_group, calculate_word_count_from_content

def migrate_word_counts():
    """Migrate word counts for all existing custom levels"""
    print("🔄 Starting word count migration for existing custom levels...")
    
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        # Get all custom level groups
        if config['type'] == 'postgresql':
            result = execute_query(conn, "SELECT id FROM custom_level_groups")
            groups = [row['id'] for row in result.fetchall()]
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM custom_level_groups")
            groups = [row[0] for row in cursor.fetchall()]
        
        print(f"📚 Found {len(groups)} custom level groups")
        
        total_updated = 0
        total_levels = 0
        
        for group_id in groups:
            print(f"🔄 Processing group {group_id}...")
            levels = get_custom_levels_for_group(group_id)
            
            for level in levels:
                total_levels += 1
                level_number = level['level_number']
                content = level.get('content', {})
                
                # Calculate word count from content
                word_count = calculate_word_count_from_content(content)
                
                if word_count > 0:
                    # Update the word count in database
                    if config['type'] == 'postgresql':
                        execute_query(conn, """
                            UPDATE custom_levels 
                            SET word_count = %s, updated_at = %s
                            WHERE group_id = %s AND level_number = %s
                        """, (word_count, datetime.now(UTC).isoformat(), group_id, level_number))
                    else:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE custom_levels 
                            SET word_count = ?, updated_at = ?
                            WHERE group_id = ? AND level_number = ?
                        """, (word_count, datetime.now(UTC).isoformat(), group_id, level_number))
                        conn.commit()
                    
                    total_updated += 1
                    print(f"✅ Updated level {group_id}/{level_number}: {word_count} words")
                else:
                    print(f"⚠️ Level {group_id}/{level_number}: No words found (ultra-lazy loading)")
        
        print(f"🎉 Migration complete!")
        print(f"📊 Total levels processed: {total_levels}")
        print(f"📊 Total levels updated: {total_updated}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 Custom Level Word Count Migration")
    print("=" * 50)
    
    success = migrate_word_counts()
    
    if success:
        print("\n✅ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
