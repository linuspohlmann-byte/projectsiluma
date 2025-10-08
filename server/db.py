
# --- Level run helpers ---
import os, sqlite3, json
import re
from datetime import datetime, UTC
from .db_config import get_db_connection, execute_query, get_database_config, PSYCOPG2_AVAILABLE

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
    if not words:
        return
    config = get_database_config()
    conn = get_db_connection()
    try:
        now = datetime.now(UTC).isoformat()
        for w in words:
            # Normalize word: trim and remove trailing punctuation/symbols
            if isinstance(w, str):
                w = re.sub(r'[.!?,;:—–-]+$', '', w.strip())
            else:
                continue
            if not w:
                continue
            if config['type'] == 'postgresql':
                # PostgreSQL syntax
                result = execute_query(conn, 'SELECT 1 FROM words WHERE word=%s AND (language=%s OR %s=\'\')', (w, target_lang, target_lang))
                if not result.fetchone():
                    execute_query(conn, '''
                        INSERT INTO words (word, language, native_language, created_at, updated_at) 
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (w, target_lang, native_lang, now, now))
            else:
                # SQLite syntax
                cur = conn.cursor()
                cur.execute('SELECT 1 FROM words WHERE word=? AND (language=? OR ?="")', (w, target_lang, target_lang))
                if not cur.fetchone():
                    cur.execute(
                        'INSERT INTO words (word, language, native_language, created_at, updated_at) VALUES (?,?,?,?,?)',
                        (w, target_lang, native_lang, now, now)
                    )
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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                    UNIQUE(group_id, level_number)
                )
            ''')
            conn.commit()
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
    
    def cursor(self, cursor_factory=None):
        """Get cursor with optional cursor_factory for PostgreSQL"""
        if self.config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
            if cursor_factory:
                return self.conn.cursor(cursor_factory=cursor_factory)
            else:
                return self.conn.cursor()
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
    config = get_database_config()
    conn = get_db()
    
    if config['type'] == 'postgresql':
        # PostgreSQL table creation
        
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
        
        # Add missing columns to existing level_runs table if they don't exist
        try:
            execute_query(conn, "ALTER TABLE level_runs ADD COLUMN IF NOT EXISTS target_lang VARCHAR(10)")
            execute_query(conn, "ALTER TABLE level_runs ADD COLUMN IF NOT EXISTS native_lang VARCHAR(10)")
            conn.commit()
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
        
        # Localization table
        execute_query(conn, """
            CREATE TABLE IF NOT EXISTS localization (
                id SERIAL PRIMARY KEY,
                reference_key VARCHAR(255) UNIQUE NOT NULL,
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Add missing language columns to existing localization table if they don't exist
        language_columns = ['german', 'english', 'french', 'italian', 'spanish', 'portuguese', 'russian', 'turkish', 'georgian']
        for column in language_columns:
            try:
                execute_query(conn, f"ALTER TABLE localization ADD COLUMN IF NOT EXISTS {column} TEXT;")
            except Exception as e:
                # Column might already exist, ignore the error
                print(f"Note: Column {column} might already exist: {e}")
                pass
        
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                UNIQUE(group_id, level_number)
            );
        """)
        
    else:
        # SQLite table creation (legacy)
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


def upsert_word_row(payload: dict) -> None:
    word = (payload.get('word') or '').strip()
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

def get_localization_entry(reference_key: str, language: str = None):
    """Get a localization entry by reference key and optionally language"""
    from server.db_config import get_database_config
    
    config = get_database_config()
    conn = get_db()
    
    try:
        if config['type'] == 'postgresql':
            cur = conn.cursor()
            cur.execute(
                'SELECT * FROM localization WHERE reference_key = %s',
                (reference_key,)
            )
            row = cur.fetchone()
            cur.close()
            
            if row:
                # Convert row to dict
                columns = [desc[0] for desc in cur.description] if hasattr(cur, 'description') else []
                row_dict = dict(zip(columns, row)) if columns else {}
                
                if language:
                    # Return only the requested language
                    lang_column = language.lower()
                    if lang_column in row_dict:
                        return {lang_column: row_dict[lang_column]}
                    else:
                        return {}
                else:
                    # Return all translations
                    return row_dict
            return {}
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

def upsert_localization_entry(payload: dict) -> None:
    """Insert or update a localization entry"""
    reference_key = (payload.get('reference_key') or '').strip()
    description = (payload.get('description') or '').strip()
    german = (payload.get('german') or '').strip()
    english = (payload.get('english') or '').strip()
    french = (payload.get('french') or '').strip()
    italian = (payload.get('italian') or '').strip()
    spanish = (payload.get('spanish') or '').strip()
    portuguese = (payload.get('portuguese') or '').strip()
    russian = (payload.get('russian') or '').strip()
    turkish = (payload.get('turkish') or '').strip()
    georgian = (payload.get('georgian') or '').strip()
    
    now = datetime.now(UTC).isoformat()
    
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            result = execute_query(conn, '''
                UPDATE localization SET 
                    description=COALESCE(%s, description), 
                    german=COALESCE(%s, german), 
                    english=COALESCE(%s, english), 
                    french=COALESCE(%s, french), 
                    italian=COALESCE(%s, italian), 
                    spanish=COALESCE(%s, spanish), 
                    portuguese=COALESCE(%s, portuguese), 
                    russian=COALESCE(%s, russian), 
                    turkish=COALESCE(%s, turkish), 
                    georgian=COALESCE(%s, georgian), 
                    updated_at=%s 
                WHERE reference_key=%s
            ''', (description or None, german or None, english or None, french or None, italian or None, spanish or None, portuguese or None, russian or None, turkish or None, georgian or None, now, reference_key))
            
            if result.rowcount == 0:
                execute_query(conn, '''
                    INSERT INTO localization (reference_key, description, german, english, french, italian, spanish, portuguese, russian, turkish, georgian, created_at, updated_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (reference_key, description or None, german or None, english or None, french or None, italian or None, spanish or None, portuguese or None, russian or None, turkish or None, georgian or None, now, now))
        else:
            # SQLite syntax
            cur = conn.cursor()
            cur.execute(
                'UPDATE localization SET description=COALESCE(?, description), german=COALESCE(?, german), english=COALESCE(?, english), french=COALESCE(?, french), italian=COALESCE(?, italian), spanish=COALESCE(?, spanish), portuguese=COALESCE(?, portuguese), russian=COALESCE(?, russian), turkish=COALESCE(?, turkish), georgian=COALESCE(?, georgian), updated_at=? WHERE reference_key=?',
                (description or None, german or None, english or None, french or None, italian or None, spanish or None, portuguese or None, russian or None, turkish or None, georgian or None, now, reference_key)
            )
            if cur.rowcount == 0:
                cur.execute(
                    'INSERT INTO localization (reference_key, description, german, english, french, italian, spanish, portuguese, russian, turkish, georgian, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (reference_key, description or None, german or None, english or None, french or None, italian or None, spanish or None, portuguese or None, russian or None, turkish or None, georgian or None, now, now)
                )
        conn.commit()
    finally:
        conn.close()

def get_all_localization_entries():
    """Get all localization entries"""
    import os
    config = get_database_config()
    conn = get_db_connection()
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL
            cur = conn.cursor()
            cur.execute('SELECT * FROM localization ORDER BY reference_key')
            rows = cur.fetchall()
            return rows
        else:
            # SQLite
            rows = conn.execute('SELECT * FROM localization ORDER BY reference_key').fetchall()
            return rows
    finally:
        conn.close()

def get_localization_for_language(language_code: str):
    """Get all localization entries for a specific language from database first, then CSV"""
    import os
    
    # Language code to database column mapping
    lang_mapping = {
        'en': 'english', 'de': 'german', 'fr': 'french', 'es': 'spanish', 'it': 'italian',
        'pt': 'portuguese', 'ru': 'russian', 'zh': 'chinese', 'ja': 'japanese', 'ko': 'korean',
        'ar': 'arabic', 'hi': 'hindi', 'tr': 'turkish', 'pl': 'polish', 'nl': 'dutch',
        'sv': 'swedish', 'da': 'danish', 'no': 'norwegian', 'fi': 'finnish', 'he': 'hebrew',
        'th': 'thai', 'my': 'burmese', 'km': 'khmer', 'lo': 'lao', 'ka': 'georgian',
        'hy': 'armenian', 'az': 'azerbaijani', 'kk': 'kazakh', 'ky': 'kyrgyz', 'uz': 'uzbek',
        'tg': 'tajik', 'mn': 'mongolian', 'bo': 'tibetan', 'ne': 'nepali', 'si': 'sinhala',
        'ml': 'malayalam', 'kn': 'kannada', 'pa': 'punjabi', 'or': 'oriya', 'as': 'assamese',
        'dv': 'dhivehi', 'ps': 'pashto', 'sd': 'sindhi', 'ks': 'kashmiri', 'cs': 'czech',
        'sk': 'slovak', 'sl': 'slovenian', 'hr': 'croatian', 'sr': 'serbian', 'bs': 'bosnian',
        'mk': 'macedonian', 'bg': 'bulgarian', 'sq': 'albanian', 'el': 'greek', 'mt': 'maltese',
        'cy': 'welsh', 'ga': 'irish', 'gd': 'scottish_gaelic', 'gv': 'manx', 'br': 'breton',
        'co': 'corsican', 'ca': 'catalan', 'gl': 'galician', 'eu': 'basque', 'is': 'icelandic',
        'fo': 'faroese', 'lb': 'luxembourgish', 'li': 'limburgish', 'fy': 'western_frisian',
        'af': 'afrikaans', 'et': 'estonian', 'lv': 'latvian', 'lt': 'lithuanian', 'ha': 'hausa',
        'yo': 'yoruba', 'ig': 'igbo', 'ff': 'fulfulde', 'am': 'amharic', 'om': 'oromo',
        'ti': 'tigrinya', 'so': 'somali', 'zu': 'zulu', 'xh': 'xhosa', 'st': 'sotho',
        'tn': 'tswana', 'ss': 'swati', 'nr': 'ndebele', 've': 'venda', 'ts': 'tsonga',
        'sn': 'shona', 'ny': 'chichewa', 'rw': 'kinyarwanda', 'rn': 'kirundi', 'lg': 'luganda',
        'mg': 'malagasy', 'wo': 'wolof', 'ms': 'malay', 'tl': 'filipino', 'jv': 'javanese',
        'su': 'sundanese', 'qu': 'quechua', 'gn': 'guarani', 'ay': 'aymara', 'sm': 'samoan',
        'to': 'tongan', 'ty': 'tahitian', 'mi': 'maori', 'fj': 'fijian', 'bi': 'bislama',
        'eo': 'esperanto', 'ia': 'interlingua', 'ie': 'interlingue', 'io': 'ido', 'vo': 'volapuk',
        'la': 'latin', 'cu': 'old_church_slavonic', 'pi': 'pali', 'sa': 'sanskrit', 'id': 'indonesian'
    }
    
    result = {}
    
    # Always use CSV file first for complete translations
    try:
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'localization_complete.csv')
        
        # Read CSV without pandas
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            raise Exception("CSV file is empty")
        
        # Parse header
        header_line = lines[0].strip().replace('\ufeff', '')
        headers = [col.strip() for col in header_line.split(',')]
        
        # Find target language column
        target_col = language_code.lower()
        if target_col not in headers:
            print(f"Language {target_col} not found in CSV headers: {headers[:10]}...")
            raise Exception(f"Language {target_col} not found in CSV")
        
        target_index = headers.index(target_col)
        # Handle BOM in KEY column
        key_index = 0
        for i, header in enumerate(headers):
            if 'KEY' in header.upper():
                key_index = i
                break
        
        # Parse data rows with better CSV parsing
        import csv
        from io import StringIO
        
        # Join lines and create CSV reader
        csv_content = ''.join(lines)
        csv_reader = csv.reader(StringIO(csv_content))
        
        # Skip header
        next(csv_reader)
        
        # Process all rows
        for row in csv_reader:
            if len(row) <= max(key_index, target_index):
                continue
                
            key = row[key_index].strip() if key_index < len(row) else ''
            translation = row[target_index].strip() if target_index < len(row) else ''
            
            if key and translation and translation not in ['___', '#VALUE!', '']:
                result[key] = translation
        
        print(f"Found {len(result)} translations in CSV for {language_code}")
        return result
    except Exception as e:
        print(f"Error reading CSV for language {language_code}: {e}")
    
    # Fallback to database if CSV fails
    try:
        conn = get_db()
        cur = conn.cursor()
        db_column = lang_mapping.get(language_code.lower(), language_code.lower())
        
        cur.execute(f'''
            SELECT reference_key, {db_column} 
            FROM localization 
            WHERE {db_column} IS NOT NULL 
            AND {db_column} != '' 
            AND {db_column} != '#VALUE!'
        ''')
        
        rows = cur.fetchall()
        for row in rows:
            key, translation = row
            if key and translation and str(translation).strip():
                result[key] = str(translation).strip()
        
        conn.close()
        
        # If we found translations in database, return them
        if result:
            print(f"Found {len(result)} translations in database for {language_code}")
            return result
            
    except Exception as e:
        print(f"Error reading from database for language {language_code}: {e}")
    
    return {}

def get_missing_translations(language_code: str):
    """Get localization entries that are missing translations for a specific language"""
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
        
        column = lang_columns.get(language_code.lower(), 'english')
        
        # Use database-agnostic query for empty string check
        config = get_database_config()
        if config['type'] == 'postgresql':
            # PostgreSQL: use COALESCE to handle NULL and empty string
            query = f'SELECT reference_key, description, {column} as translation FROM localization WHERE COALESCE({column}, \'\') = \'\' ORDER BY reference_key'
        else:
            # SQLite: use original syntax
            query = f'SELECT reference_key, description, {column} as translation FROM localization WHERE {column} IS NULL OR {column} = "" ORDER BY reference_key'
        
        rows = conn.execute(query, None).fetchall()
        
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
            # Convert PostgreSQL row to dict-like object for compatibility
            if row:
                return dict(row)
            return None
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
            # Convert PostgreSQL row to dict-like object for compatibility
            if row:
                return dict(row)
            return None
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
            row = cur.fetchone()
            cur.close()
            
            return row
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
            row = cur.fetchone()
            cur.close()
            
            return row
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
            row = result.fetchone()
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
        
        return row
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
            word_row = result.fetchone()
        else:
            cur = conn.cursor()
            word_row = cur.execute('SELECT id FROM words WHERE word = ? AND language = ? AND native_language = ?', (word, language, native_language)).fetchone()
        
        if not word_row:
            print(f"❌ Word not found: {word} ({language} -> {native_language})")
            return False
        else:
            print(f"✅ Word found: {word} ({language} -> {native_language}) with ID: {word_row['id'] if config['type'] == 'postgresql' else word_row[0]}")
        
        word_id = word_row['id'] if config['type'] == 'postgresql' else word_row[0]
        
        # Get current values by querying the database directly
        if config['type'] == 'postgresql':
            result = execute_query(conn, '''
                SELECT seen_count, correct_count, user_comment
                FROM user_word_familiarity
                WHERE user_id = %s AND word_id = %s
            ''', (user_id, word_id))
            current_row = result.fetchone()
        else:
            cur = conn.cursor()
            current_row = cur.execute('''
                SELECT seen_count, correct_count, user_comment
                FROM user_word_familiarity
                WHERE user_id = ? AND word_id = ?
            ''', (user_id, word_id)).fetchone()
        
        seen_count = current_row['seen_count'] if current_row else 0
        correct_count = current_row['correct_count'] if current_row else 0
        current_user_comment = current_row['user_comment'] if current_row else ''
        
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