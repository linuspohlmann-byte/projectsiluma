#!/usr/bin/env python3
"""
Extended Database Functions with Multi-User Support
Integrates with the new multi-user database structure
"""

import sqlite3
import json
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
from .multi_user_db import db_manager

def get_db():
    """Get connection to main database (for backward compatibility)"""
    conn = sqlite3.connect('polo.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_native_language(user_id: int) -> str:
    """Get user's native language from native_language column or settings or default to 'en'"""
    conn = get_db()
    try:
        cur = conn.cursor()
        # First try to get from native_language column
        cur.execute("SELECT native_language FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        
        if row and row['native_language']:
            return row['native_language']
        
        # Fallback to settings
        cur.execute("SELECT settings FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        
        if row and row['settings']:
            settings = json.loads(row['settings'])
            return settings.get('native_language', 'en')
        
        return 'en'  # Default to English
    finally:
        conn.close()

def update_user_native_language(user_id: int, native_language: str) -> bool:
    """Update user's native language in both settings and native_language column"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT settings FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        
        if not row:
            print(f"User {user_id} not found")
            return False
            
        settings = json.loads(row['settings']) if row['settings'] else {}
        settings['native_language'] = native_language
        
        # Update both settings JSON and native_language column
        cur.execute("UPDATE users SET settings = ?, native_language = ? WHERE id = ?", 
                   (json.dumps(settings), native_language, user_id))
        conn.commit()
        print(f"Successfully updated native language for user {user_id} to {native_language}")
        return True
    except Exception as e:
        print(f"Error updating user native language: {e}")
        return False
    finally:
        conn.close()

def ensure_user_databases(user_id: int, native_language: str = None):
    """Ensure user has databases for their native language"""
    if not native_language:
        native_language = get_user_native_language(user_id)
    
    # Ensure global database exists
    db_manager.ensure_global_database(native_language)
    
    # Ensure user database exists
    db_manager.ensure_user_database(user_id, native_language)
    
    return native_language

def get_level_words_with_familiarity(language: str, level: int, user_id: int = None) -> Dict[str, Any]:
    """Get level words with familiarity data for user"""
    
    # Get words from level file
    level_file = f"data/{language}/levels/{level}.json"
    try:
        with open(level_file, 'r', encoding='utf-8') as f:
            level_data = json.load(f)
        
        # Extract words from items if words array doesn't exist
        words = level_data.get('words', [])
        if not words and 'items' in level_data:
            words = []
            for item in level_data['items']:
                if 'words' in item:
                    words.extend(item['words'])
    except FileNotFoundError:
        return {'words': [], 'familiarity_data': {}}
    
    if not user_id:
        # Return words without familiarity data
        return {
            'words': words,
            'familiarity_data': {},
            'total_words': len(words),
            'memorized_words': 0
        }
    
    # Get user's native language
    native_language = get_user_native_language(user_id)
    ensure_user_databases(user_id, native_language)
    
    # Generate word hashes
    word_hashes = []
    for word in words:
        word_hash = db_manager.generate_word_hash(word, language, native_language)
        word_hashes.append(word_hash)
    
    # Get familiarity data from user's local database
    familiarity_data = db_manager.get_user_word_familiarity(user_id, native_language, word_hashes)
    
    # Calculate statistics
    total_words = len(words)
    memorized_words = sum(1 for data in familiarity_data.values() if data.get('familiarity', 0) >= 5)
    
    return {
        'words': words,
        'familiarity_data': familiarity_data,
        'total_words': total_words,
        'memorized_words': memorized_words,
        'word_hashes': word_hashes
    }

def unlock_level_words(user_id: int, language: str, level: int) -> bool:
    """Unlock words for user when starting a level"""
    
    # Get words from level file
    level_file = f"data/{language}/levels/{level}.json"
    try:
        with open(level_file, 'r', encoding='utf-8') as f:
            level_data = json.load(f)
        
        # Extract words from items
        words = []
        items = level_data.get('items', [])
        for item in items:
            item_words = item.get('words', [])
            words.extend(item_words)
        
        # Remove duplicates while preserving order
        words = list(dict.fromkeys(words))
    except FileNotFoundError:
        return False
    
    if not words:
        return False
    
    # Get user's native language
    native_language = get_user_native_language(user_id)
    ensure_user_databases(user_id, native_language)
    
    # Ensure words exist in global database
    for word in words:
        # Try to get existing word data from old database
        from .db import get_db
        conn = get_db()
        
        # First try to get word for specific native language
        existing_word = conn.execute(
            'SELECT word, language, native_language, translation, example, example_native, lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms, collocations, cefr, freq_rank, tags, note, info, updated_at FROM words WHERE word=? AND language=? AND native_language=? LIMIT 1',
            (word, language, native_language)
        ).fetchone()
        
        # If not found, try to get any word with translation for this word/language
        if not existing_word or not existing_word['translation']:
            existing_word = conn.execute(
                'SELECT word, language, native_language, translation, example, example_native, lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms, collocations, cefr, freq_rank, tags, note, info, updated_at FROM words WHERE word=? AND language=? AND translation IS NOT NULL AND translation != "" LIMIT 1',
                (word, language)
            ).fetchone()
        
        conn.close()
        
        if existing_word:
            # Use existing data from old database
            word_data = {
                'translation': existing_word['translation'] or '',
                'example': existing_word['example'] or '',
                'example_native': existing_word['example_native'] or '',
                'lemma': existing_word['lemma'] or '',
                'pos': existing_word['pos'] or '',
                'ipa': existing_word['ipa'] or '',
                'audio_url': existing_word['audio_url'] or '',
                'gender': existing_word['gender'] or '',
                'plural': existing_word['plural'] or '',
                'conj': existing_word['conj'] or {},
                'comp': existing_word['comp'] or {},
                'synonyms': existing_word['synonyms'] or [],
                'collocations': existing_word['collocations'] or [],
                'cefr': existing_word['cefr'] or '',
                'freq_rank': existing_word['freq_rank'],
                'tags': existing_word['tags'] or [],
                'note': existing_word['note'] or '',
                'info': existing_word['info'] or {}
            }
        else:
            # Create minimal entry that will be filled by AI if needed
            word_data = {
                'translation': '',
                'example': '',
                'example_native': '',
                'lemma': '',
                'pos': '',
                'ipa': '',
                'audio_url': '',
                'gender': '',
                'plural': '',
                'conj': {},
                'comp': {},
                'synonyms': [],
                'collocations': [],
                'cefr': '',
                'freq_rank': None,
                'tags': [],
                'note': '',
                'info': {}
            }
        
        # Add word to global database (this will create the global_words table if it doesn't exist)
        db_manager.add_word_to_global(word, language, native_language, word_data)
    
    # Generate word hashes
    word_hashes = []
    for word in words:
        word_hash = db_manager.generate_word_hash(word, language, native_language)
        word_hashes.append(word_hash)
    
    # Unlock words for user
    return db_manager.unlock_words_for_level(user_id, native_language, level, language, word_hashes)

def update_word_familiarity(user_id: int, word: str, language: str, 
                           familiarity: int, seen_count: int = None, correct_count: int = None) -> bool:
    """Update user's word familiarity"""
    
    native_language = get_user_native_language(user_id)
    ensure_user_databases(user_id, native_language)
    
    word_hash = db_manager.generate_word_hash(word, language, native_language)
    
    return db_manager.update_user_word_familiarity(
        user_id, native_language, word_hash, familiarity, seen_count, correct_count
    )

def get_familiarity_counts_for_level(language: str, level: int, user_id: int = None) -> Dict[int, int]:
    """Get familiarity count distribution for specific level"""
    
    if not user_id:
        # Return empty counts for non-authenticated users
        return {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    # Get user's native language
    native_language = get_user_native_language(user_id)
    ensure_user_databases(user_id, native_language)
    
    # Get level words from level file
    level_file = f"data/{language}/levels/{level}.json"
    try:
        with open(level_file, 'r', encoding='utf-8') as f:
            level_data = json.load(f)
        
        # Extract words from items
        level_words = []
        for item in level_data.get('items', []):
            if 'words' in item:
                level_words.extend(item['words'])
    except FileNotFoundError:
        return {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    if not level_words:
        return {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    # Get familiarity counts for level words only
    db_path = db_manager.get_user_db_path(user_id, native_language)
    if not os.path.exists(db_path):
        return {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    try:
        # Generate word hashes for level words
        level_word_hashes = []
        for word in level_words:
            word_hash = db_manager.generate_word_hash(word, language, native_language)
            level_word_hashes.append(word_hash)
        
        # Get familiarity counts for level words only
        placeholders = ','.join(['?' for _ in level_word_hashes])
        cur.execute(f"""
            SELECT familiarity, COUNT(*) as count
            FROM words_local
            WHERE word_hash IN ({placeholders})
            GROUP BY familiarity
        """, level_word_hashes)
        
        counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for row in cur.fetchall():
            fam_level = max(0, min(5, row['familiarity']))  # Clamp to 0-5
            counts[fam_level] = row['count']
        
        # Count words that are in the database but not learned (familiarity 0)
        # This gives us the actual count of unknown words in the database
        total_in_db = sum(counts[i] for i in range(6))  # All words in database
        total_learned = sum(counts[i] for i in range(1, 6))  # Learned words
        counts[0] = total_in_db - total_learned  # Unknown words in database
        
        # Add words that are not in the database at all as unknown
        words_not_in_db = len(level_words) - total_in_db
        counts[0] += words_not_in_db
        
        return counts
        
    except Exception as e:
        print(f"Error getting familiarity counts for level {level}: {e}")
        return {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    finally:
        conn.close()

def get_user_level_stats(user_id: int, language: str, level: int) -> Dict[str, Any]:
    """Get comprehensive level statistics for user"""
    
    if not user_id:
        return {
            'total_words': 0,
            'memorized_words': 0,
            'familiarity_counts': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            'level_score': 0.0
        }
    
    # Get level words with familiarity data
    level_data = get_level_words_with_familiarity(language, level, user_id)
    
    # Get level score from main database
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT score FROM user_progress 
            WHERE user_id = ? AND language = ? AND level = ?
        """, (user_id, language, level))
        
        row = cur.fetchone()
        level_score = row['score'] if row and row['score'] else 0.0
    finally:
        conn.close()
    
    # Get familiarity counts
    familiarity_counts = get_familiarity_counts_for_level(language, level, user_id)
    
    return {
        'total_words': level_data['total_words'],
        'memorized_words': level_data['memorized_words'],
        'familiarity_counts': familiarity_counts,
        'level_score': level_score,
        'words': level_data.get('words', []),
        'word_hashes': level_data.get('word_hashes', []),
        'familiarity_data': level_data.get('familiarity_data', {})
    }

def get_global_level_stats(language: str, level: int) -> Dict[str, Any]:
    """Get global level statistics (not user-specific)"""
    
    # Get words from level file
    level_file = f"data/{language}/levels/{level}.json"
    try:
        with open(level_file, 'r', encoding='utf-8') as f:
            level_data = json.load(f)
        words = level_data.get('words', [])
    except FileNotFoundError:
        return {'total_words': 0, 'level_score': 0.0}
    
    # Get global level score from main database
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT AVG(score) as avg_score FROM level_runs 
            WHERE level = ? AND score IS NOT NULL
        """, (level,))
        
        row = cur.fetchone()
        level_score = row['avg_score'] if row and row['avg_score'] else 0.0
    finally:
        conn.close()
    
    return {
        'total_words': len(words),
        'level_score': level_score
    }

# Backward compatibility functions
def fam_counts_for_level(lang: str, level: int) -> Dict[int, int]:
    """Backward compatibility: Get familiarity counts for level (global)"""
    return get_global_level_stats(lang, level)

def fam_counts_for_words(words: set[str], language: str = None) -> Dict[int, int]:
    """Backward compatibility: Get familiarity counts for words (global)"""
    # This function is used for global statistics, so return empty counts
    return {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

def get_all_users() -> List[Dict[str, Any]]:
    """Get all users from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT id, username, email, native_language FROM users")
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row['id'],
                'username': row['username'],
                'email': row['email'],
                'native_language': row['native_language']
            })
        return users
    finally:
        conn.close()

# Import all functions from original db.py for backward compatibility
from .db import *
