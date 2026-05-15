#!/usr/bin/env python3
"""Einfaches Script um Level-ID zu finden"""

import os
import sys
from urllib.parse import urlparse

# Prüfe ob DATABASE_URL gesetzt ist
database_url = os.getenv('DATABASE_URL')
if not database_url:
    print("❌ DATABASE_URL nicht gesetzt!")
    sys.exit(1)

# Parse DATABASE_URL
parsed = urlparse(database_url)
if parsed.scheme not in ('postgres', 'postgresql'):
    print(f"❌ Unsupported database scheme: {parsed.scheme}")
    sys.exit(1)

# Versuche psycopg2 zu verwenden (falls verfügbar)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Finde Story
    cursor.execute("""
        SELECT id, user_id, group_name, language, native_language, num_levels
        FROM custom_level_groups
        WHERE LOWER(group_name) LIKE LOWER(%s)
        ORDER BY created_at DESC
        LIMIT 5
    """, ('%Kleine Gespräche%',))
    
    stories = cursor.fetchall()
    if not stories:
        print("❌ Keine Story gefunden mit 'Kleine Gespräche'")
        sys.exit(1)
    
    print(f"📚 Gefundene Stories:")
    for story in stories:
        print(f"   ID: {story['id']}, Name: {story['group_name']}, User: {story['user_id']}")
    
    # Verwende erste Story
    group_id = stories[0]['id']
    print(f"\n🔍 Suche Level in Story ID {group_id}...")
    
    # 2. Finde Level
    cursor.execute("""
        SELECT id, group_id, level_number, title, topic, word_count
        FROM custom_levels
        WHERE group_id = %s
          AND (LOWER(title) LIKE LOWER(%s) 
               OR LOWER(title) LIKE LOWER(%s)
               OR LOWER(topic) LIKE LOWER(%s))
        ORDER BY level_number
    """, (group_id, '%Park%', '%spielen%', '%treffen%'))
    
    levels = cursor.fetchall()
    if not levels:
        print(f"❌ Kein Level gefunden mit 'Park', 'spielen' oder 'treffen'")
        sys.exit(1)
    
    print(f"\n📖 Gefundene Level:")
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
    
    cursor.close()
    conn.close()
    
except ImportError:
    print("❌ psycopg2 nicht installiert. Versuche pg8000...")
    try:
        import pg8000.dbapi as pg8000
        
        # Parse connection parameters
        host = parsed.hostname or 'localhost'
        port = parsed.port or 5432
        database = parsed.path[1:] if parsed.path else None
        user = parsed.username
        password = parsed.password
        
        conn = pg8000.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        
        # 1. Finde Story
        cursor.execute("""
            SELECT id, user_id, group_name, language, native_language, num_levels
            FROM custom_level_groups
            WHERE LOWER(group_name) LIKE LOWER(%s)
            ORDER BY created_at DESC
            LIMIT 5
        """, ('%Kleine Gespräche%',))
        
        stories = cursor.fetchall()
        if not stories:
            print("❌ Keine Story gefunden mit 'Kleine Gespräche'")
            sys.exit(1)
        
        print(f"📚 Gefundene Stories:")
        for story in stories:
            print(f"   ID: {story[0]}, Name: {story[2]}, User: {story[1]}")
        
        group_id = stories[0][0]
        print(f"\n🔍 Suche Level in Story ID {group_id}...")
        
        # 2. Finde Level
        cursor.execute("""
            SELECT id, group_id, level_number, title, topic, word_count
            FROM custom_levels
            WHERE group_id = %s
              AND (LOWER(title) LIKE LOWER(%s) 
                   OR LOWER(title) LIKE LOWER(%s)
                   OR LOWER(topic) LIKE LOWER(%s))
            ORDER BY level_number
        """, (group_id, '%Park%', '%spielen%', '%treffen%'))
        
        levels = cursor.fetchall()
        if not levels:
            print(f"❌ Kein Level gefunden mit 'Park', 'spielen' oder 'treffen'")
            sys.exit(1)
        
        print(f"\n📖 Gefundene Level:")
        for level in levels:
            print(f"   Level ID: {level[0]}")
            print(f"   Level Number: {level[2]}")
            print(f"   Title: {level[3]}")
            print(f"   Topic: {level[4]}")
            print(f"   Word Count: {level[5]}")
            print()
        
        if levels:
            level = levels[0]
            print(f"✅ Level-ID: {level[0]}")
            print(f"   Group ID: {level[1]}")
            print(f"   Level Number: {level[2]}")
            print(f"   Title: {level[3]}")
        
        cursor.close()
        conn.close()
        
    except ImportError:
        print("❌ Weder psycopg2 noch pg8000 installiert!")
        print("   Installiere mit: pip install psycopg2-binary")
        sys.exit(1)


