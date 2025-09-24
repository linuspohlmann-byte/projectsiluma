#!/usr/bin/env python3
"""
Word synchronization utilities to ensure all words are available in the Words tab
"""

import sqlite3
import json
import hashlib
from datetime import datetime, UTC
from typing import List, Set, Dict, Any
from .db import get_db
from .db_multi_user import get_user_native_language, ensure_user_databases
from .multi_user_db import db_manager


def generate_word_hash(word: str, language: str, native_language: str) -> str:
    """Generate stable hash for word identification across databases"""
    content = f"{word}|{language}|{native_language}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def sync_words_for_user(user_id: int, language: str) -> bool:
    """
    Sync all words for a user and language to ensure they appear in the Words tab.
    This function:
    1. Gets all words from the old database for the language
    2. Adds them to the global database if not already present
    3. Unlocks them in the user's local database
    """
    try:
        print(f"Syncing words for user {user_id}, language {language}")
        
        # Get user's native language
        native_language = get_user_native_language(user_id)
        ensure_user_databases(user_id, native_language)
        
        # Get all words from old database for this language
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get all words for this language from old database
        cur.execute("""
            SELECT word, language, native_language, translation, example, example_native, 
                   lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms, 
                   collocations, cefr, freq_rank, tags, note, info, updated_at
            FROM words 
            WHERE language = ?
        """, (language,))
        
        old_words = cur.fetchall()
        conn.close()
        
        if not old_words:
            print(f"No words found in old database for language {language}")
            return True
        
        print(f"Found {len(old_words)} words in old database for language {language}")
        
        # Add words to global database
        words_added = 0
        for word_row in old_words:
            word = word_row['word']
            
            # Create word data from old database
            word_data = {
                'translation': word_row['translation'] or '',
                'example': word_row['example'] or '',
                'example_native': word_row['example_native'] or '',
                'lemma': word_row['lemma'] or '',
                'pos': word_row['pos'] or '',
                'ipa': word_row['ipa'] or '',
                'audio_url': word_row['audio_url'] or '',
                'gender': word_row['gender'] or '',
                'plural': word_row['plural'] or '',
                'conj': word_row['conj'] or {},
                'comp': word_row['comp'] or {},
                'synonyms': word_row['synonyms'] or [],
                'collocations': word_row['collocations'] or [],
                'cefr': word_row['cefr'] or '',
                'freq_rank': word_row['freq_rank'],
                'tags': word_row['tags'] or [],
                'note': word_row['note'] or '',
                'info': word_row['info'] or {}
            }
            
            # Add to global database
            word_hash = db_manager.add_word_to_global(word, language, native_language, word_data)
            if word_hash:
                words_added += 1
        
        print(f"Added {words_added} words to global database")
        
        # Only unlock words that the user has actually encountered in levels
        # This should be based on the user's actual progress, not all words in the database
        # For now, we'll not automatically unlock all words - let the level system handle this
        print(f"Note: Not automatically unlocking all words for user {user_id}")
        print(f"Words will be unlocked when user actually starts/plays levels")
        success = True
        
        if success:
            print(f"Successfully synced words for user {user_id}")
        else:
            print(f"Failed to sync words for user {user_id}")
        
        return success
        
    except Exception as e:
        print(f"Error syncing words for user {user_id}, language {language}: {e}")
        return False


def sync_all_user_words(user_id: int) -> bool:
    """
    Sync all words for a user across all languages
    """
    try:
        print(f"Syncing all words for user {user_id}")
        
        # Get all languages from old database
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT DISTINCT language FROM words WHERE language IS NOT NULL AND language != ''")
        languages = [row['language'] for row in cur.fetchall()]
        conn.close()
        
        print(f"Found languages: {languages}")
        
        success = True
        for language in languages:
            if not sync_words_for_user(user_id, language):
                success = False
        
        return success
        
    except Exception as e:
        print(f"Error syncing all words for user {user_id}: {e}")
        return False


def ensure_level_words_synced(user_id: int, language: str, level: int) -> bool:
    """
    Ensure that all words from a specific level are synced and available.
    This is called when a level is started to make sure all words are available.
    """
    try:
        print(f"Ensuring level {level} words are synced for user {user_id}, language {language}")
        
        # First, sync all words for this language
        sync_success = sync_words_for_user(user_id, language)
        
        if not sync_success:
            print(f"Failed to sync words for language {language}")
            return False
        
        # Now specifically unlock the level words
        from .db_multi_user import unlock_level_words
        level_success = unlock_level_words(user_id, language, level)
        
        if level_success:
            print(f"Successfully ensured level {level} words are synced")
        else:
            print(f"Failed to unlock level {level} words")
        
        return level_success
        
    except Exception as e:
        print(f"Error ensuring level words are synced: {e}")
        return False
