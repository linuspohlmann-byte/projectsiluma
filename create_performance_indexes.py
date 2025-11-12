#!/usr/bin/env python3
"""
Create performance indexes for database optimization.
Run this script to add all necessary indexes for improved query performance.
"""

import os
from server.db_config import get_database_config, get_db_connection, execute_query

def create_performance_indexes():
    """Create all performance-critical indexes"""
    config = get_database_config()
    conn = get_db_connection()
    
    indexes_created = []
    indexes_existing = []
    
    try:
        # Check if PostgreSQL or SQLite
        is_postgresql = config.get('type') == 'postgresql'
        
        if is_postgresql:
            # PostgreSQL indexes
            indexes = [
                # Users table
                ("idx_users_id", "users", "CREATE INDEX IF NOT EXISTS idx_users_id ON users(id)"),
                ("idx_users_username", "users", "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"),
                
                # Custom level groups
                ("idx_custom_level_groups_user_id", "custom_level_groups", 
                 "CREATE INDEX IF NOT EXISTS idx_custom_level_groups_user_id ON custom_level_groups(user_id)"),
                ("idx_custom_level_groups_language", "custom_level_groups",
                 "CREATE INDEX IF NOT EXISTS idx_custom_level_groups_language ON custom_level_groups(language)"),
                
                # Custom levels
                ("idx_custom_levels_group_id", "custom_levels",
                 "CREATE INDEX IF NOT EXISTS idx_custom_levels_group_id ON custom_levels(group_id)"),
                ("idx_custom_levels_group_level", "custom_levels",
                 "CREATE INDEX IF NOT EXISTS idx_custom_levels_group_level ON custom_levels(group_id, level_number)"),
                
                # Custom level progress (critical for performance)
                ("idx_custom_level_progress_user_group_level", "custom_level_progress",
                 "CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user_group_level ON custom_level_progress(user_id, group_id, level_number)"),
                ("idx_custom_level_progress_user", "custom_level_progress",
                 "CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user ON custom_level_progress(user_id)"),
                
                # Words table
                ("idx_words_word_lang_native", "words",
                 "CREATE INDEX IF NOT EXISTS idx_words_word_lang_native ON words(word, language, native_language)"),
                ("idx_words_language", "words",
                 "CREATE INDEX IF NOT EXISTS idx_words_language ON words(language)"),
                
                # User word familiarity
                ("idx_user_word_fam_user_word_lang", "user_word_familiarity",
                 "CREATE INDEX IF NOT EXISTS idx_user_word_fam_user_word_lang ON user_word_familiarity(user_id, word, language, native_language)"),
            ]
        else:
            # SQLite indexes
            indexes = [
                # Users table
                ("idx_users_id", "users", "CREATE INDEX IF NOT EXISTS idx_users_id ON users(id)"),
                ("idx_users_username", "users", "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"),
                
                # Custom level groups
                ("idx_custom_level_groups_user_id", "custom_level_groups",
                 "CREATE INDEX IF NOT EXISTS idx_custom_level_groups_user_id ON custom_level_groups(user_id)"),
                ("idx_custom_level_groups_language", "custom_level_groups",
                 "CREATE INDEX IF NOT EXISTS idx_custom_level_groups_language ON custom_level_groups(language)"),
                
                # Custom levels
                ("idx_custom_levels_group_id", "custom_levels",
                 "CREATE INDEX IF NOT EXISTS idx_custom_levels_group_id ON custom_levels(group_id)"),
                ("idx_custom_levels_group_level", "custom_levels",
                 "CREATE INDEX IF NOT EXISTS idx_custom_levels_group_level ON custom_levels(group_id, level_number)"),
                
                # Custom level progress
                ("idx_custom_level_progress_user_group_level", "custom_level_progress",
                 "CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user_group_level ON custom_level_progress(user_id, group_id, level_number)"),
                ("idx_custom_level_progress_user", "custom_level_progress",
                 "CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user ON custom_level_progress(user_id)"),
                
                # Words table
                ("idx_words_word_lang_native", "words",
                 "CREATE INDEX IF NOT EXISTS idx_words_word_lang_native ON words(word, language, native_language)"),
                ("idx_words_language", "words",
                 "CREATE INDEX IF NOT EXISTS idx_words_language ON words(language)"),
                
                # User word familiarity
                ("idx_user_word_fam_user_word_lang", "user_word_familiarity",
                 "CREATE INDEX IF NOT EXISTS idx_user_word_fam_user_word_lang ON user_word_familiarity(user_id, word, language, native_language)"),
            ]
        
        # Check which indexes already exist and create missing ones
        for index_name, table_name, create_sql in indexes:
            try:
                # Check if index exists
                if is_postgresql:
                    check_sql = """
                        SELECT EXISTS (
                            SELECT 1 FROM pg_indexes 
                            WHERE indexname = %s
                        )
                    """
                    result = execute_query(conn, check_sql, (index_name,))
                    exists = result.fetchone()[0] if result else False
                else:
                    # SQLite - check sqlite_master
                    check_sql = "SELECT name FROM sqlite_master WHERE type='index' AND name=?"
                    cursor = conn.cursor()
                    cursor.execute(check_sql, (index_name,))
                    exists = cursor.fetchone() is not None
                    cursor.close()
                
                if exists:
                    indexes_existing.append(index_name)
                    print(f"✓ Index {index_name} already exists")
                else:
                    # Create index
                    execute_query(conn, create_sql)
                    conn.commit()
                    indexes_created.append(index_name)
                    print(f"✅ Created index {index_name} on {table_name}")
            except Exception as e:
                print(f"❌ Error creating index {index_name}: {e}")
        
        print(f"\n📊 Summary:")
        print(f"  ✅ Created: {len(indexes_created)} indexes")
        print(f"  ✓ Existing: {len(indexes_existing)} indexes")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating indexes: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("🚀 Creating performance indexes...")
    print("=" * 50)
    success = create_performance_indexes()
    if success:
        print("\n✅ Performance indexes created successfully!")
    else:
        print("\n❌ Some indexes failed to create. Check errors above.")
        exit(1)

