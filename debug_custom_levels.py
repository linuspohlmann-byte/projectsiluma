#!/usr/bin/env python3
"""
Debug script to check custom level creation
"""

import os
import sys
import json
from datetime import datetime, UTC

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_custom_levels():
    """Debug custom level creation"""
    print("🔍 Debugging custom level creation...")
    
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            # Check if custom_levels table exists and has word_count column
            if config['type'] == 'postgresql':
                result = execute_query(conn, '''
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'custom_levels'
                    ORDER BY ordinal_position
                ''')
                columns = [row['column_name'] for row in result.fetchall()]
            else:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(custom_levels)")
                columns = [column[1] for column in cursor.fetchall()]
            
            print(f"📊 Custom levels table columns: {columns}")
            
            # Check if word_count column exists
            if 'word_count' in columns:
                print("✅ word_count column exists")
            else:
                print("❌ word_count column missing")
            
            # Get all custom level groups
            if config['type'] == 'postgresql':
                result = execute_query(conn, "SELECT id, group_name, language, native_language FROM custom_level_groups ORDER BY id DESC LIMIT 5")
                groups = [dict(row) for row in result.fetchall()]
            else:
                cursor = conn.cursor()
                cursor.execute("SELECT id, group_name, language, native_language FROM custom_level_groups ORDER BY id DESC LIMIT 5")
                groups = [{'id': row[0], 'group_name': row[1], 'language': row[2], 'native_language': row[3]} for row in cursor.fetchall()]
            
            print(f"📚 Recent custom level groups: {len(groups)}")
            for group in groups:
                print(f"  - ID: {group['id']}, Name: {group['group_name']}, Lang: {group['language']}")
            
            # Check levels for the most recent group
            if groups:
                latest_group = groups[0]
                group_id = latest_group['id']
                
                if config['type'] == 'postgresql':
                    result = execute_query(conn, '''
                        SELECT level_number, title, topic, word_count, 
                               CASE WHEN content::text = '{}' THEN 'empty' ELSE 'has_content' END as content_status
                        FROM custom_levels 
                        WHERE group_id = %s 
                        ORDER BY level_number
                    ''', (group_id,))
                    levels = [dict(row) for row in result.fetchall()]
                else:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT level_number, title, topic, word_count, 
                               CASE WHEN content = '{}' THEN 'empty' ELSE 'has_content' END as content_status
                        FROM custom_levels 
                        WHERE group_id = ? 
                        ORDER BY level_number
                    ''', (group_id,))
                    levels = [{'level_number': row[0], 'title': row[1], 'topic': row[2], 'word_count': row[3], 'content_status': row[4]} for row in cursor.fetchall()]
                
                print(f"📖 Levels for group {group_id} ({latest_group['group_name']}): {len(levels)}")
                for level in levels:
                    print(f"  - Level {level['level_number']}: {level['title']} (words: {level['word_count']}, content: {level['content_status']})")
                
                if len(levels) == 0:
                    print("❌ No levels found for this group!")
                else:
                    print(f"✅ Found {len(levels)} levels")
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_custom_levels()
