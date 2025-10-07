#!/usr/bin/env python3
"""
Global Words Database Management for PostgreSQL
Handles global word tooltip data storage (not user-specific)
"""

import hashlib
import json
import os
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor

def get_database_connection():
    """Get PostgreSQL database connection"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise Exception('DATABASE_URL environment variable not set')
    
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def generate_word_hash(word: str, target_language: str, native_language: str) -> str:
    """Generate stable hash for word identification"""
    content = f"{word.lower()}|{target_language}|{native_language}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def ensure_global_words_table():
    """Ensure global_words table exists with proper schema"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'global_words'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("Creating global_words table...")
            cursor.execute("""
                CREATE TABLE global_words (
                    id SERIAL PRIMARY KEY,
                    word VARCHAR(255) NOT NULL,
                    target_language VARCHAR(10) NOT NULL,
                    native_language VARCHAR(10) NOT NULL,
                    translation TEXT,
                    example TEXT,
                    example_native TEXT,
                    lemma VARCHAR(255),
                    pos VARCHAR(50),
                    ipa VARCHAR(255),
                    audio_url TEXT,
                    gender VARCHAR(20) DEFAULT 'none',
                    plural VARCHAR(255),
                    conj JSONB,
                    comp JSONB,
                    synonyms JSONB,
                    collocations JSONB,
                    cefr VARCHAR(10),
                    freq_rank INTEGER,
                    tags JSONB,
                    note TEXT,
                    word_hash VARCHAR(64) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(word, target_language, native_language)
                );
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX idx_global_words_word_hash ON global_words(word_hash);")
            cursor.execute("CREATE INDEX idx_global_words_word_lang ON global_words(word, target_language);")
            cursor.execute("CREATE INDEX idx_global_words_native_lang ON global_words(native_language);")
            cursor.execute("CREATE INDEX idx_global_words_target_lang ON global_words(target_language);")
            cursor.execute("CREATE INDEX idx_global_words_created_at ON global_words(created_at);")
            
            # Create trigger function and trigger
            cursor.execute("""
                CREATE OR REPLACE FUNCTION update_global_words_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)
            
            cursor.execute("""
                CREATE TRIGGER trigger_update_global_words_updated_at
                    BEFORE UPDATE ON global_words
                    FOR EACH ROW
                    EXECUTE FUNCTION update_global_words_updated_at();
            """)
            
            conn.commit()
            print("✅ global_words table created successfully")
        else:
            print("ℹ️ global_words table already exists")
            
    except Exception as e:
        print(f"❌ Error ensuring global_words table: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def get_global_word(word: str, target_language: str, native_language: str) -> Optional[Dict[str, Any]]:
    """Get word data from global database"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        
        word_hash = generate_word_hash(word, target_language, native_language)
        cursor.execute("""
            SELECT * FROM global_words 
            WHERE word_hash = %s
        """, (word_hash,))
        
        result = cursor.fetchone()
        if result:
            # Convert to dict and handle JSON fields
            word_data = dict(result)
            
            # Parse JSON fields
            for json_field in ['conj', 'comp', 'synonyms', 'collocations', 'tags']:
                if word_data.get(json_field):
                    try:
                        word_data[json_field] = json.loads(word_data[json_field]) if isinstance(word_data[json_field], str) else word_data[json_field]
                    except (json.JSONDecodeError, TypeError):
                        word_data[json_field] = None
                else:
                    word_data[json_field] = None
            
            return word_data
        return None
        
    except Exception as e:
        print(f"❌ Error getting global word: {e}")
        return None
    finally:
        conn.close()

def upsert_global_word(word: str, target_language: str, native_language: str, 
                      word_data: Dict[str, Any]) -> bool:
    """Insert or update word in global database"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        
        word_hash = generate_word_hash(word, target_language, native_language)
        
        # Prepare data for insertion
        insert_data = {
            'word': word.lower().strip(),
            'target_language': target_language,
            'native_language': native_language,
            'translation': word_data.get('translation'),
            'example': word_data.get('example'),
            'example_native': word_data.get('example_native'),
            'lemma': word_data.get('lemma'),
            'pos': word_data.get('pos'),
            'ipa': word_data.get('ipa'),
            'audio_url': word_data.get('audio_url'),
            'gender': word_data.get('gender', 'none'),
            'plural': word_data.get('plural'),
            'conj': json.dumps(word_data.get('conj')) if word_data.get('conj') else None,
            'comp': json.dumps(word_data.get('comp')) if word_data.get('comp') else None,
            'synonyms': json.dumps(word_data.get('synonyms')) if word_data.get('synonyms') else None,
            'collocations': json.dumps(word_data.get('collocations')) if word_data.get('collocations') else None,
            'cefr': word_data.get('cefr'),
            'freq_rank': word_data.get('freq_rank'),
            'tags': json.dumps(word_data.get('tags')) if word_data.get('tags') else None,
            'note': word_data.get('note'),
            'word_hash': word_hash
        }
        
        # Use INSERT ... ON CONFLICT for upsert
        cursor.execute("""
            INSERT INTO global_words (
                word, target_language, native_language, translation, example, 
                example_native, lemma, pos, ipa, audio_url, gender, plural, 
                conj, comp, synonyms, collocations, cefr, freq_rank, tags, 
                note, word_hash
            ) VALUES (
                %(word)s, %(target_language)s, %(native_language)s, %(translation)s, 
                %(example)s, %(example_native)s, %(lemma)s, %(pos)s, %(ipa)s, 
                %(audio_url)s, %(gender)s, %(plural)s, %(conj)s, %(comp)s, 
                %(synonyms)s, %(collocations)s, %(cefr)s, %(freq_rank)s, 
                %(tags)s, %(note)s, %(word_hash)s
            )
            ON CONFLICT (word_hash) 
            DO UPDATE SET
                translation = EXCLUDED.translation,
                example = EXCLUDED.example,
                example_native = EXCLUDED.example_native,
                lemma = EXCLUDED.lemma,
                pos = EXCLUDED.pos,
                ipa = EXCLUDED.ipa,
                audio_url = EXCLUDED.audio_url,
                gender = EXCLUDED.gender,
                plural = EXCLUDED.plural,
                conj = EXCLUDED.conj,
                comp = EXCLUDED.comp,
                synonyms = EXCLUDED.synonyms,
                collocations = EXCLUDED.collocations,
                cefr = EXCLUDED.cefr,
                freq_rank = EXCLUDED.freq_rank,
                tags = EXCLUDED.tags,
                note = EXCLUDED.note,
                updated_at = CURRENT_TIMESTAMP
        """, insert_data)
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ Error upserting global word: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_global_words_batch(words: List[str], target_language: str, native_language: str) -> Dict[str, Dict[str, Any]]:
    """Get multiple words from global database in batch"""
    if not words:
        return {}
    
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        
        # Generate word hashes for all words
        word_hashes = [generate_word_hash(word, target_language, native_language) for word in words]
        
        # Use ANY() for efficient batch lookup
        cursor.execute("""
            SELECT * FROM global_words 
            WHERE word_hash = ANY(%s)
        """, (word_hashes,))
        
        results = cursor.fetchall()
        
        # Convert to dict with word as key
        word_data_map = {}
        for result in results:
            word_data = dict(result)
            
            # Parse JSON fields
            for json_field in ['conj', 'comp', 'synonyms', 'collocations', 'tags']:
                if word_data.get(json_field):
                    try:
                        word_data[json_field] = json.loads(word_data[json_field]) if isinstance(word_data[json_field], str) else word_data[json_field]
                    except (json.JSONDecodeError, TypeError):
                        word_data[json_field] = None
                else:
                    word_data[json_field] = None
            
            # Use original word (case-sensitive) as key
            original_word = next((w for w in words if generate_word_hash(w, target_language, native_language) == word_data['word_hash']), word_data['word'])
            word_data_map[original_word] = word_data
        
        return word_data_map
        
    except Exception as e:
        print(f"❌ Error getting global words batch: {e}")
        return {}
    finally:
        conn.close()

def search_global_words(query: str, target_language: str, native_language: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search for words in global database"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM global_words 
            WHERE target_language = %s AND native_language = %s 
            AND (word ILIKE %s OR translation ILIKE %s)
            ORDER BY word
            LIMIT %s
        """, (target_language, native_language, f'%{query}%', f'%{query}%', limit))
        
        results = cursor.fetchall()
        
        # Convert to list of dicts and parse JSON fields
        word_list = []
        for result in results:
            word_data = dict(result)
            
            # Parse JSON fields
            for json_field in ['conj', 'comp', 'synonyms', 'collocations', 'tags']:
                if word_data.get(json_field):
                    try:
                        word_data[json_field] = json.loads(word_data[json_field]) if isinstance(word_data[json_field], str) else word_data[json_field]
                    except (json.JSONDecodeError, TypeError):
                        word_data[json_field] = None
                else:
                    word_data[json_field] = None
            
            word_list.append(word_data)
        
        return word_list
        
    except Exception as e:
        print(f"❌ Error searching global words: {e}")
        return []
    finally:
        conn.close()

def get_global_words_count(target_language: str, native_language: str) -> int:
    """Get count of words in global database for specific language pair"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM global_words 
            WHERE target_language = %s AND native_language = %s
        """, (target_language, native_language))
        
        result = cursor.fetchone()
        return result[0] if result else 0
        
    except Exception as e:
        print(f"❌ Error getting global words count: {e}")
        return 0
    finally:
        conn.close()
