import os, json, sqlite3
from flask import Flask, request, jsonify, send_from_directory, Blueprint, g
from flask_cors import CORS
from datetime import datetime, UTC

from server.db import (
    get_db, init_db, DB_PATH,
    migrate_practice, pick_words_by_run, json_load, fam_counts_for_words,
    latest_run_id_for_level, ensure_words_exist, create_level_run,
    list_words_rows, get_word_row, count_words_fam5, delete_words_by_ids, upsert_word_row,
    get_localization_entry, upsert_localization_entry, get_all_localization_entries,
    get_localization_for_language, get_missing_translations,
)
from server.db_multi_user import (
    get_level_words_with_familiarity, unlock_level_words, update_word_familiarity,
    get_familiarity_counts_for_level, get_user_level_stats, get_global_level_stats,
    get_user_native_language, ensure_user_databases
)
from server.services.auth import (
    register_user, login_user, get_current_user, logout_user, require_auth
)
from server.middleware import inject_user_context, get_user_context, require_auth
from server.services.user_data import (
    update_user_level_progress, get_user_level_progress, 
    load_user_settings, save_user_settings, load_user_stats, save_user_stats,
    migrate_user_data_structure
)
from server.services.custom_levels import (
    create_custom_level_group, generate_custom_levels, get_custom_level_groups,
    get_custom_level_group, get_custom_level, get_custom_levels_for_group,
    delete_custom_level_group, update_custom_level_group
)

def calculate_translation_similarity(user_text, correct_text):
    """Calculate similarity between user translation and correct answer"""
    if not user_text or not correct_text:
        return 0.0
    
    # Normalize texts (lowercase, remove extra spaces)
    user_normalized = ' '.join(user_text.lower().split())
    correct_normalized = ' '.join(correct_text.lower().split())
    
    # Exact match
    if user_normalized == correct_normalized:
        return 1.0
    
    # Word-based similarity
    user_words = set(user_normalized.split())
    correct_words = set(correct_normalized.split())
    
    if not user_words or not correct_words:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = len(user_words & correct_words)
    union = len(user_words | correct_words)
    
    if union == 0:
        return 0.0
    
    jaccard_similarity = intersection / union
    
    # Boost score if most words match
    if jaccard_similarity > 0.7:
        return min(0.9, jaccard_similarity + 0.1)
    elif jaccard_similarity > 0.5:
        return min(0.8, jaccard_similarity + 0.05)
    else:
        return jaccard_similarity
from server.database_sync import sync_databases_on_startup
from server.services.llm import (
    llm_generate_sentences, llm_translate_batch, llm_similarity,
    _http_json, OPENAI_KEY, OPENAI_BASE,
    tokenize_words, suggest_topic, suggest_level_title, cefr_norm, CEFR_PRESETS, llm_enrich_word, _norm_gender,
    similarity_score
)
from server.services.tts import ensure_tts_for_alphabet_letter, ensure_tts_for_word, ensure_tts_for_sentence, ensure_tts_for_word_with_context, _audio_url_to_path, MEDIA_DIR

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# Configure CORS to allow all origins for development and production
CORS(app, origins=["*"], allow_headers=["Content-Type", "Authorization", "X-Native-Language", "X-Requested-With"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], supports_credentials=True)

from pathlib import Path
import tempfile

DATA_DIR = Path(APP_ROOT) / 'data'

def _level_file(lang: str, level: int, user_id: int = None) -> Path:
    if user_id:
        return DATA_DIR / 'users' / f'user_{user_id}' / lang / 'levels' / f"{int(level)}.json"
    return DATA_DIR / lang / 'levels' / f"{int(level)}.json"

def _ensure_parent(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)

def _read_level(lang: str, level: int, user_id: int = None, custom_group_id: int = None) -> dict | None:
    # First try custom level if group_id is provided
    if custom_group_id and user_id:
        custom_level = get_custom_level(custom_group_id, level)
        if custom_level:
            return custom_level['content']
    
    # Then try user-specific level
    if user_id:
        p = _level_file(lang, level, user_id)
        if p.exists():
            with p.open('r', encoding='utf-8') as f: 
                return json.load(f)
    
    # Fallback to global level
    p = _level_file(lang, level)
    if not p.exists(): return None
    with p.open('r', encoding='utf-8') as f: return json.load(f)

def _write_level(lang: str, level: int, data: dict, user_id: int = None) -> None:
    if user_id:
        p = _level_file(lang, level, user_id)
    else:
        p = _level_file(lang, level); _ensure_parent(p)
    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(p.parent), encoding='utf-8') as t:
        json.dump(data, t, ensure_ascii=False, indent=2)
        t.flush(); os.fsync(t.fileno()); tmp = t.name
    os.replace(tmp, p)

def _list_levels(lang: str) -> list[int]:
    d = DATA_DIR / lang / 'levels'
    if not d.exists(): return []
    out=[]; 
    for f in d.glob('*.json'):
        try: out.append(int(f.stem))
        except: pass
    return sorted(out)

# Blueprints
words_bp = Blueprint('words', __name__)
levels_bp = Blueprint('levels', __name__)
practice_bp = Blueprint('practice', __name__)
media_bp = Blueprint('media', __name__)
auth_bp = Blueprint('auth', __name__)
user_bp = Blueprint('user', __name__)
custom_levels_bp = Blueprint('custom_levels', __name__)

init_db()  # Initialize database tables



############################
# Static serving
############################

@app.get('/')
def index():
    return send_from_directory(APP_ROOT, 'index.html')

@app.get('/health')
def health():
    return jsonify({'ok': True})

@app.get('/api/debug/user-status')
def debug_user_status():
    """Debug endpoint to check user authentication status"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_current_user(session_token) if session_token else None
        
        return jsonify({
            'authenticated': user is not None,
            'user_id': user['id'] if user else None,
            'username': user.get('username') if user else None,
            'has_token': bool(session_token)
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'authenticated': False
        }), 500

@app.get('/api/debug/database-schema')
def debug_database_schema():
    """Debug endpoint to check database schema"""
    try:
        from server.db_config import get_database_config
        from server.db import get_db
        
        config = get_database_config()
        conn = get_db()
        
        # Get database type and connection info
        db_info = {
            'database_type': config['type'],
            'database_path': config.get('path', 'N/A'),
            'database_url': 'SET' if config.get('url') else 'NOT_SET'
        }
        
        # Get table schemas
        tables_info = {}
        
        # Get list of tables
        if config['type'] == 'postgresql':
            tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            tables = [row[0] for row in conn.execute(tables_query).fetchall()]
            
            for table in tables:
                schema_query = f"""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = '{table}' 
                ORDER BY ordinal_position
                """
                columns = conn.execute(schema_query).fetchall()
                tables_info[table] = [
                    {
                        'name': col[0],
                        'type': col[1],
                        'nullable': col[2],
                        'default': col[3]
                    } for col in columns
                ]
        else:
            # SQLite
            tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = [row[0] for row in conn.execute(tables_query).fetchall()]
            
            for table in tables:
                schema_query = f"PRAGMA table_info({table})"
                columns = conn.execute(schema_query).fetchall()
                tables_info[table] = [
                    {
                        'name': col[1],
                        'type': col[2],
                        'nullable': not col[3],
                        'default': col[4]
                    } for col in columns
                ]
        
        conn.close()
        
        return jsonify({
            'database_info': db_info,
            'tables': tables_info,
            'success': True
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.get('/api/debug/tts-status')
def debug_tts_status():
    """Debug endpoint to check TTS service status"""
    try:
        from server.services.tts import _openai_ready
        import os
        
        tts_info = {
            'railway_environment': bool(os.environ.get('RAILWAY_ENVIRONMENT')),
            'openai_api_key_set': bool(os.environ.get('OPENAI_API_KEY')),
            'openai_ready': _openai_ready(),
            'tts_service_available': False
        }
        
        # Check if TTS service is available
        if tts_info['openai_ready']:
            tts_info['tts_service_available'] = True
        elif tts_info['railway_environment'] and not tts_info['openai_api_key_set']:
            tts_info['tts_service_available'] = False
            tts_info['reason'] = 'Railway environment without OpenAI API key'
        else:
            tts_info['reason'] = 'OpenAI API not configured'
        
        return jsonify({
            'tts_info': tts_info,
            'success': True
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.post('/api/debug/run-progress-cache-migration')
def debug_run_progress_cache_migration():
    """Run migration to populate custom_level_progress table with existing data"""
    try:
        from server.db_progress_cache import (
            create_custom_level_progress_table,
            refresh_custom_level_group_progress,
            get_custom_level_group_progress
        )
        from server.db_config import get_database_config, get_db_connection, execute_query
        from server.services.custom_levels import get_custom_level_groups, get_custom_levels_for_group
        
        # 1. Ensure table exists
        create_custom_level_progress_table()
        
        # 2. Get all custom level groups
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config['type'] == 'postgresql':
                result = execute_query(conn, "SELECT id, user_id FROM custom_level_groups")
                groups = [(row['id'], row['user_id']) for row in result.fetchall()]
            else:
                cursor = conn.cursor()
                cursor.execute("SELECT id, user_id FROM custom_level_groups")
                groups = [(row[0], row[1]) for row in cursor.fetchall()]
        finally:
            conn.close()
        
        print(f"📚 Found {len(groups)} custom level groups")
        
        # 3. Populate progress cache for each group
        total_groups_processed = 0
        total_levels_processed = 0
        
        for group_id, user_id in groups:
            try:
                print(f"🔄 Processing group {group_id} for user {user_id}...")
                
                # Get levels for this group
                levels = get_custom_levels_for_group(group_id)
                if not levels:
                    print(f"⚠️ No levels found for group {group_id}")
                    continue
                
                # Refresh progress cache for all levels in this group
                success = refresh_custom_level_group_progress(user_id, group_id)
                
                if success:
                    # Verify the cache was populated
                    cached_data = get_custom_level_group_progress(user_id, group_id)
                    cached_levels = len(cached_data)
                    
                    print(f"✅ Group {group_id}: {cached_levels}/{len(levels)} levels cached")
                    total_groups_processed += 1
                    total_levels_processed += cached_levels
                else:
                    print(f"❌ Failed to cache progress for group {group_id}")
                    
            except Exception as e:
                print(f"❌ Error processing group {group_id}: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Migration complete! Groups processed: {total_groups_processed}/{len(groups)}, Levels cached: {total_levels_processed}',
            'groups_processed': total_groups_processed,
            'total_groups': len(groups),
            'levels_cached': total_levels_processed
        })
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500


@app.post('/api/debug/cleanup-duplicate-words')
def debug_cleanup_duplicate_words():
    """Clean up duplicate entries in words table before adding UNIQUE constraint"""
    try:
        import os
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = psycopg2.connect(database_url)
        
        try:
            print("🚀 Cleaning up duplicate words...")
            cursor = conn.cursor()
            
            # Find duplicates
            cursor.execute("""
                SELECT word, language, native_language, COUNT(*) as count
                FROM words 
                WHERE word IS NOT NULL AND language IS NOT NULL AND native_language IS NOT NULL
                GROUP BY word, language, native_language 
                HAVING COUNT(*) > 1
                ORDER BY count DESC;
            """)
            duplicates = cursor.fetchall()
            
            print(f"📊 Found {len(duplicates)} duplicate word groups")
            
            cleaned_count = 0
            for word, language, native_language, count in duplicates:
                print(f"🔧 Cleaning duplicates for '{word}' ({language} -> {native_language}): {count} entries")
                
                # Keep the most recent entry (highest id) and delete the rest
                cursor.execute("""
                    DELETE FROM words 
                    WHERE word = %s AND language = %s AND native_language = %s
                    AND id NOT IN (
                        SELECT MAX(id) 
                        FROM words 
                        WHERE word = %s AND language = %s AND native_language = %s
                    );
                """, (word, language, native_language, word, language, native_language))
                
                deleted_rows = cursor.rowcount
                cleaned_count += deleted_rows
                print(f"✅ Deleted {deleted_rows} duplicate entries for '{word}'")
            
            # Also clean up entries with NULL values
            cursor.execute("""
                DELETE FROM words 
                WHERE word IS NULL OR language IS NULL OR native_language IS NULL;
            """)
            null_cleaned = cursor.rowcount
            print(f"✅ Deleted {null_cleaned} entries with NULL values")
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Cleaned up {cleaned_count} duplicate entries and {null_cleaned} NULL entries',
                'duplicates_found': len(duplicates),
                'duplicates_cleaned': cleaned_count,
                'null_entries_cleaned': null_cleaned
            })
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Failed to cleanup duplicates: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.get('/api/debug/list-georgian-words')
def debug_list_georgian_words():
    """List Georgian words in the database"""
    try:
        import os
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = psycopg2.connect(database_url)
        
        try:
            cursor = conn.cursor()
            
            # Get Georgian words
            cursor.execute("""
                SELECT word, language, native_language, translation, example
                FROM words 
                WHERE language = 'ka'
                ORDER BY word
                LIMIT 20;
            """)
            words = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'words': [dict(word) for word in words],
                'count': len(words)
            })
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Failed to list Georgian words: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.post('/api/debug/add-words-unique-constraint')
def debug_add_words_unique_constraint():
    """Add UNIQUE constraint to words table for (word, language, native_language)"""
    try:
        import os
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = psycopg2.connect(database_url)
        
        try:
            print("🚀 Adding UNIQUE constraint to words table...")
            cursor = conn.cursor()
            
            # Check if constraint already exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints 
                    WHERE table_name = 'words' 
                    AND constraint_type = 'UNIQUE'
                    AND constraint_name LIKE '%word%language%native_language%'
                );
            """)
            constraint_exists = cursor.fetchone()[0]
            
            if not constraint_exists:
                # Add the UNIQUE constraint
                cursor.execute("""
                    ALTER TABLE words 
                    ADD CONSTRAINT words_word_language_native_language_unique 
                    UNIQUE (word, language, native_language);
                """)
                print("✅ Added UNIQUE constraint to words table")
            else:
                print("ℹ️ UNIQUE constraint already exists on words table")
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'UNIQUE constraint added successfully' if not constraint_exists else 'UNIQUE constraint already exists'
            })
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Failed to add UNIQUE constraint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.post('/api/debug/run-database-schema-migration')
def debug_run_database_schema_migration():
    """Run database schema migration to fix missing columns and schema issues"""
    try:
        import os
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = psycopg2.connect(database_url)
        
        try:
            print("🚀 Starting database schema migration...")
            
            # Fix user_word_familiarity table
            print("🔧 Fixing user_word_familiarity table schema...")
            
            # Add word_hash column if missing
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'user_word_familiarity' AND column_name = 'word_hash'
                );
            """)
            word_hash_exists = cursor.fetchone()[0]
            
            if not word_hash_exists:
                cursor.execute("ALTER TABLE user_word_familiarity ADD COLUMN word_hash VARCHAR(64);")
                print("✅ Added word_hash column to user_word_familiarity")
            else:
                print("ℹ️ word_hash column already exists in user_word_familiarity")
            
            # Add native_language column if missing
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'user_word_familiarity' AND column_name = 'native_language'
                );
            """)
            native_language_exists = cursor.fetchone()[0]
            
            if not native_language_exists:
                cursor.execute("ALTER TABLE user_word_familiarity ADD COLUMN native_language VARCHAR(10);")
                print("✅ Added native_language column to user_word_familiarity")
            else:
                print("ℹ️ native_language column already exists in user_word_familiarity")
            
            # Create index on word_hash if it doesn't exist
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_user_hash 
                ON user_word_familiarity(user_id, word_hash);
            """)
            print("✅ Created index on user_word_familiarity(user_id, word_hash)")
            
            # Populate word_hash values for existing records
            print("🔧 Populating word_hash values for existing records...")
            cursor.execute("""
                SELECT uwf.id, w.word, COALESCE(uwf.native_language, w.native_language) as native_language
                FROM user_word_familiarity uwf
                JOIN words w ON uwf.word_id = w.id
                WHERE uwf.word_hash IS NULL;
            """)
            
            records = cursor.fetchall()
            print(f"📊 Found {len(records)} records without word_hash")
            
            if records:
                import hashlib
                for record_id, word, native_language in records:
                    # Generate hash
                    word_hash = hashlib.sha256(f"{word}_{native_language}".encode()).hexdigest()
                    
                    cursor.execute("""
                        UPDATE user_word_familiarity 
                        SET word_hash = %s, native_language = %s
                        WHERE id = %s;
                    """, (word_hash, native_language, record_id))
                
                print(f"✅ Updated {len(records)} records with word_hash")
            
            # Fix level_runs table
            print("🔧 Fixing level_runs table schema...")
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'level_runs'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("ℹ️ level_runs table does not exist, creating it...")
                cursor.execute("""
                    CREATE TABLE level_runs (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        level INTEGER NOT NULL,
                        score DECIMAL(5,2),
                        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                print("✅ Created level_runs table")
            else:
                print("ℹ️ level_runs table already exists")
            
            conn.commit()
            cursor.close()
            
            print("✅ Database schema migration completed successfully!")
            
            return jsonify({
                'success': True,
                'message': 'Database schema migration completed successfully',
                'records_updated': len(records) if records else 0
            })
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return jsonify({
                'error': str(e),
                'success': False
            }), 500
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Error in database schema migration: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.get('/api/debug/check-progress-cache-table')
def debug_check_progress_cache_table():
    """Check if custom_level_progress table exists and show its structure"""
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config['type'] == 'postgresql':
                # Check if table exists
                result = execute_query(conn, """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'custom_level_progress'
                    );
                """)
                table_exists = result.fetchone()['exists']
                
                if table_exists:
                    # Get table structure
                    result = execute_query(conn, """
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = 'custom_level_progress'
                        ORDER BY ordinal_position;
                    """)
                    columns = [dict(row) for row in result.fetchall()]
                    
                    # Get row count
                    result = execute_query(conn, "SELECT COUNT(*) as count FROM custom_level_progress")
                    row_count = result.fetchone()['count']
                    
                    return jsonify({
                        'success': True,
                        'table_exists': True,
                        'columns': columns,
                        'row_count': row_count,
                        'message': 'Table exists and is accessible'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'table_exists': False,
                        'message': 'Table does not exist'
                    })
            else:
                # SQLite check
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom_level_progress'")
                table_exists = cursor.fetchone() is not None
                
                if table_exists:
                    cursor.execute("PRAGMA table_info(custom_level_progress)")
                    columns = [{'column_name': row[1], 'data_type': row[2], 'is_nullable': 'YES' if row[3] == 0 else 'NO', 'column_default': row[4]} for row in cursor.fetchall()]
                    
                    cursor.execute("SELECT COUNT(*) FROM custom_level_progress")
                    row_count = cursor.fetchone()[0]
                    
                    return jsonify({
                        'success': True,
                        'table_exists': True,
                        'columns': columns,
                        'row_count': row_count,
                        'message': 'Table exists and is accessible'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'table_exists': False,
                        'message': 'Table does not exist'
                    })
                    
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error checking progress cache table: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.post('/api/debug/create-progress-cache-table')
def debug_create_progress_cache_table():
    """Create custom_level_progress table for caching familiarity data"""
    try:
        from server.db_config import get_database_config, get_db_connection
        
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config['type'] == 'postgresql':
                cursor = conn.cursor()
                
                # Drop table if exists (for clean recreation)
                cursor.execute("DROP TABLE IF EXISTS custom_level_progress CASCADE;")
                
                # Create table with explicit schema
                cursor.execute("""
                    CREATE TABLE custom_level_progress (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        group_id INTEGER NOT NULL,
                        level_number INTEGER NOT NULL,
                        total_words INTEGER DEFAULT 0,
                        familiarity_0 INTEGER DEFAULT 0,
                        familiarity_1 INTEGER DEFAULT 0,
                        familiarity_2 INTEGER DEFAULT 0,
                        familiarity_3 INTEGER DEFAULT 0,
                        familiarity_4 INTEGER DEFAULT 0,
                        familiarity_5 INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, group_id, level_number)
                    );
                """)
                
                # Create indexes
                cursor.execute("""
                    CREATE INDEX idx_custom_level_progress_user_group 
                    ON custom_level_progress(user_id, group_id);
                """)
                
                cursor.execute("""
                    CREATE INDEX idx_custom_level_progress_last_updated 
                    ON custom_level_progress(last_updated);
                """)
                
                conn.commit()
                print("✅ Custom level progress table created successfully in PostgreSQL")
                
            else:
                # SQLite fallback
                cursor = conn.cursor()
                cursor.execute("DROP TABLE IF EXISTS custom_level_progress;")
                cursor.execute("""
                    CREATE TABLE custom_level_progress (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        group_id INTEGER NOT NULL,
                        level_number INTEGER NOT NULL,
                        total_words INTEGER DEFAULT 0,
                        familiarity_0 INTEGER DEFAULT 0,
                        familiarity_1 INTEGER DEFAULT 0,
                        familiarity_2 INTEGER DEFAULT 0,
                        familiarity_3 INTEGER DEFAULT 0,
                        familiarity_4 INTEGER DEFAULT 0,
                        familiarity_5 INTEGER DEFAULT 0,
                        last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, group_id, level_number)
                    );
                """)
                conn.commit()
                print("✅ Custom level progress table created successfully in SQLite")
            
            return jsonify({
                'success': True,
                'message': 'Custom level progress cache table created successfully'
            })
            
        except Exception as e:
            print(f"❌ Error creating table: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': str(e),
                'success': False
            }), 500
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Error in debug endpoint: {e}")
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.post('/api/debug/migrate-word-count')
def debug_migrate_word_count():
    """Add word_count column to custom_levels table and populate existing data"""
    try:
        from server.db import migrate_custom_levels_add_word_count
        from server.services.custom_levels import get_custom_levels_for_group, calculate_word_count_from_content
        
        # Add the word_count column
        migrate_custom_levels_add_word_count()
        
        # Populate word counts for existing levels
        print("🔄 Populating word counts for existing custom levels...")
        
        # Get all custom level groups
        from server.db_config import get_database_config, get_db_connection, execute_query
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config['type'] == 'postgresql':
                result = execute_query(conn, "SELECT id FROM custom_level_groups")
                groups = [row['id'] for row in result.fetchall()]
            else:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM custom_level_groups")
                groups = [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
        
        updated_count = 0
        total_levels = 0
        
        for group_id in groups:
            levels = get_custom_levels_for_group(group_id)
            for level in levels:
                total_levels += 1
                level_number = level['level_number']
                content = level.get('content', {})
                
                # Calculate word count from content
                word_count = calculate_word_count_from_content(content)
                
                if word_count > 0:
                    # Update the word count in database
                    if config['type'] == 'postgresql':
                        execute_query(conn, """
                            UPDATE custom_levels 
                            SET word_count = %s, updated_at = %s
                            WHERE group_id = %s AND level_number = %s
                        """, (word_count, datetime.now(UTC).isoformat(), group_id, level_number))
                    else:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE custom_levels 
                            SET word_count = ?, updated_at = ?
                            WHERE group_id = ? AND level_number = ?
                        """, (word_count, datetime.now(UTC).isoformat(), group_id, level_number))
                        conn.commit()
                    
                    updated_count += 1
                    print(f"✅ Updated level {group_id}/{level_number}: {word_count} words")
        
        return jsonify({
            'success': True,
            'message': f'Successfully migrated word counts for {updated_count} out of {total_levels} levels',
            'updated_levels': updated_count,
            'total_levels': total_levels
        })
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.post('/api/debug/migrate-data')
def debug_migrate_data():
    """Debug endpoint to migrate data to Railway PostgreSQL"""
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        from server.db import get_db
        from datetime import datetime
        
        print("🚀 Starting Railway data migration via API...")
        
        # Check database type
        config = get_database_config()
        print(f"📊 Database type: {config['type']}")
        
        if config['type'] != 'postgresql':
            return jsonify({
                'error': 'This endpoint is for PostgreSQL migration only',
                'success': False
            }), 400
        
        # Get connection
        conn = get_db_connection()
        print("✅ Connected to Railway PostgreSQL database")
        
        # Check if we have any data
        result = execute_query(conn, "SELECT COUNT(*) as count FROM words")
        word_count = result.fetchone()['count']
        print(f"📚 Current word count in Railway DB: {word_count}")
        
        if word_count > 0:
            return jsonify({
                'message': 'Railway database already has data - migration not needed',
                'word_count': word_count,
                'success': True
            })
        
        # Create some sample data for testing
        print("🔄 Creating sample data for testing...")
        sample_words = [
            ('hello', 'en', 'de', 'hallo', 'Hello world!', 'Hallo Welt!', 'hello', 'interjection', 'həˈloʊ', None, 'none', None, None, None, None, None, 'A1', 1, None, None, None, datetime.now().isoformat(), datetime.now().isoformat()),
            ('world', 'en', 'de', 'Welt', 'Hello world!', 'Hallo Welt!', 'world', 'noun', 'wɜːrld', None, 'none', 'worlds', None, None, None, None, 'A1', 2, None, None, None, datetime.now().isoformat(), datetime.now().isoformat()),
            ('test', 'en', 'de', 'Test', 'This is a test.', 'Das ist ein Test.', 'test', 'noun', 'test', None, 'none', 'tests', None, None, None, None, 'A1', 3, None, None, None, datetime.now().isoformat(), datetime.now().isoformat()),
            ('მიყვარს', 'ka', 'de', 'ich liebe', 'მიყვარს მუსიკა', 'Ich liebe Musik', 'მიყვარს', 'verb', None, None, 'none', None, None, None, None, None, 'A1', 4, None, None, None, datetime.now().isoformat(), datetime.now().isoformat()),
            ('კითხვა', 'ka', 'de', 'Frage', 'ეს კითხვაა', 'Das ist eine Frage', 'კითხვა', 'noun', None, None, 'none', None, None, None, None, None, 'A1', 5, None, None, None, datetime.now().isoformat(), datetime.now().isoformat())
        ]
        
        migrated = 0
        for word_data in sample_words:
            try:
                execute_query(conn, """
                    INSERT INTO words (
                        word, language, native_language, translation, example, example_native,
                        lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                        collocations, cefr, freq_rank, tags, note, info, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT (word, language) DO NOTHING
                """, word_data)
                migrated += 1
            except Exception as e:
                print(f"⚠️ Error creating sample word {word_data[0]}: {e}")
        
        print(f"✅ Created {migrated} sample words")
        
        # Check final count
        result = execute_query(conn, "SELECT COUNT(*) as count FROM words")
        final_count = result.fetchone()['count']
        print(f"📚 Final word count in Railway DB: {final_count}")
        
        conn.close()
        
        return jsonify({
            'message': f'Successfully created {migrated} sample words',
            'word_count': final_count,
            'success': True
        })
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

############################
# Authentication API
############################

@auth_bp.post('/api/auth/register')
def api_register():
    """Register a new user"""
    try:
        data = request.get_json(force=True) or {}
        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip()
        password = (data.get('password') or '').strip()
        
        result = register_user(username, email, password)
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.post('/api/auth/login')
def api_login():
    """Login a user"""
    try:
        data = request.get_json(force=True) or {}
        username_or_email = (data.get('username') or data.get('email') or '').strip()
        password = (data.get('password') or '').strip()
        
        result = login_user(username_or_email, password)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 401
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.post('/api/auth/logout')
def api_logout():
    """Logout a user"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if logout_user(session_token):
            return jsonify({'success': True, 'message': 'Logged out successfully'})
        else:
            return jsonify({'success': False, 'error': 'Invalid session'}), 401
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.get('/api/auth/me')
def api_get_current_user():
    """Get current user information"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        user = get_current_user(session_token)
        if user:
            return jsonify({'success': True, 'user': user})
        else:
            # Return success with no user instead of 401 to prevent console errors
            return jsonify({'success': True, 'user': None})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

############################
# User Management API
############################

@user_bp.get('/api/user/progress')
def api_get_user_progress():
    """Get user progress for all languages or specific language"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_current_user(session_token)
        
        if not user:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        language = request.args.get('language')
        
        if language:
            progress = get_user_level_progress(user['id'], language)
            return jsonify({'success': True, 'progress': progress})
        else:
            # Get progress for all languages
            from server.db import get_user_progress
            all_progress = get_user_progress(user['id'])
            
            # Group by language
            progress_by_lang = {}
            for row in all_progress:
                lang = row['language']
                if lang not in progress_by_lang:
                    progress_by_lang[lang] = {
                        'language': lang,
                        'levels': {},
                        'total_score': 0,
                        'levels_completed': 0
                    }
                
                level_key = str(row['level'])
                progress_by_lang[lang]['levels'][level_key] = {
                    'status': row['status'],
                    'score': row['score'],
                    'completed_at': row['completed_at'],
                    'updated_at': row['updated_at']
                }
                
                if row['status'] == 'completed':
                    progress_by_lang[lang]['levels_completed'] += 1
                    if row['score'] is not None:
                        progress_by_lang[lang]['total_score'] += row['score']
            
            return jsonify({'success': True, 'progress': list(progress_by_lang.values())})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@user_bp.get('/api/user/settings')
def api_get_user_settings():
    """Get user settings"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_current_user(session_token)
        
        if not user:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        try:
            # Try to get settings from database first
            from server.db_config import get_database_config, get_db_connection, execute_query
            
            config = get_database_config()
            conn = get_db_connection()
            
            if config['type'] == 'postgresql':
                # PostgreSQL syntax
                result = execute_query(conn, "SELECT settings FROM users WHERE id = %s", (user['id'],))
                row = result.fetchone()
            else:
                # SQLite syntax
                cur = conn.cursor()
                row = cur.execute("SELECT settings FROM users WHERE id = ?", (user['id'],)).fetchone()
            
            conn.close()
            
            if row and row['settings']:
                try:
                    settings = json.loads(row['settings'])
                    return jsonify({'success': True, 'settings': settings})
                except json.JSONDecodeError:
                    pass
            
            # Fallback to default settings
            default_settings = {
                'theme': 'light',
                'language': 'en',
                'notifications': True,
                'sound_enabled': True,
                'auto_play_audio': False,
                'difficulty_preference': 'adaptive',
                'native_language': 'de'
            }
            return jsonify({'success': True, 'settings': default_settings})
            
        except Exception as settings_error:
            print(f"Error loading user settings for user {user['id']}: {settings_error}")
            # Return default settings if loading fails
            default_settings = {
                'theme': 'light',
                'language': 'en',
                'notifications': True,
                'sound_enabled': True,
                'auto_play_audio': False,
                'difficulty_preference': 'adaptive',
                'native_language': 'de'
            }
            return jsonify({'success': True, 'settings': default_settings})
        
    except Exception as e:
        print(f"Error in api_get_user_settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@user_bp.post('/api/user/settings')
def api_update_user_settings():
    """Update user settings"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_current_user(session_token)
        
        if not user:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json(force=True) or {}
        
        # Check if native language is being updated
        if 'native_language' in data:
            from server.db_multi_user import update_user_native_language
            success = update_user_native_language(user['id'], data['native_language'])
            if not success:
                return jsonify({'success': False, 'error': 'Failed to update native language'}), 500
        
        # Save settings to database instead of file system
        try:
            from server.db_config import get_database_config, get_db_connection, execute_query
            
            config = get_database_config()
            conn = get_db_connection()
            
            settings_json = json.dumps(data, ensure_ascii=False)
            
            if config['type'] == 'postgresql':
                # PostgreSQL syntax
                execute_query(conn, "UPDATE users SET settings = %s WHERE id = %s", (settings_json, user['id']))
            else:
                # SQLite syntax
                cur = conn.cursor()
                cur.execute("UPDATE users SET settings = ? WHERE id = ?", (settings_json, user['id']))
            
            conn.commit()
            conn.close()
            
        except Exception as save_error:
            print(f"Error saving user settings for user {user['id']}: {save_error}")
            # Continue anyway - settings update is not critical
        
        # Add response header for frontend synchronization
        response = jsonify({'success': True, 'message': 'Settings updated successfully'})
        if 'native_language' in data:
            response.headers['X-Native-Language-Updated'] = data['native_language']
        return response
        
    except Exception as e:
        print(f"Error in api_update_user_settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@user_bp.get('/api/user/stats')
def api_get_user_stats():
    """Get user statistics"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_current_user(session_token)
        
        if not user:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        stats = load_user_stats(user['id'])
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@user_bp.get('/api/user/word-stats')
def api_user_word_stats():
    """Get user's word familiarity statistics"""
    try:
        # Get user context from middleware
        user_context = get_user_context()
        user_id = user_context['user_id']
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        language = request.args.get('language', 'en')
        
        # Get user-specific familiarity counts
        from server.db import get_user_familiarity_counts
        fam_counts = get_user_familiarity_counts(user_id, language)
        
        return jsonify({
            'success': True,
            'familiarity_counts': fam_counts
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@user_bp.get('/api/user/progress-summary')
def api_user_progress_summary():
    """Get user's overall learning progress"""
    try:
        # Get user context from middleware
        user_context = get_user_context()
        user_id = user_context['user_id']
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        language = request.args.get('language', 'en')
        
        # Get user progress data
        from server.db import get_user_progress
        from server.db_multi_user import get_user_native_language
        native_language = get_user_native_language(user_id)
        user_progress = get_user_progress(user_id, language, native_language)
        
        # Calculate overall progress
        total_levels = 10  # Assuming 10 levels
        completed_levels = len([p for p in user_progress if p['status'] == 'completed' and p['score'] > 0.6])
        overall_progress = (completed_levels / total_levels) * 100 if total_levels > 0 else 0
        
        return jsonify({
            'success': True,
            'overall_progress': overall_progress,
            'completed_levels': completed_levels,
            'total_levels': total_levels
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@user_bp.post('/api/user/migrate')
def api_user_migrate():
    """Manually trigger migration of global data to user data"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_current_user(session_token)
        
        if not user:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        language = request.json.get('language', 'en') if request.is_json else 'en'
        user_id = user['id']
        
        success = migrate_user_data_structure(user_id)
        if success:
            return jsonify({'success': True, 'message': f'Migration completed for language {language}'})
        else:
            return jsonify({'success': False, 'error': 'Migration failed'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Serve static files
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(APP_ROOT, 'static'), filename)

# Serve favicon or other root files if requested directly
@app.get('/<path:fname>')
def static_passthrough(fname):
    p = os.path.join(APP_ROOT, fname)
    if os.path.isfile(p):
        return send_from_directory(APP_ROOT, fname)
    # fallback to index for SPA routes
    return send_from_directory(APP_ROOT, 'index.html')

############################
# Optional OpenAI helpers (fallback to static if no key)
############################


############################
############################
# Words & i18n API
############################


@media_bp.get('/media/tts/<lang>/<fname>')
def serve_tts_audio(lang, fname):
    subdir = os.path.join(MEDIA_DIR, 'tts', lang)
    return send_from_directory(subdir, fname)

# Add symmetric route for sentence TTS
@media_bp.get('/media/tts_sentences/<lang>/<fname>')
def serve_tts_sentence(lang, fname):
    subdir = os.path.join(MEDIA_DIR, 'tts_sentences', lang)
    return send_from_directory(subdir, fname)


@app.post('/api/i18n/translate')
def api_i18n_translate():
    try:
        data = request.get_json(force=True) or {}
        text = (data.get('text') or '').strip()
        target_lang = (data.get('target_lang') or data.get('language') or 'de').strip().lower()
        if not text:
            return jsonify({'success': False, 'error': 'text required'}), 400
        # Use batch API for consistency; fall back to identity if no KEY or failure
        try:
            out = llm_translate_batch([text], target_lang) if OPENAI_KEY else None
            if isinstance(out, list) and out and isinstance(out[0], str) and out[0].strip():
                return jsonify({'success': True, 'text': out[0].strip()})
        except Exception:
            pass
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@words_bp.post('/api/word/tts')
def api_word_tts():
    try:
        payload = request.get_json(force=True) or {}
        word = (payload.get('word') or '').strip()
        language = (payload.get('language') or '').strip()
        sentence = (payload.get('sentence') or '').strip()  # Optional sentence context
        if not word or not language:
            return jsonify({'success': False, 'error': 'word and language required'}), 400
        
        # Check if we're in Railway environment and TTS is disabled
        if os.environ.get('RAILWAY_ENVIRONMENT') and not os.environ.get('OPENAI_API_KEY'):
            print(f"⚠️ Railway environment without OpenAI API key - TTS disabled for '{word}'")
            return jsonify({'success': False, 'error': 'TTS service unavailable'}), 503
        
        # Precedence for TTS instructions: request > per-language env OPENAI_TTS_INSTRUCTIONS_<LANG> > global OPENAI_TTS_INSTRUCTIONS
        instr = (payload.get('instructions') or payload.get('tts_instructions') or '').strip()
        
        # Use context-aware TTS if sentence is provided
        if sentence:
            url_path = ensure_tts_for_word_with_context(word, language, sentence, instr or None)
        else:
            url_path = ensure_tts_for_word(word, language, instr or None)
        
        if not url_path:
            print(f"❌ TTS generation failed for word '{word}' in language '{language}'")
            return jsonify({'success': False, 'error': 'TTS generation failed'}), 500
        
        return jsonify({'success': True, 'audio_url': url_path})
    
    except Exception as e:
        print(f"❌ TTS API error: {e}")
        return jsonify({'success': False, 'error': f'TTS service error: {str(e)}'}), 500


@words_bp.post('/api/sentence/tts')
def api_sentence_tts():
    try:
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        lang = (data.get('language') or 'en').strip().lower()
        if not text:
            return jsonify({'success': False, 'error': 'no text'}), 400
        
        # Check if we're in Railway environment and TTS is disabled
        if os.environ.get('RAILWAY_ENVIRONMENT') and not os.environ.get('OPENAI_API_KEY'):
            print(f"⚠️ Railway environment without OpenAI API key - TTS disabled for sentence")
            return jsonify({'success': False, 'error': 'TTS service unavailable'}), 503
        
        # Precedence for TTS instructions: request > per-language env OPENAI_TTS_INSTRUCTIONS_<LANG> > global OPENAI_TTS_INSTRUCTIONS
        instr = (data.get('instructions') or data.get('tts_instructions') or '').strip()
        url = ensure_tts_for_sentence(text, lang, instr or None)
        if not url:
            print(f"❌ TTS generation failed for sentence in language '{lang}'")
            return jsonify({'success': False, 'error': 'TTS generation failed'})
        return jsonify({'success': True, 'audio_url': url})
    
    except Exception as e:
        print(f"❌ Sentence TTS API error: {e}")
        return jsonify({'success': False, 'error': f'TTS service error: {str(e)}'})

# --- Alphabet API endpoints ---

@words_bp.get('/api/alphabet')
def api_alphabet():
    """Get alphabet letters for a language"""
    try:
        language = request.args.get('language', 'en').strip().lower()
        
        # Define alphabets for different languages
        alphabets = {
            'en': 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
            'de': 'A Ä B C D E F G H I J K L M N O Ö P Q R S ß T U Ü V W X Y Z'.split(' '),
            'fr': 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
            'es': 'A B C D E F G H I J K L M N Ñ O P Q R S T U V W X Y Z'.split(' '),
            'it': 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
            'pt': 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
            'ru': 'А Б В Г Д Е Ё Ж З И Й К Л М Н О П Р С Т У Ф Х Ц Ч Ш Щ Ъ Ы Ь Э Ю Я'.split(' '),
            'tr': 'A B C Ç D E F G Ğ H I İ J K L M N O Ö P R S Ş T U Ü V Y Z'.split(' '),
            'ka': 'ა ბ გ დ ე ვ ზ თ ი კ ლ მ ნ ო პ ჟ რ ს ტ უ ფ ქ ღ ყ შ ჩ ც ძ წ ჭ ხ ჯ ჰ'.split(' ')
        }
        
        letters = alphabets.get(language, alphabets['en'])
        
        # Convert to the expected format
        result = []
        for letter in letters:
            result.append({
                'char': letter,
                'letter': letter,  # alias for compatibility
                'ipa': '',  # Will be filled by ensure endpoint
                'audio_url': ''  # Will be generated on demand
            })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@words_bp.post('/api/alphabet/ensure')
def api_alphabet_ensure():
    """Ensure alphabet letters have audio and IPA data"""
    try:
        data = request.get_json(silent=True) or {}
        language = data.get('language', 'en').strip().lower()
        
        # Get alphabet letters
        alphabets = {
            'en': 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
            'de': 'A Ä B C D E F G H I J K L M N O Ö P Q R S ß T U Ü V W X Y Z'.split(' '),
            'fr': 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
            'es': 'A B C D E F G H I J K L M N Ñ O P Q R S T U V W X Y Z'.split(' '),
            'it': 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
            'pt': 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
            'ru': 'А Б В Г Д Е Ё Ж З И Й К Л М Н О П Р С Т У Ф Х Ц Ч Ш Щ Ъ Ы Ь Э Ю Я'.split(' '),
            'tr': 'A B C Ç D E F G Ğ H I İ J K L M N O Ö P R S Ş T U Ü V Y Z'.split(' '),
            'ka': 'ა ბ გ დ ე ვ ზ თ ი კ ლ მ ნ ო პ ჟ რ ს ტ უ ფ ქ ღ ყ შ ჩ ც ძ წ ჭ ხ ჯ ჰ'.split(' ')
        }
        
        letters = alphabets.get(language, alphabets['en'])
        
        # Generate audio for each letter using alphabet-specific TTS
        result = []
        for letter in letters:
            # Generate audio with alphabet context (phonetic pronunciation)
            audio_url = ensure_tts_for_alphabet_letter(letter, language)
            
            result.append({
                'char': letter,
                'letter': letter,  # alias for compatibility
                'ipa': '',  # Could be enhanced with IPA generation
                'audio_url': audio_url or ''
            })
        
        return jsonify({'success': True, 'letters': result})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@words_bp.post('/api/alphabet/tts')
def api_alphabet_tts():
    """Generate TTS for a specific alphabet letter with phonetic pronunciation"""
    try:
        data = request.get_json(silent=True) or {}
        letter = data.get('letter', '').strip()
        language = data.get('language', 'en').strip().lower()
        
        if not letter:
            return jsonify({'success': False, 'error': 'letter required'}), 400
        
        # Check if we're in Railway environment and TTS is disabled
        if os.environ.get('RAILWAY_ENVIRONMENT') and not os.environ.get('OPENAI_API_KEY'):
            print(f"⚠️ Railway environment without OpenAI API key - TTS disabled for letter '{letter}'")
            return jsonify({'success': False, 'error': 'TTS service unavailable'}), 503
        
        # Generate audio with alphabet context
        audio_url = ensure_tts_for_alphabet_letter(letter, language)
        
        if not audio_url:
            print(f"❌ TTS generation failed for letter '{letter}' in language '{language}'")
            return jsonify({'success': False, 'error': 'TTS generation failed'}), 500
        
        return jsonify({'success': True, 'audio_url': audio_url})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- FS helpers to locate level file by run_id ---
def _find_level_file_for_run(run_id: int):
    try: rid = int(run_id)
    except Exception: return None
    try:
        for lang_dir in (p for p in DATA_DIR.iterdir() if p.is_dir()):
            levels_dir = lang_dir / 'levels'
            if not levels_dir.exists(): continue
            for jf in levels_dir.glob('*.json'):
                try:
                    with open(jf, 'r', encoding='utf-8') as f:
                        js = json.load(f)
                    for r in (js.get('runs') or []):
                        if int(r.get('run_id') or 0) == rid:
                            lang = lang_dir.name
                            lvl = int(js.get('level') or int(jf.stem))
                            return (lang, lvl, js)
                except Exception:
                    continue
    except Exception:
        pass
    return None

def _unique_words_from_items(items):
    words=[]
    for it in (items or []):
        for w in (it.get('words') or []):
            s=str(w).strip()
            if s and s not in words: words.append(s)
    return words

# --- Pull words directly from the level file and batch-count familiarity ---

def _level_unique_words(lang: str, level: int) -> list[str]:
    fs = _read_level(lang, level)
    if not fs:
        return []
    seen = set()
    out = []
    for it in (fs.get('items') or []):
        for w in (it.get('words') or []):
            k = str(w).strip()
            if k and k not in seen:
                seen.add(k)
                out.append(k)
    return out

def _fam_counts_for_level(lang: str, level: int) -> dict:
    words = _level_unique_words(lang, level)
    return _fam_counts_for_words(words, lang)

def _fam_counts_for_words(words: list, lang: str) -> dict:
    counts = {str(i): 0 for i in range(6)}
    if not words:
        return counts
    try:
        conn = get_db(); cur = conn.cursor()
        # Batch fetch by IN clause; fall back to chunks if large
        CH = 400
        missing = set(words)
        found_words = 0
        for i in range(0, len(words), CH):
            batch = words[i:i+CH]
            ph = ','.join('?' for _ in batch)
            q = f'SELECT word FROM words WHERE (language=? OR ?="") AND word IN ({ph})'
            rows = cur.execute(q, (lang, lang, *batch)).fetchall()
            for r in rows:
                w = (r['word'] or '').strip()
                # Since familiarity is now user-specific, we can't get it from global table
                # All words in global table are considered unknown (0) for global stats
                counts['0'] += 1
                found_words += 1
                if w in missing:
                    missing.remove(w)
        conn.close()
        # Words not found in DB count as 0 (unknown)
        if missing:
            counts['0'] += len(missing)
        
    except Exception:
        pass
    return counts

# --- STUB endpoint for /api/level/finish to avoid 405 and allow frontend to proceed ---
@levels_bp.post('/api/level/finish')
def api_level_finish():
    data = request.get_json(silent=True) or {}
    req_lang = (data.get('language') or '').strip() or None
    run_id = int(data.get('run_id') or 0)
    if not run_id:
        return jsonify({'success': False, 'error': 'run_id required'}), 400

    # Get user context from middleware
    user_context = get_user_context()
    user_id = user_context['user_id']
    is_authenticated = user_id is not None
    
    # If not authenticated via middleware, try to get user from Authorization header
    if not is_authenticated:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            session_token = auth_header[7:]
            from server.db_multi_user import get_user_by_session_token
            user = get_user_by_session_token(session_token)
            if user:
                user_id = user['id']
                is_authenticated = True

    from server.db import get_db
    conn = get_db()
    row = conn.execute('SELECT level, items, score FROM level_runs WHERE id=?', (run_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'success': False, 'error': 'run not found'}), 404

    try: items = json.loads(row['items'] or '[]')
    except Exception: items = []
    all_words = _unique_words_from_items(items)

    lang_level = _find_level_file_for_run(run_id)
    if lang_level:
        tl, lvl_val, fs = lang_level
    else:
        tl, lvl_val, fs = None, int(row['level'] or 0), None
    if req_lang and not tl:
        tl = req_lang

    # Prefer counting based on the exact level-word list to avoid tokenization drift
    fam_counts = {str(i):0 for i in range(6)}
    if tl and lvl_val:
        fam_counts = _fam_counts_for_level(tl, lvl_val)
        # Fallback if level file had no items
        if sum(fam_counts.values()) == 0 and all_words:
            fam_counts = fam_counts_for_words(all_words, tl)
    else:
        fam_counts = fam_counts_for_words(all_words, tl)

    # Only save results if user is authenticated
    if is_authenticated and tl and lvl_val:
        # Save to user-specific data
        try:
            from server.db import update_user_progress, update_user_word_familiarity
            
            # Update user progress
            score = float(row['score']) if row['score'] is not None else 0.0
            # If score is 0.0 (None), assume the level was completed with a default score
            if score == 0.0:
                score = 0.8  # Default completion score
            status = 'completed' if score > 0.6 else 'in_progress'
            
            # Get native language for user
            from server.db_multi_user import get_user_native_language
            native_language = get_user_native_language(user_id)
            
            update_user_progress(
                user_id=user_id,
                language=tl,
                level=lvl_val,
                status=status,
                score=score,
                native_language=native_language
            )
            
            # Update word familiarity for learned words (familiarity = 5)
            learned_words = fam_counts.get('5', 0)
            if learned_words > 0:
                # Get words for this level
                from server.db import get_db
                conn = get_db()
                cursor = conn.execute("""
                    SELECT id FROM words 
                    WHERE language = ? AND level = ?
                """, (tl, lvl_val))
                word_ids = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                # Update word familiarity for each word
                for word_id in word_ids:
                    update_user_word_familiarity(
                        user_id=user_id,
                        word_id=word_id,
                        familiarity=5
                    )
            
            print(f"Level {lvl_val} results saved for user {user_id} (score: {score}, status: {status})")
            
        except Exception as e:
            print(f"Error saving user progress: {e}")
            # Continue execution even if user data saving fails
    else:
        # User not authenticated - don't save results anywhere
        print(f"Level {lvl_val} completed by unauthenticated user - results not saved")

    return jsonify({'success': True, 'run_id': run_id, 'fam_counts': fam_counts})

@levels_bp.post('/api/level/submit_mc')
def api_level_submit_mc():
    """Submit multiple choice answer for a standard level"""
    try:
        # Get user context from middleware
        user_context = get_user_context()
        user_id = user_context['user_id']
        is_authenticated = user_id is not None
        
        # If not authenticated via middleware, try to get user from Authorization header
        if not is_authenticated:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                session_token = auth_header[7:]
                from server.db_multi_user import get_user_by_session_token
                user = get_user_by_session_token(session_token)
                if user:
                    user_id = user['id']
                    is_authenticated = True
        
        payload = request.get_json(force=True) or {}
        run_id = payload.get('run_id')
        idx = payload.get('idx')
        word = payload.get('word')
        correct = payload.get('correct', False)
        
        if not run_id:
            return jsonify({'success': False, 'error': 'run_id required'}), 400
        
        # For standard levels, we don't need to do much - just return success
        # The actual scoring is handled in the level finish endpoint
        print(f"MC answer submitted for run {run_id}, word: {word}, correct: {correct}")
        
        return jsonify({'success': True, 'message': 'MC answer recorded'})
        
    except Exception as e:
        print(f"Error in api_level_submit_mc: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Level Rating System removed - replaced with attractive evaluation display

############################
# Custom Level Groups API
############################

@custom_levels_bp.post('/api/custom-level-groups/create')
@require_auth()
def api_create_custom_level_group():
    """Create a new custom level group with AI-generated content"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        payload = request.get_json(force=True) or {}
        group_name = (payload.get('group_name') or '').strip()
        context_description = (payload.get('context_description') or '').strip()
        language = (payload.get('language') or '').strip()
        native_language = (payload.get('native_language') or '').strip()
        cefr_level = (payload.get('cefr_level') or 'A1').strip()
        num_levels = int(payload.get('num_levels', 10))
        
        if not all([group_name, context_description, language, native_language]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if num_levels < 1 or num_levels > 20:
            return jsonify({'success': False, 'error': 'Number of levels must be between 1 and 20'}), 400
        
        # Create the level group
        group_id = create_custom_level_group(
            user_id=user_id,
            language=language,
            native_language=native_language,
            group_name=group_name,
            context_description=context_description,
            cefr_level=cefr_level,
            num_levels=num_levels
        )
        
        if not group_id:
            return jsonify({'success': False, 'error': 'Failed to create level group'}), 500
        
        # Generate AI-powered levels
        success = generate_custom_levels(
            group_id=group_id,
            language=language,
            native_language=native_language,
            context_description=context_description,
            cefr_level=cefr_level,
            num_levels=num_levels
        )
        
        if not success:
            # Clean up the group if level generation failed
            delete_custom_level_group(group_id, user_id)
            return jsonify({'success': False, 'error': 'Failed to generate levels'}), 500
        
        return jsonify({
            'success': True,
            'group_id': group_id,
            'message': f'Custom level group "{group_name}" created successfully with {num_levels} levels'
        })
        
    except Exception as e:
        print(f"Error creating custom level group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/custom-level-groups')
@require_auth()
def api_get_custom_level_groups():
    """Get all custom level groups for the current user"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        language = request.args.get('language', '').strip()
        native_language = request.args.get('native_language', '').strip()
        
        groups = get_custom_level_groups(user_id, language if language else None, native_language if native_language else None)
        
        return jsonify({
            'success': True,
            'groups': groups
        })
        
    except Exception as e:
        print(f"Error getting custom level groups: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/custom-level-groups/<int:group_id>')
@require_auth()
def api_get_custom_level_group(group_id):
    """Get a specific custom level group"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        group = get_custom_level_group(group_id, user_id)
        
        if not group:
            return jsonify({'success': False, 'error': 'Level group not found'}), 404
        
        # Get all levels for this group
        levels = get_custom_levels_for_group(group_id)
        
        # Skip word processing for now - will be done on-demand when levels are accessed
        # This dramatically improves loading speed from ~1 minute to ~2 seconds
        print(f"📚 Loaded {len(levels)} levels for group {group_id} (word processing deferred for performance)")
        
        return jsonify({
            'success': True,
            'group': group,
            'levels': levels
        })
        
    except Exception as e:
        print(f"Error getting custom level group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/custom-level-groups/<int:group_id>/levels/<int:level_number>')
@require_auth()
def api_get_custom_level(group_id, level_number):
    """Get a specific custom level"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Verify ownership
        group = get_custom_level_group(group_id, user_id)
        if not group:
            return jsonify({'success': False, 'error': 'Level group not found'}), 404
        
        level = get_custom_level(group_id, level_number)
        
        if not level:
            return jsonify({'success': False, 'error': 'Level not found'}), 404
        
        # Ensure all words from this custom level are added to user's familiarity database
        try:
            language = group.get('language', 'en')
            native_language = group.get('native_language', 'de')
            
            # Extract words from level content
            level_words = []
            if level.get('content') and level['content'].get('items'):
                for item in level['content']['items']:
                    words = item.get('words', [])
                    for word in words:
                        if word and word.strip():
                            level_words.append(word.strip().lower())
            
            # Ensure words exist in global database and add to user's familiarity database
            if level_words:
                print(f"🔤 Ensuring {len(level_words)} words from custom level {group_id}/{level_number} are in familiarity database")
                
                # Ensure words exist in global database
                ensure_words_exist(level_words, language, native_language)
                
                # Add words to user's familiarity database with default familiarity (0 = unknown)
                from server.db_multi_user import update_word_familiarity
                for word in level_words:
                    try:
                        # Get word ID from global database
                        from server.db import get_db
                        conn = get_db()
                        cursor = conn.execute("SELECT id FROM words WHERE word = ? AND language = ?", (word, language))
                        word_row = cursor.fetchone()
                        conn.close()
                        
                        if word_row:
                            word_id = word_row[0]
                            # Add to user's familiarity database with familiarity 0 (unknown)
                            print(f"🔧 Calling update_word_familiarity for user {user_id}, word '{word}', language '{language}', familiarity 0")
                            success = update_word_familiarity(user_id, word, language, 0)
                            if success:
                                print(f"✅ Added word '{word}' (ID: {word_id}) to user {user_id} familiarity database")
                            else:
                                print(f"❌ Failed to add word '{word}' to user {user_id} familiarity database")
                        else:
                            print(f"⚠️ Word '{word}' not found in global database")
                    except Exception as e:
                        print(f"⚠️ Error adding word '{word}' to familiarity database: {e}")
                        import traceback
                        traceback.print_exc()
                
                print(f"✅ Ensured all words from custom level {group_id}/{level_number} are in familiarity database")
            
        except Exception as e:
            print(f"⚠️ Error ensuring words in familiarity database: {e}")
            # Continue anyway - don't fail the level loading
        
        return jsonify({
            'success': True,
            'level': level
        })
        
    except Exception as e:
        print(f"Error getting custom level: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.delete('/api/custom-level-groups/<int:group_id>')
@require_auth()
def api_delete_custom_level_group(group_id):
    """Delete a custom level group"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        success = delete_custom_level_group(group_id, user_id)
        
        if not success:
            return jsonify({'success': False, 'error': 'Level group not found or could not be deleted'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Level group deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting custom level group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/custom-levels/<int:group_id>/<int:level_number>/progress')
@require_auth()
def api_get_custom_level_progress(group_id, level_number):
    """Get progress data for a custom level"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Get custom level data
        level_data = get_custom_level(group_id, level_number, user_id)
        if not level_data:
            return jsonify({'success': False, 'error': 'Level not found'}), 404
        
        # Get word count from database column (much faster than calculating)
        total_words = level_data.get('word_count', 0)
        
        # If no word count in database yet, calculate and store it
        if total_words == 0 and level_data.get('content') and level_data['content'].get('items'):
            from server.db import calculate_and_update_word_count
            total_words = calculate_and_update_word_count(group_id, level_number, level_data['content'])
        
        # If still no content (ultra-lazy loading), use estimated values
        if total_words == 0:
            total_words = 25  # Estimated for ultra-lazy levels
        
        # Get actual progress data from user's local database
        completed_words = 0
        level_score = 0.0
        status = 'not_started'
        fam_counts = {'0': total_words, '1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        
        # Try to get real familiarity data from user's local database
        try:
            from server.db_multi_user import get_user_familiarity_counts_for_words
            
            # Get group info for language context
            from server.services.custom_levels import get_custom_level_group
            group_data = get_custom_level_group(group_id, user_id)
            if group_data:
                language = group_data.get('language', 'en')
                native_language = group_data.get('native_language', 'de')
                
                # Get words from level content
                level_words = []
                if level_data.get('content') and level_data['content'].get('items'):
                    for item in level_data['content']['items']:
                        words = item.get('words', [])
                        for word in words:
                            if word and word.strip():
                                level_words.append(word.strip().lower())
                
                # Get familiarity counts for these words
                if level_words:
                    user_fam_counts = get_user_familiarity_counts_for_words(user_id, level_words, language, native_language)
                    if user_fam_counts:
                        fam_counts = user_fam_counts
                        completed_words = fam_counts.get('5', 0)  # Level 5 = learned
                        
                        # Calculate level score based on familiarity distribution
                        total_familiarity = sum(fam_counts.values())
                        if total_familiarity > 0:
                            # Weight: Level 5 = 100%, Level 4 = 80%, Level 3 = 60%, Level 2 = 40%, Level 1 = 20%
                            weighted_score = (
                                fam_counts.get('5', 0) * 1.0 +
                                fam_counts.get('4', 0) * 0.8 +
                                fam_counts.get('3', 0) * 0.6 +
                                fam_counts.get('2', 0) * 0.4 +
                                fam_counts.get('1', 0) * 0.2
                            ) / total_familiarity
                            level_score = weighted_score
                            
                            # Determine status based on score
                            if level_score >= 0.6:
                                status = 'completed'
                            elif level_score > 0:
                                status = 'in_progress'
                            else:
                                status = 'not_started'
                        
        except Exception as e:
            print(f"Error getting user familiarity data for custom level: {e}")
            # Fallback to default values
        
        return jsonify({
            'success': True,
            'completed_words': completed_words,
            'total_words': total_words,
            'level_score': level_score,
            'status': status,
            'fam_counts': fam_counts
        })
        
    except Exception as e:
        print(f"Error getting custom level progress: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/custom-levels/<int:group_id>/bulk-stats')
@require_auth()
def api_get_custom_level_bulk_stats(group_id):
    """Get bulk progress stats for all levels in a custom group"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Get custom level group data
        from server.services.custom_levels import get_custom_level_group
        group_data = get_custom_level_group(group_id, user_id)
        if not group_data:
            return jsonify({'success': False, 'error': 'Group not found'}), 404
        
        # Get all levels in the group (assuming 10 levels per group)
        levels_data = {}
        for level_num in range(1, 11):  # Assuming 10 levels per group
            level_data = get_custom_level(group_id, level_num, user_id)
            if level_data:
                # Get word count from database column (much faster than calculating)
                total_words = level_data.get('word_count', 0)
                fam_counts = {'0': 0, '1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                
                if level_data.get('content'):
                    content = level_data['content']
                    
                    # If no word count in database yet, calculate and store it
                    if total_words == 0 and content.get('items'):
                        from server.db import calculate_and_update_word_count
                        total_words = calculate_and_update_word_count(group_id, level_num, content)
                    
                    # Get actual fam_counts from content
                    if content.get('fam_counts'):
                        fam_counts = content['fam_counts']
                    elif total_words > 0:
                        # If no fam_counts but has words, initialize with all words as unknown
                        fam_counts = {'0': total_words, '1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                
                # If no content yet (ultra-lazy loading), use estimated values
                if total_words == 0:
                    total_words = 25  # Estimated for ultra-lazy levels
                    fam_counts = {'0': 25, '1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                
                # Try to get real familiarity data from user's local database
                try:
                    from server.db_multi_user import get_user_familiarity_counts_for_words
                    
                    language = group_data.get('language', 'en')
                    native_language = group_data.get('native_language', 'de')
                    
                    # Get words from level content
                    level_words = []
                    if level_data.get('content') and level_data['content'].get('items'):
                        for item in level_data['content']['items']:
                            words = item.get('words', [])
                            for word in words:
                                if word and word.strip():
                                    level_words.append(word.strip().lower())
                    
                    # Get familiarity counts for these words
                    if level_words:
                        # First, ensure all words are in the user's familiarity database
                        print(f"🔤 Bulk stats: Ensuring {len(level_words)} words from custom level {group_id}/{level_num} are in familiarity database")
                        
                        # Ensure words exist in global database
                        ensure_words_exist(level_words, language, native_language)
                        
                        # Add words to user's familiarity database with default familiarity (0 = unknown)
                        from server.db_multi_user import update_word_familiarity
                        for word in level_words:
                            try:
                                # Get word ID from global database
                                from server.db_config import get_database_config, get_db_connection, execute_query
                                config = get_database_config()
                                conn = get_db_connection()
                                
                                try:
                                    if config['type'] == 'postgresql':
                                        result = execute_query(conn, "SELECT id FROM words WHERE word = %s AND language = %s", (word, language))
                                        word_row = result.fetchone()
                                    else:
                                        cursor = conn.execute("SELECT id FROM words WHERE word = ? AND language = ?", (word, language))
                                        word_row = cursor.fetchone()
                                    
                                    if word_row:
                                        if config['type'] == 'postgresql':
                                            word_id = word_row['id']
                                        else:
                                            word_id = word_row[0]
                                finally:
                                    conn.close()
                                
                                if word_row:
                                    # Add to user's familiarity database with familiarity 0 (unknown)
                                    print(f"🔧 Bulk stats: Calling update_word_familiarity for user {user_id}, word '{word}', language '{language}', familiarity 0")
                                    success = update_word_familiarity(user_id, word, language, 0)
                                    if success:
                                        print(f"✅ Bulk stats: Added word '{word}' (ID: {word_id}) to user {user_id} familiarity database")
                                    else:
                                        print(f"❌ Bulk stats: Failed to add word '{word}' to user {user_id} familiarity database")
                                else:
                                    print(f"⚠️ Bulk stats: Word '{word}' not found in global database")
                            except Exception as e:
                                print(f"⚠️ Bulk stats: Error adding word '{word}' to familiarity database: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Now get familiarity counts for these words
                        user_fam_counts = get_user_familiarity_counts_for_words(user_id, level_words, language, native_language)
                        if user_fam_counts:
                            fam_counts = user_fam_counts
                            
                            # Calculate level score based on familiarity distribution
                            total_familiarity = sum(fam_counts.values())
                            if total_familiarity > 0:
                                # Weight: Level 5 = 100%, Level 4 = 80%, Level 3 = 60%, Level 2 = 40%, Level 1 = 20%
                                weighted_score = (
                                    fam_counts.get('5', 0) * 1.0 +
                                    fam_counts.get('4', 0) * 0.8 +
                                    fam_counts.get('3', 0) * 0.6 +
                                    fam_counts.get('2', 0) * 0.4 +
                                    fam_counts.get('1', 0) * 0.2
                                ) / total_familiarity
                                
                                # Determine status based on score
                                if weighted_score >= 0.6:
                                    status = 'completed'
                                elif weighted_score > 0:
                                    status = 'in_progress'
                                else:
                                    status = 'not_started'
                                
                                levels_data[level_num] = {
                                    'success': True,
                                    'status': status,
                                    'last_score': weighted_score,
                                    'fam_counts': fam_counts,
                                    'total_words': total_words,
                                    'user_progress': {
                                        'status': status,
                                        'score': weighted_score
                                    }
                                }
                            else:
                                levels_data[level_num] = {
                                    'success': True,
                                    'status': 'not_started',
                                    'last_score': 0.0,
                                    'fam_counts': fam_counts,
                                    'total_words': total_words,
                                    'user_progress': {
                                        'status': 'not_started',
                                        'score': 0.0
                                    }
                                }
                        else:
                            levels_data[level_num] = {
                                'success': True,
                                'status': 'not_started',
                                'last_score': 0.0,
                                'fam_counts': fam_counts,
                                'total_words': total_words,
                                'user_progress': {
                                    'status': 'not_started',
                                    'score': 0.0
                                }
                            }
                    else:
                        levels_data[level_num] = {
                            'success': True,
                            'status': 'not_started',
                            'last_score': 0.0,
                            'fam_counts': fam_counts,
                            'total_words': total_words,
                            'user_progress': {
                                'status': 'not_started',
                                'score': 0.0
                            }
                        }
                        
                except Exception as e:
                    print(f"Error getting user familiarity data for custom level {level_num}: {e}")
                    # Fallback to default values
                    levels_data[level_num] = {
                        'success': True,
                        'status': 'not_started',
                        'last_score': 0.0,
                        'fam_counts': fam_counts,
                        'total_words': total_words,
                        'user_progress': {
                            'status': 'not_started',
                            'score': 0.0
                        }
                    }
        
        return jsonify({
            'success': True,
            'levels': levels_data
        })
        
    except Exception as e:
        print(f"Error getting custom level bulk stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/<int:level_number>/generate-content')
@require_auth(optional=True)
def api_generate_custom_level_content(group_id, level_number):
    """Generate content for a custom level (sentences and word enrichment)"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        # For custom level content generation, authentication is optional
        # This allows the feature to work even without login
        
        # Get custom level data
        level_data = get_custom_level(group_id, level_number, user_id)
        if not level_data:
            return jsonify({'success': False, 'error': 'Level not found'}), 404
        
        content = level_data.get('content', {})
        
        # Check if content generation is needed
        if not content.get('ultra_lazy_loading', False) or content.get('sentences_generated', False):
            return jsonify({'success': True, 'message': 'Content already generated'})
        
        # Get group info for language context
        from server.services.custom_levels import get_custom_level_group
        group_data = get_custom_level_group(group_id, user_id)
        if not group_data:
            return jsonify({'success': False, 'error': 'Group not found'}), 404
        
        language = group_data.get('language', 'en')
        native_language = group_data.get('native_language', 'de')
        
        # Trigger content generation
        from server.services.custom_levels import enrich_custom_level_words_on_demand
        success = enrich_custom_level_words_on_demand(group_id, level_number, language, native_language)
        
        if success:
            return jsonify({'success': True, 'message': 'Content generated successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to generate content'}), 500
        
    except Exception as e:
        print(f"Error generating custom level content: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/generate-specific-content')
@require_auth(optional=True)
def api_generate_specific_custom_levels_content(group_id):
    """Generate content for specific custom levels (for immediate generation)"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        # Get request data
        payload = request.get_json(force=True) or {}
        level_numbers = payload.get('level_numbers', [])
        
        if not level_numbers:
            return jsonify({'success': False, 'error': 'No level numbers provided'}), 400
        
        # Get group info
        from server.services.custom_levels import get_custom_level_group, get_custom_levels_for_group
        group_data = get_custom_level_group(group_id, user_id)
        if not group_data:
            return jsonify({'success': False, 'error': 'Group not found'}), 404
        
        # Get all levels for this group
        levels = get_custom_levels_for_group(group_id)
        if not levels:
            return jsonify({'success': False, 'error': 'No levels found'}), 404
        
        # Filter to only the requested levels that need generation
        levels_needing_generation = []
        for level in levels:
            if level['level_number'] in level_numbers:
                content = level.get('content', {})
                if content.get('ultra_lazy_loading', False) and not content.get('sentences_generated', False):
                    levels_needing_generation.append(level)
        
        if not levels_needing_generation:
            return jsonify({'success': True, 'message': 'Requested levels already have content generated'})
        
        language = group_data.get('language', 'en')
        native_language = group_data.get('native_language', 'de')
        
        print(f"🚀 Starting specific content generation for {len(levels_needing_generation)} levels: {[l['level_number'] for l in levels_needing_generation]}")
        
        # Generate content for specific levels in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from server.services.custom_levels import enrich_custom_level_words_on_demand
        
        results = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit generation tasks for specific levels only
            future_to_level = {
                executor.submit(enrich_custom_level_words_on_demand, group_id, level['level_number'], language, native_language): level
                for level in levels_needing_generation
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_level):
                level = future_to_level[future]
                try:
                    success = future.result()
                    results.append({
                        'level_number': level['level_number'],
                        'success': success
                    })
                    if success:
                        print(f"✅ Generated content for level {level['level_number']}")
                    else:
                        print(f"❌ Failed to generate content for level {level['level_number']}")
                except Exception as e:
                    print(f"❌ Exception generating content for level {level['level_number']}: {e}")
                    results.append({
                        'level_number': level['level_number'],
                        'success': False,
                        'error': str(e)
                    })
        
        # Count successes and failures
        successful = len([r for r in results if r['success']])
        failed = len([r for r in results if not r['success']])
        
        print(f"🎉 Specific content generation complete: {successful} successful, {failed} failed")
        
        return jsonify({
            'success': True,
            'message': f'Generated content for {successful} specific levels',
            'results': results,
            'successful': successful,
            'failed': failed
        })
        
    except Exception as e:
        print(f"Error generating specific custom level content: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/custom-levels/<int:group_id>/progress-cache')
@require_auth()
def api_get_custom_level_group_progress_cache(group_id):
    """Get cached progress data for all levels in a custom group (ultra-fast)"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        from server.db_progress_cache import (
            create_custom_level_progress_table,
            get_custom_level_group_progress,
            refresh_custom_level_group_progress,
        )

        # Ensure cache table exists
        create_custom_level_progress_table()
        
        # Get cached progress data for all levels in the group
        print(f"🔎 progress-cache: user_id={user_id}, group_id={group_id} - reading cache")
        progress_data = get_custom_level_group_progress(user_id, group_id)
        print(f"🔎 progress-cache: initial cached_levels={len(progress_data)}")

        # If cache is empty, refresh it once on-demand
        if not progress_data:
            print(f"🔁 progress-cache: empty cache detected → refreshing for user={user_id}, group={group_id}")
            refreshed = refresh_custom_level_group_progress(user_id, group_id)
            print(f"🔁 progress-cache: refresh result={refreshed}")
            if refreshed:
                progress_data = get_custom_level_group_progress(user_id, group_id)
                print(f"🔁 progress-cache: post-refresh cached_levels={len(progress_data)}")
        
        print(f"🚀 Returning cached progress data for group {group_id}: {len(progress_data)} levels")
        
        return jsonify({
            'success': True,
            'progress_data': progress_data,
            'cached_levels': len(progress_data)
        })
        
    except Exception as e:
        print(f"Error getting custom level group progress cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/refresh-progress-cache')
@require_auth()
def api_refresh_custom_level_group_progress_cache(group_id):
    """Refresh cached progress data for all levels in a custom group"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        from server.db_progress_cache import refresh_custom_level_group_progress
        
        # Refresh cached progress data
        success = refresh_custom_level_group_progress(user_id, group_id)
        
        if success:
            print(f"✅ Refreshed progress cache for group {group_id}")
            return jsonify({
                'success': True,
                'message': 'Progress cache refreshed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to refresh progress cache'
            }), 500
        
    except Exception as e:
        print(f"Error refreshing custom level group progress cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/sync-words')
@require_auth()
def api_sync_custom_level_words(group_id):
    """Sync words from custom level to PostgreSQL words and user_word_familiarity tables"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Get group info
        from server.services.custom_levels import get_custom_level_group, get_custom_levels_for_group, sync_custom_level_words_to_postgresql
        
        group_data = get_custom_level_group(group_id, user_id)
        if not group_data:
            return jsonify({'success': False, 'error': 'Group not found'}), 404
        
        # Get all levels for this group
        levels = get_custom_levels_for_group(group_id)
        if not levels:
            return jsonify({'success': False, 'error': 'No levels found'}), 404
        
        language = group_data.get('language', 'en')
        native_language = group_data.get('native_language', 'de')
        
        print(f"🔄 Starting word sync for group {group_id} with {len(levels)} levels")
        
        # Sync words for all levels that have content
        synced_levels = 0
        total_words_synced = 0
        total_user_words_added = 0
        
        for level in levels:
            content = level.get('content', {})
            if content and content.get('items'):
                success = sync_custom_level_words_to_postgresql(
                    group_id, level['level_number'], content, language, native_language
                )
                if success:
                    synced_levels += 1
        
        print(f"🎉 Word sync complete: {synced_levels} levels synced")
        
        return jsonify({
            'success': True,
            'message': f'Successfully synced words for {synced_levels} levels',
            'synced_levels': synced_levels,
            'total_levels': len(levels)
        })
        
    except Exception as e:
        print(f"Error syncing custom level words: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/generate-all-content')
@require_auth(optional=True)
def api_generate_all_custom_levels_content(group_id):
    """Generate content for all custom levels in a group (batch processing for optimal performance)"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        # Get group info
        from server.services.custom_levels import get_custom_level_group, get_custom_levels_for_group
        group_data = get_custom_level_group(group_id, user_id)
        if not group_data:
            return jsonify({'success': False, 'error': 'Group not found'}), 404
        
        # Get all levels for this group
        levels = get_custom_levels_for_group(group_id)
        if not levels:
            return jsonify({'success': False, 'error': 'No levels found'}), 404
        
        # Filter levels that need content generation
        levels_needing_generation = []
        for level in levels:
            content = level.get('content', {})
            if content.get('ultra_lazy_loading', False) and not content.get('sentences_generated', False):
                levels_needing_generation.append(level)
        
        if not levels_needing_generation:
            return jsonify({'success': True, 'message': 'All levels already have content generated'})
        
        language = group_data.get('language', 'en')
        native_language = group_data.get('native_language', 'de')
        
        print(f"🚀 Starting batch content generation for {len(levels_needing_generation)} levels in group {group_id}")
        
        # Generate content for all levels in parallel for optimal performance
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from server.services.custom_levels import enrich_custom_level_words_on_demand
        
        results = []
        with ThreadPoolExecutor(max_workers=2) as executor:  # Reduced concurrency for faster individual completion
            # Submit all generation tasks
            future_to_level = {
                executor.submit(enrich_custom_level_words_on_demand, group_id, level['level_number'], language, native_language): level
                for level in levels_needing_generation
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_level):
                level = future_to_level[future]
                try:
                    success = future.result()
                    results.append({
                        'level_number': level['level_number'],
                        'success': success
                    })
                    if success:
                        print(f"✅ Generated content for level {level['level_number']}")
                    else:
                        print(f"❌ Failed to generate content for level {level['level_number']}")
                except Exception as e:
                    print(f"❌ Exception generating content for level {level['level_number']}: {e}")
                    results.append({
                        'level_number': level['level_number'],
                        'success': False,
                        'error': str(e)
                    })
        
        # Count successes and failures
        successful = len([r for r in results if r['success']])
        failed = len([r for r in results if not r['success']])
        
        print(f"🎉 Batch content generation complete: {successful} successful, {failed} failed")
        
        return jsonify({
            'success': True,
            'message': f'Generated content for {successful} levels',
            'results': results,
            'successful': successful,
            'failed': failed
        })
        
    except Exception as e:
        print(f"Error in batch content generation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/custom-levels/<int:group_id>/<int:level_number>/familiarity')
@require_auth()
def api_get_custom_level_familiarity(group_id, level_number):
    """Get familiarity data for a custom level"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Get custom level data
        level_data = get_custom_level(group_id, level_number, user_id)
        if not level_data:
            return jsonify({'success': False, 'error': 'Level not found'}), 404
        
        # For now, return default familiarity counts (no familiarity tracking implemented yet)
        # TODO: Implement actual familiarity tracking for custom levels
        return jsonify({
            'success': True,
            'familiarity_counts': {'0': 0, '1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        })
        
    except Exception as e:
        print(f"Error getting custom level familiarity: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/migrate-to-multi-user')
@require_auth()
def api_migrate_custom_levels_to_multi_user():
    """Migrate all existing custom levels to Multi-User-DB compatibility"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Only allow admin users to run migration (you can customize this check)
        # For now, we'll allow any authenticated user, but you might want to add admin check
        
        from server.services.custom_levels import migrate_existing_custom_levels_to_multi_user
        
        print(f"🔄 User {user_id} initiated custom level migration")
        migration_stats = migrate_existing_custom_levels_to_multi_user()
        
        return jsonify({
            'success': True,
            'message': 'Custom level migration completed',
            'stats': migration_stats
        })
        
    except Exception as e:
        print(f"Error during custom level migration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Custom Level Lesson API Endpoints
@custom_levels_bp.post('/api/custom-level-groups/<int:group_id>/publish')
@require_auth()
def api_publish_custom_level_group(group_id):
    """Publish a custom level group to the marketplace"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Verify ownership
        group = get_custom_level_group(group_id, user_id)
        if not group:
            return jsonify({'success': False, 'error': 'Level group not found'}), 404
        
        # Update group status to published
        success = update_custom_level_group(group_id, user_id, status='published')
        
        if not success:
            return jsonify({'success': False, 'error': 'Failed to publish group'}), 500
        
        return jsonify({
            'success': True,
            'message': 'Level group published successfully'
        })
        
    except Exception as e:
        print(f"Error publishing custom level group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-level-groups/<int:group_id>/unpublish')
@require_auth()
def api_unpublish_custom_level_group(group_id):
    """Unpublish a custom level group from the marketplace"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Verify ownership
        group = get_custom_level_group(group_id, user_id)
        if not group:
            return jsonify({'success': False, 'error': 'Level group not found'}), 404
        
        # Update group status to active (unpublished)
        success = update_custom_level_group(group_id, user_id, status='active')
        
        if not success:
            return jsonify({'success': False, 'error': 'Failed to unpublish group'}), 500
        
        return jsonify({
            'success': True,
            'message': 'Level group unpublished successfully'
        })
        
    except Exception as e:
        print(f"Error unpublishing custom level group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/marketplace/custom-level-groups')
@require_auth(optional=True)
def api_get_marketplace_custom_level_groups():
    """Get all published custom level groups for the marketplace"""
    try:
        # Get query parameters
        language = request.args.get('language', 'en')
        native_language = request.args.get('native_language', 'de')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        # Get published custom level groups
        conn = get_db()
        try:
            cursor = conn.execute('''
                SELECT clg.*, u.username as author_name
                FROM custom_level_groups clg
                LEFT JOIN users u ON clg.user_id = u.id
                WHERE clg.status = 'published'
                AND clg.language = ?
                AND clg.native_language = ?
                ORDER BY clg.created_at DESC
                LIMIT ? OFFSET ?
            ''', (language, native_language, limit, offset))
            
            groups = []
            for row in cursor.fetchall():
                group_data = dict(row)
                # Add level count
                level_count = conn.execute(
                    'SELECT COUNT(*) as count FROM custom_levels WHERE group_id = ?',
                    (group_data['id'],)
                ).fetchone()
                group_data['num_levels'] = level_count['count'] if level_count else 0
                groups.append(group_data)
            
            # Get total count
            total_count = conn.execute('''
                SELECT COUNT(*) as count FROM custom_level_groups 
                WHERE status = 'published' AND language = ? AND native_language = ?
            ''', (language, native_language)).fetchone()
            
            return jsonify({
                'success': True,
                'groups': groups,
                'total': total_count['count'] if total_count else 0,
                'limit': limit,
                'offset': offset
            })
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"Error getting marketplace custom level groups: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/marketplace/custom-level-groups/<int:group_id>')
@require_auth(optional=True)
def api_get_marketplace_custom_level_group(group_id):
    """Get a specific published custom level group for marketplace preview"""
    try:
        # Get published custom level group
        conn = get_db()
        try:
            cursor = conn.execute('''
                SELECT clg.*, u.username as author_name
                FROM custom_level_groups clg
                LEFT JOIN users u ON clg.user_id = u.id
                WHERE clg.id = ? AND clg.status = 'published'
            ''', (group_id,))
            
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'Group not found or not published'}), 404
            
            group_data = dict(row)
            
            # Get all levels for this group
            levels = get_custom_levels_for_group(group_id)
            
            return jsonify({
                'success': True,
                'group': group_data,
                'levels': levels
            })
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"Error getting marketplace custom level group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/marketplace/custom-level-groups/<int:group_id>/import')
@require_auth()
def api_import_marketplace_custom_level_group(group_id):
    """Import a published custom level group to user's library"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Get the published group
        conn = get_db()
        try:
            cursor = conn.execute('''
                SELECT * FROM custom_level_groups 
                WHERE id = ? AND status = 'published'
            ''', (group_id,))
            
            original_group = cursor.fetchone()
            if not original_group:
                return jsonify({'success': False, 'error': 'Group not found or not published'}), 404
            
            # Check if user already has a group with the same name
            existing_group = conn.execute('''
                SELECT id FROM custom_level_groups 
                WHERE user_id = ? AND group_name = ? AND language = ? AND native_language = ?
            ''', (user_id, original_group['group_name'], original_group['language'], original_group['native_language'])).fetchone()
            
            if existing_group:
                return jsonify({'success': False, 'error': 'You already have a group with this name'}), 400
            
            # Create a copy of the group for the user
            now = datetime.now(UTC).isoformat()
            cursor = conn.execute('''
                INSERT INTO custom_level_groups 
                (user_id, language, native_language, group_name, context_description, 
                 cefr_level, num_levels, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            ''', (user_id, original_group['language'], original_group['native_language'], 
                  original_group['group_name'], original_group['context_description'],
                  original_group['cefr_level'], original_group['num_levels'], now, now))
            
            new_group_id = cursor.lastrowid
            
            # Copy all levels from the original group
            original_levels = conn.execute('''
                SELECT * FROM custom_levels WHERE group_id = ?
            ''', (group_id,)).fetchall()
            
            for level in original_levels:
                conn.execute('''
                    INSERT INTO custom_levels 
                    (group_id, level_number, title, topic, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (new_group_id, level['level_number'], level['title'], 
                      level['topic'], level['content'], now, now))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Group imported successfully',
                'group_id': new_group_id
            })
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"Error importing marketplace custom level group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/<int:level_number>/start')
@require_auth(optional=True)
def api_start_custom_level(group_id, level_number):
    """Start a custom level lesson with lazy loading word enrichment"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        # For custom level start, authentication is optional
        # This allows the feature to work even without login
        
        # Get custom level data
        level_data = get_custom_level(group_id, level_number, user_id)
        if not level_data:
            return jsonify({'success': False, 'error': 'Level not found'}), 404
        
        # Check if this level needs lazy loading word enrichment
        content = level_data.get('content', {})
        if content.get('lazy_loading', False):
            print(f"🚀 Triggering lazy loading word enrichment for custom level {group_id}/{level_number}")
            
            # Get group info for language context
            from server.services.custom_levels import get_custom_level_group
            group_data = get_custom_level_group(group_id, user_id)
            if group_data:
                language = group_data.get('language', 'en')
                native_language = group_data.get('native_language', 'de')
                
                # Trigger word enrichment for this level
                from server.services.custom_levels import enrich_custom_level_words_on_demand
                success = enrich_custom_level_words_on_demand(group_id, level_number, language, native_language)
                
                if success:
                    print(f"✅ Lazy loading word enrichment completed for level {group_id}/{level_number}")
                    # Reload the level data with enriched content
                    level_data = get_custom_level(group_id, level_number, user_id)
                else:
                    print(f"⚠️ Lazy loading word enrichment failed for level {group_id}/{level_number}, continuing with basic content")
        
        # Create a run_id for this custom level session
        import uuid
        run_id = str(uuid.uuid4())
        
        # Extract items from level content
        items = []
        if level_data.get('content') and level_data['content'].get('items'):
            items = level_data['content']['items']
        
        return jsonify({
            'success': True,
            'run_id': run_id,
            'items': items,
            'level': level_number,
            'language': level_data.get('language', 'en')
        })
        
    except Exception as e:
        print(f"Error starting custom level: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/<int:level_number>/submit')
@require_auth(optional=True)
def api_submit_custom_level(group_id, level_number):
    """Submit answers for a custom level"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        # For custom level submit, authentication is optional
        # This allows the feature to work even without login
        
        payload = request.get_json(force=True) or {}
        answers = payload.get('answers', [])
        
        # Get custom level data to compare with user answers
        level_data = get_custom_level(group_id, level_number, user_id)
        if not level_data:
            return jsonify({'success': False, 'error': 'Level not found'}), 404
        
        # Calculate actual similarity scores
        results = []
        items = level_data.get('content', {}).get('items', [])
        
        for answer in answers:
            idx = answer.get('idx', 0)
            user_translation = answer.get('translation', '').strip()
            
            # Find the corresponding item
            item = None
            for i, it in enumerate(items):
                if (it.get('idx') == idx or 
                    it.get('id') == idx or 
                    i == idx):
                    item = it
                    break
            
            if item:
                # Get the correct translation
                correct_translation = (item.get('text_native_ref') or 
                                     item.get('text_native') or 
                                     item.get('translation') or '')
                
                # Calculate similarity (simple word-based comparison)
                similarity = calculate_translation_similarity(user_translation, correct_translation)
                
                results.append({
                    'idx': idx,
                    'similarity': similarity,
                    'ref': correct_translation
                })
            else:
                # Fallback for missing items
                results.append({
                    'idx': idx,
                    'similarity': 0.0,
                    'ref': 'Item not found'
                })
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        print(f"Error submitting custom level: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/<int:level_number>/finish')
@require_auth(optional=True)
def api_finish_custom_level(group_id, level_number):
    """Finish a custom level"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        # For custom level finish, authentication is optional
        # This allows the feature to work even without login
        
        payload = request.get_json(force=True) or {}
        run_id = payload.get('run_id')
        score = payload.get('score', 0.0)
        
        # For now, just return success (no actual progress tracking implemented yet)
        return jsonify({
            'success': True,
            'message': 'Custom level completed',
            'score': score
        })
        
    except Exception as e:
        print(f"Error finishing custom level: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/<int:level_number>/enrich_batch')
@require_auth(optional=True)
def api_enrich_custom_level_words(group_id, level_number):
    """Enrich words for a custom level"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        # For word enrichment, authentication is optional
        # This allows the feature to work even without login
        
        payload = request.get_json(force=True) or {}
        words = payload.get('words', [])
        language = payload.get('language', 'en')
        native_language = payload.get('native_language', 'de')
        sentence_context = payload.get('sentence_context', '')
        sentence_native = payload.get('sentence_native', '')
        
        # Enrich words using LLM and store in global database
        enriched_count = 0
        for word in words:
            if not word or not word.strip():
                continue
                
            word = word.strip()
            
            # Check if word already exists in PostgreSQL words table
            try:
                from server.db_config import get_database_config, get_db_connection, execute_query
                
                config = get_database_config()
                conn = get_db_connection()
                
                try:
                    if config['type'] == 'postgresql':
                        result = execute_query(conn, '''
                            SELECT translation FROM words 
                            WHERE word = %s AND language = %s AND native_language = %s
                        ''', (word, language, native_language))
                        existing = result.fetchone()
                    else:
                        cur = conn.cursor()
                        existing = cur.execute('SELECT translation FROM words WHERE word=? AND language=? AND native_language=?', (word, language, native_language)).fetchone()
                    
                    if existing and existing.get('translation'):
                        # Word already has translation, skip
                        print(f"Word '{word}' already exists in words table, skipping enrichment")
                        continue
                        
                finally:
                    conn.close()
                    
            except Exception as e:
                print(f"Error checking existing word '{word}': {e}")
                continue
            
            try:
                # Use LLM to enrich the word
                from server.services.llm import llm_enrich_word
                enriched_data = llm_enrich_word(
                    word=word,
                    language=language,
                    native_language=native_language,
                    sentence_context=sentence_context
                )
                
                if enriched_data and enriched_data.get('translation'):
                    # Store in PostgreSQL words table
                    from server.db_config import get_database_config, get_db_connection, execute_query
                    import json
                    
                    config = get_database_config()
                    conn = get_db_connection()
                    
                    try:
                        # Prepare data for insertion
                        insert_data = {
                            'word': word,
                            'language': language,
                            'native_language': native_language,
                            'translation': enriched_data.get('translation', ''),
                            'example': enriched_data.get('example', ''),
                            'example_native': enriched_data.get('example_native', ''),
                            'lemma': enriched_data.get('lemma', ''),
                            'pos': enriched_data.get('pos', ''),
                            'ipa': enriched_data.get('ipa', ''),
                            'audio_url': enriched_data.get('audio_url', ''),
                            'gender': enriched_data.get('gender', 'none'),
                            'plural': enriched_data.get('plural', ''),
                            'conj': json.dumps(enriched_data.get('conj', {})) if enriched_data.get('conj') else None,
                            'comp': json.dumps(enriched_data.get('comp', {})) if enriched_data.get('comp') else None,
                            'synonyms': json.dumps(enriched_data.get('synonyms', [])) if enriched_data.get('synonyms') else None,
                            'collocations': json.dumps(enriched_data.get('collocations', [])) if enriched_data.get('collocations') else None,
                            'cefr': enriched_data.get('cefr', ''),
                            'freq_rank': enriched_data.get('freq_rank'),
                            'tags': json.dumps(enriched_data.get('tags', [])) if enriched_data.get('tags') else None,
                            'note': enriched_data.get('note', ''),
                            'info': json.dumps(enriched_data.get('info', {})) if enriched_data.get('info') else None
                        }
                        
                        if config['type'] == 'postgresql':
                            execute_query(conn, '''
                                INSERT INTO words (
                                    word, language, native_language, translation, example, example_native,
                                    lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                                    collocations, cefr, freq_rank, tags, note, info
                                ) VALUES (
                                    %(word)s, %(language)s, %(native_language)s, %(translation)s, %(example)s, %(example_native)s,
                                    %(lemma)s, %(pos)s, %(ipa)s, %(audio_url)s, %(gender)s, %(plural)s, %(conj)s, %(comp)s, %(synonyms)s,
                                    %(collocations)s, %(cefr)s, %(freq_rank)s, %(tags)s, %(note)s, %(info)s
                                )
                                ON CONFLICT (word, language, native_language) 
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
                                    info = EXCLUDED.info,
                                    updated_at = CURRENT_TIMESTAMP
                            ''', insert_data)
                        else:
                            # SQLite fallback
                            cur = conn.cursor()
                            cur.execute('''
                                INSERT OR REPLACE INTO words (
                                    word, language, native_language, translation, example, example_native,
                                    lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                                    collocations, cefr, freq_rank, tags, note, info
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                insert_data['word'], insert_data['language'], insert_data['native_language'],
                                insert_data['translation'], insert_data['example'], insert_data['example_native'],
                                insert_data['lemma'], insert_data['pos'], insert_data['ipa'], insert_data['audio_url'],
                                insert_data['gender'], insert_data['plural'], insert_data['conj'], insert_data['comp'],
                                insert_data['synonyms'], insert_data['collocations'], insert_data['cefr'],
                                insert_data['freq_rank'], insert_data['tags'], insert_data['note'], insert_data['info']
                            ))
                        
                        conn.commit()
                        enriched_count += 1
                        print(f"Enriched custom level word: {word} -> {enriched_data.get('translation', '')}")
                        
                    finally:
                        conn.close()
                        
                else:
                    print(f"No enrichment data returned for word: {word}")
                    # Create a basic entry with just the word
                    from server.db_config import get_database_config, get_db_connection, execute_query
                    
                    config = get_database_config()
                    conn = get_db_connection()
                    
                    try:
                        if config['type'] == 'postgresql':
                            execute_query(conn, '''
                                INSERT INTO words (word, language, native_language, translation, gender)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (word, language, native_language) DO NOTHING
                            ''', (word, language, native_language, '', 'none'))
                        else:
                            cur = conn.cursor()
                            cur.execute('''
                                INSERT OR IGNORE INTO words (word, language, native_language, translation, gender)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (word, language, native_language, '', 'none'))
                        
                        conn.commit()
                        
                    finally:
                        conn.close()
                    
            except Exception as e:
                print(f"Error enriching word '{word}': {e}")
                # Create a basic entry even if enrichment fails
                try:
                    from server.db_config import get_database_config, get_db_connection, execute_query
                    
                    config = get_database_config()
                    conn = get_db_connection()
                    
                    try:
                        if config['type'] == 'postgresql':
                            execute_query(conn, '''
                                INSERT INTO words (word, language, native_language, translation, gender)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (word, language, native_language) DO NOTHING
                            ''', (word, language, native_language, '', 'none'))
                        else:
                            cur = conn.cursor()
                            cur.execute('''
                                INSERT OR IGNORE INTO words (word, language, native_language, translation, gender)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (word, language, native_language, '', 'none'))
                        
                        conn.commit()
                        
                    finally:
                        conn.close()
                        
                except Exception as db_error:
                    print(f"Error creating basic entry for word '{word}': {db_error}")
                continue
        
        return jsonify({
            'success': True,
            'message': 'Words enriched',
            'enriched_count': enriched_count
        })
        
    except Exception as e:
        print(f"Error enriching custom level words: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.post('/api/custom-levels/<int:group_id>/<int:level_number>/submit_mc')
@require_auth(optional=True)
def api_submit_custom_level_mc(group_id, level_number):
    """Submit multiple choice answer for a custom level"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        # For custom level submit_mc, authentication is optional
        # This allows the feature to work even without login
        
        payload = request.get_json(force=True) or {}
        answer = payload.get('answer', 0)
        correct_answer = payload.get('correct_answer', 0)
        
        # Check if answer is correct
        is_correct = answer == correct_answer
        
        return jsonify({
            'success': True,
            'correct': is_correct,
            'message': 'Correct!' if is_correct else 'Try again!'
        })
        
    except Exception as e:
        print(f"Error submitting custom level MC: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@custom_levels_bp.put('/api/custom-level-groups/<int:group_id>')
@require_auth()
def api_update_custom_level_group(group_id):
    """Update a custom level group"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        payload = request.get_json(force=True) or {}
        
        # Only allow updating certain fields
        update_data = {}
        if 'group_name' in payload:
            update_data['group_name'] = payload['group_name'].strip()
        if 'context_description' in payload:
            update_data['context_description'] = payload['context_description'].strip()
        if 'cefr_level' in payload:
            update_data['cefr_level'] = payload['cefr_level'].strip()
        if 'status' in payload:
            update_data['status'] = payload['status'].strip()
        
        if not update_data:
            return jsonify({'success': False, 'error': 'No valid fields to update'}), 400
        
        success = update_custom_level_group(group_id, user_id, **update_data)
        
        if not success:
            return jsonify({'success': False, 'error': 'Level group not found or could not be updated'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Level group updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating custom level group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# --- New endpoint: read stats from the level JSON ---
@levels_bp.get('/api/level/stats')
def api_level_stats():
    try:
        level = int(request.args.get('level') or 1)
    except Exception:
        return jsonify({'success': False, 'error': 'invalid level'}), 400
    lang = (request.args.get('language') or '').strip()
    if not lang:
        return jsonify({'success': False, 'error': 'language required'}), 400
    
    # Get user context from middleware
    user_context = get_user_context()
    user_id = user_context['user_id']
    
    fs = _read_level(lang, level)
    if not fs:
        return jsonify({'success': False, 'error': 'level file not found'}), 404
    
    # Use new multi-user system
    if user_id:
        # Get user-specific data
        user_stats = get_user_level_stats(user_id, lang, level)
        global_stats = get_global_level_stats(lang, level)
        
        # Get user progress for status/score
        from server.db import get_user_progress
        from server.db_multi_user import get_user_native_language
        native_language = get_user_native_language(user_id)
        user_progress_data = get_user_progress(user_id, lang, native_language)
        user_progress = next((p for p in user_progress_data if p['level'] == level), None)
            
        if user_progress:
            status = user_progress['status']
            last_score = user_progress['score']
        else:
            status = 'not_started'
            last_score = None
        
        # For authenticated users, don't show global runs
        runs = []
        
        # Return user-specific data
        return jsonify({
            'success': True,
            'language': lang,
            'level': level,
            'fam_counts': user_stats['familiarity_counts'],
            'status': status,
            'last_score': last_score,
            'runs': runs,
            'user_progress': user_progress,
            'total_words': user_stats['total_words'],
            'memorized_words': user_stats['memorized_words'],
            'level_score': user_stats['level_score']
        })
    else:
        # For unauthenticated users, show no progress data
        return jsonify({
            'success': True,
            'language': lang,
            'level': level,
            'fam_counts': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            'status': 'not_started',
            'last_score': None,
            'runs': [],
            'user_progress': None,
            'total_words': 0,
            'memorized_words': 0,
            'level_score': 0
    })

@words_bp.get('/api/words')
@require_auth(optional=True)
def api_words_list():
    # Get language filter from request
    language = request.args.get('language', '')
    
    # Get user from Flask's g object (set by require_auth decorator)
    user = g.current_user
    user_id = user['id'] if user else None
    
    print(f"DEBUG: api_words_list called with language={language}, user_id={user_id}")
    
    if not user_id:
        # Not authenticated - get words from global database
        print("DEBUG: No user_id, getting words from global database")
        try:
            # Get native language from header
            native_language = request.headers.get('X-Native-Language', 'en')
            
            # Get global database path
            from server.multi_user_db import db_manager
            global_db_path = db_manager.get_global_db_path(native_language)
            
            if not os.path.exists(global_db_path):
                return jsonify([])
            
            conn = sqlite3.connect(global_db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # Get all words for the target language
            cur.execute("""
                SELECT word, translation, word_hash
                FROM words_global 
                WHERE language = ?
                ORDER BY word
            """, (language,))
            
            global_words = cur.fetchall()
            conn.close()
            
            # Convert to API format
            result = []
            for word in global_words:
                result.append({
                    'word': word['word'],
                    'translation': word['translation'],
                    'familiarity': 0,
                    'seen_count': 0,
                    'correct_count': 0
                })
            
            print(f"DEBUG: Returning {len(result)} words from global database")
            return jsonify(result)
            
        except Exception as e:
            print(f"DEBUG: Error getting global words: {e}")
            return jsonify([])
    
    if not language:
        # Language required for authenticated users
        return jsonify({'error': 'language required'}), 400
    
    try:
        # Get user's native language
        from server.db_multi_user import get_user_native_language, ensure_user_databases
        from server.multi_user_db import db_manager
        
        native_language = get_user_native_language(user_id)
        
        # Ensure user databases exist for this native language
        ensure_user_databases(user_id, native_language)
        
        # Get all word hashes from user's local database
        db_path = db_manager.get_user_db_path(user_id, native_language)
        if not os.path.exists(db_path):
            return jsonify([])
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get all levels that have words unlocked for this language
        # In the multi-user system, levels are stored in level_words table
        cur.execute("""
            SELECT level, word_hashes FROM level_words 
            WHERE language = ?
        """, (language,))
        
        level_data = cur.fetchall()
        print(f"DEBUG: Found level data for {language}: {len(level_data)} entries")
        
        if not level_data:
            print(f"DEBUG: No level data found for user {user_id}, language {language}")
            return jsonify([])
        
        # Extract word hashes from all levels and remove duplicates
        level_word_hashes = []
        for row in level_data:
            level = row['level']
            word_hashes_json = row['word_hashes']
            if word_hashes_json:
                import json
                word_hashes = json.loads(word_hashes_json)
                level_word_hashes.extend(word_hashes)
                print(f"DEBUG: Level {level}: {len(word_hashes)} words")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_word_hashes = []
        for word_hash in level_word_hashes:
            if word_hash not in seen:
                seen.add(word_hash)
                unique_word_hashes.append(word_hash)
        
        conn.close()
        
        if not unique_word_hashes:
            print(f"DEBUG: No words found in unlocked levels for {language}")
            return jsonify([])
        
        print(f"DEBUG: Found {len(level_word_hashes)} total words, {len(unique_word_hashes)} unique words from unlocked levels")
        
        # Filter by language by checking global database
        # We need to get the language for each word hash from the global database
        global_words = db_manager.get_global_word_data(native_language, unique_word_hashes)
        
        # Filter word hashes by target language
        filtered_word_hashes = []
        for word_hash in unique_word_hashes:
            if word_hash in global_words:
                word_language = global_words[word_hash].get('language', '')
                if word_language == language:
                    filtered_word_hashes.append(word_hash)
        
        if not filtered_word_hashes:
            return jsonify([])
        
        # Get familiarity data for filtered words
        familiarity_data = db_manager.get_user_word_familiarity(user_id, native_language, filtered_word_hashes)
        
        # Use filtered word hashes for processing
        word_hashes = filtered_word_hashes
        
        # Combine local and global data
        result = []
        for word_hash in word_hashes:
            if word_hash in global_words:
                global_data = global_words[word_hash]
                
                # Get familiarity data for this word
                fam_data = familiarity_data.get(word_hash, {})
                
                # Create combined word object
                word_obj = {
                    'id': global_data.get('id'),
                    'word': global_data.get('word'),
                    'language': global_data.get('language'),
                    'native_language': global_data.get('native_language'),
                    'translation': global_data.get('translation'),
                    'example': global_data.get('example'),
                    'example_native': global_data.get('example_native'),
                    'lemma': global_data.get('lemma'),
                    'pos': global_data.get('pos'),
                    'ipa': global_data.get('ipa'),
                    'audio_url': global_data.get('audio_url'),
                    'gender': global_data.get('gender'),
                    'plural': global_data.get('plural'),
                    'conj': global_data.get('conj'),
                    'comp': global_data.get('comp'),
                    'synonyms': global_data.get('synonyms'),
                    'collocations': global_data.get('collocations'),
                    'cefr': global_data.get('cefr'),
                    'freq_rank': global_data.get('freq_rank'),
                    'tags': global_data.get('tags'),
                    'note': global_data.get('note'),
                    'info': global_data.get('info'),
                    'created_at': global_data.get('created_at'),
                    'updated_at': global_data.get('updated_at'),
                    # User-specific data from local database
                    'familiarity': fam_data.get('familiarity', 0),
                    'seen_count': fam_data.get('seen_count', 0),
                    'correct_count': fam_data.get('correct_count', 0)
                }
                
                # Parse JSON fields
                for field in ['conj', 'comp', 'synonyms', 'collocations', 'tags', 'info']:
                    if word_obj.get(field):
                        try:
                            word_obj[field] = json.loads(word_obj[field])
                        except Exception:
                            pass
                
                result.append(word_obj)
        
        # Sort by word
        result.sort(key=lambda x: x.get('word', ''))
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error loading user words: {e}")
        return jsonify({'error': str(e)}), 500

@words_bp.get('/api/words/count')
def api_words_count():
    """Get word count for a specific language (user-specific)"""
    language = request.args.get('language', 'en')
    
    # Get user context from middleware
    user_context = get_user_context()
    user_id = user_context['user_id']
    
    if not user_id:
        # Not authenticated - return 0
        return jsonify({'count': 0})
    
    try:
        # Get user's native language
        from server.db_multi_user import get_user_native_language, ensure_user_databases
        from server.multi_user_db import db_manager
        
        native_language = get_user_native_language(user_id)
        
        # Ensure user databases exist for this native language
        ensure_user_databases(user_id, native_language)
        
        # Get count from user's local database - use same logic as /api/words
        db_path = db_manager.get_user_db_path(user_id, native_language)
        if not os.path.exists(db_path):
            return jsonify({'count': 0})
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Count all words in local database for this language
        # (same logic as /api/words but just counting)
        cur.execute("""
            SELECT COUNT(DISTINCT wl.word_hash) as count
            FROM words_local wl
            JOIN level_words lw ON lw.word_hashes LIKE '%' || wl.word_hash || '%'
            WHERE lw.language = ?
        """, (language,))
        
        row = cur.fetchone()
        conn.close()
        
        # If no words found via level_words, count all words in local database
        if not row or row['count'] == 0:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            cur.execute("""
                SELECT COUNT(*) as count
                FROM words_local
            """)
            
            row = cur.fetchone()
            conn.close()
        
        return jsonify({'count': row['count'] if row else 0})
        
    except Exception as e:
        print(f"Error counting user words: {e}")
        return jsonify({'count': 0})

@words_bp.get('/api/words/count_max')
def api_words_count_max():
    language = (request.args.get('language') or '').strip()
    cnt = count_words_fam5(language or None)
    return jsonify({'success': True, 'count': cnt})

@words_bp.post('/api/words/delete')
def api_words_delete():
    payload = request.get_json(force=True) or {}
    ids = payload.get('ids') or []
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'error': 'ids required'}), 400
    try:
        ids_int = [int(x) for x in ids if str(x).isdigit()]
    except Exception:
        return jsonify({'success': False, 'error': 'invalid ids'}), 400
    if not ids_int:
        return jsonify({'success': False, 'error': 'no valid ids'}), 400
    deleted = delete_words_by_ids(ids_int)
    return jsonify({'success': True, 'deleted': deleted})



@words_bp.get('/api/word')
def api_word_get():
    word = (request.args.get('word') or '').strip()
    language = (request.args.get('language') or '').strip()
    native_language_param = (request.args.get('native_language') or '').strip()
    if not word:
        return jsonify({'error': 'word required'}), 400
    
    # Get user context from middleware
    user_context = get_user_context()
    user_id = user_context['user_id']
    
    # Get native language from URL parameter, user context, or default
    native_language = native_language_param or user_context.get('native_language', 'en')
    
    # Get word data from existing PostgreSQL words table
    from server.db_config import get_database_config, get_db_connection, execute_query
    
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            result = execute_query(conn, '''
                SELECT * FROM words 
                WHERE word = %s AND language = %s AND native_language = %s
            ''', (word, language, native_language))
            row = result.fetchone()
        else:
            # SQLite syntax (fallback)
            cur = conn.cursor()
            row = cur.execute('SELECT * FROM words WHERE word=? AND language=? AND native_language=?', (word, language, native_language)).fetchone()
        
        if not row:
            # Return empty word data if not found
            return jsonify({
              'word': word, 'language': language, 'translation': '', 'example': '', 'example_native': '',
              'lemma': '', 'pos': '', 'ipa': '', 'audio_url': '', 'gender': 'none', 'plural': '',
              'conj': {}, 'comp': {}, 'synonyms': [], 'collocations': [], 'cefr': '', 'freq_rank': None, 'tags': [], 'note': '',
              'info': {}, 'familiarity': 0, 'seen_count': 0, 'correct_count': 0
            })
        
        data = dict(row)
        
    finally:
        conn.close()
    
    # Get user-specific familiarity data if authenticated
    is_authenticated = user_id is not None
    if user_id:
        try:
            # Get familiarity from PostgreSQL user_word_familiarity table
            from server.db import get_user_word_familiarity_by_word
            familiarity_data = get_user_word_familiarity_by_word(user_id, word, language, native_language)
            
            if familiarity_data:
                data['familiarity'] = familiarity_data['familiarity'] or 0
                data['seen_count'] = familiarity_data['seen_count'] or 0
                data['correct_count'] = familiarity_data['correct_count'] or 0
                data['user_comment'] = familiarity_data['user_comment'] or ''
            else:
                # Word not in familiarity table yet
                data['familiarity'] = 0
                data['seen_count'] = 0
                data['correct_count'] = 0
                data['user_comment'] = ''
        except Exception as e:
            print(f"Error getting user familiarity data: {e}")
            # Fallback to default values
            data['familiarity'] = 0
            data['seen_count'] = 0
            data['correct_count'] = 0
            data['user_comment'] = ''
    else:
        # Not authenticated - return default values
        data['familiarity'] = 0
        data['seen_count'] = 0
        data['correct_count'] = 0
        data['user_comment'] = ''
    
    # Keep user-specific familiarity data for authenticated users
    # Only remove global familiarity data if it exists and we have user-specific data
    if is_authenticated:
        # Keep user-specific familiarity data
        pass
    else:
        # Remove familiarity from global data if it exists
        if 'familiarity' in data:
            del data['familiarity']
        if 'seen_count' in data:
            del data['seen_count']
        if 'correct_count' in data:
            del data['correct_count']
    
    if data.get('info'):
        try:
            data['info'] = json.loads(data['info'])
        except Exception:
            pass
    for k in ('conj','comp','synonyms','collocations','tags'):
        if data.get(k):
            try:
                data[k] = json.loads(data[k])
            except Exception:
                pass
    return jsonify(data)


# --- Batch word fetch endpoint ---
@words_bp.post('/api/words/get_many')
def api_words_get_many():
    payload = request.get_json(force=True) or {}
    words = payload.get('words') or []
    language = (payload.get('language') or '').strip()
    # normalize input
    words = [str(w).strip() for w in words if str(w).strip()]
    if not words:
        return jsonify({'success': True, 'data': []})
    
    try:
        # Get user context for native language
        user_context = get_user_context()
        native_language = user_context.get('native_language', 'en')
        
        # Get words from existing PostgreSQL words table
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config['type'] == 'postgresql':
                # PostgreSQL syntax
                result = execute_query(conn, '''
                    SELECT * FROM words 
                    WHERE word = ANY(%s) AND language = %s AND native_language = %s
                ''', (words, language, native_language))
                rows = result.fetchall()
            else:
                # SQLite syntax (fallback)
                cur = conn.cursor()
                placeholders = ','.join('?' for _ in words)
                rows = cur.execute(f'SELECT * FROM words WHERE word IN ({placeholders}) AND language=? AND native_language=?', (*words, language, native_language)).fetchall()
            
            # Convert to dict with word as key
            word_data_map = {}
            for row in rows:
                word_data = dict(row)
                # Parse JSON fields
                for json_field in ['conj', 'comp', 'synonyms', 'collocations', 'tags', 'info']:
                    if word_data.get(json_field):
                        try:
                            word_data[json_field] = json.loads(word_data[json_field]) if isinstance(word_data[json_field], str) else word_data[json_field]
                        except (json.JSONDecodeError, TypeError):
                            word_data[json_field] = None
                    else:
                        word_data[json_field] = None
                
                word_data_map[word_data['word']] = word_data
            
            # Convert to list format expected by frontend
            out = []
            for word in words:
                if word in word_data_map:
                    word_data = word_data_map[word]
                    # Ensure all required fields exist
                    word_data.setdefault('familiarity', 0)
                    word_data.setdefault('seen_count', 0)
                    word_data.setdefault('correct_count', 0)
                    out.append(word_data)
                else:
                    # Return empty data for words not found
                    out.append({
                        'word': word, 'language': language, 'translation': '', 'example': '', 'example_native': '',
                        'lemma': '', 'pos': '', 'ipa': '', 'audio_url': '', 'gender': 'none', 'plural': '',
                        'conj': {}, 'comp': {}, 'synonyms': [], 'collocations': [], 'cefr': '', 'freq_rank': None, 'tags': [], 'note': '',
                        'info': {}, 'familiarity': 0, 'seen_count': 0, 'correct_count': 0
                    })
            
            return jsonify({'success': True, 'data': out})
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Error in get_many: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@words_bp.post('/api/word/upsert')
def api_word_upsert():
    payload = request.get_json(force=True) or {}
    word = (payload.get('word') or '').strip()
    if not word:
        return jsonify({'success': False, 'error': 'word required'}), 400
    
    # Get user context from middleware
    user_context = get_user_context()
    user_id = user_context['user_id']
    is_authenticated = user_id is not None
    
    # For testing, use user_id from payload if provided
    if not user_id and payload.get('user_id'):
        user_id = payload.get('user_id')
        is_authenticated = True
    
    # Only save word familiarity updates if user is authenticated
    if is_authenticated:
        # Save to PostgreSQL user_word_familiarity table
        try:
            language = payload.get('language', 'en')
            native_language = payload.get('native_language') or user_context.get('native_language', 'en')
            familiarity = payload.get('familiarity', 0)
            user_comment = payload.get('user_comment', '')
            # Use user_id from payload if provided, otherwise use context user_id
            target_user_id = payload.get('user_id') or user_id
                
            # Update word familiarity in PostgreSQL database
            from server.db import update_user_word_familiarity_by_word
            success = update_user_word_familiarity_by_word(
                user_id=target_user_id,
                word=word,
                language=language,
                native_language=native_language,
                familiarity=familiarity,
                user_comment=user_comment
            )
            
            if success:
                print(f"✅ Word familiarity updated for user {target_user_id}: {word} -> {familiarity} (comment: {user_comment[:50]}...)")
            else:
                print(f"❌ Failed to update word familiarity for user {target_user_id}: {word}")
                
        except Exception as e:
            print(f"Error saving user word familiarity: {e}")
            # Continue execution even if user data saving fails
    else:
        # User not authenticated - don't save word familiarity updates
        print(f"Word familiarity update by unauthenticated user - not saved: {word}")
    
    # Always update the global word data in existing PostgreSQL words table
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        import json
        
        language = payload.get('language', 'en')
        native_language = user_context.get('native_language', 'en')
        
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            # Prepare data for insertion/update
            insert_data = {
                'word': word,
                'language': language,
                'native_language': native_language,
                'translation': payload.get('translation', ''),
                'example': payload.get('example', ''),
                'example_native': payload.get('example_native', ''),
                'lemma': payload.get('lemma', ''),
                'pos': payload.get('pos', ''),
                'ipa': payload.get('ipa', ''),
                'audio_url': payload.get('audio_url', ''),
                'gender': payload.get('gender', 'none'),
                'plural': payload.get('plural', ''),
                'conj': json.dumps(payload.get('conj', {})) if payload.get('conj') else None,
                'comp': json.dumps(payload.get('comp', {})) if payload.get('comp') else None,
                'synonyms': json.dumps(payload.get('synonyms', [])) if payload.get('synonyms') else None,
                'collocations': json.dumps(payload.get('collocations', [])) if payload.get('collocations') else None,
                'cefr': payload.get('cefr', ''),
                'freq_rank': payload.get('freq_rank'),
                'tags': json.dumps(payload.get('tags', [])) if payload.get('tags') else None,
                'note': payload.get('note', ''),
                'info': json.dumps(payload.get('info', {})) if payload.get('info') else None
            }
            
            if config['type'] == 'postgresql':
                # PostgreSQL syntax - use INSERT ... ON CONFLICT for upsert
                execute_query(conn, '''
                    INSERT INTO words (
                        word, language, native_language, translation, example, example_native,
                        lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                        collocations, cefr, freq_rank, tags, note, info
                    ) VALUES (
                        %(word)s, %(language)s, %(native_language)s, %(translation)s, %(example)s, %(example_native)s,
                        %(lemma)s, %(pos)s, %(ipa)s, %(audio_url)s, %(gender)s, %(plural)s, %(conj)s, %(comp)s, %(synonyms)s,
                        %(collocations)s, %(cefr)s, %(freq_rank)s, %(tags)s, %(note)s, %(info)s
                    )
                    ON CONFLICT (word, language, native_language) 
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
                        info = EXCLUDED.info,
                        updated_at = CURRENT_TIMESTAMP
                ''', insert_data)
            else:
                # SQLite syntax (fallback)
                cur = conn.cursor()
                cur.execute('''
                    INSERT OR REPLACE INTO words (
                        word, language, native_language, translation, example, example_native,
                        lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                        collocations, cefr, freq_rank, tags, note, info
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    insert_data['word'], insert_data['language'], insert_data['native_language'],
                    insert_data['translation'], insert_data['example'], insert_data['example_native'],
                    insert_data['lemma'], insert_data['pos'], insert_data['ipa'], insert_data['audio_url'],
                    insert_data['gender'], insert_data['plural'], insert_data['conj'], insert_data['comp'],
                    insert_data['synonyms'], insert_data['collocations'], insert_data['cefr'],
                    insert_data['freq_rank'], insert_data['tags'], insert_data['note'], insert_data['info']
                ))
            
            conn.commit()
            print(f"Word upserted to PostgreSQL words table: {word} ({language} -> {native_language})")
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"Error upserting word to PostgreSQL words table: {e}")
        # Don't use fallback to old system as it creates duplicates
        print(f"Word upsert failed for: {word} ({language} -> {native_language})")
    
    # For unauthenticated users, we still save to global database but not user-specific data
        # and use multi-user system if possible
        try:
            # Try to get native language from request headers (sent by frontend)
            native_language = request.headers.get('X-Native-Language', 'en')
            
            from server.multi_user_db import db_manager
            
            language = payload.get('language', 'en')
            
            # Add word to global database for this native language
            word_data = {
                'translation': payload.get('translation', ''),
                'example': payload.get('example', ''),
                'example_native': payload.get('example_native', ''),
                'lemma': payload.get('lemma', ''),
                'pos': payload.get('pos', ''),
                'ipa': payload.get('ipa', ''),
                'audio_url': payload.get('audio_url', ''),
                'gender': payload.get('gender', ''),
                'plural': payload.get('plural', ''),
                'conj': payload.get('conj', {}),
                'comp': payload.get('comp', {}),
                'synonyms': payload.get('synonyms', []),
                'collocations': payload.get('collocations', []),
                'cefr': payload.get('cefr', ''),
                'freq_rank': payload.get('freq_rank'),
                'tags': payload.get('tags', []),
                'note': payload.get('note', ''),
                'info': payload.get('info', {})
            }
            
            word_hash = db_manager.add_word_to_global(word, language, native_language, word_data)
            if word_hash:
                print(f"Word added to global database for unauthenticated user (native: {native_language}): {word}")
            else:
                print(f"Failed to add word to global database for unauthenticated user (native: {native_language}): {word}")
            
        except Exception as e:
            print(f"Error adding word to global database for unauthenticated user: {e}")
    
    return jsonify({'success': True})


@words_bp.post('/api/words/adjust-familiarity')
def api_words_adjust_familiarity():
    """Adjust familiarity level for a word"""
    try:
        # Get user context from middleware
        user_context = get_user_context()
        user_id = user_context['user_id']
        
        payload = request.get_json(force=True) or {}
        word = (payload.get('word') or '').strip()
        delta = payload.get('delta', 0)
        
        if not word:
            return jsonify({'success': False, 'error': 'word required'}), 400
        
        # Get current language from request
        language = request.args.get('language', 'en')
        
        if not user_id:
            # Not authenticated - return error
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Get current familiarity from local database
        from server.db_multi_user import get_user_native_language
        from server.multi_user_db import db_manager
        
        native_language = get_user_native_language(user_id)
        word_hash = db_manager.generate_word_hash(word, language, native_language)
        
        # Get current familiarity from local database
        familiarity_data = db_manager.get_user_word_familiarity(user_id, native_language, [word_hash])
        current_familiarity = 0
        if word_hash in familiarity_data:
            current_familiarity = familiarity_data[word_hash]['familiarity']
        
        new_familiarity = max(0, min(5, current_familiarity + delta))
            
        # Update familiarity in local database
        success = db_manager.update_user_word_familiarity(
            user_id=user_id,
            native_language=native_language,
            word_hash=word_hash,
            familiarity=new_familiarity
        )
        
        if not success:
            return jsonify({'success': False, 'error': 'Failed to update familiarity'}), 500
            
        return jsonify({
            'success': True,
            'familiarity': new_familiarity,
            'delta': new_familiarity - current_familiarity,
            'authenticated': True
        })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@words_bp.post('/api/word/enrich_batch')
def api_word_enrich_batch():
    """Enrich multiple words at once with optimized batch processing and TTS"""
    payload = request.get_json(force=True) or {}
    words = payload.get('words', [])
    language = (payload.get('language') or '').strip()
    native_language = (payload.get('native_language') or '').strip()
    sentence_contexts = payload.get('sentence_contexts', {})
    generate_audio = payload.get('generate_audio', True)  # New parameter
    
    if not words or not language:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    try:
        # Use optimized batch enrichment
        from server.services.llm import llm_enrich_words_batch
        enriched_results = llm_enrich_words_batch(words, language, native_language, sentence_contexts)
        
        # Generate TTS for all words in parallel if requested
        if generate_audio:
            from server.services.tts import ensure_tts_for_words_batch
            audio_results = ensure_tts_for_words_batch(words, language, max_workers=3)
            
            # Merge audio URLs into enriched results
            for word, audio_url in audio_results.items():
                if word in enriched_results and enriched_results[word]:
                    enriched_results[word]['audio_url'] = audio_url
        
        enriched_count = len([w for w, data in enriched_results.items() if data and data.get('translation')])
        
        return jsonify({
            'success': True,
            'message': 'Words enriched',
            'enriched_count': enriched_count,
            'total_words': len(words),
            'results': enriched_results
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@words_bp.post('/api/word/enrich')
def api_word_enrich():
    payload = request.get_json(force=True) or {}
    word = (payload.get('word') or '').strip()
    language = (payload.get('language') or '').strip()
    native_language = (payload.get('native_language') or '').strip()
    sentence_context = (payload.get('sentence_context') or '').strip()
    sentence_native = (payload.get('sentence_native') or '').strip()
    if not word or not language:
        return jsonify({'success': False, 'error': 'word and language required'}), 400
    
    try:
        # Use service to enrich + normalize with context
        upd = llm_enrich_word(word, language, native_language, sentence_context, sentence_native)
        
        # Persist: overwrite existing fields when new non-empty values are available
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        now = datetime.now(UTC).isoformat()
        
        # Prepare JSON strings (keep None for empty to avoid overwriting with empties)
        conj_json = json.dumps(upd['conj'], ensure_ascii=False) if upd.get('conj') else None
        comp_json = json.dumps(upd['comp'], ensure_ascii=False) if upd.get('comp') else None
        syn_json  = json.dumps(upd['synonyms'], ensure_ascii=False) if upd.get('synonyms') else None
        col_json  = json.dumps(upd['collocations'], ensure_ascii=False) if upd.get('collocations') else None

        sets = []
        vals = []
        
        if config['type'] == 'postgresql':
            # PostgreSQL syntax
            def set_if_val(key, val):
                if isinstance(val, str):
                    if val.strip():
                        sets.append(f"{key}=%s"); vals.append(val.strip())
                elif val is not None:
                    sets.append(f"{key}=%s"); vals.append(val)
        else:
            # SQLite syntax
            def set_if_val(key, val):
                if isinstance(val, str):
                    if val.strip():
                        sets.append(f"{key}=?"); vals.append(val.strip())
                elif val is not None:
                    sets.append(f"{key}=?"); vals.append(val)
        
        set_if_val('lemma', upd.get('lemma'))
        set_if_val('pos', upd.get('pos'))
        set_if_val('ipa', upd.get('ipa'))
        set_if_val('gender', upd.get('gender'))
        set_if_val('plural', upd.get('plural'))
        set_if_val('cefr', upd.get('cefr'))
        set_if_val('freq_rank', upd.get('freq_rank'))
        set_if_val('example', upd.get('example'))
        set_if_val('example_native', upd.get('example_native'))
        set_if_val('translation', upd.get('translation'))
        
        if config['type'] == 'postgresql':
            if conj_json: sets.append('conj=%s'); vals.append(conj_json)
            if comp_json: sets.append('comp=%s'); vals.append(comp_json)
            if syn_json:  sets.append('synonyms=%s'); vals.append(syn_json)
            if col_json:  sets.append('collocations=%s'); vals.append(col_json)
        else:
            if conj_json: sets.append('conj=?'); vals.append(conj_json)
            if comp_json: sets.append('comp=?'); vals.append(comp_json)
            if syn_json:  sets.append('synonyms=?'); vals.append(syn_json)
            if col_json:  sets.append('collocations=?'); vals.append(col_json)

        if sets:
            sets.append('updated_at=%s' if config['type'] == 'postgresql' else 'updated_at=?')
            vals.append(now)
            vals.extend([word, language, language])
            
            if config['type'] == 'postgresql':
                where_clause = 'WHERE word=%s AND (language=%s OR %s=\'\')'
            else:
                where_clause = 'WHERE word=? AND (language=? OR ?="")'
            
            query = f'UPDATE words SET {", ".join(sets)} {where_clause}'
            execute_query(conn, query, vals)
            conn.commit()
        
        # -- auto TTS if missing or file not found
        try:
            if config['type'] == 'postgresql':
                # PostgreSQL syntax
                result = execute_query(conn, 'SELECT audio_url FROM words WHERE word=%s AND (language=%s OR %s=\'\')', (word, language, language))
                r2 = result.fetchone()
            else:
                # SQLite syntax
                cur = conn.cursor()
                r2 = cur.execute('SELECT audio_url FROM words WHERE word=? AND (language=? OR ?="")', (word, language, language)).fetchone()
            
            need_gen = True
            if r2:
                au = (r2['audio_url'] or '').strip()
                if au:
                    # Check if it's an S3 URL or local file
                    if au.startswith('https://') and 's3' in au:
                        # S3 URL - assume it exists (S3 is reliable)
                        upd['audio_url'] = au
                        need_gen = False
                    else:
                        # Local file - check if it exists
                        fpath = _audio_url_to_path(au)
                        if fpath and os.path.isfile(fpath):
                            upd['audio_url'] = au
                            need_gen = False
            if need_gen:
                au2 = ensure_tts_for_word(word, language)
                if au2:
                    upd['audio_url'] = au2
        except Exception as e:
            print(f"❌ Error in enrich TTS: {e}")
            pass
        finally:
            conn.close()
        
        return jsonify({'success': True, 'data': upd})
        
    except Exception as e:
        print(f"❌ Error in enrich endpoint: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@levels_bp.post('/api/level/ensure_topic')
def api_level_ensure_topic():
    payload = request.get_json(force=True) or {}
    level = int(payload.get('level') or 1)
    target_lang = (payload.get('target_lang') or 'en').lower()
    native_lang = (payload.get('native_lang') or 'de').lower()
    cefr = cefr_norm(payload.get('cefr') or 'A1')
    base_topic = (payload.get('base_topic') or '').strip()

    conn = get_db(); cur = conn.cursor()
    row = cur.execute('SELECT id, topic FROM level_runs WHERE level=? ORDER BY id DESC LIMIT 1', (level,)).fetchone()
    if row and (row['topic'] or '').strip():
        conn.close()
        return jsonify({'success': True, 'topic': row['topic']})

    topic = suggest_topic(target_lang, native_lang, cefr, base_topic)
    if row:
        cur.execute('UPDATE level_runs SET topic=? WHERE id=?', (topic, row['id']))
        conn.commit()
    conn.close()
    return jsonify({'success': True, 'topic': topic})

import random

############################
# Level generation and evaluation
############################

FALLBACK_SENTENCES = {
    'en': [
        "The quick brown fox jumps over the lazy dog.",
        "I drink coffee every morning before work.",
        "Learning languages takes time and practice.",
        "Please open the window, it is too hot here.",
        "She wrote a letter and sent it yesterday."
    ],
    'de': [
        "Der schnelle braune Fuchs springt über den faulen Hund.",
        "Ich trinke jeden Morgen vor der Arbeit Kaffee.",
        "Sprachenlernen braucht Zeit und Übung.",
        "Bitte öffne das Fenster, es ist hier zu heiß.",
        "Sie schrieb einen Brief und schickte ihn gestern ab."
    ],
    'sv': [
        "Den snabba bruna räven hoppar över den lata hunden.",
        "Jag dricker kaffe varje morgon före jobbet.",
        "Att lära sig språk tar tid och övning.",
        "Snälla öppna fönstret, det är för varmt här.",
        "Hon skrev ett brev och skickade det igår."
    ],
    'fr': [
        "Le renard brun rapide saute par-dessus le chien paresseux.",
        "Je bois du café tous les matins avant le travail.",
        "Apprendre les langues prend du temps et de la pratique.",
        "Veuillez ouvrir la fenêtre, il fait trop chaud ici.",
        "Elle a écrit une lettre et l'a envoyée hier."
    ],
    'es': [
        "El zorro marrón rápido salta sobre el perro perezoso.",
        "Bebo café todas las mañanas antes del trabajo.",
        "Aprender idiomas requiere tiempo y práctica.",
        "Por favor abre la ventana, hace demasiado calor aquí.",
        "Ella escribió una carta y la envió ayer."
    ],
    'it': [
        "La volpe marrone veloce salta sopra il cane pigro.",
        "Bevo caffè ogni mattina prima del lavoro.",
        "Imparare le lingue richiede tempo e pratica.",
        "Per favore apri la finestra, fa troppo caldo qui.",
        "Ha scritto una lettera e l'ha inviata ieri."
    ],
    'pt': [
        "A raposa marrom rápida pula sobre o cão preguiçoso.",
        "Eu bebo café todas as manhãs antes do trabalho.",
        "Aprender idiomas leva tempo e prática.",
        "Por favor abra a janela, está muito quente aqui.",
        "Ela escreveu uma carta e a enviou ontem."
    ],
    'ru': [
        "Быстрая коричневая лиса прыгает через ленивую собаку.",
        "Я пью кофе каждое утро перед работой.",
        "Изучение языков требует времени и практики.",
        "Пожалуйста, откройте окно, здесь слишком жарко.",
        "Она написала письмо и отправила его вчера."
    ],
    'zh': [
        "敏捷的棕色狐狸跳过懒惰的狗。",
        "我每天早上上班前喝咖啡。",
        "学习语言需要时间和练习。",
        "请打开窗户，这里太热了。",
        "她昨天写了一封信并寄了出去。"
    ],
    'ja': [
        "素早い茶色の狐が怠け者の犬を飛び越える。",
        "私は毎朝仕事の前にコーヒーを飲む。",
        "言語を学ぶには時間と練習が必要だ。",
        "窓を開けてください、ここは暑すぎます。",
        "彼女は昨日手紙を書いて送った。"
    ],
    'ko': [
        "빠른 갈색 여우가 게으른 개를 뛰어넘는다.",
        "나는 매일 아침 일하기 전에 커피를 마신다.",
        "언어를 배우는 것은 시간과 연습이 필요하다.",
        "창문을 열어주세요, 여기가 너무 덥습니다.",
        "그녀는 어제 편지를 써서 보냈다."
    ],
    'ar': [
        "الثعلب البني السريع يقفز فوق الكلب الكسول.",
        "أشرب القهوة كل صباح قبل العمل.",
        "تعلم اللغات يتطلب وقتاً وممارسة.",
        "من فضلك افتح النافذة، الجو حار جداً هنا.",
        "كتبت رسالة وأرسلتها أمس."
    ],
    'hi': [
        "तेज भूरी लोमड़ी आलसी कुत्ते के ऊपर कूदती है।",
        "मैं हर सुबह काम से पहले कॉफी पीता हूं।",
        "भाषाएं सीखने में समय और अभ्यास लगता है।",
        "कृपया खिड़की खोलें, यहां बहुत गर्मी है।",
        "उसने कल एक पत्र लिखा और भेजा।"
    ],
    'tr': [
        "Hızlı kahverengi tilki tembel köpeğin üzerinden atlar.",
        "Her sabah işe gitmeden önce kahve içerim.",
        "Dil öğrenmek zaman ve pratik gerektirir.",
        "Lütfen pencereyi açın, burada çok sıcak.",
        "Dün bir mektup yazdı ve gönderdi."
    ],
    'ka': [
        "სწრაფი ყვითელი მელა ხტება ზარმაც ძაღლზე.",
        "ყოველ დილას სამუშაოს წინ ყავას ვსვამ.",
        "ენების სწავლას დრო და პრაქტიკა სჭირდება.",
        "გთხოვთ გახსენით ფანჯარა, აქ ძალიან ცხელა.",
        "მან გუშინ წერილი დაწერა და გაგზავნა."
    ]
}




@levels_bp.post('/api/level/start')
def api_level_start():
    try:
        payload = request.get_json(force=True) or {}
        level = int(payload.get('level') or 1)
        target_lang = (payload.get('target_lang') or 'en').lower()
        native_lang = (payload.get('native_lang') or 'de').lower()
        # Normalize BCP-47 tags to base codes and guard against accidental swaps
        target_lang = (target_lang.split('-')[0] or 'en').lower()
        native_lang = (native_lang.split('-')[0] or 'de').lower()
        if target_lang == native_lang:
            # Heuristic: if identical, keep native as-is and default target to English to avoid German-on-German
            # This prevents LLM from using the native language by mistake.
            target_lang = 'en' if native_lang != 'en' else 'de'
        topic = (payload.get('topic') or 'daily life').strip() or 'daily life'
        cefr = (payload.get('cefr') or 'A0').strip()  # Default to A0 instead of 'none'
        reuse = bool(payload.get('reuse', False))
        
        # Check for user authentication
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_current_user(session_token) if session_token else None
        user_id = user['id'] if user else None

        # Gate: only allow starting level N>1 if previous level score > 0.6
        try:
            if level > 1:
                if user_id:
                    try:
                        # Check user's previous level progress
                        from server.db import get_user_progress
                        from server.db_multi_user import get_user_native_language
                        native_language = get_user_native_language(user_id)
                        prev_progress = get_user_progress(user_id, target_lang, native_language)
                        prev_level_data = next((p for p in prev_progress if p['level'] == level-1), None)
                        prev_score = prev_level_data['score'] if prev_level_data else None
                    except Exception as user_error:
                        print(f"Error checking user progress: {user_error}")
                        # Fallback to global level data for logged-in users
                        prev = _read_level(target_lang, level-1)
                        prev_score = None if not prev else prev.get('last_score')
                else:
                    # For anonymous users, use global level data
                    prev = _read_level(target_lang, level-1)
                    prev_score = None if not prev else prev.get('last_score')
                
                if not (isinstance(prev_score, (int, float)) and float(prev_score) > 0.6):
                    return jsonify({'success': False, 'error': 'previous level score must be > 0.6'}), 403
        except Exception as gate_error:
            print(f"Error in level gate check: {gate_error}")
            # For anonymous users, allow level 1 and block higher levels
            if level > 1:
                return jsonify({'success': False, 'error': 'Please log in to access higher levels'}), 403

        # Check if user-specific level file already exists and should be reused
        try:
            _ensure_course_dirs(target_lang)
            existing_fs = _read_level(target_lang, level, user_id)
        except Exception as fs_error:
            print(f"Error checking existing level file: {fs_error}")
            existing_fs = None
    
        # Reuse existing items from FS if available and not explicitly regenerating
        if reuse or (existing_fs and existing_fs.get('items')):
            try:
                _ensure_course_dirs(target_lang)
                fs = _read_level(target_lang, level, user_id)
            except Exception:
                fs = None
            
            # Check if we should regenerate content based on topic changes
            should_regenerate = False
            if fs:
                existing_topic = fs.get('topic', '').strip()
                existing_title = fs.get('title', '').strip()
                existing_items = fs.get('items', [])
                
                # Only regenerate if level file is empty/invalid
                if not existing_items or len(existing_items) == 0:
                    print(f"Level file exists but has no items (placeholder) - regenerating content")
                    should_regenerate = True
                # If level file has content, always reuse it unless explicitly told not to
                else:
                    print(f"Level file has content - reusing existing level (topic: '{existing_topic}')")
                    should_regenerate = False
            
            if fs and isinstance(fs.get('items'), list) and fs['items'] and not should_regenerate:
                items = fs['items']
                # ensure words exist in DB for these items
                try:
                    for it in (items or []):
                        ensure_words_exist(it.get('words') or [], target_lang, native_lang)
                except Exception:
                    pass
                run_id = create_level_run(level, items, topic, target_lang, native_lang)
                
                # Sync all words for this language to ensure they appear in Words tab
                if user_id:
                    try:
                        from server.word_sync import ensure_level_words_synced
                        
                        # Ensure all words for this language are synced and level words are unlocked
                        sync_success = ensure_level_words_synced(user_id, target_lang, level)
                        
                        if sync_success:
                            print(f"Words synced and unlocked for user {user_id}, level {level}, language {target_lang} (reuse path)")
                        else:
                            print(f"Warning: Word sync failed for user {user_id}, level {level}, language {target_lang} (reuse path)")
                            
                    except Exception as e:
                        print(f"Error syncing words for user {user_id}, level {level}, language {target_lang} (reuse path): {e}")
                        # Fallback to old method
                        try:
                            from server.db_multi_user import unlock_level_words
                            unlock_level_words(user_id, target_lang, level)
                            print(f"Fallback: Words unlocked for user {user_id}, level {level}, language {target_lang} (reuse path)")
                        except Exception as e2:
                            print(f"Fallback also failed: {e2}")
                
                # NOTE: Global level file updates removed - runs are now user-specific only
                # Only save the topic to global level file, no progress data
                try:
                    fs['topic'] = topic
                    # Update meta section with correct topic and title
                    if 'meta' not in fs:
                        fs['meta'] = {}
                    fs['meta']['level'] = level
                    fs['meta']['language'] = target_lang
                    fs['meta']['cefr'] = cefr
                    fs['meta']['topic'] = topic
                    fs['meta']['title'] = fs.get('title', f'Level {level}')
                    fs['meta']['section'] = fs.get('section') or ''
                    _write_level(target_lang, level, fs, user_id)
                except Exception:
                    pass
                return jsonify({'success': True, 'run_id': run_id, 'level': level, 'items': items, 'target_lang': target_lang, 'native_lang': native_lang})

        # Only generate new content if no existing level file was reused
        print(f"No existing level file found or regeneration requested - generating new content for level {level}")
        
        # v0.3: LLM-Satzgenerierung mit Thema + Referenzübersetzungen
        # Generate better topic if current one is generic
        if topic.lower() in ['level 1', 'level 2', 'level 3', 'level 4', 'level 5']:
            topic = suggest_topic(target_lang, native_lang, cefr, topic, level)
        
        # Generate level title based on topic
        level_title = suggest_level_title(target_lang, native_lang, topic, level, cefr)
        
        sentences = llm_generate_sentences(target_lang, native_lang, n=5, topic=topic, cefr=cefr, level_title=level_title) or FALLBACK_SENTENCES.get(target_lang, FALLBACK_SENTENCES['en'])
        refs = llm_translate_batch(sentences, native_lang) if OPENAI_KEY else None

        # Build items with native reference if we have a quick translation (none yet). Keep old ref as empty to avoid biasing score.
        items = []
        for idx, s in enumerate(sentences, start=1):
            txt = str(s).strip()
            words = tokenize_words(txt)
            ref_txt = ''
            if isinstance(refs, list) and idx-1 < len(refs):
                ref_txt = str(refs[idx-1] or '').strip()
            items.append({
                'idx': idx,
                'text_target': txt,
                'text_native_ref': ref_txt,
                'words': words
            })
            ensure_words_exist(words, target_lang, native_lang)

        run_id = create_level_run(level, items, topic, target_lang, native_lang)

        # Update user progress if authenticated
        if user_id:
            update_user_level_progress(user_id, target_lang, level, 'in_progress')
            
            # Sync all words for this language to ensure they appear in Words tab
            try:
                from server.word_sync import ensure_level_words_synced
                
                # Ensure all words for this language are synced and level words are unlocked
                sync_success = ensure_level_words_synced(user_id, target_lang, level)
                
                if sync_success:
                    print(f"Words synced and unlocked for user {user_id}, level {level}, language {target_lang}")
                else:
                    print(f"Warning: Word sync failed for user {user_id}, level {level}, language {target_lang}")
                    
            except Exception as e:
                print(f"Error syncing words for user {user_id}, level {level}, language {target_lang}: {e}")
                # Fallback to old method
                try:
                    from server.db_multi_user import unlock_level_words
                    unlock_level_words(user_id, target_lang, level)
                    print(f"Fallback: Words unlocked for user {user_id}, level {level}, language {target_lang}")
                except Exception as e2:
                    print(f"Fallback also failed: {e2}")

        # --- FS: persist level file per target language and create initial run stub
        try:
            _ensure_course_dirs(target_lang)
            fs = _read_level(target_lang, level) or {}
            # merge or initialize structure
            fs.setdefault('language', target_lang)
            fs.setdefault('level', level)
            fs['title'] = level_title  # Use the generated level title
            fs['section'] = fs.get('section') or ''
            fs['topic'] = topic
            fs['items'] = items  # overwrite with latest generated items
            
            # Update meta section with correct topic and title
            if 'meta' not in fs:
                fs['meta'] = {}
            fs['meta']['level'] = level
            fs['meta']['language'] = target_lang
            fs['meta']['cefr'] = cefr
            fs['meta']['topic'] = topic
            fs['meta']['title'] = level_title
            fs['meta']['section'] = fs.get('section') or ''
            # optional quick familiarity snapshot for summary
            try:
                all_words = []
                for it in (items or []):
                    for w in (it.get('words') or []):
                        k = str(w).strip()
                        if k and k not in all_words:
                            all_words.append(k)
                # Use user-specific familiarity counts if authenticated
                if user_id:
                    from server.db import get_user_familiarity_counts
                    dist = get_user_familiarity_counts(user_id, target_lang)
                else:
                    dist = fam_counts_for_words(all_words, target_lang)
            except Exception:
                dist = {str(i):0 for i in range(6)}
            # NOTE: Global level file updates removed - runs are now user-specific only
            # Only save the items and meta data to global level file, no progress data
            fs['items'] = items
            fs['topic'] = topic
            _write_level(target_lang, level, fs, user_id)
        except Exception:
            pass

        return jsonify({'success': True, 'run_id': run_id, 'level': level, 'items': items, 'target_lang': target_lang, 'native_lang': native_lang, 'user_id': user_id})
    except Exception as e:
        print(f"Error in api_level_start: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ... oben unverändert ...
@levels_bp.post('/api/level/submit')
def api_level_submit():
    payload = request.get_json(force=True) or {}
    run_id = int(payload.get('run_id') or 0)
    answers = payload.get('answers') or []  # list[{idx, translation}]
    
    # Check for user authentication
    session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_current_user(session_token) if session_token else None
    user_id = user['id'] if user else None

    conn = get_db()
    row = conn.execute('SELECT level, items, user_translations FROM level_runs WHERE id=?', (run_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': 'run not found'}), 404
    items = json.loads(row['items'])
    ref_map = {it['idx']: (it.get('text_native_ref') or it.get('text_target') or '') for it in items}

    # Vorhandene Antworten laden und per idx mergen
    try:
        existing = json.loads(row['user_translations'] or '[]')
    except Exception:
        existing = []
    by_idx = {int(x.get('idx')): (x.get('translation') or '') for x in existing if isinstance(x, dict)}
    for a in answers:
        try:
            by_idx[int(a.get('idx'))] = a.get('translation') or ''
        except Exception:
            pass

    # Resolve target language for correct word updates
    tl_submit = None
    try:
        found = _find_level_file_for_run(run_id)
        if found:
            tl_submit = found[0]
        else:
            # fallback infer from items
            langs_seen = set()
            for it in (items or []):
                for w in (it.get('words') or []):
                    r = get_word_row(str(w), '', None)
                    if r and (r.get('language') or '').strip():
                        langs_seen.add((r.get('language') or '').strip().lower())
            if langs_seen:
                tl_submit = sorted(list(langs_seen))[0]
    except Exception:
        tl_submit = None

    # Update word stats for current answers only - use local database for authenticated users
    now = datetime.now(UTC).isoformat()
    for a in (answers or []):
        try:
            i = int(a.get('idx'))
        except Exception:
            continue
        user_t = (a.get('translation') or '').strip()
        ref_t = ref_map.get(i, '')
        sim_i = similarity_score(user_t, ref_t)
        passed = bool(sim_i >= 0.75)
        # find item words
        item = next((it for it in items if int(it['idx'])==i), None)
        if not item:
            continue
        for w in (item.get('words') or []):
            # seen +0,5, correct +0,5 if passed, familiarity bounded [0,5]
            delta = 1 if passed else -1
            
            # Update local database for authenticated users
            if user_id:
                try:
                    from server.db_multi_user import get_user_native_language
                    from server.multi_user_db import db_manager
                    
                    native_language = get_user_native_language(user_id)
                    word_hash = db_manager.generate_word_hash(w, tl_submit or '', native_language)
                    
                    # Update familiarity in local database
                    db_manager.update_word_familiarity(
                        user_id, 
                        native_language, 
                        word_hash, 
                        delta, 
                        passed
                    )
                except Exception as e:
                    print(f"Error updating local familiarity for word {w}: {e}")
            else:
                # Fallback to global database for unauthenticated users
                try:
                    conn.execute(
                        'UPDATE words SET seen_count=COALESCE(seen_count,0)+1, correct_count=COALESCE(correct_count,0)+?, '
                        'familiarity=CASE WHEN COALESCE(familiarity,0)+? < 0 THEN 0 WHEN COALESCE(familiarity,0)+? > 5 THEN 5 ELSE COALESCE(familiarity,0)+? END, '
                        'updated_at=? WHERE word=? AND (language=? OR ?="")',
                        (1 if passed else 0, delta, delta, delta, now, w, tl_submit or '', tl_submit or '')
                    )
                    if conn.total_changes == 0:
                        # fallback: try lowercase token to be resilient to capitalization
                        wl = str(w or '').lower()
                        if wl != w:
                            conn.execute(
                                'UPDATE words SET seen_count=COALESCE(seen_count,0)+1, correct_count=COALESCE(correct_count,0)+?, '
                                'familiarity=CASE WHEN COALESCE(familiarity,0)+? < 0 THEN 0 WHEN COALESCE(familiarity,0)+? > 5 THEN 5 ELSE COALESCE(familiarity,0)+? END, '
                                'updated_at=? WHERE word=? AND (language=? OR ?="")',
                                (1 if passed else 0, delta, delta, delta, now, wl, tl_submit or '', tl_submit or '')
                            )
                except Exception:
                    pass
    
    if not user_id:
        conn.commit()

    # Bewertung über alle bisher beantworteten Indizes
    results, total, count = [], 0.0, 0
    for idx, user_t in by_idx.items():
        ref_t = ref_map.get(idx, '')
        sim = float(similarity_score(user_t, ref_t))
        results.append({'idx': idx, 'similarity': round(sim, 3), 'ref': ref_t})
        total += sim; count += 1

    score = round(total / max(1, count), 3)

    merged_list = [{'idx': i, 'translation': by_idx[i]} for i in sorted(by_idx)]
    conn.execute('UPDATE level_runs SET user_translations=?, score=? WHERE id=?',
                 (json.dumps(merged_list, ensure_ascii=False), score, run_id))
    conn.commit()
    # Aggregate familiarity over all unique words in this run (ordered)
    all_words = _unique_words_from_items(items)

    # Prefer FS lookup by run_id to determine correct language and level
    lang_level = _find_level_file_for_run(run_id)
    tl = None
    lvl_val = int(row['level'] or 0)
    if lang_level:
        tl, lvl_val, fs_js = lang_level
    else:
        # fallback via words table
        try:
            langs_seen=set()
            for w in all_words:
                r = get_word_row(str(w), '', None)
                if r and (r.get('language') or '').strip():
                    langs_seen.add((r.get('language') or '').strip().lower())
            if langs_seen: tl = sorted(list(langs_seen))[0]
        except Exception:
            tl=None

    try:
        fam_counts = fam_counts_for_words(all_words, tl) if tl else fam_counts_for_words(all_words)
    except Exception:
        fam_counts = {str(i):0 for i in range(6)}

    # Update user progress if authenticated
    if user_id and tl:
        status = 'completed' if score >= 0.6 else 'in_progress'
        update_user_level_progress(user_id, tl, lvl_val, status, score)

    payload = {'success': True, 'score': score, 'results': results, 'fam_counts': fam_counts, 'words_count': len(all_words), 'user_id': user_id}
    conn.close()

    # NOTE: Global level file updates removed - progress is now user-specific only
    # User progress is saved via update_user_level_progress() above

    return jsonify(payload)

############################
# Practice (Flashcards) API v1
############################


# Removed duplicate API endpoint - using the JSON-based one below

@practice_bp.post('/api/practice/grade')
def api_practice_grade():
    payload = request.get_json(force=True) or {}
    run_id = int(payload.get('run_id') or 0)
    level = int(payload.get('level') or 0)
    lang = (payload.get('language') or 'en').strip().lower()
    word = (payload.get('word') or '').strip()
    mark = (payload.get('mark') or '').strip().lower()  # 'bad'|'ok'|'good'
    
    if run_id <= 0 or not word or mark not in ('bad','ok','good'):
        return jsonify({'success': False, 'error': 'run_id, word, mark required'}), 400
    
    custom_session = None
    practice_words = []
    current_run = None
    js = None

    if level > 0:
        js = _read_level(lang, level)
        if not js:
            return jsonify({'success': False, 'error': 'level not found'}), 404
        runs = js.get('runs') or []
        for r in runs:
            if int(r.get('run_id', 0)) == run_id:
                current_run = r
                break

    if current_run:
        practice_words = current_run.get('practice_words', [])
        if not practice_words:
            for it in (js.get('items') or []):
                for w in (it.get('words') or []):
                    w = str(w).strip()
                    if w and w not in practice_words:
                        practice_words.append(w)
            import random as _r
            _r.shuffle(practice_words)
            practice_words = practice_words[:10]
    else:
        custom_session = _get_custom_practice_session(lang, run_id)
        if not custom_session:
            return jsonify({'success': False, 'error': 'run not found'}), 404
        practice_words = list(custom_session.get('practice_words', []))
        level = 0
    
    # Update familiarity in user-specific local database
    delta_map = {'bad': -1.0, 'ok': 0.5, 'good': 1.0}
    delta = float(delta_map.get(mark, 0.0))
    
    # Get user context from middleware
    user_context = get_user_context()
    user_id = user_context['user_id']
    is_authenticated = user_id is not None
    
    # If not authenticated via middleware, try to get user from Authorization header
    if not is_authenticated:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            session_token = auth_header[7:]
            from server.db_multi_user import get_user_by_session_token
            user = get_user_by_session_token(session_token)
            if user:
                user_id = user['id']
                is_authenticated = True
    
    if is_authenticated:
        try:
            from server.db_multi_user import get_user_native_language
            from server.multi_user_db import db_manager
            
            # Get user's native language
            native_language = get_user_native_language(user_id)
            
            # Generate word hash for the word
            word_hash = db_manager.generate_word_hash(word, lang, native_language)
            
            # Get current familiarity to calculate new value
            familiarity_data = db_manager.get_user_word_familiarity(user_id, native_language, [word_hash])
            current_familiarity = 0
            if word_hash in familiarity_data:
                current_familiarity = familiarity_data[word_hash]['familiarity']
            
            # Calculate new familiarity value
            new_familiarity = max(0, min(5, current_familiarity + delta))
            
            # Update familiarity in user's local database
            success = db_manager.update_user_word_familiarity(
                user_id=user_id,
                native_language=native_language,
                word_hash=word_hash,
                familiarity=new_familiarity
            )
            
            # Success is handled silently - no need for debug output
        except Exception as e:
            print(f"Error updating user word familiarity: {e}")
            import traceback
            traceback.print_exc()
    else:
        # For unauthenticated users, update global database (legacy behavior)
        now = datetime.now(UTC).isoformat()
        try:
            conn = get_db(); cur = conn.cursor()
            # Update with language filter to ensure correct word matching
            cur.execute('UPDATE words SET familiarity=CASE WHEN COALESCE(familiarity,0)+? < 0 THEN 0 WHEN COALESCE(familiarity,0)+? > 5 THEN 5 ELSE COALESCE(familiarity,0)+? END, updated_at=? WHERE word=? AND (language=? OR ?="")',
                        (delta_map[mark], delta_map[mark], delta_map[mark], now, word, lang, lang))
            conn.commit(); conn.close()
        except Exception:
            pass
    
    # Track practiced words in the run
    if custom_session is not None:
        practiced_words = list(custom_session.get('practiced_words', []))
    else:
        practiced_words = current_run.get('practiced_words', [])

    if word not in practiced_words:
        practiced_words.append(word)

    if custom_session is not None:
        custom_session['practiced_words'] = practiced_words
    else:
        current_run['practiced_words'] = practiced_words
        # Save updated run data back to level file
        _write_level(lang, level, js)
    
    # Get next word from practice session
    import random as _r
    remaining_words = [w for w in practice_words if w not in practiced_words]
    _r.shuffle(remaining_words)
    next_word = remaining_words[0] if remaining_words else ''
    done = len(remaining_words) == 0
    
    # Calculate correct remaining count (excluding the next word that will be shown)
    remaining_count = len(remaining_words) - 1 if next_word else 0
    seen_count = len(practiced_words)
    
    if custom_session is not None:
        if done:
            _update_custom_practice_session(lang, custom_session, delete=True)
        else:
            custom_session['practice_words'] = practice_words
            _update_custom_practice_session(lang, custom_session)

    return jsonify({'success': True, 'done': done, 'word': next_word, 'remaining': remaining_count, 'seen': seen_count})


@levels_bp.get('/api/level/stats')
def api_level_stats_fs():
    lvl_raw = request.args.get('level')
    if not lvl_raw:
        return jsonify({'success': False, 'error': 'level required'}), 400
    try:
        level = int(lvl_raw)
    except Exception:
        return jsonify({'success': False, 'error': 'invalid level'}), 400
    lang = (request.args.get('language') or 'en').strip().lower()
    _ensure_course_dirs(lang)
    js = _read_level(lang, level)
    if not js:
        return jsonify({'success': False, 'error': 'not found'}), 404

    # unique words from items
    words = []
    for it in (js.get('items') or []):
        for w in (it.get('words') or []):
            w = str(w).strip()
            if w and w not in words:
                words.append(w)

    try:
        dist = _fam_counts_for_words(words, lang)
    except Exception:
        dist = {str(i): 0 for i in range(6)}

    js['fam_counts'] = dist
    _write_level(lang, level, js)
    arr = [int(dist.get(str(i), 0) or 0) for i in range(6)]
    return jsonify({'success': True, 'familiarity': arr, 'counts': dist, 'fam_counts': dist})

@app.route('/api/level/<int:level>/words')
def api_level_words(level):
    """Get words from level JSON file"""
    lang = request.args.get('language', 'en').strip().lower()
    _ensure_course_dirs(lang)
    
    js = _read_level(lang, level)
    if not js:
        return jsonify({'success': False, 'error': 'Level not found'}), 404
    
    # Collect unique words from level
    words = []
    for item in (js.get('items') or []):
        for word in (item.get('words') or []):
            if word and word not in words:
                words.append(word)
    
    return jsonify({'success': True, 'words': words, 'count': len(words)})

@app.route('/api/words/familiarity-count')
def api_words_familiarity_count():
    """Get count of words with specific familiarity level"""
    lang = request.args.get('language', 'en').strip().lower()
    level = request.args.get('level')
    familiarity = request.args.get('familiarity', '5')
    
    # Get user context from middleware
    user_context = get_user_context()
    user_id = user_context['user_id']
    
    try:
        if level:
            # Use new multi-user system
            if user_id:
                try:
                    # Get user-specific familiarity counts
                    from server.db_multi_user import get_familiarity_counts_for_level
                    fam_counts = get_familiarity_counts_for_level(lang, int(level), user_id)
                    count = int(fam_counts.get(int(familiarity), 0))
                except Exception as e:
                    print(f"Error getting familiarity counts for level {level}: {e}")
                    count = 0
            else:
                # For unauthenticated users, return 0
                count = 0
        else:
            # Count all words with specified familiarity for the language
            if user_id:
                try:
                    # Get user's native language and count from local database
                    from server.db_multi_user import get_user_native_language, ensure_user_databases
                    native_language = get_user_native_language(user_id)
                    ensure_user_databases(user_id, native_language)
                
                    # Count words with specified familiarity level
                    from server.multi_user_db import db_manager
                    import sqlite3
                    import os
                    db_path = db_manager.get_user_db_path(user_id, native_language)
                    if os.path.exists(db_path):
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cur = conn.cursor()
                        
                        cur.execute("""
                            SELECT COUNT(*) as count
                            FROM words_local
                            WHERE familiarity = ?
                        """, (int(familiarity),))
                        
                        row = cur.fetchone()
                        count = row['count'] if row else 0
                        conn.close()
                    else:
                        count = 0
                except Exception as e:
                    print(f"Error counting words familiarity for user {user_id}: {e}")
                    count = 0
            else:
                # For unauthenticated users, return 0
                count = 0
        
        return jsonify({'success': True, 'count': count})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/words/familiarity-counts')
def api_words_familiarity_counts():
    """Get all familiarity counts for a specific level in one call"""
    lang = request.args.get('language', 'en').strip().lower()
    level = request.args.get('level')
    user_context = get_user_context()
    user_id = user_context['user_id']
    
    if not level:
        return jsonify({'success': False, 'error': 'level parameter required'}), 400
    
    try:
        if user_id:
            try:
                # Use existing function to get all familiarity counts for the level
                from server.db_multi_user import get_familiarity_counts_for_level
                fam_counts = get_familiarity_counts_for_level(lang, int(level), user_id)
                return jsonify({'success': True, 'fam_counts': fam_counts})
            except Exception as e:
                print(f"Error getting familiarity counts for level {level}: {e}")
                # Return all zeros if function fails
                return jsonify({'success': True, 'fam_counts': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}})
        else:
            # For unauthenticated users, return all zeros
            return jsonify({'success': True, 'fam_counts': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}})
    except Exception as e:
        print(f"Error in api_words_familiarity_counts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/levels/bulk-stats')
def api_levels_bulk_stats():
    """Get stats for multiple levels in one call"""
    try:
        lang = request.args.get('language', 'en').strip().lower()
        levels_param = request.args.get('levels', '1,2,3,4,5')
        user_context = get_user_context()
        user_id = user_context['user_id']
        
        print(f"🔍 Bulk-stats request: lang={lang}, levels={levels_param}, user_id={user_id}")
        
        # Handle unauthenticated users - return empty stats instead of error
        if user_id is None:
            print("📊 Returning empty stats for unauthenticated user")
            return jsonify({'success': True, 'stats': {}, 'levels': {}})
        
        try:
            # Parse levels parameter
            levels = []
            for level_str in levels_param.split(','):
                try:
                    level = int(level_str.strip())
                    if 1 <= level <= 50:  # Reasonable range
                        levels.append(level)
                except ValueError:
                    continue
        
            if not levels:
                return jsonify({'success': False, 'error': 'no valid levels provided'}), 400
        
            result = {}
            
            if user_id:
                # Get user-specific data for all levels
                try:
                    from server.db_multi_user import get_user_native_language, ensure_user_databases
                    from server.multi_user_db import db_manager
                    native_language = get_user_native_language(user_id)
                    ensure_user_databases(user_id, native_language)
                except Exception as db_error:
                    print(f"Error setting up user databases for user {user_id}: {db_error}")
                    # Fall back to unauthenticated behavior
                    user_id = None
                
                for level in levels:
                    try:
                        # Get user-specific level content first
                        user_level_content = _read_level(lang, level, user_id)
                        
                        # Get level stats for this level
                        user_stats = get_user_level_stats(user_id, lang, level)
                        global_stats = get_global_level_stats(lang, level)
                        
                        # Get user progress for status/score
                        from server.db import get_user_progress
                        user_progress_data = get_user_progress(user_id, lang, native_language)
                        user_progress = next((p for p in user_progress_data if p['level'] == level), None)
                    
                        if user_progress:
                            status = user_progress['status']
                            last_score = user_progress['score']
                        else:
                            status = 'not_started'
                            last_score = None
                        
                        result[level] = {
                            'success': True,
                            'language': lang,
                            'level': level,
                            'fam_counts': user_stats['familiarity_counts'],
                            'status': status,
                            'last_score': last_score,
                            'total_words': user_stats['total_words'],
                            'memorized_words': user_stats['memorized_words'],
                            'level_score': user_stats['level_score'],
                            'user_progress': user_progress,
                            'words': user_stats.get('words', []),
                            'word_hashes': user_stats.get('word_hashes', []),
                            'familiarity_data': user_stats.get('familiarity_data', {})
                        }
                    except Exception as e:
                        result[level] = {
                            'success': False,
                            'error': str(e),
                            'level': level
                        }
            else:
                # For unauthenticated users, return empty data
                for level in levels:
                    level_words_info = get_level_words_with_familiarity(lang, level, None)
                    plain_words = level_words_info.get('words', [])
                    hash_keys = []
                    for w in plain_words:
                            key = f"{lang}:{w.strip().lower()}"
                            hash_keys.append(key)

                    result[level] = {
                            'success': True,
                            'language': lang,
                            'level': level,
                            'fam_counts': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                            'status': 'not_started',
                            'last_score': None,
                            'total_words': level_words_info.get('total_words', len(plain_words)),
                            'memorized_words': 0,
                            'level_score': 0,
                            'user_progress': None,
                            'words': plain_words,
                            'word_hashes': hash_keys,
                            'familiarity_data': {}
                    }
        
            # Add header stats to the response
            header_stats = {}
            # Compute header stats from requested levels
            try:
                all_word_ids = set()
                memorized_ids = set()
                for lvl in levels:
                    entry = result.get(lvl)
                    if not entry or not entry.get('success'):
                            continue
                    word_hashes = entry.get('word_hashes') or []
                    words_list = entry.get('words') or []
                    familiarity_data = entry.get('familiarity_data') or {}

                    # Ensure hash list aligns with words list
                    if not word_hashes:
                            for idx, word in enumerate(words_list):
                                key = f"{lang}:{str(word).strip().lower()}"
                                word_hashes.append(key)
                    
                    for idx, hash_key in enumerate(word_hashes):
                            if not hash_key:
                                # fallback to normalized word string
                                base_word = words_list[idx] if idx < len(words_list) else ''
                                hash_key = f"{lang}:{str(base_word).strip().lower()}"
                            all_word_ids.add(hash_key)
                            fam_entry = familiarity_data.get(hash_key)
                            if fam_entry and isinstance(fam_entry, dict):
                                try:
                                    fam_value = fam_entry.get('familiarity', fam_entry.get('familiarity_level', 0))
                                except Exception:
                                    fam_value = 0
                                if fam_value is not None and float(fam_value) >= 5:
                                    memorized_ids.add(hash_key)

                header_stats = {
                    'total_words': len(all_word_ids),
                    'memorized_words': len(memorized_ids)
                }
            except Exception as e:
                print(f"Error computing header stats: {e}")
                header_stats = {'total_words': 0, 'memorized_words': 0}

            return jsonify({'success': True, 'levels': result, 'header_stats': header_stats})

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _custom_practice_sessions_path(lang: str) -> Path:
    base = DATA_DIR / lang
    base.mkdir(parents=True, exist_ok=True)
    return base / 'practice_sessions.json'


def _load_custom_practice_sessions(lang: str) -> list:
    path = _custom_practice_sessions_path(lang)
    if not path.exists():
        return []
    try:
        with path.open('r', encoding='utf-8') as fh:
            return json.load(fh) or []
    except Exception:
        return []


def _save_custom_practice_sessions(lang: str, sessions: list) -> None:
    path = _custom_practice_sessions_path(lang)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(path.parent), encoding='utf-8') as tmp:
        json.dump(sessions, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_name = tmp.name
    os.replace(temp_name, path)


def _create_custom_practice_session(lang: str, words: list, label: str, exclude_max: bool) -> int:
    sessions = _load_custom_practice_sessions(lang)
    next_id = (max((int(s.get('run_id', 0)) for s in sessions), default=0) + 1)
    session = {
        'run_id': int(next_id),
        'language': lang,
        'practice_words': list(words),
        'practiced_words': [],
        'created_at': datetime.now(UTC).isoformat(),
        'label': label,
        'exclude_max': bool(exclude_max)
    }
    sessions = [s for s in sessions if int(s.get('run_id', -1)) != int(next_id)]
    sessions.append(session)
    _save_custom_practice_sessions(lang, sessions)
    return int(next_id)


def _get_custom_practice_session(lang: str, run_id: int) -> dict | None:
    sessions = _load_custom_practice_sessions(lang)
    for session in sessions:
        try:
            if int(session.get('run_id', 0)) == int(run_id):
                return session
        except Exception:
            continue
    return None


def _update_custom_practice_session(lang: str, updated: dict | None, *, delete: bool = False) -> None:
    sessions = _load_custom_practice_sessions(lang)
    run_id = int(updated.get('run_id', 0)) if updated else None
    filtered = []
    for session in sessions:
        try:
            if run_id is not None and int(session.get('run_id', 0)) == run_id:
                if not delete and updated:
                    filtered.append(updated)
                continue
        except Exception:
            pass
        filtered.append(session)
    _save_custom_practice_sessions(lang, filtered)

@levels_bp.post('/api/level/unlock-words')
def api_level_unlock_words():
    """Start a level and unlock words for user"""
    try:
        data = request.get_json(force=True) or {}
        level = int(data.get('level', 1))
        language = data.get('language', 'en').strip()
        
        if not language:
            return jsonify({'success': False, 'error': 'language required'}), 400
        
        # Get user context from middleware
        user_context = get_user_context()
        user_id = user_context['user_id']
        
        if not user_id:
            return jsonify({'success': False, 'error': 'authentication required'}), 401
        
        # Unlock words for this level
        success = unlock_level_words(user_id, language, level)
        
        if success:
            return jsonify({'success': True, 'message': f'Words unlocked for level {level}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to unlock words'}), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@levels_bp.post('/api/level/sync-data')
def api_sync_user_data():
    """Sync user data from database to file system"""
    try:
        # Get user context from middleware
        user_context = get_user_context()
        user_id = user_context['user_id']
        
        if not user_id:
            return jsonify({'success': False, 'error': 'authentication required'}), 401
        
        # Sync user data
        migrate_user_data_structure(user_id)
        
        return jsonify({'success': True, 'message': 'User data synchronized successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@levels_bp.post('/api/level/sync-words')
def api_sync_words():
    """Sync all words for a user to ensure they appear in Words tab"""
    try:
        # Get user context from middleware
        user_context = get_user_context()
        user_id = user_context['user_id']
        
        if not user_id:
            return jsonify({'success': False, 'error': 'authentication required'}), 401
        
        # Get language parameter
        data = request.get_json(force=True) or {}
        language = data.get('language', '').strip()
        
        if not language:
            return jsonify({'success': False, 'error': 'language required'}), 400
        
        # Sync words for the specified language
        from server.word_sync import sync_words_for_user
        
        success = sync_words_for_user(user_id, language)
        
        if success:
            return jsonify({'success': True, 'message': f'Words synchronized successfully for language {language}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to synchronize words'}), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/bug-report', methods=['POST'])
def api_bug_report():
    """Submit a bug report from a logged-in user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        # Check if user is logged in
        if not user_id:
            return jsonify({'error': 'User must be logged in to submit bug reports'}), 401
        
        # Get user information
        from server.db_multi_user import get_user_native_language
        native_language = get_user_native_language(user_id)
        
        # Extract bug report data
        bug_data = {
            'user_id': user_id,
            'native_language': native_language,
            'timestamp': datetime.now(UTC).isoformat(),
            'title': data.get('title', ''),
            'description': data.get('description', ''),
            'steps_to_reproduce': data.get('steps_to_reproduce', ''),
            'expected_behavior': data.get('expected_behavior', ''),
            'actual_behavior': data.get('actual_behavior', ''),
            'browser_info': data.get('browser_info', ''),
            'device_info': data.get('device_info', ''),
            'current_url': data.get('current_url', ''),
            'language': data.get('language', ''),
            'level': data.get('level', ''),
            'severity': data.get('severity', 'medium'),
            'status': 'open'
        }
        
        # Save bug report to file
        from pathlib import Path
        import json
        
        bug_reports_dir = Path('bug_reports')
        bug_reports_dir.mkdir(exist_ok=True)
        
        # Create filename with timestamp and user ID
        timestamp_str = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        filename = f"bug_report_{user_id}_{timestamp_str}.json"
        filepath = bug_reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(bug_data, f, ensure_ascii=False, indent=2)
        
        print(f"Bug report saved: {filepath}")
        
        return jsonify({
            'message': 'Bug report submitted successfully',
            'report_id': filename
        })
        
    except Exception as e:
        print(f"Error submitting bug report: {e}")
        return jsonify({'error': 'Failed to submit bug report'}), 500

@app.route('/api/bug-reports', methods=['GET'])
def api_get_bug_reports():
    """Get all bug reports for admin viewing"""
    try:
        from pathlib import Path
        import json
        
        bug_reports_dir = Path('bug_reports')
        if not bug_reports_dir.exists():
            return jsonify([])
        
        reports = []
        for file_path in bug_reports_dir.glob('bug_report_*.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                    reports.append(report_data)
            except Exception as e:
                print(f"Error reading bug report {file_path}: {e}")
                continue
        
        # Sort by timestamp (newest first)
        reports.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify(reports)
        
    except Exception as e:
        print(f"Error getting bug reports: {e}")
        return jsonify({'error': 'Failed to get bug reports'}), 500

@app.route('/bug-reports')
def bug_reports_viewer():
    """Serve the bug reports viewer page"""
    return send_from_directory('.', 'bug_reports_viewer.html')

@practice_bp.post('/api/practice/start')
def api_practice_start_fs():
    data = request.get_json(silent=True) or {}
    lvl_raw = data.get('level')
    custom_words_input = data.get('custom_words') or data.get('words') or []
    try:
        custom_words = [str(w).strip() for w in custom_words_input if str(w).strip()]
    except Exception:
        custom_words = []
    is_custom_session = bool(custom_words)

    if not lvl_raw and not is_custom_session:
        return jsonify({'success': False, 'error': 'level required'}), 400
    try:
        level = int(lvl_raw or 0)
    except Exception:
        return jsonify({'success': False, 'error': 'invalid level'}), 400
    lang = (data.get('language') or request.args.get('language') or 'en').strip().lower()
    exclude_max = bool(data.get('exclude_max', True))
    peek = bool(data.get('peek', False))
    _ensure_course_dirs(lang)

    js = None
    words = []
    if is_custom_session:
        seen = set()
        for w in custom_words:
            lw = w.strip()
            if lw and lw.lower() not in seen:
                seen.add(lw.lower())
                words.append(lw)
    else:
        js = _read_level(lang, level)
        if not js:
            return jsonify({'success': False, 'error': 'not found'}), 404

        # collect unique words
        for it in (js.get('items') or []):
            for w in (it.get('words') or []):
                w = str(w).strip()
                if w and w not in words:
                    words.append(w)

    # filter out fam==5 if requested
    if exclude_max and words:
        kept = []
        user_context = get_user_context()
        user_id = user_context['user_id']
        if user_id:
            from server.db_multi_user import get_user_native_language
            from server.multi_user_db import db_manager
            
            # Get user's native language
            native_language = get_user_native_language(user_id)
            
            # Generate word hashes for all words
            word_hashes = []
            for w in words:
                word_hash = db_manager.generate_word_hash(w, lang, native_language)
                word_hashes.append(word_hash)
            
            # Get familiarity data for all words at once
            familiarity_data = db_manager.get_user_word_familiarity(user_id, native_language, word_hashes)
            
            # Filter words based on familiarity
            for w in words:
                word_hash = db_manager.generate_word_hash(w, lang, native_language)
                fam = 0
                if word_hash in familiarity_data:
                    fam = familiarity_data[word_hash]['familiarity']
                if fam < 5:
                    kept.append(w)
        else:
            # For unauthenticated users, keep all words
            kept = words
        words = kept

    if not words:
        return jsonify({'success': True, 'run_id': None, 'word': '', 'remaining': 0, 'total': 0})

    import random as _r
    _r.shuffle(words)
    words = words[:10]  # cap session size

    if peek:
        return jsonify({'success': True, 'run_id': None, 'word': '', 'remaining': len(words), 'total': len(words)})

    if is_custom_session:
        run_id = _create_custom_practice_session(lang, words, data.get('label', 'custom'), exclude_max)
        first = words[0]
        remaining = max(0, len(words) - 1)
        return jsonify({'success': True, 'run_id': run_id, 'level': 0, 'language': lang,
                        'word': first, 'remaining': remaining, 'total': len(words), 'seen': 0})

    runs = js.get('runs') or []
    next_id = (max([r.get('run_id', 0) for r in runs]) + 1) if runs else 1
    run = {'run_id': next_id, 'ts': datetime.now(UTC).isoformat(), 'score': None,
           'fam_counts': js.get('fam_counts') or {str(i): 0 for i in range(6)},
           'practice_words': words}  # Store the 10 words for this practice session
    runs.append(run)
    js['runs'] = runs
    _write_level(lang, level, js)

    first = words[0]
    remaining = max(0, len(words) - 1)
    return jsonify({'success': True, 'run_id': next_id, 'level': level, 'language': lang,
                    'word': first, 'remaining': remaining, 'total': len(words), 'seen': 0})


def _ensure_course_dirs(lang: str):
    base = DATA_DIR / lang
    (base / 'levels').mkdir(parents=True, exist_ok=True)

@levels_bp.post('/api/course/init')
def api_course_init():
    data = request.get_json(silent=True) or {}
    lang = (data.get('language') or request.args.get('language') or 'en').strip().lower()
    _ensure_course_dirs(lang)
    return jsonify({'success': True, 'language': lang})


# New endpoint: level summaries with status and last_score
@levels_bp.get('/api/levels/summary')
def api_levels_summary_fs():
    lang = (request.args.get('language') or 'en').strip().lower()
    
    # Get user context from middleware
    user_context = get_user_context()
    user_id = user_context['user_id']
    
    try:
        _ensure_course_dirs(lang)
    except Exception:
        pass
    
    # Get user progress if authenticated
    user_progress_data = []
    if user_id:
        try:
            # Check and migrate global data to user data if needed
            migrate_user_data_structure(user_id)
            
            from server.db import get_user_progress, get_user_familiarity_counts
            from server.db_multi_user import get_user_native_language
            native_language = get_user_native_language(user_id)
            user_progress_data = get_user_progress(user_id, lang, native_language)
            user_fam_counts = get_user_familiarity_counts(user_id, lang)
        except Exception as e:
            print(f"Error getting user progress: {e}")
            user_fam_counts = None
    else:
        user_fam_counts = None
    
    out = []
    for lvl in _list_levels(lang):
        js = _read_level(lang, lvl) or {}
        runs = js.get('runs') or []
        last = max(runs, key=lambda r: r.get('run_id', 0)) if runs else None
        
        # Get user-specific progress for this level
        user_level_progress = next((p for p in user_progress_data if p['level'] == lvl), None)
        
        # If user is authenticated, only show user-specific data
        if user_id:
            # Use user-specific familiarity counts
            fam_counts = user_fam_counts or {str(i):0 for i in range(6)}
            
            # Use user-specific status/score
            if user_level_progress:
                status = user_level_progress['status']
                score = user_level_progress['score']
            else:
                status = 'not_started'
                score = None
        else:
            # For unauthenticated users, show no progress data
            fam_counts = {str(i):0 for i in range(6)}
            status = 'not_started'
            score = None
        
        out.append({
            'language': lang,
            'level': lvl,
            'run_id': (last or {}).get('run_id'),
            'score': score,
            'last_score': score,
            'fam_counts': fam_counts,
            'status': status,
            'user_progress': user_level_progress
        })
    return jsonify({'success': True, 'levels': out})
    # --- If there is a submit endpoint that assembles a payload with fam_counts, swap computation similarly
    # (Search for payload = { ... 'fam_counts': ... })

@levels_bp.post('/api/language/validate')
def api_language_validate():
    """Validate and add a new language through AI"""
    data = request.get_json(silent=True) or {}
    language_name = data.get('language_name', '').strip()
    native_lang = data.get('native_lang', 'de').strip()
    
    if not language_name:
        return jsonify({'success': False, 'error': 'language_name is required'}), 400
    
    try:
        # Use AI to validate and generate language code
        prompt = f"""You are a language expert. The user wants to add a new language to a language learning system.

Language name: {language_name}
Native language: {native_lang}

Please:
1. Validate that this is a real, learnable language
2. Provide a 2-3 letter ISO language code (e.g., 'sv' for Swedish, 'pl' for Polish)
3. Confirm the language name is correct

Respond in JSON format:
{{
    "is_valid": true/false,
    "language_code": "xx",
    "language_name": "Corrected name if needed",
    "reasoning": "Brief explanation"
}}

If the language is not valid, set is_valid to false and provide a reason."""
        
        # Call AI service
        from server.services.llm import _http_json, OPENAI_KEY, OPENAI_BASE
        if not OPENAI_KEY:
            return jsonify({'success': False, 'error': 'AI service not available'}), 500
        
        response = _http_json(
            f"{OPENAI_BASE}/chat/completions",
            {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 200
            },
            {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'}
        )
        
        if not response or 'choices' not in response:
            return jsonify({'success': False, 'error': 'AI service error'}), 500
        
        content = response['choices'][0]['message']['content']
        
        # Parse AI response
        import json
        try:
            # Try to extract JSON from the response if it's wrapped in markdown
            content_clean = content.strip()
            if content_clean.startswith('```json'):
                content_clean = content_clean[7:]
            if content_clean.endswith('```'):
                content_clean = content_clean[:-3]
            content_clean = content_clean.strip()
            
            ai_result = json.loads(content_clean)
        except json.JSONDecodeError:
            print(f"AI response parsing failed. Raw content: {content}")
            return jsonify({'success': False, 'error': 'Invalid AI response format'}), 500
        
        if not ai_result.get('is_valid', False):
            return jsonify({'success': False, 'error': ai_result.get('reasoning', 'Language not valid')}), 400
        
        language_code = ai_result.get('language_code', '').lower()
        if not language_code or len(language_code) < 2:
            return jsonify({'success': False, 'error': 'Invalid language code generated'}), 500
        
        # Check if language already exists
        if (DATA_DIR / language_code).exists():
            return jsonify({'success': False, 'error': 'Language already exists'}), 409
        
        # Create language directory structure
        _ensure_course_dirs(language_code)
        
        # Create basic course.json if it doesn't exist
        course_file = DATA_DIR / language_code / 'course.json'
        if not course_file.exists():
            course_data = {
                "name": ai_result.get('language_name', language_name),
                "code": language_code,
                "native_name": ai_result.get('language_name', language_name),
                "created": datetime.now(UTC).isoformat(),
                "ai_validated": True
            }
            with course_file.open('w', encoding='utf-8') as f:
                json.dump(course_data, f, ensure_ascii=False, indent=2)
        
        # Create first level with basic content
        level_1_file = DATA_DIR / language_code / 'levels' / '1.json'
        if not level_1_file.exists():
            # Generate basic first level content using AI
            level_prompt = f"""Generate a basic first lesson for {ai_result.get('language_name', language_name)} (language code: {language_code}).

Create exactly 5 simple sentences suitable for absolute beginners. Each sentence should be 3-6 words.

Output JSON format:
{{
    "items": [
        {{
            "text_target": "sentence in target language",
            "words": ["word1", "word2", "word3"]
        }}
    ],
    "meta": {{
        "level": 1,
        "section": "Foundations",
        "theme": "Basic greetings and introductions"
    }}
}}

Keep sentences very simple and natural for {ai_result.get('language_name', language_name)}."""
            
            level_response = _http_json(
                f"{OPENAI_BASE}/chat/completions",
                {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": level_prompt}],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'}
            )
            
            if level_response and 'choices' in level_response:
                level_content = level_response['choices'][0]['message']['content']
                try:
                    level_data = json.loads(level_content)
                    level_data['runs'] = []
                    level_data['fam_counts'] = {str(i): 0 for i in range(6)}
                    with level_1_file.open('w', encoding='utf-8') as f:
                        json.dump(level_data, f, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    # Fallback to basic structure if AI fails
                    fallback_data = {
                        "items": [
                            {"text_target": "Hello", "words": ["hello"]},
                            {"text_target": "Good morning", "words": ["good", "morning"]},
                            {"text_target": "How are you?", "words": ["how", "are", "you"]},
                            {"text_target": "Thank you", "words": ["thank", "you"]},
                            {"text_target": "Goodbye", "words": ["goodbye"]}
                        ],
                        "meta": {
                            "level": 1,
                            "section": "Foundations",
                            "theme": "Basic greetings"
                        },
                        "runs": [],
                        "fam_counts": {str(i): 0 for i in range(6)}
                    }
                    
                    with level_1_file.open('w', encoding='utf-8') as f:
                        json.dump(fallback_data, f, ensure_ascii=False, indent=2)
        
        # Generate all levels 2-50 with minimal content
        for level_num in range(2, 51):
            level_file = DATA_DIR / language_code / 'levels' / f'{level_num}.json'
            if not level_file.exists():
                placeholder_data = {
                    "items": [],
                    "meta": {
                        "level": level_num,
                        "section": "Placeholder",
                        "theme": "Not yet generated"
                    },
                    "runs": [],
                    "fam_counts": {str(i): 0 for i in range(6)},
                    "status": None,
                    "score": None,
                    "last_score": None,
                    "placeholder": True,
                    "created": datetime.now(UTC).isoformat()
                }
                
                with level_file.open('w', encoding='utf-8') as f:
                    json.dump(placeholder_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'language_code': language_code,
            'language_name': ai_result.get('language_name', language_name),
            'message': f'Language {ai_result.get("language_name", language_name)} successfully added'
        })
        
    except Exception as e:
        print(f"Error validating language: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@levels_bp.get('/api/languages/list')
def api_languages_list():
    """List all available languages - returns only language codes, names are loaded from localization files"""
    try:
        languages = []
        
        # Check which languages exist in data directory
        for item in DATA_DIR.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # For builtin languages, just return the code
                if item.name in ['en', 'de', 'fr', 'it', 'es', 'pt', 'ru', 'tr', 'ka', 'nl', 'jp', 'ko', 'zh', 'ar', 'da']:
                    languages.append({
                        'code': item.name,
                        'builtin': True
                    })
                else:
                    # For user-added languages, try to read course.json for display name
                    course_file = item / 'course.json'
                    if course_file.exists():
                        try:
                            with course_file.open('r', encoding='utf-8') as f:
                                course_data = json.load(f)
                                display_name = course_data.get('name', item.name.upper())
                        except:
                            display_name = item.name.upper()
                    else:
                        display_name = item.name.upper()
                    
                    languages.append({
                        'code': item.name,
                        'display_name': display_name,  # Only for user-added languages
                        'builtin': False
                    })
        
        # Sort languages: builtin first, then alphabetically
        languages.sort(key=lambda x: (not x['builtin'], x.get('display_name', x['code']).lower()))
        
        return jsonify({
            'success': True,
            'languages': languages
        })
        
    except Exception as e:
        print(f"Error listing languages: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def ensure_all_languages_have_levels():
    """Ensure all languages have levels 1-50"""
    try:
        for lang_dir in DATA_DIR.iterdir():
            if lang_dir.is_dir() and not lang_dir.name.startswith('.'):
                lang_code = lang_dir.name
                levels_dir = lang_dir / 'levels'
                
                # Create levels directory if it doesn't exist
                if not levels_dir.exists():
                    levels_dir.mkdir(parents=True, exist_ok=True)
                
                # Ensure all levels 1-50 exist
                for level_num in range(1, 51):
                    level_file = levels_dir / f'{level_num}.json'
                    if not level_file.exists():
                        if level_num == 1:
                            # Level 1 gets basic content
                            level_data = {
                                "items": [
                                    {"text_target": "Hello", "words": ["hello"]},
                                    {"text_target": "Good morning", "words": ["good", "morning"]},
                                    {"text_target": "How are you?", "words": ["how", "are", "you"]},
                                    {"text_target": "Thank you", "words": ["thank", "you"]},
                                    {"text_target": "Goodbye", "words": ["goodbye"]}
                                ],
                                "meta": {
                                    "level": 1,
                                    "section": "Foundations",
                                    "theme": "Basic greetings"
                                },
                                "runs": [],
                                "fam_counts": {str(i): 0 for i in range(6)}
                            }
                        else:
                            # Levels 2-50 get placeholder content
                            level_data = {
                                "items": [],
                                "meta": {
                                    "level": level_num,
                                    "section": "Placeholder",
                                    "theme": "Not yet generated"
                                },
                                "runs": [],
                                "fam_counts": {str(i): 0 for i in range(6)},
                                "status": None,
                                "score": None,
                                "last_score": None,
                                "placeholder": True,
                                "created": datetime.now(UTC).isoformat()
                            }
                        
                        with level_file.open('w', encoding='utf-8') as f:
                            json.dump(level_data, f, ensure_ascii=False, indent=2)
                        
                        print(f"Generated level {level_num} for language {lang_code}")
        
        print("All languages now have levels 1-50")
    except Exception as e:
        print(f"Error ensuring levels: {e}")

# Ensure all languages have levels when app starts
ensure_all_languages_have_levels()

@levels_bp.get('/api/localization/<lang_code>')
def api_localization(lang_code):
    """Get localization data for a specific language, generate with AI if not exists"""
    try:
        # Get localization data from database
        localization_data = get_localization_for_language(lang_code)
        
        # If we have missing translations, try to fill them with AI
        missing_translations = get_missing_translations(lang_code)
        if missing_translations and OPENAI_KEY:
            try:
                # Create a list of terms to translate
                terms_to_translate = []
                for row in missing_translations:
                    if row['description']:
                        terms_to_translate.append(row['description'])
                    else:
                        terms_to_translate.append(row['reference_key'])
                
                if terms_to_translate:
                    # Use AI to translate missing terms
                    translations = llm_translate_batch(terms_to_translate, lang_code)
                    
                    # Update database with AI translations
                    for i, row in enumerate(missing_translations):
                        if i < len(translations) and translations[i]:
                            payload = {
                                'reference_key': row['reference_key'],
                                lang_code.lower(): translations[i]
                            }
                            upsert_localization_entry(payload)
                    
                    # Get updated localization data
                    localization_data = get_localization_for_language(lang_code)
            except Exception as e:
                print(f"AI translation failed for {lang_code}: {e}")
        
        return jsonify({
            'success': True,
            'localization': localization_data
        })
    except Exception as e:
        print(f"Error loading localization for {lang_code}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@levels_bp.get('/api/localization/entry')
def api_get_localization_entry():
    """Get a localization entry by key and language"""
    try:
        key = request.args.get('key')
        language = request.args.get('language')
        
        if not key or not language:
            return jsonify({'success': False, 'error': 'key and language parameters required'}), 400
        
        entry = get_localization_entry(key, language)
        if entry:
            return jsonify({'success': True, 'localization': entry})
        else:
            return jsonify({'success': True, 'localization': {}})
    except Exception as e:
        print(f"Error getting localization entry: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@levels_bp.post('/api/localization/entry')
def api_localization_entry():
    """Create or update a localization entry"""
    try:
        payload = request.get_json() or {}
        upsert_localization_entry(payload)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating localization entry: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@levels_bp.get('/api/localization/entries')
def api_localization_entries():
    """Get all localization entries"""
    try:
        entries = get_all_localization_entries()
        entries_list = []
        for entry in entries:
            entry_dict = dict(entry)
            entries_list.append(entry_dict)
        
        return jsonify({
            'success': True,
            'entries': entries_list
        })
    except Exception as e:
        print(f"Error getting localization entries: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@levels_bp.post('/api/localization/import-excel')
def api_import_excel():
    """Import localization data from uploaded Excel/CSV file"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Save uploaded file temporarily
        import tempfile
        import os
        import csv
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
            file.save(tmp_file.name)
            temp_file_path = tmp_file.name
        
        try:
            # Import the file using our import function
            from import_excel_localization import import_excel_to_database
            success = import_excel_to_database(temp_file_path)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'File imported successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Import failed'
                }), 500
                
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        print(f"Error importing Excel file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@levels_bp.delete('/api/localization/entry/<int:entry_id>')
def api_delete_localization_entry(entry_id):
    """Delete a localization entry"""
    try:
        conn = sqlite3.connect('polo.db')
        cur = conn.cursor()
        
        # Check if entry exists
        cur.execute('SELECT id FROM localization WHERE id = ?', (entry_id,))
        if not cur.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Entry not found'}), 404
        
        # Delete entry
        cur.execute('DELETE FROM localization WHERE id = ?', (entry_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Entry deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting localization entry: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@levels_bp.get('/api/available-languages')
def api_get_available_languages():
    """Get all available languages with their native names in CSV order"""
    try:
        # Simple hardcoded list for now to get the app working
        languages = [
            {'code': 'en', 'native_name': 'English', 'english_name': 'English'},
            {'code': 'de', 'native_name': 'Deutsch', 'english_name': 'German'},
            {'code': 'fr', 'native_name': 'Français', 'english_name': 'French'},
            {'code': 'es', 'native_name': 'Español', 'english_name': 'Spanish'},
            {'code': 'it', 'native_name': 'Italiano', 'english_name': 'Italian'},
            {'code': 'pt', 'native_name': 'Português', 'english_name': 'Portuguese'},
            {'code': 'ru', 'native_name': 'Русский', 'english_name': 'Russian'},
            {'code': 'ja', 'native_name': '日本語', 'english_name': 'Japanese'},
            {'code': 'ko', 'native_name': '한국어', 'english_name': 'Korean'},
            {'code': 'zh', 'native_name': '中文', 'english_name': 'Chinese'},
            {'code': 'ar', 'native_name': 'العربية', 'english_name': 'Arabic'},
            {'code': 'hi', 'native_name': 'हिन्दी', 'english_name': 'Hindi'},
            {'code': 'tr', 'native_name': 'Türkçe', 'english_name': 'Turkish'},
            {'code': 'pl', 'native_name': 'Polski', 'english_name': 'Polish'},
            {'code': 'nl', 'native_name': 'Nederlands', 'english_name': 'Dutch'},
            {'code': 'sv', 'native_name': 'Svenska', 'english_name': 'Swedish'},
            {'code': 'da', 'native_name': 'Dansk', 'english_name': 'Danish'},
            {'code': 'no', 'native_name': 'Norsk', 'english_name': 'Norwegian'},
            {'code': 'fi', 'native_name': 'Suomi', 'english_name': 'Finnish'},
            {'code': 'is', 'native_name': 'Íslenska', 'english_name': 'Icelandic'},
            {'code': 'ka', 'native_name': 'ქართული', 'english_name': 'Georgian'},
            {'code': 'sr', 'native_name': 'Српски', 'english_name': 'Serbian'},
            {'code': 'sw', 'native_name': 'Kiswahili', 'english_name': 'Swahili'},
            {'code': 'fa', 'native_name': 'فارسی', 'english_name': 'Persian'},
            {'code': 'th', 'native_name': 'ไทย', 'english_name': 'Thai'},
            {'code': 'vi', 'native_name': 'Tiếng Việt', 'english_name': 'Vietnamese'},
            {'code': 'id', 'native_name': 'Bahasa Indonesia', 'english_name': 'Indonesian'},
            {'code': 'mr', 'native_name': 'मराठी', 'english_name': 'Marathi'},
            {'code': 'gu', 'native_name': 'ગુજરાતી', 'english_name': 'Gujarati'},
            {'code': 'ta', 'native_name': 'தமிழ்', 'english_name': 'Tamil'},
            {'code': 'te', 'native_name': 'తెలుగు', 'english_name': 'Telugu'},
            {'code': 'bn', 'native_name': 'বাংলা', 'english_name': 'Bengali'},
            {'code': 'ur', 'native_name': 'اردو', 'english_name': 'Urdu'},
            {'code': 'ro', 'native_name': 'Română', 'english_name': 'Romanian'},
            {'code': 'hu', 'native_name': 'Magyar', 'english_name': 'Hungarian'},
            {'code': 'uk', 'native_name': 'Українська', 'english_name': 'Ukrainian'}
        ]
        
        return jsonify({'languages': languages})
        
    except Exception as e:
        print(f"Error getting available languages: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@levels_bp.get('/api/available-courses')
def api_get_available_courses():
    """Get all available courses (languages with show_course=Yes) with names in the specified native language"""
    try:
        # Simple hardcoded list for now to get the app working
        courses = [
            {'code': 'en', 'name': 'English', 'native_name': 'English', 'english_name': 'English'},
            {'code': 'de', 'name': 'Deutsch', 'native_name': 'Deutsch', 'english_name': 'German'},
            {'code': 'fr', 'name': 'Français', 'native_name': 'Français', 'english_name': 'French'},
            {'code': 'es', 'name': 'Español', 'native_name': 'Español', 'english_name': 'Spanish'},
            {'code': 'it', 'name': 'Italiano', 'native_name': 'Italiano', 'english_name': 'Italian'},
            {'code': 'pt', 'name': 'Português', 'native_name': 'Português', 'english_name': 'Portuguese'},
            {'code': 'ru', 'name': 'Русский', 'native_name': 'Русский', 'english_name': 'Russian'},
            {'code': 'ja', 'name': '日本語', 'native_name': '日本語', 'english_name': 'Japanese'},
            {'code': 'ko', 'name': '한국어', 'native_name': '한국어', 'english_name': 'Korean'},
            {'code': 'zh', 'name': '中文', 'native_name': '中文', 'english_name': 'Chinese'},
            {'code': 'ar', 'name': 'العربية', 'native_name': 'العربية', 'english_name': 'Arabic'},
            {'code': 'hi', 'name': 'हिन्दी', 'native_name': 'हिन्दी', 'english_name': 'Hindi'},
            {'code': 'tr', 'name': 'Türkçe', 'native_name': 'Türkçe', 'english_name': 'Turkish'},
            {'code': 'pl', 'name': 'Polski', 'native_name': 'Polski', 'english_name': 'Polish'},
            {'code': 'nl', 'name': 'Nederlands', 'native_name': 'Nederlands', 'english_name': 'Dutch'},
            {'code': 'sv', 'name': 'Svenska', 'native_name': 'Svenska', 'english_name': 'Swedish'},
            {'code': 'da', 'name': 'Dansk', 'native_name': 'Dansk', 'english_name': 'Danish'},
            {'code': 'no', 'name': 'Norsk', 'native_name': 'Norsk', 'english_name': 'Norwegian'},
            {'code': 'fi', 'name': 'Suomi', 'native_name': 'Suomi', 'english_name': 'Finnish'},
            {'code': 'is', 'name': 'Íslenska', 'native_name': 'Íslenska', 'english_name': 'Icelandic'},
            {'code': 'ka', 'name': 'ქართული', 'native_name': 'ქართული', 'english_name': 'Georgian'},
            {'code': 'sr', 'name': 'Српски', 'native_name': 'Српски', 'english_name': 'Serbian'},
            {'code': 'sw', 'name': 'Kiswahili', 'native_name': 'Kiswahili', 'english_name': 'Swahili'},
            {'code': 'fa', 'name': 'فارسی', 'native_name': 'فارسی', 'english_name': 'Persian'},
            {'code': 'th', 'name': 'ไทย', 'native_name': 'ไทย', 'english_name': 'Thai'},
            {'code': 'vi', 'name': 'Tiếng Việt', 'native_name': 'Tiếng Việt', 'english_name': 'Vietnamese'},
            {'code': 'id', 'name': 'Bahasa Indonesia', 'native_name': 'Bahasa Indonesia', 'english_name': 'Indonesian'},
            {'code': 'mr', 'name': 'मराठी', 'native_name': 'मराठी', 'english_name': 'Marathi'},
            {'code': 'gu', 'name': 'ગુજરાતી', 'native_name': 'ગુજરાતી', 'english_name': 'Gujarati'},
            {'code': 'ta', 'name': 'தமிழ்', 'native_name': 'தமிழ்', 'english_name': 'Tamil'},
            {'code': 'te', 'name': 'తెలుగు', 'native_name': 'తెలుగు', 'english_name': 'Telugu'},
            {'code': 'bn', 'name': 'বাংলা', 'native_name': 'বাংলা', 'english_name': 'Bengali'},
            {'code': 'ur', 'name': 'اردو', 'native_name': 'اردو', 'english_name': 'Urdu'},
            {'code': 'ro', 'name': 'Română', 'native_name': 'Română', 'english_name': 'Romanian'},
            {'code': 'hu', 'name': 'Magyar', 'native_name': 'Magyar', 'english_name': 'Hungarian'},
            {'code': 'uk', 'name': 'Українська', 'native_name': 'Українська', 'english_name': 'Ukrainian'}
        ]
        
        return jsonify({'success': True, 'languages': courses})
        
    except Exception as e:
        print(f"Error getting available courses: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Register blueprints
app.register_blueprint(media_bp)
app.register_blueprint(words_bp)
app.register_blueprint(levels_bp)
app.register_blueprint(practice_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(custom_levels_bp)

# Add before_request handler for user context
@app.before_request
def set_user_context():
    """Set user context for all API requests"""
    # Extract session token from Authorization header
    auth_header = request.headers.get('Authorization', '')
    session_token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else None
    
    # Get current user
    user = None
    if session_token:
        try:
            user = get_current_user(session_token)
        except Exception as e:
            print(f"Auth error: {e}")
    
    # Store user in Flask's g object for access in route handlers
    g.current_user = user
    g.user_id = user['id'] if user else None
    g.session_token = session_token

# Serve CSV file for direct access
@app.route('/localization_complete.csv')
def serve_csv():
    return send_from_directory(APP_ROOT, 'localization_complete.csv')

def periodic_sync():
    """Periodic synchronization of user data"""
    try:
        from server.db import get_db
        conn = get_db()
        
        # Get all active users
        users = conn.execute("SELECT id FROM users WHERE is_active = 1").fetchall()
        conn.close()
        
        for user in users:
            try:
                migrate_user_data_structure(user['id'])
            except Exception as e:
                print(f"Error syncing user {user['id']}: {e}")
                
    except Exception as e:
        print(f"Error in periodic sync: {e}")

if __name__ == '__main__':
    # Sync databases on startup
    print("🚀 Starting ProjectSiluma...")
    sync_databases_on_startup()
    
    # Start periodic sync (every 5 minutes)
    import threading
    import time
    
    def sync_worker():
        while True:
            time.sleep(300)  # 5 minutes
            periodic_sync()
    
    sync_thread = threading.Thread(target=sync_worker, daemon=True)
    sync_thread.start()
    print("🔄 Periodic sync started (every 5 minutes)")
    
    # Development server
    app.run(debug=True, port=5001)
else:
    # Production configuration for WSGI
    import os
    try:
        # Try domain-specific config first
        from config_domain_specific import DomainConfig
        app.config.from_object(DomainConfig)
        DomainConfig.init_app(app)
    except ImportError:
        # Fallback to general production config
        from config_production import ProductionConfig
        app.config.from_object(ProductionConfig)
        ProductionConfig.init_app(app)
    
    # Set up logging for production
    import logging
    logging.basicConfig(level=logging.WARNING)

@app.route('/api/setup-database', methods=['POST'])
def api_setup_database():
    """Setup database and create test user (for Railway deployment)"""
    try:
        # Initialize database
        init_db()
        
        # Add missing columns to users table if they don't exist (SQLite only)
        from server.db_config import get_database_config
        config = get_database_config()
        
        if config['type'] == 'sqlite':
            conn = get_db()
            cur = conn.cursor()
            
            # Check if native_language column exists
            cur.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cur.fetchall()]
            
            if 'native_language' not in columns:
                cur.execute("ALTER TABLE users ADD COLUMN native_language TEXT DEFAULT 'en'")
                print("Added native_language column to users table")
            
            conn.commit()
            conn.close()
        elif config['type'] == 'postgresql':
            # For PostgreSQL, ensure tables exist
            conn = get_db()
            cur = conn.cursor()
            
            # Check if users table exists
            cur = execute_query(conn, """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'users'
                );
            """)
            users_table_exists = cur.fetchone()[0]
            
            if not users_table_exists:
                print("Creating PostgreSQL tables...")
                
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
                        note TEXT,
                        UNIQUE(word, language, native_language)
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
                        topic VARCHAR(100)
                    );
                """)
                
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
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                print("PostgreSQL tables created successfully!")
            
            conn.close()
        
        # Create test user if it doesn't exist
        from server.services.auth import register_user
        
        # Check if test user exists
        from server.db import get_user_by_username
        existing_user = get_user_by_username('testuser')
        
        if not existing_user:
            result = register_user('testuser', 'test@example.com', 'password123')
            if result['success']:
                return jsonify({
                    'success': True, 
                    'message': 'Database initialized and test user created',
                    'database_type': config['type'],
                    'test_credentials': {
                        'username': 'testuser',
                        'password': 'password123'
                    }
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to create test user'}), 500
        else:
            return jsonify({
                'success': True, 
                'message': 'Database already initialized',
                'database_type': config['type'],
                'test_credentials': {
                    'username': 'testuser',
                    'password': 'password123'
                }
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/migrate-to-postgresql', methods=['POST'])
def api_migrate_to_postgresql():
    """Migrate from SQLite to PostgreSQL"""
    try:
        from server.db_config import get_database_config
        config = get_database_config()
        
        if config['type'] != 'postgresql':
            return jsonify({
                'success': False, 
                'error': 'DATABASE_URL not set or not PostgreSQL'
            }), 400
        
        # Initialize PostgreSQL database
        init_db()
        
        # Create test user
        from server.services.auth import register_user
        from server.db import get_user_by_username
        
        existing_user = get_user_by_username('testuser')
        if not existing_user:
            result = register_user('testuser', 'test@example.com', 'password123')
            if not result['success']:
                return jsonify({'success': False, 'error': 'Failed to create test user'}), 500
        
        return jsonify({
            'success': True,
            'message': 'Successfully migrated to PostgreSQL',
            'database_type': 'postgresql'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/create-postgresql-tables', methods=['POST'])
def api_create_postgresql_tables():
    """Create PostgreSQL tables manually"""
    try:
        from server.db_config import get_database_config
        config = get_database_config()
        
        if config['type'] != 'postgresql':
            return jsonify({
                'success': False, 
                'error': 'DATABASE_URL not set or not PostgreSQL'
            }), 400
        
        # Create PostgreSQL tables manually
        conn = get_db()
        
        # Users table
        cur = execute_query(conn, """
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
                note TEXT,
                UNIQUE(word, language, native_language)
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
                topic VARCHAR(100)
            );
        """)
        
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.close()
        
        # Create test user
        from server.services.auth import register_user
        from server.db import get_user_by_username
        
        existing_user = get_user_by_username('testuser')
        if not existing_user:
            result = register_user('testuser', 'test@example.com', 'password123')
            if not result['success']:
                return jsonify({'success': False, 'error': 'Failed to create test user'}), 500
        
        return jsonify({
            'success': True,
            'message': 'PostgreSQL tables created successfully',
            'database_type': 'postgresql'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database-info', methods=['GET'])
def api_database_info():
    """Get database information and table list"""
    try:
        import psycopg2
        from urllib.parse import urlparse
        import os
        
        # Check if DATABASE_URL is set (PostgreSQL)
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            try:
                # Parse and connect to PostgreSQL
                parsed = urlparse(database_url)
                conn = psycopg2.connect(
                    host=parsed.hostname,
                    port=parsed.port,
                    database=parsed.path[1:],
                    user=parsed.username,
                    password=parsed.password
                )
                
                # Get table list
                cur = conn.cursor()
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cur.fetchall()]
                
                # Get user count
                cur.execute("SELECT COUNT(*) FROM users")
                user_count = cur.fetchone()[0]
                
                # Get session count
                cur.execute("SELECT COUNT(*) FROM user_sessions")
                session_count = cur.fetchone()[0]
                
                cur.close()
                conn.close()
                
                return jsonify({
                    'success': True,
                    'database_type': 'postgresql',
                    'tables': tables,
                    'user_count': user_count,
                    'session_count': session_count,
                    'message': f'Found {len(tables)} tables in PostgreSQL database'
                })
                
            except Exception as e:
                return jsonify({
                    'success': False, 
                    'error': f'PostgreSQL connection failed: {str(e)}'
                }), 500
        else:
            # No DATABASE_URL, assume SQLite
            return jsonify({
                'success': True,
                'database_type': 'sqlite',
                'tables': [],
                'user_count': 0,
                'message': 'No DATABASE_URL set, using SQLite'
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/create-test-user', methods=['POST'])
def api_create_test_user():
    """Create a test user directly"""
    try:
        import psycopg2
        from urllib.parse import urlparse
        import os
        import hashlib
        
        # Get DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False, 
                'error': 'DATABASE_URL not set'
            }), 400
        
        # Parse and connect to PostgreSQL
        parsed = urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
        
        # Check if test user already exists
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s", ('testuser',))
        existing_user = cur.fetchone()
        
        if existing_user:
            cur.close()
            conn.close()
            return jsonify({
                'success': True,
                'message': 'Test user already exists',
                'username': 'testuser',
                'password': 'password123'
            })
        
        # Create test user
        password_hash = hashlib.sha256('password123'.encode()).hexdigest()
        
        cur.execute("""
            INSERT INTO users (username, email, password_hash, created_at, is_active, native_language)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, TRUE, 'de')
            RETURNING id
        """, ('testuser', 'test@example.com', password_hash))
        
        user_id = cur.fetchone()[0]
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Test user created successfully',
            'user_id': user_id,
            'username': 'testuser',
            'password': 'password123'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test-postgresql', methods=['GET'])
def api_test_postgresql():
    """Test PostgreSQL connection directly"""
    try:
        import psycopg2
        from urllib.parse import urlparse
        import os
        
        # Get DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({'success': False, 'error': 'DATABASE_URL not set'}), 400
        
        # Parse and connect
        parsed = urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
        
        # Test query
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM users')
        user_count = cur.fetchone()[0]
        
        # Get table structure
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        # Also get all tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'PostgreSQL connection successful',
            'user_count': user_count,
            'users_table_columns': columns,
            'all_tables': tables
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/api/debug/add-user-comment-column", methods=["POST"])
def debug_add_user_comment_column():
    """Debug endpoint to add user_comment column to user_word_familiarity table"""
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config["type"] == "postgresql":
                # Check if column exists
                result = execute_query(conn, """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = "user_word_familiarity" AND column_name = "user_comment"
                """)
                
                if not result.fetchone():
                    print("Adding user_comment column to user_word_familiarity table...")
                    execute_query(conn, """
                        ALTER TABLE user_word_familiarity 
                        ADD COLUMN user_comment TEXT
                    """)
                    conn.commit()
                    print("✅ Added user_comment column to user_word_familiarity table")
                    return jsonify({"success": True, "message": "user_comment column added successfully"})
                else:
                    print("user_comment column already exists in user_word_familiarity table")
                    return jsonify({"success": True, "message": "user_comment column already exists"})
            else:
                # SQLite syntax - check if column exists first
                cur = conn.cursor()
                cur.execute("PRAGMA table_info(user_word_familiarity)")
                columns = [column[1] for column in cur.fetchall()]
                
                if "user_comment" not in columns:
                    print("Adding user_comment column to user_word_familiarity table...")
                    cur.execute("""
                        ALTER TABLE user_word_familiarity 
                        ADD COLUMN user_comment TEXT
                    """)
                    conn.commit()
                    print("✅ Added user_comment column to user_word_familiarity table")
                    return jsonify({"success": True, "message": "user_comment column added successfully"})
                else:
                    print("user_comment column already exists in user_word_familiarity table")
                    return jsonify({"success": True, "message": "user_comment column already exists"})
                    
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/debug/check-word-familiarity", methods=["GET"])
def debug_check_word_familiarity():
    """Debug endpoint to check familiarity for a specific word and user"""
    try:
        word = request.args.get('word', '').strip()
        user_id = request.args.get('user_id', '').strip()
        language = request.args.get('language', 'ka').strip()
        native_language = request.args.get('native_language', 'de').strip()
        
        if not word or not user_id:
            return jsonify({"success": False, "error": "word and user_id required"}), 400
        
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({"success": False, "error": "user_id must be a number"}), 400
        
        # Check familiarity using the new function
        from server.db import get_user_word_familiarity_by_word
        familiarity_data = get_user_word_familiarity_by_word(user_id, word, language, native_language)
        
        if familiarity_data:
            return jsonify({
                "success": True,
                "word": word,
                "user_id": user_id,
                "language": language,
                "native_language": native_language,
                "familiarity": familiarity_data['familiarity'] or 0,
                "seen_count": familiarity_data['seen_count'] or 0,
                "correct_count": familiarity_data['correct_count'] or 0,
                "user_comment": familiarity_data['user_comment'] or '',
                "found": True
            })
        else:
            return jsonify({
                "success": True,
                "word": word,
                "user_id": user_id,
                "language": language,
                "native_language": native_language,
                "familiarity": 0,
                "seen_count": 0,
                "correct_count": 0,
                "user_comment": '',
                "found": False,
                "reason": "No familiarity data found"
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/debug/test-update-familiarity", methods=["POST"])
def debug_test_update_familiarity():
    """Debug endpoint to test updating familiarity directly"""
    try:
        payload = request.get_json(force=True) or {}
        word = payload.get('word', '').strip()
        user_id = payload.get('user_id')
        language = payload.get('language', 'ka').strip()
        native_language = payload.get('native_language', 'de').strip()
        familiarity = payload.get('familiarity', 0)
        user_comment = payload.get('user_comment', '')
        
        if not word or not user_id:
            return jsonify({"success": False, "error": "word and user_id required"}), 400
        
        # Test the update function directly
        from server.db import update_user_word_familiarity_by_word
        success = update_user_word_familiarity_by_word(
            user_id=user_id,
            word=word,
            language=language,
            native_language=native_language,
            familiarity=familiarity,
            user_comment=user_comment
        )
        
        return jsonify({
            "success": success,
            "word": word,
            "user_id": user_id,
            "language": language,
            "native_language": native_language,
            "familiarity": familiarity,
            "user_comment": user_comment,
            "message": "Update successful" if success else "Update failed"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
