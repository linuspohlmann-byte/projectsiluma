#!/usr/bin/env python3
"""Einfaches Script um Level-ID zu finden - verwendet vorhandene DB-Config"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.db_config import get_database_config, get_db_connection, execute_query

def find_level():
    """Finde Level-ID für 'Im Park spielen und treffen'"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        print(f"📊 Datenbank-Typ: {config['type']}\n")
        
        # 1. Finde Story
        if config['type'] == 'postgresql':
            result = execute_query(conn, """
                SELECT id, user_id, group_name, language, native_language, num_levels
                FROM custom_level_groups
                WHERE LOWER(group_name) LIKE LOWER(%s)
                ORDER BY created_at DESC
                LIMIT 5
            """, ('%Kleine Gespräche%',))
        else:
            result = execute_query(conn, """
                SELECT id, user_id, group_name, language, native_language, num_levels
                FROM custom_level_groups
                WHERE LOWER(group_name) LIKE LOWER(?)
                ORDER BY created_at DESC
                LIMIT 5
            """, ('%Kleine Gespräche%',))
        
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
                    'num_levels': row[5]
                })
        
        if not stories:
            print("❌ Keine Story gefunden mit 'Kleine Gespräche'")
            return
        
        print(f"📚 Gefundene Stories:")
        for story in stories:
            print(f"   ID: {story['id']}, Name: {story['group_name']}, User: {story['user_id']}")
        
        group_id = stories[0]['id']
        print(f"\n🔍 Suche Level in Story ID {group_id}...\n")
        
        # 2. Finde Level
        if config['type'] == 'postgresql':
            result = execute_query(conn, """
                SELECT id, group_id, level_number, title, topic, word_count
                FROM custom_levels
                WHERE group_id = %s
                  AND (LOWER(title) LIKE LOWER(%s) 
                       OR LOWER(title) LIKE LOWER(%s)
                       OR LOWER(title) LIKE LOWER(%s)
                       OR LOWER(topic) LIKE LOWER(%s))
                ORDER BY level_number
            """, (group_id, '%Park%', '%spielen%', '%treffen%', '%Park%'))
        else:
            result = execute_query(conn, """
                SELECT id, group_id, level_number, title, topic, word_count
                FROM custom_levels
                WHERE group_id = ?
                  AND (LOWER(title) LIKE LOWER(?) 
                       OR LOWER(title) LIKE LOWER(?)
                       OR LOWER(title) LIKE LOWER(?)
                       OR LOWER(topic) LIKE LOWER(?))
                ORDER BY level_number
            """, (group_id, '%Park%', '%spielen%', '%treffen%', '%Park%'))
        
        levels = []
        for row in result.fetchall():
            if isinstance(row, dict):
                levels.append(row)
            else:
                levels.append({
                    'id': row[0],
                    'group_id': row[1],
                    'level_number': row[2],
                    'title': row[3],
                    'topic': row[4],
                    'word_count': row[5]
                })
        
        if not levels:
            print(f"❌ Kein Level gefunden mit 'Park', 'spielen' oder 'treffen'")
            return
        
        print(f"📖 Gefundene Level:")
        for level in levels:
            print(f"   Level ID: {level['id']}")
            print(f"   Level Number: {level['level_number']}")
            print(f"   Title: {level['title']}")
            print(f"   Topic: {level['topic']}")
            print(f"   Word Count: {level['word_count']}")
            print()
        
        # Zeige die ID des ersten gefundenen Levels
        if levels:
            level = levels[0]
            print(f"✅ Level-ID: {level['id']}")
            print(f"   Group ID: {level['group_id']}")
            print(f"   Level Number: {level['level_number']}")
            print(f"   Title: {level['title']}")
        
    finally:
        conn.close()

if __name__ == '__main__':
    find_level()


