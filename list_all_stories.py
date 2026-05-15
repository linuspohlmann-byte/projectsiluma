#!/usr/bin/env python3
"""Liste alle Stories und Level auf"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.db_config import get_database_config, get_db_connection, execute_query

def list_all():
    """Liste alle Stories und ihre Level"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        print(f"📊 Datenbank-Typ: {config['type']}\n")
        
        # Liste alle Stories
        if config['type'] == 'postgresql':
            result = execute_query(conn, """
                SELECT id, user_id, group_name, language, native_language, num_levels, created_at
                FROM custom_level_groups
                ORDER BY created_at DESC
                LIMIT 20
            """)
        else:
            result = execute_query(conn, """
                SELECT id, user_id, group_name, language, native_language, num_levels, created_at
                FROM custom_level_groups
                ORDER BY created_at DESC
                LIMIT 20
            """)
        
        stories = []
        for row in result.fetchall():
            if isinstance(row, dict):
                stories.append(row)
            else:
                stories.append({
                    'id': row[0],
                    'user_id': row[1],
                    'group_name': row[2],
                    'language': row[3],
                    'native_language': row[4],
                    'num_levels': row[5],
                    'created_at': row[6]
                })
        
        if not stories:
            print("❌ Keine Stories gefunden in der Datenbank")
            return
        
        print(f"📚 Gefundene Stories ({len(stories)}):\n")
        for story in stories:
            print(f"   Story ID: {story['id']}")
            print(f"   Name: {story['group_name']}")
            print(f"   User ID: {story['user_id']}")
            print(f"   Sprache: {story['language']} → {story['native_language']}")
            print(f"   Level: {story['num_levels']}")
            
            # Liste Level dieser Story
            if config['type'] == 'postgresql':
                level_result = execute_query(conn, """
                    SELECT id, level_number, title, topic, word_count
                    FROM custom_levels
                    WHERE group_id = %s
                    ORDER BY level_number
                    LIMIT 10
                """, (story['id'],))
            else:
                level_result = execute_query(conn, """
                    SELECT id, level_number, title, topic, word_count
                    FROM custom_levels
                    WHERE group_id = ?
                    ORDER BY level_number
                    LIMIT 10
                """, (story['id'],))
            
            levels = []
            for row in level_result.fetchall():
                if isinstance(row, dict):
                    levels.append(row)
                else:
                    levels.append({
                        'id': row[0],
                        'level_number': row[1],
                        'title': row[2],
                        'topic': row[3],
                        'word_count': row[4]
                    })
            
            if levels:
                print(f"   Level:")
                for level in levels:
                    print(f"      - Level ID: {level['id']}, Nummer: {level['level_number']}, Titel: {level['title']}, Words: {level['word_count']}")
            else:
                print(f"   (Keine Level gefunden)")
            
            print()
        
    finally:
        conn.close()

if __name__ == '__main__':
    list_all()


