#!/usr/bin/env python3
"""
Migration script to populate word_ids for existing custom_levels
This optimizes performance by storing word IDs directly instead of extracting from content each time
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.db_config import get_database_config, get_db_connection, execute_query
from server.db import migrate_custom_levels_add_word_ids
from server.services.custom_levels import get_custom_levels_for_group, sync_custom_level_words_to_postgresql
from server.db_multi_user import get_user_id_from_group_id

def migrate_existing_levels_to_word_ids():
    """Populate word_ids for all existing custom levels"""
    print("🔄 Starting migration: Populating word_ids for existing custom levels...")
    
    # First, ensure the column exists
    migrate_custom_levels_add_word_ids()
    
    config = get_database_config()
    if config['type'] != 'postgresql':
        print("⚠️ Migration only supports PostgreSQL. SQLite levels will be migrated on-demand.")
        return
    
    conn = get_db_connection()
    try:
        # Get all custom level groups
        result = execute_query(conn, """
            SELECT DISTINCT group_id FROM custom_levels
            ORDER BY group_id
        """)
        
        group_ids = [row['group_id'] if isinstance(row, dict) else row[0] for row in result.fetchall()]
        print(f"📋 Found {len(group_ids)} custom level groups to process")
        
        total_levels = 0
        migrated_levels = 0
        skipped_levels = 0
        
        for group_id in group_ids:
            try:
                # Get user_id for this group
                user_id = get_user_id_from_group_id(group_id)
                if not user_id:
                    print(f"⚠️ Could not find user_id for group {group_id}, skipping")
                    continue
                
                # Get all levels for this group
                levels = get_custom_levels_for_group(group_id)
                
                for level in levels:
                    total_levels += 1
                    level_number = level['level_number']
                    
                    # Check if word_ids already exists
                    check_result = execute_query(conn, """
                        SELECT word_ids FROM custom_levels 
                        WHERE group_id = %s AND level_number = %s
                    """, (group_id, level_number))
                    
                    row = check_result.fetchone()
                    existing_word_ids = None
                    if row:
                        if isinstance(row, dict):
                            existing_word_ids = row.get('word_ids')
                        else:
                            existing_word_ids = row[0] if len(row) > 0 else None
                    
                    if existing_word_ids:
                        print(f"⏭️ Level {group_id}/{level_number} already has word_ids, skipping")
                        skipped_levels += 1
                        continue
                    
                    # Get language info from group
                    group_result = execute_query(conn, """
                        SELECT language, native_language FROM custom_level_groups 
                        WHERE id = %s
                    """, (group_id,))
                    
                    group_row = group_result.fetchone()
                    if not group_row:
                        print(f"⚠️ Could not find group {group_id}, skipping level {level_number}")
                        continue
                    
                    if isinstance(group_row, dict):
                        language = group_row.get('language', 'en')
                        native_language = group_row.get('native_language', 'de')
                    else:
                        language = group_row[0] if len(group_row) > 0 else 'en'
                        native_language = group_row[1] if len(group_row) > 1 else 'de'
                    
                    # Sync words to populate word_ids
                    content = level.get('content', {})
                    if content and content.get('items'):
                        print(f"🔄 Migrating level {group_id}/{level_number}...")
                        success = sync_custom_level_words_to_postgresql(
                            group_id, level_number, content, language, native_language
                        )
                        if success:
                            migrated_levels += 1
                            print(f"✅ Migrated level {group_id}/{level_number}")
                        else:
                            print(f"❌ Failed to migrate level {group_id}/{level_number}")
                    else:
                        print(f"⚠️ Level {group_id}/{level_number} has no content, skipping")
                        skipped_levels += 1
                        
            except Exception as e:
                print(f"❌ Error processing group {group_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n🎉 Migration complete!")
        print(f"   Total levels: {total_levels}")
        print(f"   Migrated: {migrated_levels}")
        print(f"   Skipped (already migrated or no content): {skipped_levels}")
        
    except Exception as e:
        print(f"❌ Error in migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_existing_levels_to_word_ids()


