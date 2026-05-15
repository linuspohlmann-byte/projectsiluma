#!/usr/bin/env python3
"""
Debug-Script für Custom Level Progress Problem
Analysiert und behebt das Problem: Level zeigt "completed" aber kein Progress
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.db_config import get_database_config, get_db_connection, execute_query
from server.services.custom_levels import (
    get_custom_level_group,
    get_custom_level,
    get_custom_levels_for_group,
    enrich_custom_level_words_on_demand
)
from server.db_progress_cache import (
    get_custom_level_progress,
    refresh_custom_level_progress,
    calculate_familiarity_counts_from_user_words
)
from server.db_multi_user import get_user_id_from_group_id


def find_story_by_name(story_name_pattern):
    """Finde Story nach Name (case-insensitive)"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            result = execute_query(conn, """
                SELECT id, user_id, group_name, language, native_language, 
                       num_levels, status, created_at
                FROM custom_level_groups
                WHERE LOWER(group_name) LIKE LOWER(%s)
                ORDER BY created_at DESC
            """, (f'%{story_name_pattern}%',))
        else:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, group_name, language, native_language, 
                       num_levels, status, created_at
                FROM custom_level_groups
                WHERE LOWER(group_name) LIKE LOWER(?)
                ORDER BY created_at DESC
            """, (f'%{story_name_pattern}%',))
            result = cursor
        
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
                    'status': row[6],
                    'created_at': row[7]
                })
        
        return stories
    finally:
        conn.close()


def find_level_by_title(group_id, title_pattern):
    """Finde Level nach Titel (case-insensitive)"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            result = execute_query(conn, """
                SELECT id, group_id, level_number, title, topic, word_count,
                       created_at, updated_at
                FROM custom_levels
                WHERE group_id = %s
                  AND (LOWER(title) LIKE LOWER(%s) OR LOWER(topic) LIKE LOWER(%s))
                ORDER BY level_number
            """, (group_id, f'%{title_pattern}%', f'%{title_pattern}%'))
        else:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, group_id, level_number, title, topic, word_count,
                       created_at, updated_at
                FROM custom_levels
                WHERE group_id = ?
                  AND (LOWER(title) LIKE LOWER(?) OR LOWER(topic) LIKE LOWER(?))
                ORDER BY level_number
            """, (group_id, f'%{title_pattern}%', f'%{title_pattern}%'))
            result = cursor
        
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
                    'word_count': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                })
        
        return levels
    finally:
        conn.close()


def analyze_level(group_id, level_number, user_id=None):
    """Analysiere ein Level und zeige alle relevanten Informationen"""
    print(f"\n{'='*60}")
    print(f"Analyse: Group {group_id}, Level {level_number}")
    print(f"{'='*60}\n")
    
    # 1. Level-Daten abrufen
    level_data = get_custom_level(group_id, level_number, user_id)
    if not level_data:
        print(f"❌ Level {level_number} nicht gefunden!")
        return None
    
    print(f"📋 Level-Info:")
    print(f"   Title: {level_data.get('title', 'N/A')}")
    print(f"   Topic: {level_data.get('topic', 'N/A')}")
    print(f"   Word Count (DB): {level_data.get('word_count', 0)}")
    
    # 2. Level-Content prüfen
    content = level_data.get('content', {})
    items = content.get('items', [])
    print(f"\n📝 Content-Info:")
    print(f"   Items: {len(items)}")
    
    if len(items) == 0:
        print(f"   ⚠️ WARNUNG: Level hat keine Items (Sätze)!")
        print(f"   → Level muss generiert werden")
    else:
        # Zähle Wörter
        all_words = set()
        for item in items:
            words = item.get('words', [])
            for word in words:
                if word and word.strip():
                    import re
                    clean_word = re.sub(r'[.!?,;:—–-]+$', '', word.strip().lower())
                    if clean_word:
                        all_words.add(clean_word)
        
        print(f"   Unique Words: {len(all_words)}")
        if len(all_words) == 0:
            print(f"   ⚠️ WARNUNG: Level hat keine Wörter!")
        else:
            print(f"   Sample Words: {list(all_words)[:10]}")
    
    # 3. Progress prüfen (wenn user_id vorhanden)
    if user_id:
        progress = get_custom_level_progress(user_id, group_id, level_number)
        print(f"\n📊 Progress-Info (User {user_id}):")
        
        if not progress:
            print(f"   ⚠️ Kein Progress-Eintrag gefunden!")
            print(f"   → Progress muss initialisiert werden")
        else:
            total_words = progress.get('total_words', 0)
            fam_counts = progress.get('fam_counts', {})
            status = progress.get('status', 'not_started')
            score = progress.get('score')
            
            print(f"   Status: {status}")
            print(f"   Total Words: {total_words}")
            print(f"   Score: {score}")
            print(f"   Familiarity Counts:")
            for i in range(6):
                count = fam_counts.get(i, 0)
                print(f"      Level {i}: {count}")
            
            # Problem-Erkennung
            if status == 'completed' and total_words == 0:
                print(f"\n   ⚠️ PROBLEM: Level ist 'completed' aber total_words = 0!")
                print(f"   → Progress muss refresht werden")
            elif status == 'completed' and sum(fam_counts.values()) == 0:
                print(f"\n   ⚠️ PROBLEM: Level ist 'completed' aber keine Familiarity-Counts!")
                print(f"   → Progress muss refresht werden")
            elif total_words == 0 and len(all_words) > 0:
                print(f"\n   ⚠️ PROBLEM: Level hat Wörter aber total_words = 0!")
                print(f"   → Progress muss refresht werden")
    
    return {
        'level_data': level_data,
        'progress': progress if user_id else None,
        'has_items': len(items) > 0,
        'has_words': len(all_words) > 0 if items else False,
        'word_count': len(all_words) if items else 0
    }


def fix_level_progress(group_id, level_number, user_id=None, force_refresh=False):
    """Behebe Progress-Probleme für ein Level"""
    print(f"\n{'='*60}")
    print(f"Fix: Group {group_id}, Level {level_number}")
    print(f"{'='*60}\n")
    
    # 1. Prüfe ob Level generiert ist
    level_data = get_custom_level(group_id, level_number, user_id)
    if not level_data:
        print(f"❌ Level nicht gefunden!")
        return False
    
    content = level_data.get('content', {})
    items = content.get('items', [])
    
    # 2. Falls Level nicht generiert, generiere es
    if len(items) == 0:
        print(f"📝 Level hat keine Items - generiere Level...")
        
        group_info = get_custom_level_group(group_id, user_id)
        if not group_info:
            print(f"❌ Group nicht gefunden!")
            return False
        
        language = group_info.get('language')
        native_language = group_info.get('native_language')
        
        success = enrich_custom_level_words_on_demand(
            group_id, level_number, language, native_language
        )
        
        if success:
            print(f"✅ Level erfolgreich generiert!")
            # Level-Daten neu laden
            level_data = get_custom_level(group_id, level_number, user_id)
            content = level_data.get('content', {})
            items = content.get('items', [])
        else:
            print(f"❌ Level-Generierung fehlgeschlagen!")
            return False
    
    # 3. Prüfe Progress (wenn user_id vorhanden)
    if user_id:
        progress = get_custom_level_progress(user_id, group_id, level_number)
        
        needs_refresh = False
        if not progress:
            print(f"📊 Kein Progress-Eintrag - erstelle neuen...")
            needs_refresh = True
        elif force_refresh:
            print(f"🔄 Force-Refresh angefordert...")
            needs_refresh = True
        elif progress.get('total_words', 0) == 0:
            print(f"📊 Progress hat total_words = 0 - refreshe...")
            needs_refresh = True
        elif progress.get('status') == 'completed' and sum(progress.get('fam_counts', {}).values()) == 0:
            print(f"📊 Progress ist 'completed' aber keine Counts - refreshe...")
            needs_refresh = True
        
        if needs_refresh:
            print(f"🔄 Refreshe Progress...")
            success = refresh_custom_level_progress(user_id, group_id, level_number)
            if success:
                print(f"✅ Progress erfolgreich refresht!")
                
                # Zeige neuen Progress
                new_progress = get_custom_level_progress(user_id, group_id, level_number)
                if new_progress:
                    print(f"\n📊 Neuer Progress:")
                    print(f"   Total Words: {new_progress.get('total_words', 0)}")
                    print(f"   Status: {new_progress.get('status', 'not_started')}")
                    print(f"   Score: {new_progress.get('score')}")
                    fam_counts = new_progress.get('fam_counts', {})
                    for i in range(6):
                        print(f"   Level {i}: {fam_counts.get(i, 0)}")
            else:
                print(f"❌ Progress-Refresh fehlgeschlagen!")
                return False
        else:
            print(f"✅ Progress ist bereits korrekt")
    
    return True


def main():
    """Hauptfunktion"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Debug Custom Level Progress')
    parser.add_argument('--story', type=str, help='Story-Name (Pattern)')
    parser.add_argument('--level-title', type=str, help='Level-Titel (Pattern)')
    parser.add_argument('--group-id', type=int, help='Group ID')
    parser.add_argument('--level-number', type=int, help='Level Number')
    parser.add_argument('--user-id', type=int, help='User ID (optional)')
    parser.add_argument('--fix', action='store_true', help='Fix-Probleme automatisch')
    parser.add_argument('--force-refresh', action='store_true', help='Force-Refresh Progress')
    
    args = parser.parse_args()
    
    # Finde Story
    if args.story:
        stories = find_story_by_name(args.story)
        if not stories:
            print(f"❌ Keine Story gefunden mit Pattern: {args.story}")
            return
        
        print(f"📚 Gefundene Stories:")
        for story in stories:
            print(f"   ID: {story['id']}, Name: {story['group_name']}, User: {story['user_id']}")
        
        if len(stories) > 1:
            print(f"\n⚠️ Mehrere Stories gefunden - verwende erste")
        
        group_id = stories[0]['id']
        if not args.user_id:
            args.user_id = stories[0]['user_id']
    elif args.group_id:
        group_id = args.group_id
    else:
        print(f"❌ Bitte --story oder --group-id angeben!")
        return
    
    # Finde Level
    if args.level_title:
        levels = find_level_by_title(group_id, args.level_title)
        if not levels:
            print(f"❌ Kein Level gefunden mit Pattern: {args.level_title}")
            return
        
        print(f"\n📖 Gefundene Level:")
        for level in levels:
            print(f"   Level {level['level_number']}: {level['title']}")
        
        if len(levels) > 1:
            print(f"\n⚠️ Mehrere Level gefunden - verwende erstes")
        
        level_number = levels[0]['level_number']
    elif args.level_number:
        level_number = args.level_number
    else:
        print(f"❌ Bitte --level-title oder --level-number angeben!")
        return
    
    # Analysiere
    analysis = analyze_level(group_id, level_number, args.user_id)
    
    # Fix falls gewünscht
    if args.fix and analysis:
        fix_level_progress(group_id, level_number, args.user_id, args.force_refresh)


if __name__ == '__main__':
    main()


