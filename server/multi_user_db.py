#!/usr/bin/env python3
"""
Multi-User & Multi-Language Database Management System
Handles global databases per native language and user-specific local databases
"""

import sqlite3
import hashlib
import json
import os
from datetime import datetime, UTC
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

class MultiUserDBManager:
    """Manages global databases per native language and user-specific local databases"""
    
    def __init__(self, base_path: str = "databases"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.base_path / "global").mkdir(exist_ok=True)
        (self.base_path / "users").mkdir(exist_ok=True)
    
    def generate_word_hash(self, word: str, language: str, native_language: str) -> str:
        """Generate stable hash for word identification across databases"""
        content = f"{word}|{language}|{native_language}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get_global_db_path(self, native_language: str) -> str:
        """Get path to global database for specific native language"""
        return str(self.base_path / "global" / f"words_global_{native_language}.db")
    
    def get_user_db_path(self, user_id: int, native_language: str) -> str:
        """Get path to user's local database for specific native language"""
        return str(self.base_path / "users" / f"user_{user_id}_{native_language}.db")
    
    def create_global_database(self, native_language: str) -> bool:
        """Create global database for specific native language"""
        db_path = self.get_global_db_path(native_language)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        try:
            # Create words_global table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS words_global (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT NOT NULL,
                    language TEXT NOT NULL,
                    native_language TEXT NOT NULL,
                    translation TEXT,
                    example TEXT,
                    info TEXT,
                    lemma TEXT,
                    pos TEXT,
                    ipa TEXT,
                    audio_url TEXT,
                    gender TEXT,
                    plural TEXT,
                    conj TEXT,
                    comp TEXT,
                    synonyms TEXT,
                    collocations TEXT,
                    example_native TEXT,
                    cefr TEXT,
                    freq_rank INTEGER,
                    tags TEXT,
                    note TEXT,
                    word_hash TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create index for fast lookups
            cur.execute("CREATE INDEX IF NOT EXISTS idx_word_hash ON words_global(word_hash)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_word_lang ON words_global(word, language)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_native_lang ON words_global(native_language)")
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error creating global database for {native_language}: {e}")
            return False
        finally:
            conn.close()
    
    def create_user_database(self, user_id: int, native_language: str) -> bool:
        """Create user's local database for specific native language"""
        db_path = self.get_user_db_path(user_id, native_language)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        try:
            # Create words_local table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS words_local (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word_hash TEXT NOT NULL,
                    familiarity INTEGER DEFAULT 0,
                    seen_count INTEGER DEFAULT 0,
                    correct_count INTEGER DEFAULT 0,
                    unlocked_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(word_hash)
                )
            """)
            
            # Create level_words table for tracking unlocked words per level
            cur.execute("""
                CREATE TABLE IF NOT EXISTS level_words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    word_hashes TEXT NOT NULL,  -- JSON array of word hashes
                    unlocked_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Create indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_word_hash ON words_local(word_hash)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_level_lang ON level_words(level, language)")
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error creating user database for user {user_id}, language {native_language}: {e}")
            return False
        finally:
            conn.close()
    
    def ensure_global_database(self, native_language: str) -> bool:
        """Ensure global database exists for native language"""
        try:
            db_path = self.get_global_db_path(native_language)
            if not os.path.exists(db_path):
                return self.create_global_database(native_language)
            return True
        except Exception as e:
            print(f"Error ensuring global database for {native_language}: {e}")
            return False
    
    def ensure_user_database(self, user_id: int, native_language: str) -> bool:
        """Ensure user database exists for native language"""
        # Check if we should use PostgreSQL instead of local SQLite
        from .db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        if config['type'] == 'postgresql':
            # Use PostgreSQL - ensure user_word_familiarity table exists
            conn = get_db_connection()
            try:
                # Create user_word_familiarity table if it doesn't exist
                execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS user_word_familiarity (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        word_hash TEXT NOT NULL,
                        native_language TEXT NOT NULL,
                        familiarity INTEGER DEFAULT 0,
                        seen_count INTEGER DEFAULT 0,
                        correct_count INTEGER DEFAULT 0,
                        unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, word_hash, native_language)
                    )
                """)
                
                # Create indexes
                execute_query(conn, "CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_user_hash ON user_word_familiarity(user_id, word_hash)")
                execute_query(conn, "CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_native_lang ON user_word_familiarity(native_language)")
                
                conn.commit()
                return True
                
            except Exception as e:
                print(f"Error ensuring PostgreSQL user database: {e}")
                return False
            finally:
                conn.close()
        else:
            # Fallback to local SQLite databases
            try:
                db_path = self.get_user_db_path(user_id, native_language)
                if not os.path.exists(db_path):
                    return self.create_user_database(user_id, native_language)
                return True
            except Exception as e:
                print(f"Error ensuring user database for user {user_id}, language {native_language}: {e}")
                return False
    
    def add_word_to_global(self, word: str, language: str, native_language: str, 
                          word_data: Dict[str, Any]) -> Optional[str]:
        """Add word to global database and return word_hash"""
        if not self.ensure_global_database(native_language):
            return None
        
        word_hash = self.generate_word_hash(word, language, native_language)
        db_path = self.get_global_db_path(native_language)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        try:
            now = datetime.now(UTC).isoformat()
            
            # Convert complex data types to JSON strings
            info_json = json.dumps(word_data.get('info', {})) if isinstance(word_data.get('info'), (dict, list)) else (str(word_data.get('info', '')) if word_data.get('info') else None)
            conj_json = json.dumps(word_data.get('conj', {})) if isinstance(word_data.get('conj'), dict) else (None if word_data.get('conj') is None else str(word_data.get('conj')))
            comp_json = json.dumps(word_data.get('comp', {})) if isinstance(word_data.get('comp'), dict) else (None if word_data.get('comp') is None else str(word_data.get('comp')))
            syn_json = json.dumps(word_data.get('synonyms', [])) if isinstance(word_data.get('synonyms'), list) else (None if word_data.get('synonyms') is None else str(word_data.get('synonyms')))
            coll_json = json.dumps(word_data.get('collocations', [])) if isinstance(word_data.get('collocations'), list) else (None if word_data.get('collocations') is None else str(word_data.get('collocations')))
            tags_json = json.dumps(word_data.get('tags', [])) if isinstance(word_data.get('tags'), list) else (None if word_data.get('tags') is None else str(word_data.get('tags')))
            
            cur.execute("""
                INSERT OR REPLACE INTO words_global 
                (word, language, native_language, translation, example, info, lemma, pos, 
                 ipa, audio_url, gender, plural, conj, comp, synonyms, collocations, 
                 example_native, cefr, freq_rank, tags, note, word_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                word, language, native_language,
                word_data.get('translation'),
                word_data.get('example'),
                info_json,
                word_data.get('lemma'),
                word_data.get('pos'),
                word_data.get('ipa'),
                word_data.get('audio_url'),
                word_data.get('gender'),
                word_data.get('plural'),
                conj_json,
                comp_json,
                syn_json,
                coll_json,
                word_data.get('example_native'),
                word_data.get('cefr'),
                word_data.get('freq_rank'),
                tags_json,
                word_data.get('note'),
                word_hash, now, now
            ))
            
            conn.commit()
            return word_hash
            
        except Exception as e:
            print(f"Error adding word to global database: {e}")
            return None
        finally:
            conn.close()
    
    def unlock_words_for_level(self, user_id: int, native_language: str, 
                              level: int, language: str, word_hashes: List[str]) -> bool:
        """Unlock words for user at specific level"""
        if not self.ensure_user_database(user_id, native_language):
            return False
        
        db_path = self.get_user_db_path(user_id, native_language)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        try:
            # Check if this level is already unlocked for this language
            cur.execute("""
                SELECT id, word_hashes FROM level_words 
                WHERE level = ? AND language = ?
            """, (level, language))
            existing = cur.fetchone()
            
            if existing:
                # Level already unlocked - check if word hashes are the same
                existing_hashes = set(json.loads(existing['word_hashes']))
                new_hashes = set(word_hashes)
                
                if existing_hashes == new_hashes:
                    # Same words - no need to update
                    print(f"Level {level} for language {language} already unlocked with same words")
                    return True
                else:
                    # Different words - update the entry
                    print(f"Level {level} for language {language} already unlocked but with different words - updating")
                    now = datetime.now(UTC).isoformat()
                    cur.execute("""
                        UPDATE level_words 
                        SET word_hashes = ?, unlocked_at = ?
                        WHERE id = ?
                    """, (json.dumps(word_hashes), now, existing['id']))
            else:
                # Level not unlocked yet - create new entry
                now = datetime.now(UTC).isoformat()
                cur.execute("""
                    INSERT INTO level_words 
                    (level, language, word_hashes, unlocked_at, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (level, language, json.dumps(word_hashes), now, now))
            
            # Add individual words to words_local table (only if not already present)
            for word_hash in word_hashes:
                cur.execute("""
                    INSERT OR IGNORE INTO words_local 
                    (word_hash, familiarity, seen_count, correct_count, unlocked_at, created_at, updated_at)
                    VALUES (?, 0, 0, 0, ?, ?, ?)
                """, (word_hash, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error unlocking words for level: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_word_familiarity(self, user_id: int, native_language: str, 
                                 word_hashes: List[str]) -> Dict[str, Dict[str, int]]:
        """Get familiarity data for user's words"""
        if not self.ensure_user_database(user_id, native_language):
            return {}
        
        # Check if we should use PostgreSQL instead of local SQLite
        from .db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        if config['type'] == 'postgresql':
            # Use PostgreSQL
            conn = get_db_connection()
            try:
                if word_hashes:
                    placeholders = ','.join(['%s' for _ in word_hashes])
                    query_params = [user_id, native_language] + word_hashes
                    result = execute_query(conn, f"""
                        SELECT word_hash, familiarity, seen_count, correct_count
                        FROM user_word_familiarity 
                        WHERE user_id = %s AND native_language = %s AND word_hash IN ({placeholders})
                    """, query_params)
                else:
                    # No word hashes, return empty result
                    result = execute_query(conn, """
                        SELECT word_hash, familiarity, seen_count, correct_count
                        FROM user_word_familiarity 
                        WHERE user_id = %s AND native_language = %s AND 1=0
                    """, [user_id, native_language])
                
                familiarity_data = {}
                for row in result.fetchall():
                    familiarity_data[row['word_hash']] = {
                        'familiarity': row['familiarity'],
                        'seen_count': row['seen_count'],
                        'correct_count': row['correct_count']
                    }
                
                return familiarity_data
                
            except Exception as e:
                print(f"Error getting user word familiarity from PostgreSQL: {e}")
                return {}
            finally:
                conn.close()
        else:
            # Fallback to local SQLite databases
            db_path = self.get_user_db_path(user_id, native_language)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            try:
                if word_hashes:
                    placeholders = ','.join(['?' for _ in word_hashes])
                    cur.execute(f"""
                        SELECT word_hash, familiarity, seen_count, correct_count
                        FROM words_local 
                        WHERE word_hash IN ({placeholders})
                    """, word_hashes)
                else:
                    # No word hashes, return empty result
                    cur.execute("""
                        SELECT word_hash, familiarity, seen_count, correct_count
                        FROM words_local 
                        WHERE 1=0
                    """)
                
                result = {}
                for row in cur.fetchall():
                    result[row['word_hash']] = {
                        'familiarity': row['familiarity'],
                        'seen_count': row['seen_count'],
                        'correct_count': row['correct_count']
                    }
                
                return result
                
            except Exception as e:
                print(f"Error getting user word familiarity: {e}")
                return {}
            finally:
                conn.close()
    
    def update_user_word_familiarity(self, user_id: int, native_language: str, 
                                   word_hash: str, familiarity: int, 
                                   seen_count: int = None, correct_count: int = None) -> bool:
        """Update user's word familiarity data"""
        print(f"🔧 MultiUserDBManager.update_user_word_familiarity called: user_id={user_id}, native_language={native_language}, word_hash={word_hash}, familiarity={familiarity}")
        
        if not self.ensure_user_database(user_id, native_language):
            print(f"❌ Failed to ensure user database for user {user_id}, language {native_language}")
            return False
        
        # Check if we should use PostgreSQL instead of local SQLite
        from .db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        print(f"🔧 Database config: {config}")
        if config['type'] == 'postgresql':
            # Use PostgreSQL
            print(f"🔧 Using PostgreSQL for user word familiarity update")
            conn = get_db_connection()
            try:
                now = datetime.now(UTC).isoformat()
                
                # Build update query dynamically
                updates = ['familiarity = %s', 'updated_at = %s']
                values = [familiarity, now]
                
                if seen_count is not None:
                    updates.append('seen_count = %s')
                    values.append(seen_count)
                
                if correct_count is not None:
                    updates.append('correct_count = %s')
                    values.append(correct_count)
                
                values.extend([user_id, word_hash, native_language])
                
                print(f"🔧 Attempting UPDATE with values: {values}")
                
                # First try to update existing record
                result = execute_query(conn, f"""
                    UPDATE user_word_familiarity 
                    SET {', '.join(updates)}
                    WHERE user_id = %s AND word_hash = %s AND native_language = %s
                """, values)
                
                print(f"🔧 UPDATE result rowcount: {result.rowcount}")
                
                # If no rows were affected, insert new record
                if result.rowcount == 0:
                    print(f"🔧 No rows updated, attempting INSERT")
                    insert_values = [user_id, word_hash, native_language, familiarity, now, now]
                    insert_updates = ['user_id', 'word_hash', 'native_language', 'familiarity', 'created_at', 'updated_at']
                    
                    if seen_count is not None:
                        insert_values.append(seen_count)
                        insert_updates.append('seen_count')
                    else:
                        insert_values.append(0)
                        insert_updates.append('seen_count')
                    
                    if correct_count is not None:
                        insert_values.append(correct_count)
                        insert_updates.append('correct_count')
                    else:
                        insert_values.append(0)
                        insert_updates.append('correct_count')
                    
                    insert_values.append(now)  # unlocked_at
                    insert_updates.append('unlocked_at')
                    
                    print(f"🔧 INSERT values: {insert_values}")
                    print(f"🔧 INSERT columns: {insert_updates}")
                    
                    placeholders = ','.join(['%s' for _ in insert_values])
                    insert_result = execute_query(conn, f"""
                        INSERT INTO user_word_familiarity ({', '.join(insert_updates)})
                        VALUES ({placeholders})
                    """, insert_values)
                    
                    print(f"🔧 INSERT result rowcount: {insert_result.rowcount}")
                
                conn.commit()
                print(f"🔧 PostgreSQL update successful")
                return True
                
            except Exception as e:
                print(f"Error updating user word familiarity in PostgreSQL: {e}")
                return False
            finally:
                conn.close()
        else:
            # Fallback to local SQLite databases
            db_path = self.get_user_db_path(user_id, native_language)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            try:
                now = datetime.now(UTC).isoformat()
                
                # Build update query dynamically
                updates = ['familiarity = ?', 'updated_at = ?']
                values = [familiarity, now]
                
                if seen_count is not None:
                    updates.append('seen_count = ?')
                    values.append(seen_count)
                
                if correct_count is not None:
                    updates.append('correct_count = ?')
                    values.append(correct_count)
                
                values.append(word_hash)
                
                # First try to update existing record
                cur.execute(f"""
                    UPDATE words_local 
                    SET {', '.join(updates)}
                    WHERE word_hash = ?
                """, values)
                
                # If no rows were affected, insert new record
                if cur.rowcount == 0:
                    insert_values = [word_hash, familiarity, now]
                    insert_updates = ['word_hash', 'familiarity', 'created_at', 'updated_at']
                    
                    if seen_count is not None:
                        insert_values.append(seen_count)
                        insert_updates.append('seen_count')
                    else:
                        insert_values.append(0)
                        insert_updates.append('seen_count')
                    
                    if correct_count is not None:
                        insert_values.append(correct_count)
                        insert_updates.append('correct_count')
                    else:
                        insert_values.append(0)
                        insert_updates.append('correct_count')
                    
                    insert_values.append(now)  # unlocked_at
                    insert_updates.append('unlocked_at')
                    
                    placeholders = ','.join(['?' for _ in insert_values])
                    cur.execute(f"""
                        INSERT INTO words_local ({', '.join(insert_updates)})
                        VALUES ({placeholders})
                    """, insert_values)
                
                conn.commit()
                return True
                
            except Exception as e:
                print(f"Error updating user word familiarity: {e}")
                return False
            finally:
                conn.close()
    
    def get_global_word_data(self, native_language: str, word_hashes: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get global word data for given word hashes"""
        if not self.ensure_global_database(native_language):
            return {}
        
        db_path = self.get_global_db_path(native_language)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        try:
            if word_hashes:
                placeholders = ','.join(['?' for _ in word_hashes])
                cur.execute(f"""
                    SELECT id, word_hash, word, language, translation, example, info, lemma, pos,
                           ipa, audio_url, gender, plural, conj, comp, synonyms, collocations,
                           example_native, cefr, freq_rank, tags, note, created_at, updated_at
                    FROM words_global 
                    WHERE word_hash IN ({placeholders})
                """, word_hashes)
            else:
                # No word hashes, return empty result
                cur.execute("""
                    SELECT id, word_hash, word, language, translation, example, info, lemma, pos,
                           ipa, audio_url, gender, plural, conj, comp, synonyms, collocations,
                           example_native, cefr, freq_rank, tags, note, created_at, updated_at
                    FROM words_global 
                    WHERE 1=0
                """)
            
            result = {}
            for row in cur.fetchall():
                result[row['word_hash']] = dict(row)
            
            return result
            
        except Exception as e:
            print(f"Error getting global word data: {e}")
            return {}
        finally:
            conn.close()
    
    def get_user_unlocked_words_for_level(self, user_id: int, native_language: str, 
                                        level: int, language: str) -> List[str]:
        """Get word hashes unlocked by user for specific level"""
        if not self.ensure_user_database(user_id, native_language):
            return []
        
        db_path = self.get_user_db_path(user_id, native_language)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT word_hashes FROM level_words 
                WHERE level = ? AND language = ?
                ORDER BY unlocked_at DESC
                LIMIT 1
            """, (level, language))
            
            row = cur.fetchone()
            if row:
                return json.loads(row['word_hashes'])
            return []
            
        except Exception as e:
            print(f"Error getting user unlocked words: {e}")
            return []
        finally:
            conn.close()

# Global instance
db_manager = MultiUserDBManager()
