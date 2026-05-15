
# --- Level run helpers ---
import os, sqlite3, json, threading
import random
import re
import unicodedata
from datetime import datetime, UTC
from collections import defaultdict
from typing import Dict, Any
from .db_config import get_db_connection, execute_query, get_database_config, POSTGRES_DRIVER_AVAILABLE, POSTGRES_EXECUTE_VALUES, get_db_cursor
from .postgres import RealDictCursor


PRIMARY_LANGUAGE_FIELDS: Dict[str, str] = {
    'en': 'english',
    'de': 'german',
    'fr': 'french',
    'es': 'spanish',
    'pt': 'portuguese',
    'it': 'italian',
    'ru': 'russian',
    'tr': 'turkish',
    'ka': 'georgian',
    'nl': 'dutch',
    'sv': 'swedish',
    'no': 'norwegian',
    'da': 'danish',
    'fi': 'finnish',
    'pl': 'polish',
    'cs': 'czech',
    'sk': 'slovak',
    'hu': 'hungarian',
    'ro': 'romanian',
    'bg': 'bulgarian',
    'el': 'greek',
    'uk': 'ukrainian',
    'zh': 'chinese',
    'ja': 'japanese',
    'ko': 'korean',
    'hi': 'hindi',
    'ur': 'urdu',
    'id': 'indonesian',
    'ms': 'malay',
    'th': 'thai',
    'vi': 'vietnamese',
    'fa': 'persian',
    'ar': 'arabic',
    'sw': 'swahili',
}

LANGUAGE_ALIASES: Dict[str, str] = {
    'english': 'en',
    'en': 'en',
    'german': 'de',
    'de': 'de',
    'french': 'fr',
    'fr': 'fr',
    'italian': 'it',
    'it': 'it',
    'spanish': 'es',
    'es': 'es',
    'portuguese': 'pt',
    'pt': 'pt',
    'portuguese_br': 'pt',
    'brazilian_portuguese': 'pt',
    'russian': 'ru',
    'ru': 'ru',
    'turkish': 'tr',
    'tr': 'tr',
    'georgian': 'ka',
    'ka': 'ka',
    'dutch': 'nl',
    'nl': 'nl',
    'swedish': 'sv',
    'sv': 'sv',
    'norwegian': 'no',
    'no': 'no',
    'danish': 'da',
    'da': 'da',
    'finnish': 'fi',
    'fi': 'fi',
    'polish': 'pl',
    'pl': 'pl',
    'czech': 'cs',
    'cs': 'cs',
    'slovak': 'sk',
    'sk': 'sk',
    'hungarian': 'hu',
    'hu': 'hu',
    'romanian': 'ro',
    'ro': 'ro',
    'bulgarian': 'bg',
    'bg': 'bg',
    'greek': 'el',
    'el': 'el',
    'ukrainian': 'uk',
    'uk': 'uk',
    'chinese': 'zh',
    'zh': 'zh',
    'japanese': 'ja',
    'ja': 'ja',
    'korean': 'ko',
    'ko': 'ko',
    'hindi': 'hi',
    'hi': 'hi',
    'urdu': 'ur',
    'ur': 'ur',
    'indonesian': 'id',
    'id': 'id',
    'malay': 'ms',
    'ms': 'ms',
    'thai': 'th',
    'th': 'th',
    'vietnamese': 'vi',
    'vi': 'vi',
    'persian': 'fa',
    'farsi': 'fa',
    'fa': 'fa',
    'arabic': 'ar',
    'ar': 'ar',
    'swahili': 'sw',
    'sw': 'sw',
    'bengali': 'bn',
    'bn': 'bn',
    'punjabi': 'pa',
    'pa': 'pa',
    'tamil': 'ta',
    'ta': 'ta',
    'telugu': 'te',
    'te': 'te',
    'marathi': 'mr',
    'mr': 'mr',
    'gujarati': 'gu',
    'gu': 'gu',
    'malagasy': 'mg',
    'mg': 'mg',
    'tagalog': 'tl',
    'filipino': 'tl',
    'tl': 'tl',
    'azerbaijani': 'az',
    'az': 'az',
    'kazakh': 'kk',
    'kk': 'kk',
    'armenian': 'hy',
    'hy': 'hy',
    'nepali': 'ne',
    'ne': 'ne',
    'lao': 'lo',
    'lo': 'lo',
    'khmer': 'km',
    'km': 'km',
    'burmese': 'my',
    'my': 'my',
}

LANGUAGE_CODE_TO_FIELD: Dict[str, str] = {code: field for code, field in PRIMARY_LANGUAGE_FIELDS.items()}
LOCALIZATION_INVALID_VALUES = {'', '___', '#VALUE!'}
LOCALIZATION_SEED_LOCK = threading.Lock()
LOCALIZATION_SEED_STARTED = False


def _coerce_row_to_dict(row, description=None):
    """Normalize DBAPI rows (tuple/list/Row) into plain dicts."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys'):
        try:
            return dict(row)
        except TypeError:
            return {key: row[key] for key in row.keys()}
    if description:
        keys: list[str] = []
        for column in description:
            if isinstance(column, (tuple, list)):
                keys.append(column[0])
            elif hasattr(column, 'name'):
                keys.append(column.name)
            else:
                keys.append(str(column))
        return {keys[idx]: row[idx] for idx in range(min(len(keys), len(row)))}
    return None


def normalize_language_identifier(identifier: str | None) -> str | None:
    """Normalize various language identifiers to ISO-ish codes"""
    if not identifier:
        return None
    lang = str(identifier).strip().lower()
    if not lang:
        return None
    lang = lang.replace('-', '_').replace(' ', '_')
    if '.' in lang:
        lang = lang.split('.', 1)[0]
    return LANGUAGE_ALIASES.get(lang, lang if 1 < len(lang) <= 5 else None)


def normalize_word(word: str) -> str:
    """
    Normalize word for consistent database storage.
    Removes leading/trailing punctuation, whitespace, and normalizes Unicode.
    
    This function ensures that words like "ávexti" and "ávexti." are treated as the same word.
    """
    if not word or not isinstance(word, str):
        return ''
    
    # Strip whitespace
    normalized = word.strip()
    
    # Remove leading punctuation
    normalized = re.sub(r'^[.!?,;:—–\-]+', '', normalized)
    
    # Remove trailing punctuation
    normalized = re.sub(r'[.!?,;:—–\-]+$', '', normalized)
    
    # Normalize Unicode (NFC) - ensures consistent representation
    normalized = unicodedata.normalize('NFC', normalized)
    
    # Normalize whitespace (replace multiple spaces/tabs with single space)
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Final strip
    normalized = normalized.strip()
    
    return normalized


def language_code_to_field(code: str) -> str:
    """Map language code back to UI field name"""
    if not code:
        return code
    return LANGUAGE_CODE_TO_FIELD.get(code, code)


def _pg_get_table_columns(conn, table_name: str) -> list[str]:
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
          AND table_schema = current_schema()
        ORDER BY ordinal_position
    """, (table_name,))
    rows = cur.fetchall()
    cur.close()
    columns = []
    for row in rows:
        if isinstance(row, dict):
            columns.append(row.get('column_name'))
        else:
            columns.append(row[0])
    return columns


def migrate_postgres_localization_table(conn) -> None:
    """Migrate legacy wide localization table to normalized schema if needed"""
    columns = _pg_get_table_columns(conn, 'localization')
    if not columns:
        return
    if {'key', 'language', 'value'} <= set(columns):
        return  # already normalized
    if 'reference_key' not in columns:
        print("Localization table present with unexpected schema; migration skipped.")
        return
    print("Migrating legacy localization table to normalized schema...")
    execute_query(conn, "ALTER TABLE localization RENAME TO localization_legacy")
    execute_query(conn, """
        CREATE TABLE IF NOT EXISTS localization (
            id SERIAL PRIMARY KEY,
            key VARCHAR(255) NOT NULL,
            language VARCHAR(16) NOT NULL,
            value TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(key, language)
        );
    """)
    legacy_columns = columns
    cur = conn.cursor()
    cur.execute("SELECT * FROM localization_legacy")
    rows = cur.fetchall()
    cur.close()
    language_columns = [c for c in legacy_columns if c not in {'id', 'reference_key', 'description', 'created_at', 'updated_at'}]
    migrated = 0
    for row in rows:
        if isinstance(row, dict):
            row_dict = row
        else:
            row_dict = {legacy_columns[i]: row[i] if i < len(row) else None for i in range(len(legacy_columns))}
        payload = {
            'reference_key': row_dict.get('reference_key'),
            'description': row_dict.get('description')
        }
        inserted = False
        for col in language_columns:
            lang_code = normalize_language_identifier(col)
            if not lang_code:
                continue
            value = row_dict.get(col)
            if value is None:
                continue
            text_value = str(value).strip()
            if not text_value or text_value in LOCALIZATION_INVALID_VALUES:
                continue
            payload[language_code_to_field(lang_code)] = text_value
            inserted = True
        if inserted:
            upsert_localization_entry(payload, conn=conn)
            migrated += 1
    conn.commit()
    execute_query(conn, "DROP TABLE localization_legacy")
    print(f"Migrated {migrated} localization entries to normalized schema.")


def using_postgresql() -> bool:
    config = get_database_config()
    return config['type'] == 'postgresql' and POSTGRES_DRIVER_AVAILABLE

def latest_run_id_for_level(level: int) -> int | None:
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            result = execute_query(conn, 'SELECT id FROM level_runs WHERE level=%s ORDER BY id DESC LIMIT 1', (level,))
            r = result.fetchone()
        else:
            # SQLite syntax
            cur = conn.cursor()
            r = cur.execute('SELECT id FROM level_runs WHERE level=? ORDER BY id DESC LIMIT 1', (level,)).fetchone()
        return int(r['id']) if r else None
    finally:
        conn.close()


def ensure_words_exist(words: list[str], target_lang: str, native_lang: str) -> None:
    """Ensure words exist in database - optimized with batch operations"""
    if not words:
        return
    config = get_database_config()
    conn = get_db_connection()
    try:
        now = datetime.now(UTC).isoformat()
        
        # Normalize words first using centralized normalization function
        normalized_words = []
        for w in words:
            if isinstance(w, str):
                w = normalize_word(w)
            else:
                continue
            if w:
                normalized_words.append(w)
        
        if not normalized_words:
            return
        
        if config['type'] == 'postgresql':
            # Batch check which words already exist
            cur = conn.cursor()
            try:
                # Build query to check all words at once
                placeholders = ', '.join(['%s'] * len(normalized_words))
                cur.execute(f'''
                    SELECT word FROM words 
                    WHERE word IN ({placeholders}) 
                    AND (language = %s OR %s = '')
                ''', normalized_words + [target_lang, target_lang])
                
                existing_words = {row[0] if isinstance(row, (list, tuple)) else row.get('word') for row in cur.fetchall()}
                
                # Insert only words that don't exist
                words_to_insert = [w for w in normalized_words if w not in existing_words]
                
                if words_to_insert:
                    # Batch insert using VALUES clause
                    if len(words_to_insert) == 1:
                        cur.execute('''
                            INSERT INTO words (word, language, native_language, created_at, updated_at) 
                            VALUES (%s, %s, %s, %s, %s)
                        ''', (words_to_insert[0], target_lang, native_lang, now, now))
                    else:
                        # Build bulk INSERT
                        values_placeholders = ', '.join(['(%s, %s, %s, %s, %s)'] * len(words_to_insert))
                        params = []
                        for w in words_to_insert:
                            params.extend([w, target_lang, native_lang, now, now])
                        
                        cur.execute(f'''
                            INSERT INTO words (word, language, native_language, created_at, updated_at) 
                            VALUES {values_placeholders}
                        ''', params)
            finally:
                cur.close()
        else:
            # SQLite - batch operations
            cur = conn.cursor()
            try:
                placeholders = ', '.join(['?'] * len(normalized_words))
                existing = cur.execute(f'SELECT word FROM words WHERE word IN ({placeholders}) AND (language=? OR ?="")', normalized_words + [target_lang, target_lang]).fetchall()
                existing_words = {row[0] for row in existing}
                words_to_insert = [w for w in normalized_words if w not in existing_words]
                
                # OPTIMIZATION: Batch insert instead of individual inserts
                if words_to_insert:
                    # Build batch insert query
                    values_placeholders = ', '.join(['(?,?,?,?,?)'] * len(words_to_insert))
                    params = []
                    for w in words_to_insert:
                        params.extend([w, target_lang, native_lang, now, now])
                    
                    cur.execute(
                        f'INSERT INTO words (word, language, native_language, created_at, updated_at) VALUES {values_placeholders}',
                        params
                    )
            finally:
                cur.close()
        conn.commit()
    finally:
        conn.close()


def create_level_run(level: int, items: list, topic: str, target_lang: str = None, native_lang: str = None) -> int:
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            result = execute_query(conn, '''
                INSERT INTO level_runs (level, items, user_translations, score, topic, target_lang, native_lang, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            ''', (level, _json.dumps(items, ensure_ascii=False), _json.dumps({}, ensure_ascii=False), None, topic, target_lang, native_lang, datetime.now(UTC).isoformat()))
            return int(result.fetchone()['id'])
        else:
            # SQLite syntax
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO level_runs (level, items, user_translations, score, topic, target_lang, native_lang, created_at) VALUES (?,?,?,?,?,?,?,?)',
                (level, _json.dumps(items, ensure_ascii=False), _json.dumps({}, ensure_ascii=False), None, topic, target_lang, native_lang, datetime.now(UTC).isoformat())
            )
            rid = cur.lastrowid
            conn.commit()
            return int(rid)
    finally:
        conn.close()

# --- Level Rating System ---

def create_level_ratings_table():
    """Create the level_ratings table if it doesn't exist"""
    conn = get_db()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS level_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                level INTEGER NOT NULL,
                language TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating IN (1, -1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, level, language)
            )
        ''')
        conn.commit()
    finally:
        conn.close()

def create_custom_level_groups_table():
    """Create the custom_level_groups table if it doesn't exist"""
    config = get_database_config()
    conn = get_db_connection()  # Get raw connection
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            execute_query(conn, '''
                CREATE TABLE IF NOT EXISTS custom_level_groups (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    language VARCHAR(10) NOT NULL,
                    native_language VARCHAR(10) NOT NULL,
                    group_name VARCHAR(255) NOT NULL,
                    context_description TEXT NOT NULL,
                    topic VARCHAR(100) DEFAULT 'daily life',
                    cefr_level VARCHAR(10) DEFAULT 'A1',
                    num_levels INTEGER DEFAULT 10,
                    status VARCHAR(50) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, language, group_name)
                );
            ''')
        else:
            # SQLite syntax
            conn.execute('''
                CREATE TABLE IF NOT EXISTS custom_level_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    native_language TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    context_description TEXT NOT NULL,
                    topic TEXT DEFAULT 'daily life',
                    cefr_level TEXT DEFAULT 'A1',
                    num_levels INTEGER DEFAULT 10,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, language, group_name)
                )
            ''')
            conn.commit()
    finally:
        conn.close()

def create_custom_levels_table():
    """Create the custom_levels table if it doesn't exist"""
    config = get_database_config()
    conn = get_db_connection()  # Get raw connection
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            execute_query(conn, '''
                CREATE TABLE IF NOT EXISTS custom_levels (
                    id SERIAL PRIMARY KEY,
                    group_id INTEGER NOT NULL,
                    level_number INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    topic VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    word_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                    UNIQUE(group_id, level_number)
                );
            ''')
        else:
            # SQLite syntax
            conn.execute('''
                CREATE TABLE IF NOT EXISTS custom_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    level_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,  -- JSON content
                    word_count INTEGER DEFAULT 0,
                    word_ids TEXT DEFAULT NULL,  -- JSON array of word IDs
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                    UNIQUE(group_id, level_number)
                )
            ''')
            conn.commit()
        
        # Run migration to add topic column if it doesn't exist
        migrate_custom_level_groups_add_topic()
    finally:
        conn.close()

def migrate_custom_level_groups_add_topic():
    """Add topic column to existing custom_level_groups table"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax - check if column exists first
            result = execute_query(conn, '''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'custom_level_groups' AND column_name = 'topic'
            ''')
            
            if not result.fetchone():
                print("Adding topic column to custom_level_groups table...")
                execute_query(conn, '''
                    ALTER TABLE custom_level_groups 
                    ADD COLUMN topic VARCHAR(100) DEFAULT 'daily life'
                ''')
                print("✅ Added topic column to custom_level_groups table")
            else:
                print("topic column already exists in custom_level_groups table")
        else:
            # SQLite syntax - check if column exists first
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(custom_level_groups)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'topic' not in columns:
                print("Adding topic column to custom_level_groups table...")
                cursor.execute('''
                    ALTER TABLE custom_level_groups 
                    ADD COLUMN topic TEXT DEFAULT 'daily life'
                ''')
                conn.commit()
                print("✅ Added topic column to custom_level_groups table")
            else:
                print("topic column already exists in custom_level_groups table")
                
    except Exception as e:
        print(f"Error adding topic column: {e}")
    finally:
        conn.close()

def migrate_custom_levels_add_word_count():
    """Add word_count column to existing custom_levels table"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax - check if column exists first
            result = execute_query(conn, '''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'custom_levels' AND column_name = 'word_count'
            ''')
            
            if not result.fetchone():
                print("Adding word_count column to custom_levels table...")
                execute_query(conn, '''
                    ALTER TABLE custom_levels 
                    ADD COLUMN word_count INTEGER DEFAULT 0
                ''')
                print("✅ Added word_count column to custom_levels table")
            else:
                print("word_count column already exists in custom_levels table")
        else:
            # SQLite syntax - check if column exists first
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(custom_levels)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'word_count' not in columns:
                print("Adding word_count column to custom_levels table...")
                cursor.execute('''
                    ALTER TABLE custom_levels 
                    ADD COLUMN word_count INTEGER DEFAULT 0
                ''')
                conn.commit()
                print("✅ Added word_count column to custom_levels table")
            else:
                print("word_count column already exists in custom_levels table")
                
    except Exception as e:
        print(f"Error adding word_count column: {e}")
    finally:
        conn.close()

def migrate_custom_levels_add_word_ids():
    """Add word_ids column to existing custom_levels table for performance optimization"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax - check if column exists first
            result = execute_query(conn, '''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'custom_levels' AND column_name = 'word_ids'
            ''')
            
            if not result.fetchone():
                print("Adding word_ids column to custom_levels table...")
                execute_query(conn, '''
                    ALTER TABLE custom_levels 
                    ADD COLUMN word_ids INTEGER[] DEFAULT NULL
                ''')
                conn.commit()
                print("✅ Added word_ids column to custom_levels table")
            else:
                print("word_ids column already exists in custom_levels table")
        else:
            # SQLite syntax - check if column exists first
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(custom_levels)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'word_ids' not in columns:
                print("Adding word_ids column to custom_levels table...")
                cursor.execute('''
                    ALTER TABLE custom_levels 
                    ADD COLUMN word_ids TEXT DEFAULT NULL
                ''')
                conn.commit()
                print("✅ Added word_ids column to custom_levels table (SQLite: stored as JSON)")
            else:
                print("word_ids column already exists in custom_levels table")
                
    except Exception as e:
        print(f"Error adding word_ids column: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def calculate_and_update_word_count(group_id: int, level_number: int, content: dict) -> int:
    """Calculate word count from content and update the database"""
    if not content or not content.get('items'):
        return 0
    
    # Calculate unique words from content
    import re
    all_words = set()
    for item in content['items']:
        words = item.get('words', [])
        for word in words:
            if word and word.strip():
                # Remove trailing punctuation before adding
                clean_word = re.sub(r'[.!?,;:—–-]+$', '', word.strip().lower())
                if clean_word:
                    all_words.add(clean_word)
    
    word_count = len(all_words)
    
    # Update database with calculated word count
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            execute_query(conn, '''
                UPDATE custom_levels 
                SET word_count = %s, updated_at = %s
                WHERE group_id = %s AND level_number = %s
            ''', (word_count, datetime.now(UTC).isoformat(), group_id, level_number))
        else:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE custom_levels 
                SET word_count = ?, updated_at = ?
                WHERE group_id = ? AND level_number = ?
            ''', (word_count, datetime.now(UTC).isoformat(), group_id, level_number))
            conn.commit()
        
        print(f"✅ Updated word count for level {group_id}/{level_number}: {word_count} words")
        return word_count
        
    except Exception as e:
        print(f"Error updating word count: {e}")
        return 0
    finally:
        conn.close()

def submit_level_rating(user_id: int, level: int, language: str, rating: int) -> bool:
    """Submit or update a level rating (1 for thumbs up, -1 for thumbs down)"""
    if rating not in [1, -1]:
        return False
    
    config = get_database_config()
    conn = get_db_connection()
    try:
        now = datetime.now(UTC).isoformat()
        if config['type'] == 'postgresql':
            # PostgreSQL syntax - use ON CONFLICT
            execute_query(conn, '''
                INSERT INTO level_ratings 
                (user_id, level, language, rating, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, level, language) 
                DO UPDATE SET rating = EXCLUDED.rating, updated_at = EXCLUDED.updated_at
            ''', (user_id, level, language, rating, now, now))
        else:
            # SQLite syntax
            cur = conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO level_ratings 
                (user_id, level, language, rating, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, level, language, rating, now, now))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error submitting rating: {e}")
        return False
    finally:
        conn.close()

############################
# --- Marketplace Ratings ---
############################

def upsert_group_rating(group_id: int, user_id: int, stars: int, comment: str | None) -> tuple[bool, str | None, str | None]:
    """Create or update a rating for a marketplace custom level group.
    Returns (ok, error_code). error_code None on success.
    """
    if not group_id or not user_id:
        return False, 'stars_invalid', None
    try:
        stars_int = int(stars)
    except Exception:
        return False
    if stars_int < 1 or stars_int > 5:
        return False

    config = get_database_config()
    conn = get_db_connection()
    try:
        now = datetime.now(UTC).isoformat()
        # Pre-check FKs to provide clearer errors
        try:
            # Check group exists
            execute_query(conn, 'SELECT id FROM custom_level_groups WHERE id = %s' if config['type']=='postgresql' else 'SELECT id FROM custom_level_groups WHERE id = ?', (group_id,))
            if not getattr(conn, 'fetchone', None):
                # For execute_query we must fetch from returned cursor
                pass
            cur = execute_query(conn, 'SELECT id FROM custom_level_groups WHERE id = %s' if config['type']=='postgresql' else 'SELECT id FROM custom_level_groups WHERE id = ?', (group_id,))
            if not cur.fetchone():
                return False, 'fk_group_missing', None
            # Check user exists
            cur = execute_query(conn, 'SELECT id FROM users WHERE id = %s' if config['type']=='postgresql' else 'SELECT id FROM users WHERE id = ?', (user_id,))
            if not cur.fetchone():
                return False, 'fk_user_missing', None
        except Exception as _e:
            # If pre-check fails unexpectedly, continue to attempt write; DB will enforce
            pass
        # Resolve column names in case the table was created with different column naming
        def resolve_columns():
            try:
                if config['type'] == 'postgresql':
                    cols_cur = execute_query(conn, """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'custom_level_group_ratings'
                    """)
                    cols = {r['column_name'] for r in cols_cur.fetchall()}
                else:
                    cur2 = conn.cursor(); cur2.execute("PRAGMA table_info(custom_level_group_ratings)")
                    cols = {row[1] for row in cur2.fetchall()}
                stars_col = 'stars' if 'stars' in cols else ('rating' if 'rating' in cols else None)
                comment_col = 'comment' if 'comment' in cols else ('review' if 'review' in cols else None)
                return stars_col, comment_col
            except Exception:
                return 'stars', 'comment'

        stars_col, comment_col = resolve_columns()
        if not stars_col:
            return False, 'table_mismatch'

        # Generate a 32-bit safe positive integer ID (PostgreSQL SERIAL range)
        def generate_safe_id():
            base = int(datetime.now(UTC).timestamp() * 1000)  # ms epoch
            base = base % 2_000_000_000
            if base <= 0:
                base = 1
            # Mix in group and user to reduce collision probability
            mix = ((group_id & 0x7FFF) << 16) ^ ((user_id & 0x7FFF) << 1) ^ random.randint(0, 0xFFFF)
            rid = (base ^ mix) % 2_000_000_000
            return rid if rid > 0 else 1
        rating_id = generate_safe_id()

        if config['type'] == 'postgresql':
            # Try update first
            updated = execute_query(conn, f'''
                UPDATE custom_level_group_ratings
                SET {stars_col} = %s, {comment_col or 'comment'} = %s, updated_at = %s
                WHERE group_id = %s AND user_id = %s
            ''', (stars_int, comment, now, group_id, user_id)).rowcount
            if not updated:
                # Retry loop in case of random PK collision
                attempts = 0
                while True:
                    try:
                        execute_query(conn, f'''
                            INSERT INTO custom_level_group_ratings (id, group_id, user_id, {stars_col}{', ' + comment_col if comment_col else ''}, created_at, updated_at)
                            VALUES (%s, %s, %s, %s{', %s' if comment_col else ''}, %s, %s)
                        ''', (rating_id, group_id, user_id, stars_int, *( [comment] if comment_col else [] ), now, now))
                        break
                    except Exception as ins_e:
                        # Unique violation on PK id → regenerate and retry a few times
                        code = getattr(ins_e, 'pgcode', None)
                        if code == '23505' and attempts < 5:
                            attempts += 1
                            rating_id = generate_safe_id()
                            continue
                        raise
        else:
            cur = conn.cursor()
            cur.execute(f'''
                UPDATE custom_level_group_ratings
                SET {stars_col} = ?, {comment_col or 'comment'} = ?, updated_at = ?
                WHERE group_id = ? AND user_id = ?
            ''', (stars_int, comment, now, group_id, user_id))
            if cur.rowcount == 0:
                attempts = 0
                while True:
                    try:
                        if comment_col:
                            cur.execute(f'''
                                INSERT INTO custom_level_group_ratings (id, group_id, user_id, {stars_col}, {comment_col}, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (rating_id, group_id, user_id, stars_int, comment, now, now))
                        else:
                            cur.execute(f'''
                                INSERT INTO custom_level_group_ratings (id, group_id, user_id, {stars_col}, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (rating_id, group_id, user_id, stars_int, now, now))
                        break
                    except Exception as ins_e:
                        if attempts < 5:
                            attempts += 1
                            rating_id = generate_safe_id()
                            continue
                        raise
        conn.commit()
        return True, None, None
    except Exception as e:
        print(f"Error upserting group rating: {e}")
        # Try to map common PG error codes
        try:
            pgcode = getattr(getattr(e, 'pgcode', None), 'strip', lambda: None)()
        except Exception:
            pgcode = None
        if pgcode == '23503':
            return False, 'fk_violation', str(e)
        if pgcode == '23505':
            return False, 'unique_violation', str(e)
        # Detect missing relation
        msg = str(e).lower()
        if 'does not exist' in msg or 'no such table' in msg:
            return False, 'table_missing', str(e)
        if 'column' in msg and 'does not exist' in msg:
            return False, 'column_missing', str(e)
        return False, 'db_error', str(e)
    finally:
        conn.close()

def get_group_rating_stats(group_id: int) -> dict:
    """Return average stars, count, and distribution for a group."""
    if not group_id:
        return { 'avg': 0.0, 'count': 0, 'dist': {str(i): 0 for i in range(1,6)} }
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            cursor_avg = execute_query(conn, '''
                SELECT AVG(stars) AS avg_stars, COUNT(*) AS cnt FROM custom_level_group_ratings WHERE group_id=%s
            ''', (group_id,))
            avg_description = getattr(cursor_avg, 'description', None)
            row = cursor_avg.fetchone()
            cursor_dist = execute_query(conn, '''
                SELECT stars, COUNT(*) AS c FROM custom_level_group_ratings WHERE group_id=%s GROUP BY stars
            ''', (group_id,))
            dist_rows = cursor_dist.fetchall()
            dist_description = getattr(cursor_dist, 'description', None)
        else:
            cur = conn.cursor()
            row = cur.execute('SELECT AVG(stars) AS avg_stars, COUNT(*) AS cnt FROM custom_level_group_ratings WHERE group_id=?', (group_id,)).fetchone()
            avg_description = getattr(cur, 'description', None)
            dist_rows = cur.execute('SELECT stars, COUNT(*) AS c FROM custom_level_group_ratings WHERE group_id=? GROUP BY stars', (group_id,)).fetchall()
            dist_description = getattr(cur, 'description', None)

        row_dict = _coerce_row_to_dict(row, avg_description) or {}
        avg_val = float(row_dict.get('avg_stars')) if row_dict.get('avg_stars') is not None else 0.0
        cnt_val = int(row_dict.get('cnt')) if row_dict.get('cnt') is not None else 0
        dist = {str(i): 0 for i in range(1,6)}
        for r in dist_rows or []:
            row_data = _coerce_row_to_dict(r, dist_description)
            if not row_data:
                if isinstance(r, dict):
                    row_data = r
                else:
                    continue
            stars_val = row_data.get('stars')
            count_val = row_data.get('c')
            if stars_val is None or count_val is None:
                continue
            s = int(stars_val)
            c = int(count_val)
            if 1 <= s <= 5:
                dist[str(s)] = c
        return { 'avg': round(avg_val, 2), 'count': cnt_val, 'dist': dist }
    finally:
        conn.close()

def get_recent_group_comments(group_id: int, limit: int = 5) -> list[dict]:
    """Return recent rating comments for a group."""
    if not group_id:
        return []
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            rows = execute_query(conn, '''
                SELECT r.user_id, r.stars, r.comment, r.updated_at, u.username
                FROM custom_level_group_ratings r
                LEFT JOIN users u ON u.id = r.user_id
                WHERE r.group_id=%s AND COALESCE(r.comment, '') <> ''
                ORDER BY r.updated_at DESC
                LIMIT %s
            ''', (group_id, limit)).fetchall()
            return [dict(row) for row in rows]
        else:
            cur = conn.cursor()
            rows = cur.execute('''
                SELECT r.user_id, r.stars, r.comment, r.updated_at, u.username
                FROM custom_level_group_ratings r
                LEFT JOIN users u ON u.id = r.user_id
                WHERE r.group_id=? AND IFNULL(r.comment, '') <> ''
                ORDER BY r.updated_at DESC
                LIMIT ?
            ''', (group_id, limit)).fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()

def get_level_rating_stats(level: int, language: str) -> dict:
    """Get rating statistics for a level"""
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            result = execute_query(conn, '''
                SELECT 
                    COUNT(*) as total_ratings,
                    SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as positive_ratings,
                    SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) as negative_ratings
                FROM level_ratings 
                WHERE level = %s AND language = %s
            ''', (level, language)).fetchone()
        else:
            # SQLite syntax
            cur = conn.cursor()
            result = cur.execute('''
                SELECT 
                    COUNT(*) as total_ratings,
                    SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as positive_ratings,
                    SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) as negative_ratings
                FROM level_ratings 
                WHERE level = ? AND language = ?
            ''', (level, language)).fetchone()
        
        total = result['total_ratings'] or 0
        positive = result['positive_ratings'] or 0
        negative = result['negative_ratings'] or 0
        
        return {
            'total_ratings': total,
            'positive_ratings': positive,
            'negative_ratings': negative,
            'positive_percentage': round((positive / total * 100) if total > 0 else 0, 1)
        }
    finally:
        conn.close()

def get_user_level_rating(user_id: int, level: int, language: str) -> int | None:
    """Get user's rating for a specific level (1, -1, or None if not rated)"""
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            result = execute_query(conn, '''
                SELECT rating FROM level_ratings 
                WHERE user_id = %s AND level = %s AND language = %s
            ''', (user_id, level, language)).fetchone()
        else:
            # SQLite syntax
            cur = conn.cursor()
            result = cur.execute('''
                SELECT rating FROM level_ratings 
                WHERE user_id = ? AND level = ? AND language = ?
            ''', (user_id, level, language)).fetchone()
        
        return result['rating'] if result else None
    finally:
        conn.close()
# --- Aggregations ---

def fam_counts_for_words(words: set[str], language: str = None) -> dict:
    fam_counts = {0:0,1:0,2:0,3:0,4:0,5:0}
    if not words:
        return fam_counts
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            if language:
                # Query with language filter
                result = execute_query(conn, f'SELECT 0 as fam FROM words WHERE (language=%s OR %s=\'\') AND word = ANY(%s)', (language, language, list(words)))
            else:
                # Query without language filter (backward compatibility)
                result = execute_query(conn, f'SELECT 0 as fam FROM words WHERE word = ANY(%s)', (list(words),))
            rows = result.fetchall()
        else:
            # SQLite syntax
            cur = conn.cursor()
            qmarks = ','.join('?' for _ in words)
            if language:
                # Query with language filter
                rows = cur.execute(f'SELECT 0 as fam FROM words WHERE (language=? OR ?="") AND word IN ({qmarks})', (language, language, *words)).fetchall()
            else:
                # Query without language filter (backward compatibility)
                rows = cur.execute(f'SELECT 0 as fam FROM words WHERE word IN ({qmarks})', tuple(words)).fetchall()
        for rr in rows:
            f = int(rr['fam']) if rr['fam'] is not None else 0
            f = max(0, min(5, f))
            fam_counts[f] += 1
    finally:
        conn.close()
    return fam_counts

# --- Practice helpers moved from app ---

def migrate_practice():
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            execute_query(conn, '''
                CREATE TABLE IF NOT EXISTS practice_runs (
                  id SERIAL PRIMARY KEY,
                  level INTEGER,
                  words TEXT,
                  todo TEXT,
                  seen_count INTEGER,
                  created_at TEXT,
                  bad_counts TEXT
                )
            ''')
        else:
            # SQLite syntax
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS practice_runs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  level INTEGER,
                  words TEXT,
                  todo  TEXT,
                  seen_count INTEGER,
                  created_at TEXT
                )
            ''')
            cols = {r['name'] for r in cur.execute('PRAGMA table_info(practice_runs)').fetchall()}
            if 'level' not in cols:
                cur.execute('ALTER TABLE practice_runs ADD COLUMN level INTEGER')
            if 'words' not in cols:
                cur.execute('ALTER TABLE practice_runs ADD COLUMN words TEXT')
            if 'todo' not in cols:
                cur.execute('ALTER TABLE practice_runs ADD COLUMN todo TEXT')
            if 'seen_count' not in cols:
                cur.execute('ALTER TABLE practice_runs ADD COLUMN seen_count INTEGER')
            if 'created_at' not in cols:
                cur.execute('ALTER TABLE practice_runs ADD COLUMN created_at TEXT')
            if 'bad_counts' not in cols:
                cur.execute('ALTER TABLE practice_runs ADD COLUMN bad_counts TEXT')
        conn.commit()
    finally:
        conn.close()

import json as _json

# Safe JSON loader used by app routes

def json_load(s, fallback):
    try:
        return _json.loads(s or '')
    except Exception:
        return fallback

def pick_words_by_run(run_id: int, limit: int = 10) -> list[str]:
    if not run_id:
        return []
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            result = execute_query(conn, 'SELECT items FROM level_runs WHERE id=%s', (run_id,))
            row = result.fetchone()
        else:
            # SQLite syntax
            cur = conn.cursor()
            row = cur.execute('SELECT items FROM level_runs WHERE id=?', (run_id,)).fetchone()
    finally:
        conn.close()
    
    if not row:
        return []
    try:
      items = _json.loads(row['items'] or '[]')
    except Exception:
      items = []
    bag = []
    for it in items:
        for w in (it.get('words') or []):
            if isinstance(w, str):
                bag.append(w)
    seen = set(); out = []
    for w in bag:
        if w not in seen:
            seen.add(w); out.append(w)
    if len(out) > limit:
        import random as _r; _r.shuffle(out); out = out[:limit]
    return out

# Wrapper to maintain compatibility with old conn.execute() calls
class ConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
        self.config = get_database_config()
        self._current_cursor = None
    
    def execute(self, query, params=None):
        """Wrapper for conn.execute() to maintain compatibility"""
        if self.config['type'] == 'postgresql':
            # For PostgreSQL, use execute_query
            self._current_cursor = execute_query(self.conn, query, params)
            return self
        else:
            # For SQLite, use original conn.execute
            if params is None:
                self._current_cursor = self.conn.execute(query)
            else:
                self._current_cursor = self.conn.execute(query, params)
            return self
    
    def fetchall(self):
        """Fetch all results from the current cursor"""
        if self._current_cursor:
            return self._current_cursor.fetchall()
        return []
    
    def fetchone(self):
        """Fetch one result from the current cursor"""
        if self._current_cursor:
            return self._current_cursor.fetchone()
        return None
    
    def commit(self):
        if hasattr(self.conn, 'commit'):
            return self.conn.commit()
        return None
    
    def close(self):
        if self._current_cursor:
            self._current_cursor.close()
        return self.conn.close()
    
    @property
    def description(self):
        if self._current_cursor:
            return getattr(self._current_cursor, 'description', None)
        return None

    def cursor(self, cursor_factory=None):
        """Get cursor with optional cursor_factory for PostgreSQL"""
        if self.config['type'] == 'postgresql' and POSTGRES_DRIVER_AVAILABLE:
            cursor = get_db_cursor(self.conn)
            if cursor_factory is RealDictCursor:
                # row_factory already applied in get_db_cursor
                return cursor
            if cursor_factory is not None:
                raise TypeError("Unsupported cursor_factory requested")
            return cursor
        else:
            # SQLite doesn't support cursor_factory
            return self.conn.cursor()
    
    def __getattr__(self, name):
        """Delegate any other attributes to the underlying connection"""
        if name == 'lastrowid' and self._current_cursor:
            return self._current_cursor.lastrowid
        return getattr(self.conn, name)

# Legacy support - will be removed after migration
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(APP_ROOT, 'polo.db')

def get_db():
    """Get database connection - supports both SQLite and PostgreSQL"""
    conn = get_db_connection()
    return ConnectionWrapper(conn)

def execute_sql(conn, query, params=None):
    """Execute SQL query with appropriate parameter style"""
    return execute_query(conn, query, params)

def init_db():
    """Initialize database tables - supports both SQLite and PostgreSQL"""
    print("init_db: start", flush=True)
    config = get_database_config()
    conn = get_db()
    print(f"init_db: database type={config.get('type')}", flush=True)
    
    if config['type'] == 'postgresql':
        # PostgreSQL table creation
        print("init_db: creating PostgreSQL tables", flush=True)
        # Users table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                settings TEXT,
                native_language VARCHAR(10) DEFAULT 'en'
            );
        """)
        
        # User sessions table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                session_token VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)
        
        # User progress table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS user_progress (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                language VARCHAR(10) NOT NULL,
                native_language VARCHAR(10) NOT NULL,
                level INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'not_started',
                score REAL,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(user_id, language, native_language, level)
            );
        """)
        
        # User word familiarity table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS user_word_familiarity (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                familiarity INTEGER DEFAULT 0,
                seen_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                user_comment TEXT,
                last_seen TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(user_id, word_id)
            );
        """)
        
        # Words table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS words (
                id SERIAL PRIMARY KEY,
                word VARCHAR(255) NOT NULL,
                language VARCHAR(10),
                native_language VARCHAR(10),
                translation TEXT,
                example TEXT,
                info TEXT,
                seen_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                familiarity INTEGER DEFAULT 0,
                lemma VARCHAR(255), 
                pos VARCHAR(50), 
                ipa VARCHAR(255), 
                audio_url TEXT,
                gender VARCHAR(10), 
                plural VARCHAR(255), 
                conj TEXT, 
                comp TEXT, 
                synonyms TEXT,
                collocations TEXT, 
                example_native TEXT, 
                cefr VARCHAR(10), 
                freq_rank INTEGER,
                tags TEXT, 
                note TEXT
            );
        """)
        
        # Level runs table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS level_runs (
                id SERIAL PRIMARY KEY,
                level INTEGER,
                items TEXT,
                user_translations TEXT,
                score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                topic VARCHAR(100),
                target_lang VARCHAR(10),
                native_lang VARCHAR(10)
            );
        """)
        print("init_db: created base tables", flush=True)
        
        # Add missing columns to existing level_runs table if they don't exist
        try:
            execute_query(conn, "ALTER TABLE level_runs ADD COLUMN IF NOT EXISTS target_lang VARCHAR(10)")
            execute_query(conn, "ALTER TABLE level_runs ADD COLUMN IF NOT EXISTS native_lang VARCHAR(10)")
            conn.commit()
            print("init_db: ensured level_runs columns", flush=True)
        except Exception as e:
            print(f"Warning: Could not add columns to level_runs: {e}")
        
        # Practice runs table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS practice_runs (
                id SERIAL PRIMARY KEY,
                level INTEGER,
                words TEXT,
                todo TEXT,
                seen_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Localization table - normalized by language
        try:
            migrate_postgres_localization_table(conn.conn)
        except Exception as e:
            print(f"Warning: localization migration skipped: {e}")
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS localization (
                id SERIAL PRIMARY KEY,
                key VARCHAR(255) NOT NULL,
                language VARCHAR(16) NOT NULL,
                value TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(key, language)
            );
        """)
        conn.commit()
        print("init_db: ensured localization table", flush=True)
        # Skip description column check - it's optional and may cause locks
        # The column will be added automatically if needed during inserts
        print("init_db: skipping description column check (optional)", flush=True)
        print("init_db: committing localization table changes", flush=True)
        conn.commit()
        print("init_db: commit complete, about to ensure core localization entries", flush=True)
        ensure_core_localization_entries(conn)
        print("init_db: ensure_core_localization_entries returned", flush=True)
        conn.commit()
        # CSV sync disabled - using PostgreSQL only
        # trigger_localization_seed_if_needed()
        print("init_db: core localization entries done (CSV sync disabled)", flush=True)
        
        # Custom level groups table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS custom_level_groups (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                language VARCHAR(10) NOT NULL,
                native_language VARCHAR(10) NOT NULL,
                group_name VARCHAR(255) NOT NULL,
                context_description TEXT NOT NULL,
                cefr_level VARCHAR(10) DEFAULT 'A1',
                num_levels INTEGER DEFAULT 10,
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, language, group_name)
            );
        """)
        
        # Custom levels table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS custom_levels (
                id SERIAL PRIMARY KEY,
                group_id INTEGER NOT NULL,
                level_number INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                topic VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                word_ids INTEGER[] DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                UNIQUE(group_id, level_number)
            );
        """)
        
        # Marketplace group ratings table (PostgreSQL)
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS custom_level_group_ratings (
                id SERIAL PRIMARY KEY,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                stars INTEGER NOT NULL CHECK (stars >= 1 AND stars <= 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id),
                FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)
        print("init_db: ensured custom level tables", flush=True)
        conn.commit()
        
    else:
        # SQLite table creation (legacy)
        print("init_db: creating SQLite tables", flush=True)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS words (
          id INTEGER PRIMARY KEY,
          word TEXT NOT NULL,
          language TEXT,
          native_language TEXT,
          translation TEXT,
          example TEXT,
          info TEXT,
          seen_count INTEGER DEFAULT 0,
          correct_count INTEGER DEFAULT 0,
          created_at TEXT,
          updated_at TEXT,
          familiarity INTEGER DEFAULT 0,
          lemma TEXT, pos TEXT, ipa TEXT, audio_url TEXT,
          gender TEXT, plural TEXT, conj TEXT, comp TEXT, synonyms TEXT,
          collocations TEXT, example_native TEXT, cefr TEXT, freq_rank INTEGER,
          tags TEXT, note TEXT
        );
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS level_runs (
          id INTEGER PRIMARY KEY,
          level INTEGER,
          items TEXT,
          user_translations TEXT,
          score REAL,
          created_at TEXT,
          topic TEXT,
          target_lang TEXT,
          native_lang TEXT
        );
        """)
        
        # Add missing columns to existing level_runs table if they don't exist (SQLite)
        try:
            # Check if columns exist
            cursor = conn.execute("PRAGMA table_info(level_runs)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'target_lang' not in columns:
                conn.execute("ALTER TABLE level_runs ADD COLUMN target_lang TEXT")
                print("Added target_lang column to level_runs")
            
            if 'native_lang' not in columns:
                conn.execute("ALTER TABLE level_runs ADD COLUMN native_lang TEXT")
                print("Added native_lang column to level_runs")
                
            conn.commit()
        except Exception as e:
            print(f"Warning: Could not add columns to level_runs: {e}")
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS practice_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          level INTEGER,
          words TEXT,
          todo TEXT,
          seen_count INTEGER,
          created_at TEXT
        );
        """)
        
        # Create localization table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS localization (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          reference_key TEXT UNIQUE NOT NULL,
          description TEXT,
          german TEXT,
          english TEXT,
          french TEXT,
          italian TEXT,
          spanish TEXT,
          portuguese TEXT,
          russian TEXT,
          turkish TEXT,
          georgian TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """)
        
        # Create custom level tables
        create_custom_level_groups_table()
        create_custom_levels_table()

        # Marketplace group ratings table (SQLite)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS custom_level_group_ratings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          group_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,
          stars INTEGER NOT NULL CHECK (stars >= 1 AND stars <= 5),
          comment TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(user_id, group_id),
          FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
          FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        ensure_core_localization_entries(conn)
        print("init_db: ensured SQLite localization entries", flush=True)
        
        # User system tables
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          last_login TEXT,
          is_active BOOLEAN DEFAULT 1,
          settings TEXT,
          native_language TEXT DEFAULT 'en'
        );
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          language TEXT NOT NULL,
          native_language TEXT NOT NULL,
          level INTEGER NOT NULL,
          status TEXT DEFAULT 'not_started',
          score REAL,
          completed_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
          UNIQUE(user_id, language, native_language, level)
        );
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_word_familiarity (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          word_id INTEGER NOT NULL,
          familiarity INTEGER DEFAULT 0,
          seen_count INTEGER DEFAULT 0,
          correct_count INTEGER DEFAULT 0,
          user_comment TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
          FOREIGN KEY (word_id) REFERENCES words (id) ON DELETE CASCADE,
          UNIQUE(user_id, word_id)
        );
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          session_token TEXT UNIQUE NOT NULL,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        
        conn.commit()
    
    # Run migrations for custom_levels table
    try:
        migrate_custom_levels_add_word_count()
        migrate_custom_levels_add_word_ids()
        print("init_db: custom_levels migrations completed", flush=True)
    except Exception as e:
        print(f"init_db: Warning - custom_levels migrations failed: {e}", flush=True)
        # Continue anyway - migrations are idempotent
    
    conn.close()
    print("init_db: done", flush=True)

def create_custom_level_group_ratings_table():
    """Create ratings table explicitly; safe to run multiple times."""
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            execute_query(conn, """
                CREATE TABLE IF NOT EXISTS custom_level_group_ratings (
                    id SERIAL PRIMARY KEY,
                    group_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    stars INTEGER NOT NULL CHECK (stars >= 1 AND stars <= 5),
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, group_id),
                    FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                );
            """)
        else:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS custom_level_group_ratings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              stars INTEGER NOT NULL CHECK (stars >= 1 AND stars <= 5),
              comment TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(user_id, group_id),
              FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
              FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """)
            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating ratings table: {e}")
        return False
    finally:
        conn.close()
# --- Words CRUD helpers ---

def list_words_rows():
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            cur = conn.cursor()
            cur.execute(
                'SELECT id, word, language, native_language, translation, example, example_native, lemma, pos, ipa, audio_url, gender, plural, cefr, freq_rank, synonyms, collocations, tags, note, info, updated_at FROM words ORDER BY COALESCE(updated_at, created_at) DESC'
            )
            rows = cur.fetchall()
            cur.close()
            return rows
        else:
            rows = conn.execute(
                'SELECT id, word, language, native_language, translation, example, example_native, lemma, pos, ipa, audio_url, gender, plural, cefr, freq_rank, synonyms, collocations, tags, note, info, updated_at FROM words ORDER BY COALESCE(updated_at, created_at) DESC'
            ).fetchall()
            return rows
    finally:
        conn.close()


def get_word_row(word: str, language: str, native_language: str = None):
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            cur = conn.cursor()
            if native_language:
                cur.execute(
                    'SELECT word, language, native_language, translation, example, example_native, lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms, collocations, cefr, freq_rank, tags, note, info, updated_at FROM words WHERE word=%s AND language=%s AND native_language=%s LIMIT 1',
                    (word, language, native_language)
                )
            else:
                cur.execute(
                    'SELECT word, language, native_language, translation, example, example_native, lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms, collocations, cefr, freq_rank, tags, note, info, updated_at FROM words WHERE word=%s AND (language=%s OR %s=\'\') LIMIT 1',
                    (word, language, language)
                )
            row = cur.fetchone()
            cur.close()
            return row
        else:
            if native_language:
                row = conn.execute(
                    'SELECT word, language, native_language, translation, example, example_native, lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms, collocations, cefr, freq_rank, tags, note, info, updated_at FROM words WHERE word=? AND language=? AND native_language=? LIMIT 1',
                    (word, language, native_language)
                ).fetchone()
            else:
                row = conn.execute(
                    'SELECT word, language, native_language, translation, example, example_native, lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms, collocations, cefr, freq_rank, tags, note, info, updated_at FROM words WHERE word=? AND (language=? OR ?="") LIMIT 1',
                    (word, language, language)
                ).fetchone()
            return row
    finally:
        conn.close()


def count_words_fam5(language: str | None = None) -> int:
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            cur = conn.cursor()
            if language:
                cur.execute('SELECT COUNT(*) AS c FROM words WHERE (language=%s OR %s=\'\')', (language, language))
            else:
                cur.execute('SELECT COUNT(*) AS c FROM words')
            row = cur.fetchone()
            cur.close()
            return int(row[0] if row else 0)
        else:
            if language:
                row = conn.execute('SELECT COUNT(*) AS c FROM words WHERE (language=? OR ?="")', (language, language)).fetchone()
            else:
                row = conn.execute('SELECT COUNT(*) AS c FROM words').fetchone()
            return int(row['c'] if row else 0)
    finally:
        conn.close()


def delete_words_by_ids(ids_int: list[int]) -> int:
    if not ids_int:
        return 0
    
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db(); cur = conn.cursor()
    
    if config['type'] == 'postgresql':
        q = ','.join('%s' for _ in ids_int)
        cur.execute(f'DELETE FROM words WHERE id IN ({q})', tuple(ids_int))
    else:
        q = ','.join('?' for _ in ids_int)
        cur.execute(f'DELETE FROM words WHERE id IN ({q})', tuple(ids_int))
    
    n = cur.rowcount
    conn.commit(); conn.close()
    return int(n)


def batch_upsert_word_rows(payloads: list[dict]) -> None:
    """
    Batch upsert multiple words efficiently.
    Much faster than calling upsert_word_row individually.
    """
    if not payloads:
        return
    
    from datetime import datetime, UTC
    import json as _json
    from .db_config import get_database_config, get_db_connection, execute_query
    
    config = get_database_config()
    conn = get_db_connection()
    now = datetime.now(UTC).isoformat()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL batch upsert using VALUES and ON CONFLICT
            values_list = []
            for payload in payloads:
                word = normalize_word(payload.get('word') or '')
                language = (payload.get('language') or '').strip()
                native_language = (payload.get('native_language') or '').strip()
                translation = (payload.get('translation') or '').strip()
                example = (payload.get('example') or '').strip()
                example_native = (payload.get('example_native') or '').strip()
                lemma = (payload.get('lemma') or '').strip()
                pos = (payload.get('pos') or '').strip()
                ipa = (payload.get('ipa') or '').strip()
                audio_url = (payload.get('audio_url') or '').strip()
                gender = (payload.get('gender') or '').strip()
                plural = (payload.get('plural') or '').strip()
                conj = payload.get('conj')
                comp = payload.get('comp')
                synonyms = payload.get('synonyms')
                collocations = payload.get('collocations')
                cefr = (payload.get('cefr') or '').strip()
                freq_rank = payload.get('freq_rank')
                tags = payload.get('tags')
                note = (payload.get('note') or '').strip()
                info = payload.get('info')
                
                info_json = _json.dumps(info) if isinstance(info, (dict, list)) else (str(info) if info else None)
                conj_json = _json.dumps(conj, ensure_ascii=False) if isinstance(conj, dict) else (None if conj is None else str(conj))
                comp_json = _json.dumps(comp, ensure_ascii=False) if isinstance(comp, dict) else (None if comp is None else str(comp))
                syn_json = _json.dumps(synonyms, ensure_ascii=False) if isinstance(synonyms, list) else (None if synonyms is None else str(synonyms))
                coll_json = _json.dumps(collocations, ensure_ascii=False) if isinstance(collocations, list) else (None if collocations is None else str(collocations))
                tags_json = _json.dumps(tags, ensure_ascii=False) if isinstance(tags, list) else (None if tags is None else str(tags))
                
                try:
                    freq_rank = int(freq_rank) if (freq_rank is not None and str(freq_rank).strip()!='') else None
                except Exception:
                    freq_rank = None
                
                values_list.append((
                    word, language or None, native_language or None, translation or None, example or None,
                    example_native or None, lemma or None, pos or None, ipa or None, audio_url or None,
                    gender or None, plural or None, conj_json, comp_json, syn_json, coll_json,
                    cefr or None, freq_rank, tags_json, note or None, info_json, now, now
                ))
            
            if values_list:
                # Use pg8000-compatible batch insert with multiple VALUES clauses
                cur = conn.cursor()
                try:
                    if len(values_list) == 1:
                        # Single insert
                        cur.execute('''
                            INSERT INTO words (
                                word, language, native_language, translation, example, example_native,
                                lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                                collocations, cefr, freq_rank, tags, note, info, created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (word, language, native_language) 
                            DO UPDATE SET
                                translation = COALESCE(EXCLUDED.translation, words.translation),
                                example = COALESCE(EXCLUDED.example, words.example),
                                example_native = COALESCE(EXCLUDED.example_native, words.example_native),
                                lemma = COALESCE(EXCLUDED.lemma, words.lemma),
                                pos = COALESCE(EXCLUDED.pos, words.pos),
                                ipa = COALESCE(EXCLUDED.ipa, words.ipa),
                                audio_url = COALESCE(EXCLUDED.audio_url, words.audio_url),
                                gender = COALESCE(EXCLUDED.gender, words.gender),
                                plural = COALESCE(EXCLUDED.plural, words.plural),
                                conj = COALESCE(EXCLUDED.conj, words.conj),
                                comp = COALESCE(EXCLUDED.comp, words.comp),
                                synonyms = COALESCE(EXCLUDED.synonyms, words.synonyms),
                                collocations = COALESCE(EXCLUDED.collocations, words.collocations),
                                cefr = COALESCE(EXCLUDED.cefr, words.cefr),
                                freq_rank = COALESCE(EXCLUDED.freq_rank, words.freq_rank),
                                tags = COALESCE(EXCLUDED.tags, words.tags),
                                note = COALESCE(EXCLUDED.note, words.note),
                                info = COALESCE(EXCLUDED.info, words.info),
                                updated_at = EXCLUDED.updated_at
                        ''', values_list[0])
                    else:
                        # Batch insert - build VALUES clause with multiple tuples
                        values_placeholders = ', '.join(['(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'] * len(values_list))
                        params = []
                        for val_tuple in values_list:
                            params.extend(val_tuple)
                        
                        cur.execute(f'''
                            INSERT INTO words (
                                word, language, native_language, translation, example, example_native,
                                lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                                collocations, cefr, freq_rank, tags, note, info, created_at, updated_at
                            ) VALUES {values_placeholders}
                            ON CONFLICT (word, language, native_language) 
                            DO UPDATE SET
                                translation = COALESCE(EXCLUDED.translation, words.translation),
                                example = COALESCE(EXCLUDED.example, words.example),
                                example_native = COALESCE(EXCLUDED.example_native, words.example_native),
                                lemma = COALESCE(EXCLUDED.lemma, words.lemma),
                                pos = COALESCE(EXCLUDED.pos, words.pos),
                                ipa = COALESCE(EXCLUDED.ipa, words.ipa),
                                audio_url = COALESCE(EXCLUDED.audio_url, words.audio_url),
                                gender = COALESCE(EXCLUDED.gender, words.gender),
                                plural = COALESCE(EXCLUDED.plural, words.plural),
                                conj = COALESCE(EXCLUDED.conj, words.conj),
                                comp = COALESCE(EXCLUDED.comp, words.comp),
                                synonyms = COALESCE(EXCLUDED.synonyms, words.synonyms),
                                collocations = COALESCE(EXCLUDED.collocations, words.collocations),
                                cefr = COALESCE(EXCLUDED.cefr, words.cefr),
                                freq_rank = COALESCE(EXCLUDED.freq_rank, words.freq_rank),
                                tags = COALESCE(EXCLUDED.tags, words.tags),
                                note = COALESCE(EXCLUDED.note, words.note),
                                info = COALESCE(EXCLUDED.info, words.info),
                                updated_at = EXCLUDED.updated_at
                        ''', params)
                finally:
                    cur.close()
        else:
            # SQLite - fallback to individual inserts (SQLite doesn't support efficient batch upsert)
            for payload in payloads:
                upsert_word_row(payload)
        
        conn.commit()
    finally:
        conn.close()

def upsert_word_row(payload: dict) -> None:
    word = normalize_word(payload.get('word') or '')
    language = (payload.get('language') or '').strip()
    native_language = (payload.get('native_language') or '').strip()
    translation = (payload.get('translation') or '').strip()
    example = (payload.get('example') or '').strip()
    example_native = (payload.get('example_native') or '').strip()
    lemma = (payload.get('lemma') or '').strip()
    pos = (payload.get('pos') or '').strip()
    ipa = (payload.get('ipa') or '').strip()
    audio_url = (payload.get('audio_url') or '').strip()
    gender = (payload.get('gender') or '').strip()
    plural = (payload.get('plural') or '').strip()
    conj = payload.get('conj')
    comp = payload.get('comp')
    synonyms = payload.get('synonyms')
    collocations = payload.get('collocations')
    cefr = (payload.get('cefr') or '').strip()
    freq_rank = payload.get('freq_rank')
    tags = payload.get('tags')
    note = (payload.get('note') or '').strip()
    info = payload.get('info')
    info_json = _json.dumps(info) if isinstance(info, (dict, list)) else (str(info) if info else None)
    conj_json = _json.dumps(conj, ensure_ascii=False) if isinstance(conj, dict) else (None if conj is None else str(conj))
    comp_json = _json.dumps(comp, ensure_ascii=False) if isinstance(comp, dict) else (None if comp is None else str(comp))
    syn_json = _json.dumps(synonyms, ensure_ascii=False) if isinstance(synonyms, list) else (None if synonyms is None else str(synonyms))
    coll_json = _json.dumps(collocations, ensure_ascii=False) if isinstance(collocations, list) else (None if collocations is None else str(collocations))
    tags_json = _json.dumps(tags, ensure_ascii=False) if isinstance(tags, list) else (None if tags is None else str(tags))
    try:
        freq_rank = int(freq_rank) if (freq_rank is not None and str(freq_rank).strip()!='') else None
    except Exception:
        freq_rank = None
    now = datetime.now(UTC).isoformat()
    
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax - use INSERT ... ON CONFLICT for proper upsert
            execute_query(conn, '''
                INSERT INTO words (
                    word, language, native_language, translation, example, example_native,
                    lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                    collocations, cefr, freq_rank, tags, note, info, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (word, language, native_language) 
                DO UPDATE SET
                    translation = COALESCE(EXCLUDED.translation, words.translation),
                    example = COALESCE(EXCLUDED.example, words.example),
                    example_native = COALESCE(EXCLUDED.example_native, words.example_native),
                    lemma = COALESCE(EXCLUDED.lemma, words.lemma),
                    pos = COALESCE(EXCLUDED.pos, words.pos),
                    ipa = COALESCE(EXCLUDED.ipa, words.ipa),
                    audio_url = COALESCE(EXCLUDED.audio_url, words.audio_url),
                    gender = COALESCE(EXCLUDED.gender, words.gender),
                    plural = COALESCE(EXCLUDED.plural, words.plural),
                    conj = COALESCE(EXCLUDED.conj, words.conj),
                    comp = COALESCE(EXCLUDED.comp, words.comp),
                    synonyms = COALESCE(EXCLUDED.synonyms, words.synonyms),
                    collocations = COALESCE(EXCLUDED.collocations, words.collocations),
                    cefr = COALESCE(EXCLUDED.cefr, words.cefr),
                    freq_rank = COALESCE(EXCLUDED.freq_rank, words.freq_rank),
                    tags = COALESCE(EXCLUDED.tags, words.tags),
                    note = COALESCE(EXCLUDED.note, words.note),
                    info = COALESCE(EXCLUDED.info, words.info),
                    updated_at = EXCLUDED.updated_at
            ''', (word, language or None, native_language or None, translation or None, example or None, example_native or None, lemma or None, pos or None, ipa or None, audio_url or None, gender or None, plural or None, conj_json, comp_json, syn_json, coll_json, cefr or None, freq_rank, tags_json, note or None, info_json, now, now))
        else:
            # SQLite syntax
            cur = conn.cursor()
            cur.execute(
                'UPDATE words SET language=COALESCE(?, language), native_language=COALESCE(?, native_language), translation=COALESCE(?, translation), example=COALESCE(?, example), example_native=COALESCE(?, example_native), lemma=COALESCE(?, lemma), pos=COALESCE(?, pos), ipa=COALESCE(?, ipa), audio_url=COALESCE(?, audio_url), gender=COALESCE(?, gender), plural=COALESCE(?, plural), conj=COALESCE(?, conj), comp=COALESCE(?, comp), synonyms=COALESCE(?, synonyms), collocations=COALESCE(?, collocations), cefr=COALESCE(?, cefr), freq_rank=COALESCE(?, freq_rank), tags=COALESCE(?, tags), note=COALESCE(?, note), info=COALESCE(?, info), updated_at=? WHERE word=? AND (language=? OR ?="")',
                (language or None, native_language or None, translation or None, example or None, example_native or None,
                 lemma or None, pos or None, ipa or None, audio_url or None, gender or None, plural or None, conj_json, comp_json, syn_json, coll_json, cefr or None, freq_rank, tags_json, note or None, info_json, now, word, language, language)
            )
            if cur.rowcount == 0:
                cur.execute(
                    'INSERT INTO words (word, language, native_language, translation, example, example_native, lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms, collocations, cefr, freq_rank, tags, note, info, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (word, language or None, native_language or None, translation or None, example or None, example_native or None, lemma or None, pos or None, ipa or None, audio_url or None, gender or None, plural or None, conj_json, comp_json, syn_json, coll_json, cefr or None, freq_rank, tags_json, note or None, info_json, now, now)
                )
        conn.commit()
    finally:
        conn.close()

# --- Localization helpers ---

def _pg_fetch_localization_rows(conn, reference_key: str | None = None, language_code: str | None = None):
    """Fetch localization rows from PostgreSQL"""
    query = "SELECT id, key, language, value, description FROM localization"
    conditions = []
    params: list[Any] = []
    if reference_key:
        conditions.append("key = %s")
        params.append(reference_key)
    if language_code:
        conditions.append("language = %s")
        params.append(language_code)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY key, language"
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    normalized = []
    for row in rows:
        try:
            normalized.append(dict(row))
        except Exception:
            # fallback for tuple rows
            keys = ('id', 'key', 'language', 'value', 'description')
            normalized.append({k: row[i] if i < len(row) else None for i, k in enumerate(keys)})
    return normalized


def _pg_aggregate_localization_rows(rows: list[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    aggregated: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        ref_key = row.get('key')
        if not ref_key:
            continue
        entry = aggregated.setdefault(ref_key, {
            'reference_key': ref_key,
            'id': row.get('id'),
            'description': row.get('description')
        })
        # Keep the smallest id so editing works
        row_id = row.get('id')
        if row_id is not None:
            entry_id = entry.get('id')
            if entry_id is None or (isinstance(row_id, int) and isinstance(entry_id, int) and row_id < entry_id):
                entry['id'] = row_id
        # Preserve description if we do not have one yet
        if (not entry.get('description')) and row.get('description'):
            entry['description'] = row.get('description')
        lang_code = normalize_language_identifier(row.get('language'))
        if not lang_code:
            continue
        alias = language_code_to_field(lang_code)
        entry[alias] = row.get('value')
    return aggregated


def seed_postgres_localization_from_csv(conn, csv_path=None) -> None:
    """DEPRECATED: CSV sync removed - using PostgreSQL only.
    This function is kept for reference but is no longer called."""
    print("Warning: seed_postgres_localization_from_csv is deprecated. CSV sync disabled - using PostgreSQL only.")
    return


def trigger_localization_seed_if_needed():
    """DEPRECATED: CSV sync removed - using PostgreSQL only.
    This function is kept for reference but is no longer called."""
    # CSV sync disabled - using PostgreSQL only
    return


CORE_LOCALIZATION_ENTRIES: list[Dict[str, Any]] = [
    {
        'reference_key': 'lesson.replay_sentence',
        'description': 'Tooltip for replay sentence button',
        'en': 'Replay sentence',
        'de': 'Satz erneut abspielen'
    },
    {
        'reference_key': 'lesson.build_sentence',
        'description': 'Label for sentence builder area',
        'en': 'Build the sentence',
        'de': 'Satz aufbauen'
    },
    {
        'reference_key': 'lesson.available_words',
        'description': 'Label for available words list',
        'en': 'Available words',
        'de': 'Verfügbare Wörter'
    },
    {
        'reference_key': 'lesson.prompt_translate',
        'description': 'Prompt shown when translation is missing',
        'en': 'Please translate.',
        'de': 'Bitte übersetzen.'
    },
    {
        'reference_key': 'errors.generic',
        'description': 'Generic error message',
        'en': 'An error occurred.',
        'de': 'Es ist ein Fehler aufgetreten.'
    },
    {
        'reference_key': 'lesson.custom_level_start_failed',
        'description': 'Alert when a custom level cannot be started',
        'en': 'Failed to start custom level.',
        'de': 'Fehler beim Starten des Custom Levels.'
    },
    {
        'reference_key': 'lesson.level_locked',
        'description': 'Message explaining a level is locked',
        'en': 'Level {level} is locked. Complete level {requiredLevel} with at least 60%.',
        'de': 'Level {level} ist gesperrt. Du musst Level {requiredLevel} mit mindestens 60% abschließen.'
    },
    {
        'reference_key': 'levels.locked_title',
        'description': 'Title on level locked overlay',
        'en': 'Level {level} is locked',
        'de': 'Level {level} ist gesperrt'
    },
    {
        'reference_key': 'levels.locked_body',
        'description': 'Body text on level locked overlay',
        'en': 'Complete level {prevLevel} with at least {percent}% to unlock level {level}.',
        'de': 'Du musst Level {prevLevel} mit mindestens {percent}% abschließen, um Level {level} freizuschalten.'
    },
    {
        'reference_key': 'levels.locked_progress',
        'description': 'Progress label on level locked overlay',
        'en': 'Level {prevLevel} progress: {percent}%',
        'de': 'Level {prevLevel} Fortschritt: {percent}%'
    },
    {
        'reference_key': 'levels.locked_required',
        'description': 'Required score label on level locked overlay',
        'en': 'Required: {percent}%',
        'de': 'Benötigt: {percent}%'
    },
    {
        'reference_key': 'levels.continue_previous',
        'description': 'Button to continue previous level from locked overlay',
        'en': 'Continue level {level}',
        'de': 'Level {level} fortsetzen'
    },
    {
        'reference_key': 'buttons.close',
        'description': 'Generic close button',
        'en': 'Close',
        'de': 'Schließen'
    },
    {
        'reference_key': 'onboarding.preferences_saved',
        'description': 'Onboarding success message after saving preferences',
        'en': 'Welcome to Siluma! Your preferences have been saved.',
        'de': 'Willkommen bei Siluma! Deine Einstellungen wurden gespeichert.'
    },
    {
        'reference_key': 'marketplace.load_error',
        'description': 'Generic marketplace loading error',
        'en': 'Failed to load marketplace.',
        'de': 'Fehler beim Laden des Marketplaces.'
    },
    {
        'reference_key': 'marketplace.load_error_with_reason',
        'description': 'Marketplace loading error with appended reason',
        'en': 'Failed to load marketplace data: {reason}',
        'de': 'Fehler beim Laden der Marketplace-Inhalte: {reason}'
    },
    {
        'reference_key': 'marketplace.empty_title',
        'description': 'Title shown when no marketplace groups match filters',
        'en': 'No level groups found',
        'de': 'Keine Level-Gruppen gefunden'
    },
    {
        'reference_key': 'marketplace.empty_text',
        'description': 'Description when no marketplace groups match filters',
        'en': 'No published level groups match your filters.<br>Try different filters or create your own level group!',
        'de': 'Es wurden keine publizierten Level-Gruppen für die gewählten Filter gefunden.<br>Versuche andere Filter oder erstelle deine eigene Level-Gruppe!'
    },
    {
        'reference_key': 'marketplace.page_info',
        'description': 'Pagination label in marketplace',
        'en': 'Page {current} of {total}',
        'de': 'Seite {current} von {total}'
    },
    {
        'reference_key': 'marketplace.loading',
        'description': 'Loading message for marketplace',
        'en': 'Loading marketplace data...',
        'de': 'Lade Marketplace-Inhalte...'
    },
    {
        'reference_key': 'marketplace.login_to_rate',
        'description': 'Prompt to log in before rating',
        'en': 'Please sign in to rate.',
        'de': 'Bitte anmelden, um zu bewerten.'
    },
    {
        'reference_key': 'marketplace.select_rating',
        'description': 'Prompt to select star rating',
        'en': 'Please choose between 1 and 5 stars.',
        'de': 'Bitte 1–5 Sterne wählen.'
    },
    {
        'reference_key': 'marketplace.sending',
        'description': 'Status while rating is being submitted',
        'en': 'Sending...',
        'de': 'Senden...'
    },
    {
        'reference_key': 'marketplace.submit_error',
        'description': 'Generic error when rating submission fails',
        'en': 'Failed to submit rating',
        'de': 'Fehler beim Senden'
    },
    {
        'reference_key': 'marketplace.thank_you',
        'description': 'Thank you message after submitting rating',
        'en': 'Thanks for your rating!',
        'de': 'Danke für deine Bewertung!'
    },
    {
        'reference_key': 'marketplace.error_status',
        'description': 'Prefix shown when rating submission fails',
        'en': 'Error: {message}',
        'de': 'Fehler: {message}'
    },
    {
        'reference_key': 'errors.title',
        'description': 'Generic error title label',
        'en': 'Error',
        'de': 'Fehler'
    },
    {
        'reference_key': 'errors.unknown',
        'description': 'Message shown when error reason is unknown',
        'en': 'Unknown error',
        'de': 'Unbekannter Fehler'
    },
    {
        'reference_key': 'localization.ai_fill_in_progress',
        'description': 'Button label shown while AI fill runs',
        'en': '🤖 AI filling...',
        'de': '🤖 KI füllt aus...'
    },
    {
        'reference_key': 'localization.delete_confirm',
        'description': 'Confirmation prompt when deleting a localization entry',
        'en': 'Are you sure you want to delete this entry?',
        'de': 'Möchtest du diesen Eintrag wirklich löschen?'
    },
    {
        'reference_key': 'localization.delete_failed',
        'description': 'Error message when deleting localization entry fails',
        'en': 'Failed to delete entry: {error}',
        'de': 'Löschen des Eintrags fehlgeschlagen: {error}'
    },
    {
        'reference_key': 'localization.delete_error',
        'description': 'Generic delete error message',
        'en': 'Error deleting entry: {error}',
        'de': 'Fehler beim Löschen des Eintrags: {error}'
    },
    {
        'reference_key': 'localization.ai_fill_confirm',
        'description': 'Confirmation message before triggering AI fill',
        'en': 'This will use AI to fill missing translations for the top 20 most spoken languages.\n\nThis may take a few minutes and will use OpenAI API credits.\n\nDo you want to continue?',
        'de': 'Dies nutzt KI, um fehlende Übersetzungen für die 20 meistgesprochenen Sprachen zu ergänzen.\n\nDies kann einige Minuten dauern und OpenAI-Guthaben verbrauchen.\n\nMöchtest du fortfahren?'
    },
    {
        'reference_key': 'localization.ai_fill_success',
        'description': 'Success message after AI fill completes',
        'en': '✅ AI translation filling completed successfully!\n\nPlease refresh the page to see the new translations.',
        'de': '✅ KI-Übersetzungsergänzung erfolgreich abgeschlossen!\n\nBitte lade die Seite neu, um die neuen Übersetzungen zu sehen.'
    },
    {
        'reference_key': 'localization.ai_fill_error',
        'description': 'Error message when AI fill fails, with reason',
        'en': '❌ AI translation filling failed: {error}',
        'de': '❌ KI-Übersetzungsergänzung fehlgeschlagen: {error}'
    },
    {
        'reference_key': 'localization.ai_fill_error_generic',
        'description': 'Generic error message when AI fill throws',
        'en': '❌ Error during AI fill: {error}',
        'de': '❌ Fehler während der KI-Ergänzung: {error}'
    },
    {
        'reference_key': 'ui.loading',
        'description': 'Loading text shown on buttons and UI elements',
        'en': 'Loading...',
        'de': 'Lädt...',
        'fr': 'Chargement...',
        'it': 'Caricamento...',
        'es': 'Cargando...',
        'pt': 'Carregando...',
        'ru': 'Загрузка...',
        'tr': 'Yükleniyor...',
        'ka': 'იტვირთება...'
    },
    {
        'reference_key': 'practice.preparing_session',
        'description': 'Message shown while preparing practice session',
        'en': 'Preparing practice session...',
        'de': 'Übung wird vorbereitet...',
        'fr': 'Préparation de la session...',
        'it': 'Preparazione della sessione...',
        'es': 'Preparando sesión...',
        'pt': 'Preparando sessão...',
        'ru': 'Подготовка сессии...',
        'tr': 'Oturum hazırlanıyor...',
        'ka': 'სესია მზადდება...'
    }
]


def ensure_core_localization_entries(conn=None):
    """Ensure critical localization keys exist with defaults - optimized with batch operations"""
    print("ensure_core_localization_entries: starting", flush=True)
    managed_connection = False
    if conn is None:
        print("ensure_core_localization_entries: creating new connection", flush=True)
        config = get_database_config()
        if config['type'] == 'postgresql':
            conn = get_db_connection()
        else:
            conn = get_db()
        managed_connection = True
    else:
        print("ensure_core_localization_entries: using provided connection", flush=True)

    try:
        config = get_database_config()
        print(f"ensure_core_localization_entries: database type = {config['type']}", flush=True)
        now = datetime.now(UTC).isoformat()
        
        if config['type'] == 'postgresql':
            # Batch insert/update for PostgreSQL - optimized with single bulk INSERT
            print("init_db: batch upserting core localization entries", flush=True)
            
            # Prepare all values for bulk insert
            values_to_insert = []
            print(f"ensure_core_localization_entries: processing {len(CORE_LOCALIZATION_ENTRIES)} entries", flush=True)
            for entry in CORE_LOCALIZATION_ENTRIES:
                reference_key = (entry.get('reference_key') or entry.get('key') or '').strip()
                if not reference_key:
                    continue
                    
                description = (entry.get('description') or '').strip() or None
                
                # Extract translations
                explicit_language = normalize_language_identifier(entry.get('language'))
                explicit_text = entry.get('text') or entry.get('value')
                if explicit_language and explicit_text:
                    text_value = str(explicit_text).strip()
                    if text_value and text_value not in LOCALIZATION_INVALID_VALUES:
                        values_to_insert.append((reference_key, explicit_language, text_value, description, now, now))
                
                for key, value in entry.items():
                    if key in {'reference_key', 'key', 'description', 'language', 'text', 'value'}:
                        continue
                    if value is None:
                        continue
                    lang_code = normalize_language_identifier(key)
                    if not lang_code:
                        continue
                    text_value = str(value).strip()
                    if text_value and text_value not in LOCALIZATION_INVALID_VALUES:
                        values_to_insert.append((reference_key, lang_code, text_value, description, now, now))
            
            print(f"ensure_core_localization_entries: prepared {len(values_to_insert)} values to insert", flush=True)
            
            # Use batch inserts - optimized approach
            # TODO: Further optimize with larger batches once we verify it works
            if values_to_insert:
                print("ensure_core_localization_entries: starting batch inserts", flush=True)
                total_inserted = 0
                cur = conn.cursor()
                try:
                    # Use smaller batches (10 at a time) to avoid issues
                    batch_size = 10
                    for i in range(0, len(values_to_insert), batch_size):
                        batch = values_to_insert[i:i + batch_size]
                        
                        # Build VALUES clause for this batch
                        if len(batch) == 1:
                            # Single insert
                            ref_key, lang_code, text_value, desc, created, updated = batch[0]
                            cur.execute("""
                                INSERT INTO localization (key, language, value, description, created_at, updated_at)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (key, language) DO UPDATE SET
                                    value = EXCLUDED.value,
                                    description = COALESCE(EXCLUDED.description, localization.description),
                                    updated_at = EXCLUDED.updated_at
                            """, (ref_key, lang_code, text_value, desc, created, updated))
                        else:
                            # Bulk insert for batch
                            values_placeholders = ', '.join(['(%s, %s, %s, %s, %s, %s)'] * len(batch))
                            params = []
                            for ref_key, lang_code, text_value, desc, created, updated in batch:
                                params.extend([ref_key, lang_code, text_value, desc, created, updated])
                            
                            cur.execute(f"""
                                INSERT INTO localization (key, language, value, description, created_at, updated_at)
                                VALUES {values_placeholders}
                                ON CONFLICT (key, language) DO UPDATE SET
                                    value = EXCLUDED.value,
                                    description = COALESCE(EXCLUDED.description, localization.description),
                                    updated_at = EXCLUDED.updated_at
                            """, params)
                        
                        total_inserted += len(batch)
                        if (i + batch_size) % 20 == 0 or i + batch_size >= len(values_to_insert):
                            print(f"ensure_core_localization_entries: inserted {min(i + batch_size, len(values_to_insert))}/{len(values_to_insert)} entries", flush=True)
                finally:
                    cur.close()
                
                print(f"init_db: batch upserted {total_inserted} core localization entries", flush=True)
            else:
                print("init_db: no core localization entries to upsert", flush=True)
        else:
            # SQLite - batch operations
            print("init_db: batch upserting core localization entries", flush=True)
            cur = conn.cursor()
            
            for entry in CORE_LOCALIZATION_ENTRIES:
                reference_key = (entry.get('reference_key') or entry.get('key') or '').strip()
                if not reference_key:
                    continue
                    
                description = (entry.get('description') or '').strip() or None
                german = (entry.get('german') or entry.get('de') or '').strip() or None
                english = (entry.get('english') or entry.get('en') or '').strip() or None
                french = (entry.get('french') or entry.get('fr') or '').strip() or None
                italian = (entry.get('italian') or entry.get('it') or '').strip() or None
                spanish = (entry.get('spanish') or entry.get('es') or '').strip() or None
                portuguese = (entry.get('portuguese') or entry.get('pt') or '').strip() or None
                russian = (entry.get('russian') or entry.get('ru') or '').strip() or None
                turkish = (entry.get('turkish') or entry.get('tr') or '').strip() or None
                georgian = (entry.get('georgian') or entry.get('ka') or '').strip() or None
                
                cur.execute(
                    'UPDATE localization SET description=COALESCE(?, description), german=COALESCE(?, german), english=COALESCE(?, english), french=COALESCE(?, french), italian=COALESCE(?, italian), spanish=COALESCE(?, spanish), portuguese=COALESCE(?, portuguese), russian=COALESCE(?, russian), turkish=COALESCE(?, turkish), georgian=COALESCE(?, georgian), updated_at=? WHERE reference_key=?',
                    (description, german, english, french, italian, spanish, portuguese, russian, turkish, georgian, now, reference_key)
                )
                if cur.rowcount == 0:
                    cur.execute(
                        'INSERT INTO localization (reference_key, description, german, english, french, italian, spanish, portuguese, russian, turkish, georgian, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (reference_key, description, german, english, french, italian, spanish, portuguese, russian, turkish, georgian, now, now)
                    )
            
            print(f"init_db: batch upserted {len(CORE_LOCALIZATION_ENTRIES)} core localization entries", flush=True)

        print("init_db: core localization entries done", flush=True)
        if managed_connection:
            conn.commit()
    except Exception as exc:
        print(f"Warning: failed to batch upsert core localization entries: {exc}", flush=True)
        if managed_connection:
            conn.rollback()
        raise
    finally:
        if managed_connection:
            conn.close()


def get_localization_entry(reference_key: str, language: str = None):
    """Get a localization entry by reference key and optionally language"""
    from server.db_config import get_database_config
    
    config = get_database_config()
    if config['type'] == 'postgresql':
        conn = get_db_connection()
    else:
        conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            lang_code = normalize_language_identifier(language)
            rows = _pg_fetch_localization_rows(conn, reference_key, lang_code if lang_code else None)
            if not rows and lang_code:
                # Allow fallback to fetch other languages for metadata
                rows = _pg_fetch_localization_rows(conn, reference_key, None)
            if not rows:
                return {}
            aggregated = _pg_aggregate_localization_rows(rows)
            entry = aggregated.get(reference_key, {})
            if lang_code:
                alias = language_code_to_field(lang_code)
                return {
                    'reference_key': reference_key,
                    'language': lang_code,
                    'description': entry.get('description'),
                    alias: entry.get(alias)
                }
            return entry
        else:
            if language:
                # Get specific language translation
                row = conn.execute(
                    'SELECT * FROM localization WHERE reference_key = ?',
                    (reference_key,)
                ).fetchone()
                if row:
                    # Convert row to dict and return only the requested language
                    row_dict = dict(row)
                    lang_column = language.lower()
                    if lang_column in row_dict:
                        return {lang_column: row_dict[lang_column]}
                    else:
                        return {}
                return {}
            else:
                # Get all translations for the key
                row = conn.execute(
                    'SELECT * FROM localization WHERE reference_key = ?',
                    (reference_key,)
                ).fetchone()
                return row
    finally:
        conn.close()

def upsert_localization_entry(payload: dict, conn=None) -> None:
    """Insert or update a localization entry"""
    reference_key = (payload.get('reference_key') or payload.get('key') or '').strip()
    if not reference_key:
        raise ValueError("reference_key is required for localization upsert")
    description = (payload.get('description') or '').strip() or None
    
    now = datetime.now(UTC).isoformat()
    
    config = get_database_config()
    managed_connection = False
    if conn is None:
        conn = get_db_connection()
        managed_connection = True
    try:
        if config['type'] == 'postgresql':
            translations: Dict[str, str] = {}
            
            explicit_language = normalize_language_identifier(payload.get('language'))
            explicit_text = payload.get('text') or payload.get('value')
            if explicit_language and explicit_text:
                text_value = str(explicit_text).strip()
                if text_value and text_value not in LOCALIZATION_INVALID_VALUES:
                    translations[explicit_language] = text_value
            
            for key, value in payload.items():
                if key in {'reference_key', 'key', 'description', 'language', 'text', 'value'}:
                    continue
                if value is None:
                    continue
                lang_code = normalize_language_identifier(key)
                if not lang_code:
                    continue
                text_value = str(value).strip()
                if text_value and text_value not in LOCALIZATION_INVALID_VALUES:
                    translations[lang_code] = text_value
            
            if not translations:
                if description is not None:
                    execute_query(conn, """
                        UPDATE localization
                        SET description = %s, updated_at = %s
                        WHERE key = %s
                    """, (description, now, reference_key))
            else:
                for lang_code, text_value in translations.items():
                    execute_query(conn, """
                        INSERT INTO localization (key, language, value, description, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (key, language) DO UPDATE SET
                            value = EXCLUDED.value,
                            description = COALESCE(EXCLUDED.description, localization.description),
                            updated_at = EXCLUDED.updated_at
                    """, (reference_key, lang_code, text_value, description, now, now))
        else:
            german = (payload.get('german') or '').strip() or None
            english = (payload.get('english') or '').strip() or None
            french = (payload.get('french') or '').strip() or None
            italian = (payload.get('italian') or '').strip() or None
            spanish = (payload.get('spanish') or '').strip() or None
            portuguese = (payload.get('portuguese') or '').strip() or None
            russian = (payload.get('russian') or '').strip() or None
            turkish = (payload.get('turkish') or '').strip() or None
            georgian = (payload.get('georgian') or '').strip() or None
            
            cur = conn.cursor()
            cur.execute(
                'UPDATE localization SET description=COALESCE(?, description), german=COALESCE(?, german), english=COALESCE(?, english), french=COALESCE(?, french), italian=COALESCE(?, italian), spanish=COALESCE(?, spanish), portuguese=COALESCE(?, portuguese), russian=COALESCE(?, russian), turkish=COALESCE(?, turkish), georgian=COALESCE(?, georgian), updated_at=? WHERE reference_key=?',
                (description, german, english, french, italian, spanish, portuguese, russian, turkish, georgian, now, reference_key)
            )
            if cur.rowcount == 0:
                cur.execute(
                    'INSERT INTO localization (reference_key, description, german, english, french, italian, spanish, portuguese, russian, turkish, georgian, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (reference_key, description, german, english, french, italian, spanish, portuguese, russian, turkish, georgian, now, now)
                )
        if managed_connection:
            conn.commit()
    finally:
        if managed_connection:
            conn.close()

def get_all_localization_entries():
    """Get all localization entries"""
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            rows = _pg_fetch_localization_rows(conn)
            aggregated = _pg_aggregate_localization_rows(rows)
            entries = list(aggregated.values())
            entries.sort(key=lambda e: e.get('reference_key', ''))
            return entries
        else:
            # SQLite
            rows = conn.execute('SELECT * FROM localization ORDER BY reference_key').fetchall()
            return rows
    finally:
        conn.close()

def get_localization_for_language(language_code: str):
    """Get all localization entries for a specific language as key -> text map."""
    config = get_database_config()
    lang_code = normalize_language_identifier(language_code)
    if not lang_code:
        return {}

    translations: Dict[str, str] = {}

    if config['type'] == 'postgresql':
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT key, value FROM localization WHERE language = %s ORDER BY key',
                (lang_code,)
            )
            rows = cur.fetchall()
            for row in rows:
                if isinstance(row, dict):
                    key = row.get('key')
                    value = row.get('value')
                else:
                    key, value = row
                if not key or value is None:
                    continue
                text_value = str(value).strip()
                if text_value in LOCALIZATION_INVALID_VALUES:
                    continue
                translations[key] = text_value
            return translations
        finally:
            conn.close()

    # SQLite: wide table (reference_key + language columns)
    sqlite_columns = {
        'de': 'german', 'en': 'english', 'fr': 'french', 'it': 'italian',
        'es': 'spanish', 'pt': 'portuguese', 'ru': 'russian', 'tr': 'turkish', 'ka': 'georgian',
    }
    column = sqlite_columns.get(lang_code) or language_code_to_field(lang_code)
    if column not in sqlite_columns.values():
        column = 'english'

    conn = get_db()
    try:
        rows = conn.execute(
            f'''
            SELECT reference_key, {column} AS value
            FROM localization
            WHERE {column} IS NOT NULL AND TRIM({column}) != ''
            ORDER BY reference_key
            '''
        ).fetchall()
        for row in rows:
            row_dict = dict(row) if not isinstance(row, dict) else row
            key = row_dict.get('reference_key')
            value = row_dict.get('value')
            if not key or value is None:
                continue
            text_value = str(value).strip()
            if text_value in LOCALIZATION_INVALID_VALUES:
                continue
            translations[key] = text_value
        return translations
    finally:
        conn.close()

def get_missing_translations(language_code: str):
    """Get localization entries that are missing translations for a specific language"""
    config = get_database_config()
    lang_code = normalize_language_identifier(language_code)
    if not lang_code:
        return []
    
    if config['type'] == 'postgresql':
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                WITH keys AS (
                    SELECT DISTINCT key, MAX(description) AS description
                    FROM localization
                    GROUP BY key
                )
                SELECT k.key AS reference_key,
                       k.description,
                       t.value AS translation
                FROM keys k
                LEFT JOIN localization t
                  ON t.key = k.key AND t.language = %s
                WHERE t.key IS NULL OR COALESCE(t.value, '') = ''
                ORDER BY k.key
            """, (lang_code,))
            rows = cur.fetchall()
            results = []
            for row in rows:
                if isinstance(row, dict):
                    reference_key = row.get('reference_key') or row.get('key')
                    description = row.get('description')
                    translation = row.get('translation')
                else:
                    reference_key, description, translation = row
                results.append({
                    'reference_key': reference_key,
                    'description': description,
                    'translation': translation
                })
            return results
        finally:
            conn.close()
    else:
        conn = get_db()
        try:
            # Map language codes to column names
            lang_columns = {
                'de': 'german',
                'en': 'english',
                'fr': 'french',
                'it': 'italian',
                'es': 'spanish',
                'pt': 'portuguese',
                'ru': 'russian',
                'tr': 'turkish',
                'ka': 'georgian'
            }
            
            column = lang_columns.get(lang_code, 'english')
            query = f'SELECT reference_key, description, {column} as translation FROM localization WHERE {column} IS NULL OR {column} = "" ORDER BY reference_key'
            rows = conn.execute(query).fetchall()
            return rows
        finally:
            conn.close()

# --- User Management Functions ---

def create_user(username: str, email: str, password_hash: str) -> int:
    """Create a new user and return user ID"""
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        now = datetime.now(UTC).isoformat()
        
        if config['type'] == 'postgresql':
            # PostgreSQL doesn't have updated_at column in users table
            cursor = conn.execute(
                'INSERT INTO users (username, email, password_hash, created_at) VALUES (%s,%s,%s,%s) RETURNING id',
                (username, email, password_hash, now)
            )
            result = cursor.fetchone()
            # Handle both tuple and dict-like results (RealDictCursor)
            if result:
                if hasattr(result, 'keys'):  # RealDictCursor returns dict-like object
                    user_id = result['id']
                else:  # Regular cursor returns tuple
                    user_id = result[0]
            else:
                user_id = None
        else:
            # SQLite has updated_at column
            cursor = conn.execute(
                'INSERT INTO users (username, email, password_hash, created_at, updated_at) VALUES (?,?,?,?,?)',
                (username, email, password_hash, now, now)
            )
            user_id = cursor.lastrowid
            
        conn.commit()
        return int(user_id)
    finally:
        conn.close()

def get_user_by_username(username: str):
    """Get user by username"""
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL doesn't have updated_at column in users table
            cursor = conn.execute(
                'SELECT id, username, email, password_hash, created_at, last_login, is_active, settings FROM users WHERE username=%s AND is_active=TRUE',
                (username,)
            )
            row = cursor.fetchone()
            return _coerce_row_to_dict(row, getattr(cursor, 'description', None))
        else:
            # SQLite has updated_at column
            row = conn.execute(
                'SELECT id, username, email, password_hash, created_at, updated_at, last_login, is_active, settings FROM users WHERE username=? AND is_active=1',
                (username,)
            ).fetchone()
            return row
    finally:
        conn.close()

def get_user_by_email(email: str):
    """Get user by email"""
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL doesn't have updated_at column in users table
            cursor = conn.execute(
                'SELECT id, username, email, password_hash, created_at, last_login, is_active, settings FROM users WHERE email=%s AND is_active=TRUE',
                (email,)
            )
            row = cursor.fetchone()
            return _coerce_row_to_dict(row, getattr(cursor, 'description', None))
        else:
            # SQLite has updated_at column
            row = conn.execute(
                'SELECT id, username, email, password_hash, created_at, updated_at, last_login, is_active, settings FROM users WHERE email=? AND is_active=1',
                (email,)
            ).fetchone()
            return row
    finally:
        conn.close()

def get_user_by_id(user_id: int):
    """Get user by ID"""
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL doesn't have updated_at column in users table
            cur = conn.cursor()
            cur.execute(
                'SELECT id, username, email, password_hash, created_at, last_login, is_active, settings FROM users WHERE id=%s AND is_active=TRUE',
                (user_id,)
            )
            description = getattr(cur, 'description', None)
            row = cur.fetchone()
            cur.close()
            
            return _coerce_row_to_dict(row, description)
        else:
            # SQLite has updated_at column
            row = conn.execute(
                'SELECT id, username, email, password_hash, created_at, updated_at, last_login, is_active, settings FROM users WHERE id=? AND is_active=1',
                (user_id,)
            ).fetchone()
            return row
    finally:
        conn.close()

def update_user_last_login(user_id: int):
    """Update user's last login timestamp"""
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db(); cur = conn.cursor()
    
    try:
        now = datetime.now(UTC).isoformat()
        
        if config['type'] == 'postgresql':
            # PostgreSQL doesn't have updated_at column in users table
            cur.execute(
                'UPDATE users SET last_login=%s WHERE id=%s',
                (now, user_id)
            )
        else:
            # SQLite has updated_at column
            cur.execute(
                'UPDATE users SET last_login=?, updated_at=? WHERE id=?',
                (now, now, user_id)
            )
            
        conn.commit()
    finally:
        conn.close()

def create_user_session(user_id: int, session_token: str, expires_at: str) -> int:
    """Create a new user session"""
    from server.db_config import get_database_config, get_db_connection
    
    config = get_database_config()
    
    try:
        now = datetime.now(UTC).isoformat()
        
        if config['type'] == 'postgresql':
            # Use direct PostgreSQL connection for better control
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # First, let's check if the table exists and has the right structure
                cursor.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'user_sessions' 
                    ORDER BY ordinal_position
                """)
                columns = cursor.fetchall()
                print(f"DEBUG: user_sessions table columns: {columns}")
                
                cursor.execute(
                    'INSERT INTO user_sessions (user_id, session_token, expires_at, created_at) VALUES (%s,%s,%s,%s) RETURNING id',
                    (user_id, session_token, expires_at, now)
                )
                result = cursor.fetchone()
                print(f"DEBUG: PostgreSQL session creation - raw result: {result}")
                print(f"DEBUG: PostgreSQL session creation - result type: {type(result)}")
                
                if result is None:
                    print("ERROR: PostgreSQL session creation - result is None!")
                    raise Exception("INSERT statement returned no result")
                
                # Handle both tuple and dict-like results (RealDictCursor)
                if hasattr(result, 'keys'):  # RealDictCursor returns dict-like object
                    session_id = result['id']
                    print(f"DEBUG: PostgreSQL session creation - session_id from dict: {session_id}, type: {type(session_id)}")
                else:  # Regular cursor returns tuple
                    if len(result) == 0:
                        print("ERROR: PostgreSQL session creation - result is empty!")
                        raise Exception("INSERT statement returned empty result")
                    session_id = result[0]
                    print(f"DEBUG: PostgreSQL session creation - session_id from tuple: {session_id}, type: {type(session_id)}")
                
                if session_id is None:
                    print("ERROR: PostgreSQL session creation - session_id is None!")
                    raise Exception("INSERT statement returned None for id")
                
                # Commit the transaction
                conn.commit()
                print(f"DEBUG: PostgreSQL commit successful")
                
            except Exception as e:
                print(f"DEBUG: PostgreSQL session creation error: {str(e)}")
                conn.rollback()
                raise e
            finally:
                cursor.close()
                conn.close()
        else:
            # Use ConnectionWrapper for SQLite
            conn = get_db()
            cursor = conn.execute(
                'INSERT INTO user_sessions (user_id, session_token, expires_at, created_at) VALUES (?,?,?,?)',
                (user_id, session_token, expires_at, now)
            )
            session_id = cursor.lastrowid
            print(f"DEBUG: SQLite session creation - session_id: {session_id}")
            conn.commit()
            conn.close()
            
        return int(session_id) if session_id else 0
    except Exception as e:
        print(f"DEBUG: create_user_session error: {str(e)}")
        return 0

def get_user_by_session(session_token: str):
    """Get user by session token"""
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL doesn't have updated_at column in users table
            cur = conn.cursor()
            cur.execute('''
                SELECT u.id, u.username, u.email, u.password_hash, u.created_at, u.last_login, u.is_active, u.settings
                FROM users u
                JOIN user_sessions s ON u.id = s.user_id
                WHERE s.session_token = %s AND s.expires_at > NOW() AND u.is_active = TRUE
            ''', (session_token,))
            description = getattr(cur, 'description', None)
            row = cur.fetchone()
            cur.close()
            
            return _coerce_row_to_dict(row, description)
        else:
            # SQLite has updated_at column
            row = conn.execute('''
                SELECT u.id, u.username, u.email, u.password_hash, u.created_at, u.updated_at, u.last_login, u.is_active, u.settings
                FROM users u
                JOIN user_sessions s ON u.id = s.user_id
                WHERE s.session_token = ? AND s.expires_at > datetime('now') AND u.is_active = 1
            ''', (session_token,)).fetchone()
            return row
    finally:
        conn.close()

def delete_user_session(session_token: str):
    """Delete a user session"""
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute('DELETE FROM user_sessions WHERE session_token=?', (session_token,))
        conn.commit()
    finally:
        conn.close()

def cleanup_expired_sessions():
    """Clean up expired sessions"""
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            cursor = conn.execute('DELETE FROM user_sessions WHERE expires_at <= NOW()')
        else:
            cursor = conn.execute('DELETE FROM user_sessions WHERE expires_at <= datetime("now")')
            
        conn.commit()
    finally:
        conn.close()

# --- User Progress Functions ---

def get_user_progress(user_id: int, language: str = None, native_language: str = None):
    """Get user progress for all languages or specific language and native language"""
    conn = get_db()
    try:
        if language and native_language:
            rows = conn.execute(
                'SELECT language, native_language, level, status, score, completed_at, created_at, updated_at FROM user_progress WHERE user_id=? AND language=? AND native_language=? ORDER BY level',
                (user_id, language, native_language)
            ).fetchall()
        elif language:
            rows = conn.execute(
                'SELECT language, native_language, level, status, score, completed_at, created_at, updated_at FROM user_progress WHERE user_id=? AND language=? ORDER BY native_language, level',
                (user_id, language)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT language, native_language, level, status, score, completed_at, created_at, updated_at FROM user_progress WHERE user_id=? ORDER BY language, native_language, level',
                (user_id,)
            ).fetchall()
        # Convert Row objects to dictionaries for JSON serialization
        return [dict(row) for row in rows]
    finally:
        conn.close()

def update_user_progress(user_id: int, language: str, level: int, status: str, score: float = None, native_language: str = None):
    """Update or create user progress for a level"""
    conn = get_db(); cur = conn.cursor()
    try:
        now = datetime.now(UTC).isoformat()
        completed_at = now if status == 'completed' else None
        
        # Get native language from user settings if not provided
        if not native_language:
            from server.db_multi_user import get_user_native_language
            native_language = get_user_native_language(user_id)
        
        cur.execute('''
            INSERT OR REPLACE INTO user_progress 
            (user_id, language, native_language, level, status, score, completed_at, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (user_id, language, native_language, level, status, score, completed_at, now, now))
        
        conn.commit()
    finally:
        conn.close()

def get_user_word_familiarity(user_id: int, word_id: int):
    """Get user's familiarity with a specific word"""
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT familiarity, seen_count, correct_count, user_comment FROM user_word_familiarity WHERE user_id=? AND word_id=?',
            (user_id, word_id)
        ).fetchone()
        return row
    finally:
        conn.close()

def update_user_word_familiarity(user_id: int, word_id: int, familiarity: int, seen_count: int = None, correct_count: int = None, user_comment: str = None):
    """Update user's familiarity with a word"""
    from server.db_config import get_database_config, get_db_connection, execute_query
    
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        now = datetime.now(UTC).isoformat()
        
        # Set default values
        seen_count = seen_count or 0
        correct_count = correct_count or 0
        user_comment = user_comment or ''
        
        if config['type'] == 'postgresql':
            # PostgreSQL syntax - use INSERT ... ON CONFLICT
            execute_query(conn, '''
                INSERT INTO user_word_familiarity 
                (user_id, word_id, familiarity, seen_count, correct_count, user_comment, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, word_id) 
                DO UPDATE SET
                    familiarity = EXCLUDED.familiarity,
                    seen_count = EXCLUDED.seen_count,
                    correct_count = EXCLUDED.correct_count,
                    user_comment = EXCLUDED.user_comment,
                    updated_at = EXCLUDED.updated_at
            ''', (user_id, word_id, familiarity, seen_count, correct_count, user_comment, now, now))
        else:
            # SQLite syntax
            cur = conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO user_word_familiarity 
                (user_id, word_id, familiarity, seen_count, correct_count, user_comment, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
            ''', (user_id, word_id, familiarity, seen_count, correct_count, user_comment, now, now))
        
        conn.commit()
    finally:
        conn.close()

def get_user_word_familiarity_by_word(user_id: int, word: str, language: str, native_language: str):
    """Get user's familiarity with a word by word text, language, and native language"""
    from server.db_config import get_database_config, get_db_connection, execute_query
    
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            print(f"🔍 Querying familiarity: user_id={user_id}, word='{word}', language='{language}', native_language='{native_language}'")
            result = execute_query(conn, '''
                SELECT uwf.familiarity, uwf.seen_count, uwf.correct_count, uwf.user_comment
                FROM user_word_familiarity uwf
                JOIN words w ON uwf.word_id = w.id
                WHERE uwf.user_id = %s AND w.word = %s AND w.language = %s AND w.native_language = %s
            ''', (user_id, word, language, native_language))
            description = getattr(result, 'description', None)
            row = _coerce_row_to_dict(result.fetchone(), description)
            print(f"🔍 Query result: {row}")
        else:
            # SQLite syntax
            cur = conn.cursor()
            row = cur.execute('''
                SELECT uwf.familiarity, uwf.seen_count, uwf.correct_count, uwf.user_comment
                FROM user_word_familiarity uwf
                JOIN words w ON uwf.word_id = w.id
                WHERE uwf.user_id = ? AND w.word = ? AND w.language = ? AND w.native_language = ?
            ''', (user_id, word, language, native_language)).fetchone()
            row = _coerce_row_to_dict(row, getattr(cur, 'description', None))
        
        return row
    finally:
        conn.close()

def ensure_words_exist_by_ids(word_ids: list[int]) -> bool:
    """Prüft nur, ob die word_ids noch existieren (Referenz-Integrität)
    Optimiert für Performance: Keine Wort-Extraktion nötig, nur ID-Check
    """
    if not word_ids:
        return True
    
    from server.db_config import get_database_config, get_db_connection, execute_query
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            placeholders = ','.join(['%s'] * len(word_ids))
            result = execute_query(conn, f"""
                SELECT id FROM words 
                WHERE id IN ({placeholders})
            """, word_ids)
            
            existing_ids = {row['id'] if isinstance(row, dict) else row[0] for row in result.fetchall()}
            missing_ids = set(word_ids) - existing_ids
            
            if missing_ids:
                print(f"⚠️ Warning: {len(missing_ids)} word_ids are missing from words table: {list(missing_ids)[:10]}")
                return False
            return True
        else:
            # SQLite
            placeholders = ','.join(['?'] * len(word_ids))
            cursor = conn.cursor()
            cursor.execute(f'SELECT id FROM words WHERE id IN ({placeholders})', word_ids)
            existing_ids = {row[0] for row in cursor.fetchall()}
            missing_ids = set(word_ids) - existing_ids
            
            if missing_ids:
                print(f"⚠️ Warning: {len(missing_ids)} word_ids are missing from words table: {list(missing_ids)[:10]}")
                return False
            return True
    except Exception as e:
        print(f"❌ Error checking word_ids: {e}")
        return False
    finally:
        conn.close()

def batch_ensure_user_word_familiarity_by_ids(
    user_id: int, 
    word_ids: list[int], 
    default_familiarity: int = 0
):
    """Batch ensure words exist in user's familiarity database using word_ids directly.
    Optimiert für Performance: Keine Wort-Extraktion oder -Normalisierung nötig.
    """
    if not word_ids or not user_id:
        return
    
    from server.db_config import get_database_config, get_db_connection, execute_query
    from datetime import datetime, UTC
    
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        now = datetime.now(UTC).isoformat()
        
        if config['type'] == 'postgresql':
            # Prüfe, welche Einträge bereits existieren
            placeholders = ','.join(['%s'] * len(word_ids))
            existing_result = execute_query(conn, f'''
                SELECT word_id FROM user_word_familiarity 
                WHERE user_id = %s AND word_id IN ({placeholders})
            ''', [user_id] + word_ids)
            
            existing_word_ids = {row['word_id'] if isinstance(row, dict) else row[0] for row in existing_result.fetchall()}
            
            # Insert nur neue Einträge
            new_word_ids = [wid for wid in word_ids if wid not in existing_word_ids]
            
            if new_word_ids:
                # Batch insert
                insert_values = ','.join([f'(%s, %s, %s, %s, %s, %s)' for _ in new_word_ids])
                insert_params = []
                for word_id in new_word_ids:
                    insert_params.extend([user_id, word_id, default_familiarity, 0, 0, ''])
                
                execute_query(conn, f'''
                    INSERT INTO user_word_familiarity 
                    (user_id, word_id, familiarity, seen_count, correct_count, user_comment)
                    VALUES {insert_values}
                    ON CONFLICT (user_id, word_id) DO NOTHING
                ''', insert_params)
                conn.commit()
                print(f"✅ Batch inserted {len(new_word_ids)} familiarity records by IDs")
        else:
            # SQLite batch insert
            cursor = conn.cursor()
            placeholders = ','.join(['?'] * len(word_ids))
            existing = cursor.execute(f'''
                SELECT word_id FROM user_word_familiarity 
                WHERE user_id = ? AND word_id IN ({placeholders})
            ''', [user_id] + word_ids).fetchall()
            
            existing_word_ids = {row[0] for row in existing}
            new_word_ids = [wid for wid in word_ids if wid not in existing_word_ids]
            
            if new_word_ids:
                cursor.executemany('''
                    INSERT OR IGNORE INTO user_word_familiarity 
                    (user_id, word_id, familiarity, seen_count, correct_count, user_comment)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', [(user_id, wid, default_familiarity, 0, 0, '') for wid in new_word_ids])
                conn.commit()
                print(f"✅ Batch inserted {len(new_word_ids)} familiarity records by IDs (SQLite)")
    except Exception as e:
        print(f"❌ Error in batch_ensure_user_word_familiarity_by_ids: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def batch_ensure_user_word_familiarity(user_id: int, words: list[str], language: str, native_language: str, default_familiarity: int = 0):
    """Batch ensure words exist in user's familiarity database with default familiarity.
    This is much faster than calling update_user_word_familiarity_by_word for each word individually.
    """
    if not words or not user_id:
        return
    
    from server.db_config import get_database_config, get_db_connection, execute_query
    import re
    
    # Normalize words (remove trailing punctuation)
    normalized_words = [re.sub(r'[.!?,;:—–-]+$', '', (w or '').strip().lower()) for w in words if w and w.strip()]
    if not normalized_words:
        return
    
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            # Get all word IDs in one query - use a simpler approach with multiple OR conditions
            # This is still much faster than individual queries
            conditions = []
            params = []
            for word in normalized_words:
                conditions.append('(LOWER(word) = LOWER(%s) AND language = %s AND native_language = %s)')
                params.extend([word, language, native_language])
            
            word_ids_query = f'''
                SELECT id, LOWER(word) as word_lower
                FROM words 
                WHERE {' OR '.join(conditions)}
            '''
            
            result = execute_query(conn, word_ids_query, params)
            word_map = {}
            for row in result.fetchall():
                row_dict = _coerce_row_to_dict(row, getattr(result, 'description', None))
                if row_dict:
                    word_map[row_dict.get('word_lower', '').lower()] = row_dict['id']
            
            if not word_map:
                print(f"⚠️ No words found in database for batch familiarity update")
                return
            
            # Get existing familiarity records
            word_ids = list(word_map.values())
            placeholders = ','.join(['%s'] * len(word_ids))
            existing_query = f'''
                SELECT word_id FROM user_word_familiarity 
                WHERE user_id = %s AND word_id IN ({placeholders})
            '''
            existing_result = execute_query(conn, existing_query, [user_id] + word_ids)
            existing_word_ids = {row['word_id'] if isinstance(row, dict) else row[0] for row in existing_result.fetchall()}
            
            # Insert only new records
            new_word_ids = [wid for wid in word_map.values() if wid not in existing_word_ids]
            if new_word_ids:
                insert_values = ','.join([f'(%s, %s, %s, %s, %s, %s)' for _ in new_word_ids])
                insert_params = []
                for word_id in new_word_ids:
                    insert_params.extend([user_id, word_id, default_familiarity, 0, 0, ''])
                
                insert_query = f'''
                    INSERT INTO user_word_familiarity (user_id, word_id, familiarity, seen_count, correct_count, user_comment)
                    VALUES {insert_values}
                    ON CONFLICT (user_id, word_id) DO NOTHING
                '''
                execute_query(conn, insert_query, insert_params)
                conn.commit()
                print(f"✅ Batch inserted {len(new_word_ids)} familiarity records")
        else:
            # SQLite batch insert
            cur = conn.cursor()
            # Get word IDs
            placeholders = ','.join(['?'] * len(normalized_words))
            word_ids_query = f'''
                SELECT id, word FROM words 
                WHERE word IN ({placeholders}) AND language = ? AND native_language = ?
            '''
            result = cur.execute(word_ids_query, normalized_words + [language, native_language])
            word_map = {}
            for row in result.fetchall():
                row_dict = _coerce_row_to_dict(row, getattr(cur, 'description', None))
                if row_dict:
                    word_map[row_dict['word'].lower()] = row_dict['id']
            
            if not word_map:
                print(f"⚠️ No words found in database for batch familiarity update")
                return
            
            # Get existing records
            word_ids = list(word_map.values())
            placeholders = ','.join(['?'] * len(word_ids))
            existing_result = cur.execute(f'''
                SELECT word_id FROM user_word_familiarity 
                WHERE user_id = ? AND word_id IN ({placeholders})
            ''', [user_id] + word_ids)
            existing_word_ids = {row[0] if isinstance(row, (list, tuple)) else row['word_id'] for row in existing_result.fetchall()}
            
            # Insert new records
            new_word_ids = [wid for wid in word_map.values() if wid not in existing_word_ids]
            if new_word_ids:
                for word_id in new_word_ids:
                    cur.execute('''
                        INSERT OR IGNORE INTO user_word_familiarity 
                        (user_id, word_id, familiarity, seen_count, correct_count, user_comment)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, word_id, default_familiarity, 0, 0, ''))
                conn.commit()
                print(f"✅ Batch inserted {len(new_word_ids)} familiarity records")
    except Exception as e:
        print(f"❌ Error in batch familiarity update: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

def update_user_word_familiarity_by_word(user_id: int, word: str, language: str, native_language: str, familiarity: int, user_comment: str = None):
    """Update user's familiarity with a word by word text, language, and native language"""
    from server.db_config import get_database_config, get_db_connection, execute_query
    
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        # First, get the word_id
        if config['type'] == 'postgresql':
            result = execute_query(conn, '''
                SELECT id FROM words WHERE word = %s AND language = %s AND native_language = %s
            ''', (word, language, native_language))
            word_row = _coerce_row_to_dict(result.fetchone(), getattr(result, 'description', None))
        else:
            cur = conn.cursor()
            word_row = _coerce_row_to_dict(
                cur.execute('SELECT id FROM words WHERE word = ? AND language = ? AND native_language = ?', (word, language, native_language)).fetchone(),
                getattr(cur, 'description', None)
            )
        
        if not word_row:
            print(f"❌ Word not found: {word} ({language} -> {native_language})")
            return False
        else:
            print(f"✅ Word found: {word} ({language} -> {native_language}) with ID: {word_row.get('id')}")
        
        word_id = word_row.get('id')
        
        # Get current values by querying the database directly
        if config['type'] == 'postgresql':
            result = execute_query(conn, '''
                SELECT seen_count, correct_count, user_comment
                FROM user_word_familiarity
                WHERE user_id = %s AND word_id = %s
            ''', (user_id, word_id))
            current_row = _coerce_row_to_dict(result.fetchone(), getattr(result, 'description', None))
        else:
            cur = conn.cursor()
            current_row = _coerce_row_to_dict(cur.execute('''
                SELECT seen_count, correct_count, user_comment
                FROM user_word_familiarity
                WHERE user_id = ? AND word_id = ?
            ''', (user_id, word_id)).fetchone(), getattr(cur, 'description', None))
        
        seen_count = current_row.get('seen_count', 0) if current_row else 0
        correct_count = current_row.get('correct_count', 0) if current_row else 0
        current_user_comment = current_row.get('user_comment', '') if current_row else ''
        
        # Use provided user_comment or keep existing one
        final_user_comment = user_comment if user_comment is not None else current_user_comment
        
        # Update familiarity
        print(f"🔧 Updating familiarity: user_id={user_id}, word_id={word_id}, familiarity={familiarity}, seen_count={seen_count}, correct_count={correct_count}, user_comment='{final_user_comment}'")
        update_user_word_familiarity(user_id, word_id, familiarity, seen_count, correct_count, final_user_comment)
        print(f"✅ Familiarity update completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error updating familiarity: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def get_user_familiarity_counts(user_id: int, language: str = None):
    """Get familiarity counts for a user"""
    conn = get_db()
    try:
        if language:
            query = '''
                SELECT uwf.familiarity, COUNT(*) as count
                FROM user_word_familiarity uwf
                JOIN words w ON uwf.word_id = w.id
                WHERE uwf.user_id = ? AND (w.language = ? OR ? = "")
                GROUP BY uwf.familiarity
            '''
            rows = conn.execute(query, (user_id, language, language)).fetchall()
        else:
            query = '''
                SELECT familiarity, COUNT(*) as count
                FROM user_word_familiarity
                WHERE user_id = ?
                GROUP BY familiarity
            '''
            rows = conn.execute(query, (user_id,)).fetchall()
        
        # Convert to dict with all familiarity levels 0-5
        counts = {str(i): 0 for i in range(6)}
        for row in rows:
            fam = int(row['familiarity']) if row['familiarity'] is not None else 0
            fam = max(0, min(5, fam))
            counts[str(fam)] = int(row['count'])
        
        return counts
    finally:
        conn.close()
