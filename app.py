import os, json, sqlite3, io, csv, random
from flask import Flask, request, jsonify, send_from_directory, Blueprint, g, Response, stream_with_context
from server.services.s3_storage import s3_storage
from flask_cors import CORS
from datetime import datetime, UTC

from server.db import (
    get_db, init_db, DB_PATH,
    migrate_practice, pick_words_by_run, json_load, fam_counts_for_words,
    latest_run_id_for_level, ensure_words_exist, create_level_run,
    list_words_rows, get_word_row, count_words_fam5, delete_words_by_ids, upsert_word_row,
    get_localization_entry, upsert_localization_entry, get_all_localization_entries,
    get_localization_for_language, get_missing_translations,
    get_user_word_familiarity_by_word, update_user_word_familiarity_by_word,
    _coerce_row_to_dict,
    # marketplace ratings helpers
    upsert_group_rating, get_group_rating_stats, get_recent_group_comments, create_custom_level_group_ratings_table
)

def _register_debug_routes():
    @app.get('/api/debug/ratings-table')
    @require_auth(optional=True)
    def api_debug_ratings_table():
        """Ensure and verify the marketplace ratings table exists (PostgreSQL) and report stats."""
        try:
            # Ensure tables exist
            init_db(); create_custom_level_group_ratings_table()
            
            conn = get_db()
            try:
                # Check existence in a database-agnostic way
                # Try a simple select count; if it fails, table is missing
                try:
                    row = conn.execute('SELECT COUNT(*) AS c FROM custom_level_group_ratings').fetchone()
                    count = int(row['c']) if row and row['c'] is not None else 0
                    exists = True
                except Exception:
                    exists = False
                    count = 0
                
                return jsonify({
                    'success': True,
                    'exists': exists,
                    'row_count': count
                })
            finally:
                conn.close()
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
from server.db_multi_user import (
    get_level_words_with_familiarity, unlock_level_words,
    get_familiarity_counts_for_level, get_user_level_stats, get_global_level_stats,
    get_user_native_language, ensure_user_databases
)
from server.services.auth import (
    register_user, login_user, get_current_user, logout_user
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


def _extract_row_value(row, key, default=0):
    """Safely extract a column value from sqlite/PostgreSQL rows."""
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default


def _adjust_user_word_familiarity(user_id, word, language, native_language, *, delta=None, set_value=None):
    """Adjust familiarity for a user/word pair using the central PostgreSQL helper."""
    if not user_id or not word or not language or not native_language:
        return
    # Normalize word by trimming and removing trailing punctuation/symbols
    import re
    word = re.sub(r'[.!?,;:—–-]+$', '', (word or '').strip())
    language = (language or '').strip()
    native_language = (native_language or '').strip()
    if not word or not language or not native_language:
        return

    try:
        ensure_words_exist([word], language, native_language)
    except Exception as e:
        print(f"Error ensuring word '{word}' exists ({language}->{native_language}): {e}")

    try:
        current_row = get_user_word_familiarity_by_word(user_id, word, language, native_language)
        current_familiarity = _extract_row_value(current_row, 'familiarity', 0) or 0
    except Exception as e:
        print(f"Error fetching familiarity for '{word}' ({language}->{native_language}): {e}")
        current_familiarity = 0
        current_row = None

    if set_value is not None:
        target_value = set_value
    elif delta is not None:
        target_value = (current_familiarity or 0) + delta
    else:
        target_value = current_familiarity or 0

    target_value = max(0, min(5, target_value))
    target_int = int(round(target_value + 1e-8))
    target_int = max(0, min(5, target_int))

    if current_row and _extract_row_value(current_row, 'familiarity', 0) == target_int:
        return

    try:
        success = update_user_word_familiarity_by_word(
            user_id=user_id,
            word=word,
            language=language,
            native_language=native_language,
            familiarity=target_int
        )
        if not success:
            print(f"⚠️ Failed to update familiarity for '{word}' ({language}->{native_language}) to {target_int}")
    except Exception as e:
        print(f"Error updating familiarity for '{word}' ({language}->{native_language}): {e}")
from server.database_sync import sync_databases_on_startup
from server.services.llm import (
    llm_generate_sentences, llm_translate_batch, llm_similarity,
    _http_json, OPENAI_KEY, OPENAI_BASE,
    tokenize_words, suggest_topic, suggest_level_title, cefr_norm, CEFR_PRESETS, llm_enrich_word, _norm_gender,
    similarity_score
)
from server.services.tts import ensure_tts_for_alphabet_letter, ensure_tts_for_word, ensure_tts_for_sentence, ensure_tts_for_word_with_context

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# Configure CORS to allow all origins for development and production
CORS(app, origins=["*"], allow_headers=["Content-Type", "Authorization", "X-Native-Language", "X-Requested-With"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], supports_credentials=True)

from pathlib import Path
import tempfile

# Standard level file operations removed - standard levels are deactivated

# Blueprints
words_bp = Blueprint('words', __name__)
levels_bp = Blueprint('levels', __name__)
practice_bp = Blueprint('practice', __name__)
media_bp = Blueprint('media', __name__)

def convert_s3_url_to_proxy_url(s3_url: str) -> str:
    """
    Convert S3 URL to proxy URL to avoid CORS issues.
    Example: https://bucket.s3.region.amazonaws.com/media/tts/ka/file.mp3
    -> /media/tts/ka/file.mp3
    """
    if not s3_url or not isinstance(s3_url, str):
        return s3_url
    
    s3_url = s3_url.strip()
    
    # If already a proxy URL (starts with /media/), return as-is
    if s3_url.startswith('/media/'):
        return s3_url
    
    # If it's an S3 URL, extract the path
    if 's3' in s3_url and 'amazonaws.com' in s3_url:
        # Extract path after bucket name
        # Format: https://bucket.s3.region.amazonaws.com/media/tts/ka/file.mp3
        try:
            from urllib.parse import urlparse
            parsed = urlparse(s3_url)
            path = parsed.path.lstrip('/')
            # Path should be like: media/tts/ka/file.mp3 or media/tts_sentences/ka/file.mp3
            if path.startswith('media/'):
                return '/' + path
        except Exception as e:
            print(f"⚠️ Could not convert S3 URL to proxy URL: {s3_url}, error: {e}")
    
    # If conversion failed, return original URL
    return s3_url
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

@app.get('/api/debug/localization-stats')
def debug_localization_stats():
    """Return summary statistics for localization storage."""
    from server.db_config import get_database_config, get_db_connection, execute_query
    config = get_database_config()
    conn = get_db_connection()
    try:
        summary = {
            'database_type': config['type'],
            'keys': 0,
            'rows': 0,
            'top_languages': []
        }
        cursor = execute_query(conn, "SELECT COUNT(DISTINCT key) AS keys, COUNT(*) AS rows FROM localization")
        row = cursor.fetchone()
        if row:
            if isinstance(row, dict):
                summary['keys'] = int(row.get('keys', 0) or 0)
                summary['rows'] = int(row.get('rows', 0) or 0)
            else:
                summary['keys'] = int(row[0] or 0)
                summary['rows'] = int(row[1] or 0)
        cursor.close()

        cursor = execute_query(conn, """
            SELECT language, COUNT(*) AS entries
            FROM localization
            GROUP BY language
            ORDER BY entries DESC
            LIMIT 10
        """)
        for lang_row in cursor.fetchall():
            if isinstance(lang_row, dict):
                summary['top_languages'].append({
                    'language': lang_row.get('language'),
                    'entries': int(lang_row.get('entries', 0) or 0)
                })
            else:
                summary['top_languages'].append({
                    'language': lang_row[0],
                    'entries': int(lang_row[1] or 0)
                })
        cursor.close()

        return jsonify({'success': True, 'summary': summary})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500
    finally:
        conn.close()

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
        from server import postgres
        from server.postgres import RealDictCursor
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = postgres.connect(database_url)
        
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
        from server import postgres
        from server.postgres import RealDictCursor
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = postgres.connect(database_url)
        
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

@app.get('/api/debug/check-words-with-punctuation')
def debug_check_words_with_punctuation():
    """Check for words with punctuation marks that might be duplicates"""
    try:
        import os
        from server import postgres
        import re
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = postgres.connect(database_url)
        
        try:
            cursor = conn.cursor()
            
            # Get all words with punctuation
            cursor.execute("""
                SELECT id, word, language, native_language
                FROM words 
                WHERE word ~ '[.!?,;:—–-]'
                ORDER BY language, word
                LIMIT 100;
            """)
            words_with_punct = cursor.fetchall()
            
            # Group potential duplicates
            potential_duplicates = []
            for word_id, word, language, native_language in words_with_punct:
                # Remove punctuation to find the base word
                base_word = re.sub(r'[.!?,;:—–-]+$', '', word)
                
                if base_word != word:
                    # Check if base word exists in database
                    cursor.execute("""
                        SELECT id, word, translation
                        FROM words 
                        WHERE word = %s AND language = %s AND native_language = %s
                        LIMIT 1;
                    """, (base_word, language, native_language))
                    
                    base_exists = cursor.fetchone()
                    
                    potential_duplicates.append({
                        'with_punct_id': word_id,
                        'with_punct': word,
                        'base_word': base_word,
                        'base_exists': base_exists is not None,
                        'base_id': base_exists[0] if base_exists else None,
                        'language': language,
                        'native_language': native_language
                    })
            
            return jsonify({
                'success': True,
                'total_words_with_punctuation': len(words_with_punct),
                'potential_duplicates': potential_duplicates,
                'duplicate_count': len([d for d in potential_duplicates if d['base_exists']])
            })
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Failed to check words with punctuation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.post('/api/debug/remove-trailing-punctuation')
def debug_remove_trailing_punctuation():
    """Remove trailing punctuation from words that have duplicates without punctuation"""
    try:
        import os
        from server import postgres
        import re
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = postgres.connect(database_url)
        
        try:
            cursor = conn.cursor()
            
            # Get all words with trailing punctuation
            cursor.execute("""
                SELECT id, word, language, native_language
                FROM words 
                WHERE word ~ '[.!?,;:—–-]$'
                ORDER BY language, word;
            """)
            words_with_punct = cursor.fetchall()
            
            removed_count = 0
            updated_count = 0
            
            for word_id, word, language, native_language in words_with_punct:
                # Remove trailing punctuation
                base_word = re.sub(r'[.!?,;:—–-]+$', '', word)
                
                if base_word != word:
                    # Check if base word already exists
                    cursor.execute("""
                        SELECT id
                        FROM words 
                        WHERE word = %s AND language = %s AND native_language = %s
                        LIMIT 1;
                    """, (base_word, language, native_language))
                    
                    base_exists = cursor.fetchone()
                    
                    if base_exists:
                        base_id = base_exists[0]
                        # Repoint any user_word_familiarity rows to the base word and merge familiarity stats
                        # Move rows that refer to the punctuated word to the base word, resolving conflicts by keeping max familiarity and summing counts
                        cursor.execute("""
                            UPDATE user_word_familiarity u
                            SET word_id = %s
                            WHERE u.word_id = %s
                              AND NOT EXISTS (
                                  SELECT 1 FROM user_word_familiarity t
                                  WHERE t.user_id = u.user_id AND t.word_id = %s
                              );
                        """, (base_id, word_id, base_id))
                        # For conflicts where both exist, merge by keeping max familiarity and summing counts, then delete duplicate
                        cursor.execute("""
                            UPDATE user_word_familiarity t
                            SET familiarity = GREATEST(t.familiarity, u.familiarity),
                                seen_count = COALESCE(t.seen_count,0) + COALESCE(u.seen_count,0),
                                correct_count = COALESCE(t.correct_count,0) + COALESCE(u.correct_count,0),
                                updated_at = CURRENT_TIMESTAMP
                            FROM user_word_familiarity u
                            WHERE t.user_id = u.user_id
                              AND t.word_id = %s
                              AND u.word_id = %s;
                        """, (base_id, word_id))
                        cursor.execute("""
                            DELETE FROM user_word_familiarity
                            WHERE word_id = %s;
                        """, (word_id,))
                        # Base word exists, delete the punctuated version
                        cursor.execute("""
                            DELETE FROM words
                            WHERE id = %s;
                        """, (word_id,))
                        removed_count += 1
                        print(f"🗑️ Removed '{word}' (duplicate of '{base_word}')")
                    else:
                        # Base word doesn't exist, update the word to remove punctuation
                        cursor.execute("""
                            UPDATE words
                            SET word = %s
                            WHERE id = %s;
                        """, (base_word, word_id))
                        # No base; user_word_familiarity already points to this id, keep as-is
                        updated_count += 1
                        print(f"✏️ Updated '{word}' to '{base_word}'")
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Removed {removed_count} duplicate words and updated {updated_count} words',
                'removed_count': removed_count,
                'updated_count': updated_count,
                'total_processed': len(words_with_punct)
            })
            
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Failed to remove trailing punctuation: {e}")
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
        from server import postgres
        from server.postgres import RealDictCursor
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = postgres.connect(database_url)
        
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
        from server import postgres
        from server.postgres import RealDictCursor
        
        # Get database connection
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                'success': False,
                'error': 'DATABASE_URL environment variable not set'
            }), 500
        
        conn = postgres.connect(database_url)
        
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
    """Get current user information - optimized to return only essential fields"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        user = get_current_user(session_token)
        if user:
            # Return only essential fields for better performance
            lightweight_user = {
                'id': user.get('id'),
                'username': user.get('username'),
                'email': user.get('email'),
                'native_language': user.get('native_language', 'en'),
                'created_at': user.get('created_at')
            }
            return jsonify({'success': True, 'user': lightweight_user})
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
    # S3 is REQUIRED - no local disk fallback
    if not s3_storage.s3_client:
        print(f"❌ S3 storage not configured for {fname}")
        return Response("S3 storage not configured", status=503, mimetype='text/plain')
    
        s3_key = f"media/tts/{lang}/{fname}"
        try:
            print(f"🔵 Fetching audio from S3: {s3_key}")
            # Get file from S3
            s3_obj = s3_storage.s3_client.get_object(Bucket=s3_storage.bucket_name, Key=s3_key)
            
            # Read the entire file into memory for more reliable serving
            # This is acceptable for audio files which are typically small (< 1MB)
            audio_data = s3_obj['Body'].read()
            print(f"✅ Loaded {len(audio_data)} bytes from S3: {s3_key}")
            
            return Response(
                audio_data,
                mimetype='audio/mpeg',
                headers={
                    'Content-Type': 'audio/mpeg',
                'Content-Length': str(len(audio_data)),
                    'Cache-Control': 'public, max-age=31536000',
                'Access-Control-Allow-Origin': '*',
                'Accept-Ranges': 'bytes'
                }
            )
        except s3_storage.s3_client.exceptions.NoSuchKey:
            print(f"❌ File not found in S3: {s3_key}")
            return Response(f"Audio file not found: {s3_key}", status=404, mimetype='text/plain')
        except Exception as e:
            import traceback
            print(f"❌ Could not load {s3_key} from S3: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
        return Response(f"Error loading audio: {str(e)}", status=500, mimetype='text/plain')

# Add symmetric route for sentence TTS
@media_bp.get('/media/tts_sentences/<lang>/<fname>')
def serve_tts_sentence(lang, fname):
    # S3 is REQUIRED - no local disk fallback
    if not s3_storage.s3_client:
        print(f"❌ S3 storage not configured for {fname}")
        return Response("S3 storage not configured", status=503, mimetype='text/plain')
    
        s3_key = f"media/tts_sentences/{lang}/{fname}"
        try:
            print(f"🔵 Fetching sentence audio from S3: {s3_key}")
            # Get file from S3
            s3_obj = s3_storage.s3_client.get_object(Bucket=s3_storage.bucket_name, Key=s3_key)
            
            # Read the entire file into memory for more reliable serving
            # This is acceptable for audio files which are typically small (< 1MB)
            audio_data = s3_obj['Body'].read()
            print(f"✅ Loaded {len(audio_data)} bytes from S3: {s3_key}")
            
            return Response(
            audio_data,
                mimetype='audio/mpeg',
                headers={
                    'Content-Type': 'audio/mpeg',
                'Content-Length': str(len(audio_data)),
                    'Cache-Control': 'public, max-age=31536000',
                'Access-Control-Allow-Origin': '*',
                'Accept-Ranges': 'bytes'
                }
            )
        except s3_storage.s3_client.exceptions.NoSuchKey:
            print(f"❌ File not found in S3: {s3_key}")
            return Response(f"Audio file not found: {s3_key}", status=404, mimetype='text/plain')
        except Exception as e:
            import traceback
            print(f"❌ Could not load {s3_key} from S3: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
        return Response(f"Error loading audio: {str(e)}", status=500, mimetype='text/plain')


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
        
        # Convert S3 URL to proxy URL to avoid CORS issues
        proxy_url = convert_s3_url_to_proxy_url(url_path)
        return jsonify({'success': True, 'audio_url': proxy_url})
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ TTS API error: {e}")
        print(f"❌ Traceback: {error_trace}")
        return jsonify({
            'success': False, 
            'error': f'TTS service error: {str(e)}',
            'error_type': type(e).__name__
        }), 500


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
        
        # Convert S3 URL to proxy URL to avoid CORS issues
        proxy_url = convert_s3_url_to_proxy_url(url)
        return jsonify({'success': True, 'audio_url': proxy_url})
    
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

# Standard level helper functions removed - standard levels are deactivated

def _unique_words_from_items(items):
    words=[]
    for it in (items or []):
        for w in (it.get('words') or []):
            s=str(w).strip()
            if s and s not in words: words.append(s)
    return words

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

# Standard level endpoints removed - standard levels are deactivated
# All /api/level/* endpoints (finish, submit_mc, start, submit, stats, etc.) have been removed
# All /api/levels/* endpoints (summary, bulk-stats) have been removed
# All /api/practice/* endpoints have been removed
# All /api/course/* endpoints have been removed

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
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error creating custom level group: {e}")
        print(f"❌ Traceback: {error_trace}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'error_type': type(e).__name__
        }), 500

@custom_levels_bp.get('/api/custom-levels/groups/summary')
@require_auth(optional=True)
def api_custom_levels_groups_summary():
    """Return lightweight summary of all groups for current user - optimized for performance"""
    try:
        user_context = get_user_context()
        user_id = user_context.get('user_id')
        
        if not user_id:
            return jsonify({'success': True, 'groups': []})
        
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            # Single optimized query with JOINs for efficiency
            if config['type'] == 'postgresql':
                result = execute_query(conn, '''
                    SELECT 
                        clg.id,
                        clg.group_name,
                        clg.language,
                        clg.native_language,
                        COUNT(DISTINCT cl.id) as level_count,
                        COALESCE(SUM(cl.word_count), 0) as total_words,
                        COUNT(DISTINCT CASE WHEN clp.status = 'completed' THEN cl.id END) as completed_levels
                    FROM custom_level_groups clg
                    LEFT JOIN custom_levels cl ON cl.group_id = clg.id
                    LEFT JOIN custom_level_progress clp ON 
                        clp.group_id = clg.id AND 
                        clp.level_number = cl.level_number AND
                        clp.user_id = %s
                    WHERE clg.user_id = %s
                    GROUP BY clg.id, clg.group_name, clg.language, clg.native_language
                    ORDER BY clg.created_at DESC
                ''', (user_id, user_id))
            else:
                # SQLite syntax
                cur = conn.cursor()
                cur.execute('''
                    SELECT 
                        clg.id,
                        clg.group_name,
                        clg.language,
                        clg.native_language,
                        COUNT(DISTINCT cl.id) as level_count,
                        COALESCE(SUM(cl.word_count), 0) as total_words,
                        COUNT(DISTINCT CASE WHEN clp.status = 'completed' THEN cl.id END) as completed_levels
                    FROM custom_level_groups clg
                    LEFT JOIN custom_levels cl ON cl.group_id = clg.id
                    LEFT JOIN custom_level_progress clp ON 
                        clp.group_id = clg.id AND 
                        clp.level_number = cl.level_number AND
                        clp.user_id = ?
                    WHERE clg.user_id = ?
                    GROUP BY clg.id, clg.group_name, clg.language, clg.native_language
                    ORDER BY clg.created_at DESC
                ''', (user_id, user_id))
                result = cur
            
            groups = []
            for row in result.fetchall():
                if isinstance(row, dict):
                    groups.append({
                        'id': row.get('id'),
                        'name': row.get('group_name'),
                        'language': row.get('language'),
                        'native_language': row.get('native_language'),
                        'level_count': row.get('level_count') or 0,
                        'total_words': row.get('total_words') or 0,
                        'completed_levels': row.get('completed_levels') or 0
                    })
                else:
                    # Handle tuple/list results
                    groups.append({
                        'id': row[0],
                        'name': row[1],  # group_name is at index 1
                        'language': row[2],
                        'native_language': row[3],
                        'level_count': row[4] or 0,
                        'total_words': row[5] or 0,
                        'completed_levels': row[6] or 0
                    })
            
            return jsonify({'success': True, 'groups': groups})
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Error in api_custom_levels_groups_summary: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Get all levels for this group WITHOUT content (ultra-lazy loading)
        # This dramatically improves loading speed - content loaded on-demand
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config['type'] == 'postgresql':
                result = execute_query(conn, '''
                    SELECT 
                        id, level_number, word_count, created_at, updated_at
                    FROM custom_levels
                    WHERE group_id = %s
                    ORDER BY level_number
                ''', (group_id,))
            else:
                cur = conn.cursor()
                cur.execute('''
                    SELECT 
                        id, level_number, word_count, created_at, updated_at
                    FROM custom_levels
                    WHERE group_id = ?
                    ORDER BY level_number
                ''', (group_id,))
                result = cur
            
            levels = []
            for row in result.fetchall():
                if isinstance(row, dict):
                    levels.append({
                        'id': row.get('id'),
                        'level_number': row.get('level_number'),
                        'word_count': row.get('word_count') or 0,
                        'created_at': row.get('created_at'),
                        'updated_at': row.get('updated_at'),
                        'content': None  # Loaded on-demand via separate endpoint
                    })
                else:
                    levels.append({
                        'id': row[0],
                        'level_number': row[1],
                        'word_count': row[2] or 0,
                        'created_at': row[3],
                        'updated_at': row[4],
                        'content': None  # Loaded on-demand via separate endpoint
                    })
            
            print(f"📚 Loaded {len(levels)} levels for group {group_id} (ultra-lazy: content loaded on-demand)")
            
            return jsonify({
                'success': True,
                'group': group,
                'levels': levels
            })
        finally:
            conn.close()
        
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
                
                # Batch add words to user's familiarity database (much faster than individual calls)
                try:
                    from server.db import batch_ensure_user_word_familiarity
                    batch_ensure_user_word_familiarity(
                        user_id=user_id,
                        words=level_words,
                        language=language,
                        native_language=native_language,
                        default_familiarity=0
                        )
                    print(f"✅ Ensured all words from custom level {group_id}/{level_number} are in familiarity database")
                except Exception as e:
                    print(f"⚠️ Error batch adding words to familiarity database: {e}")
                    import traceback
                    traceback.print_exc()
            
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
        from server.services.custom_levels import get_custom_level_group, get_custom_levels_for_group
        group_data = get_custom_level_group(group_id, user_id)
        if not group_data:
            return jsonify({'success': False, 'error': 'Group not found'}), 404
        
        # OPTIMIZATION: Fetch all levels at once instead of individual queries
        # Pass group_data to avoid redundant query
        all_levels = get_custom_levels_for_group(group_id, group_data)
        levels_dict = {level['level_number']: level for level in all_levels}
        
        language = group_data.get('language', 'en')
        native_language = group_data.get('native_language', 'de')
        
        # Get familiarity counts for all words in all levels in a single batch
        from server.db_multi_user import get_user_familiarity_counts_for_words
        all_level_words = {}  # level_num -> list of words
        
        for level in all_levels:
            level_num = level['level_number']
            level_words = []
            if level.get('content') and level['content'].get('items'):
                for item in level['content']['items']:
                    words = item.get('words', [])
                    for word in words:
                        if word and word.strip():
                            level_words.append(word.strip().lower())
            if level_words:
                all_level_words[level_num] = level_words
        
        # Batch ensure all words exist
        if all_level_words:
            all_unique_words = set()
            for words in all_level_words.values():
                all_unique_words.update(words)
            if all_unique_words:
                from server.db import ensure_words_exist
                ensure_words_exist(list(all_unique_words), language, native_language)
        
        # Process all levels
        levels_data = {}
        for level_num in range(1, 11):  # Assuming 10 levels per group
            try:
                level_data = levels_dict.get(level_num)
                if not level_data:
                    continue
                    
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
                
                # Get familiarity counts for this level's words (batch processed)
                level_words = all_level_words.get(level_num, [])
                if level_words:
                    user_fam_counts = get_user_familiarity_counts_for_words(
                        user_id, level_words, language, native_language
                    )
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
                    'fam_counts': {'0': 0, '1': 0, '2': 0, '3': 0, '4': 0, '5': 0},
                    'total_words': 0,
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
        # OPTIMIZATION: Increased max_workers from 2 to 5 for better parallelization
        # Each level generation involves multiple LLM calls, so 5 concurrent levels is optimal
        with ThreadPoolExecutor(max_workers=5) as executor:
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
        # OPTIMIZATION: Increased max_workers from 2 to 5 for better parallelization
        # Each level generation involves multiple LLM calls, so 5 concurrent levels is optimal
        with ThreadPoolExecutor(max_workers=5) as executor:  # Increased concurrency for faster batch completion
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
        
        # OPTIMIZATION: Use progress cache instead of fetching level data
        # This endpoint is called when flipping level cards, so use cached data
        from server.db_progress_cache import get_custom_level_group_progress
        progress_data = get_custom_level_group_progress(user_id, group_id)
        
        level_progress = progress_data.get(str(level_number))
        if level_progress and level_progress.get('fam_counts'):
            return jsonify({
                'success': True,
                'familiarity_counts': level_progress['fam_counts']
            })
        
        # Fallback: return default if no cache available
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
        cefr_level = request.args.get('cefr_level', '')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        # Get published custom level groups
        conn = get_db()
        try:
            # Build query based on whether CEFR level filter is provided
            if cefr_level:
                cursor = conn.execute('''
                    SELECT clg.*, u.username as author_name
                    FROM custom_level_groups clg
                    LEFT JOIN users u ON clg.user_id = u.id
                    WHERE clg.status = 'published'
                    AND clg.language = ?
                    AND clg.native_language = ?
                    AND clg.cefr_level = ?
                    ORDER BY clg.created_at DESC
                    LIMIT ? OFFSET ?
                ''', (language, native_language, cefr_level, limit, offset))
            else:
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
            description = getattr(cursor, 'description', None)
            for row in cursor.fetchall():
                group_data = _coerce_row_to_dict(row, description) or {}
                if not group_data:
                    continue
                # Add level count
                level_count_row = conn.execute(
                    'SELECT COUNT(*) as count FROM custom_levels WHERE group_id = ?',
                    (group_data['id'],)
                ).fetchone()
                level_count = _coerce_row_to_dict(level_count_row, getattr(conn, 'description', None))
                group_data['num_levels'] = (level_count or {}).get('count', 0)
                # Add rating stats
                try:
                    stats = get_group_rating_stats(group_data['id'])
                    group_data['rating_avg'] = stats.get('avg', 0)
                    group_data['rating_count'] = stats.get('count', 0)
                except Exception as _e:
                    group_data['rating_avg'] = 0
                    group_data['rating_count'] = 0
                groups.append(group_data)
            
            # Get total count
            total_count_row = conn.execute('''
                SELECT COUNT(*) as count FROM custom_level_groups 
                WHERE status = 'published' AND language = ? AND native_language = ?
            ''', (language, native_language)).fetchone()
            total_count = _coerce_row_to_dict(total_count_row, getattr(conn, 'description', None))
            
            return jsonify({
                'success': True,
                'groups': groups,
                'total': (total_count or {}).get('count', 0),
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
            # Add rating stats
            try:
                stats = get_group_rating_stats(group_id)
                group_data['rating_avg'] = stats.get('avg', 0)
                group_data['rating_count'] = stats.get('count', 0)
                recent_comments = get_recent_group_comments(group_id, 5)
                group_data['recent_comments'] = recent_comments
            except Exception:
                group_data['rating_avg'] = 0
                group_data['rating_count'] = 0
                group_data['recent_comments'] = []
            
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

# --- Marketplace Ratings API ---

@custom_levels_bp.post('/api/marketplace/custom-level-groups/<int:group_id>/ratings')
@require_auth()
def api_rate_marketplace_group(group_id):
    """Submit a star rating (1-5) and optional comment for a published group."""
    try:
        user = g.current_user
        user_id = user['id'] if user else None
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        data = request.get_json(silent=True) or {}
        stars = data.get('stars')
        comment = (data.get('comment') or '').strip()

        # Validate minimal payload
        if stars is None:
            return jsonify({'success': False, 'error': 'stars is required'}), 400

        # Ensure group is published before rating
        conn = get_db()
        try:
            row = conn.execute('SELECT status FROM custom_level_groups WHERE id = ?', (group_id,)).fetchone()
            if not row or str(row['status']) != 'published':
                return jsonify({'success': False, 'error': 'Group not found or not published'}), 404
        finally:
            conn.close()

        ok, err, detail = upsert_group_rating(group_id, user_id, stars, comment or None)
        if not ok:
            return jsonify({'success': False, 'error': 'Invalid rating or database error', 'code': err, 'detail': detail}), 400

        stats = get_group_rating_stats(group_id)
        return jsonify({'success': True, 'message': 'Rating submitted', 'stats': stats})
    except Exception as e:
        print(f"Error rating marketplace group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/marketplace/custom-level-groups/<int:group_id>/ratings')
@require_auth(optional=True)
def api_get_marketplace_group_ratings(group_id):
    """Get rating stats and recent comments for a group."""
    try:
        stats = get_group_rating_stats(group_id)
        comments = get_recent_group_comments(group_id, 10)
        return jsonify({'success': True, 'stats': stats, 'recent_comments': comments})
    except Exception as e:
        print(f"Error fetching marketplace group ratings: {e}")
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
            payload = request.get_json(silent=True) or {}
            requested_new_name = (payload.get('new_group_name') or '').strip()
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
                # If client provided a new name, use it; otherwise inform duplicate
                if not requested_new_name:
                    return jsonify({'success': False, 'error': 'You already have a group with this name', 'code': 'duplicate_name', 'suggested_name': f"{original_group['group_name']} (Imported)"}), 400
                # Ensure the new name is not also taken
                second = conn.execute('''
                    SELECT id FROM custom_level_groups 
                    WHERE user_id = ? AND group_name = ? AND language = ? AND native_language = ?
                ''', (user_id, requested_new_name, original_group['language'], original_group['native_language'])).fetchone()
                if second:
                    return jsonify({'success': False, 'error': 'Chosen name already exists', 'code': 'duplicate_name'}), 400
                final_group_name = requested_new_name
            else:
                final_group_name = original_group['group_name']
            
            # Create a copy of the group for the user
            now = datetime.now(UTC).isoformat()
            cursor = conn.execute('''
                INSERT INTO custom_level_groups 
                (user_id, language, native_language, group_name, context_description, 
                 cefr_level, num_levels, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            ''', (user_id, original_group['language'], original_group['native_language'], 
                  final_group_name, original_group['context_description'],
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
        
        # Determine language context for familiarity updates
        language = ''
        native_language = ''
        if level_data:
            language = (level_data.get('language') or '').strip()
            native_language = (level_data.get('native_language') or '').strip()
        if user_id and (not language or not native_language):
            try:
                group_data = get_custom_level_group(group_id, user_id)
            except Exception:
                group_data = None
            if group_data:
                language = language or (group_data.get('language') or '').strip()
                native_language = native_language or (group_data.get('native_language') or '').strip()
        if user_id and not native_language:
            try:
                native_language = get_user_native_language(user_id)
            except Exception as e:
                print(f"Error resolving native language for custom submit: {e}")
                native_language = ''

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
                passed = similarity >= 0.75

                if user_id and language and native_language:
                    for word in (item.get('words') or []):
                        _adjust_user_word_familiarity(
                            user_id=user_id,
                            word=word,
                            language=language,
                            native_language=native_language,
                            delta=1 if passed else -1
                        )
                
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
    """Finish a custom level and save progress to PostgreSQL"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'Authentication required to save progress'
            }), 401
        
        payload = request.get_json(force=True) or {}
        run_id = payload.get('run_id')
        score = float(payload.get('score', 0.0))
        
        # Save progress to custom_level_progress table
        from server.db_progress_cache import complete_custom_level, refresh_custom_level_progress
        
        # Complete the level with score
        success = complete_custom_level(user_id, group_id, level_number, score)
        
        if not success:
            print(f"⚠️  Failed to save custom level progress for user={user_id}, group={group_id}, level={level_number}")
        
        # Get updated progress data including familiarity counts
        from server.db_progress_cache import get_custom_level_progress
        progress_data = get_custom_level_progress(user_id, group_id, level_number)
        
        return jsonify({
            'success': True,
            'message': 'Custom level completed',
            'score': progress_data.get('score') if progress_data else None,
            'status': progress_data.get('status') if progress_data else ('completed' if (score or 0) >= 0.6 else 'in_progress'),
            'fam_counts': progress_data.get('fam_counts', {}) if progress_data else {},
            'total_words': progress_data.get('total_words', 0) if progress_data else 0,
            'completed_at': progress_data.get('completed_at') if progress_data else None
        })
        
    except Exception as e:
        print(f"Error finishing custom level: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/custom-levels/<int:group_id>/<int:level_number>/progress')
@require_auth(optional=True)
def api_get_custom_level_progress(group_id, level_number):
    """Get progress data for a custom level (for evaluation display)"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Use ONLY cached progress from custom_level_progress (stable, already contains all data)
        from server.db_progress_cache import get_custom_level_progress
        progress_data = get_custom_level_progress(user_id, group_id, level_number)

        if not progress_data:
            return jsonify({
                'success': True,
                'score': None,
                'status': 'not_started',
                'fam_counts': {'0': 0, '1': 0, '2': 0, '3': 0, '4': 0, '5': 0},
                'total_words': 0,
                'completed_at': None,
                'last_updated': datetime.now(UTC).isoformat()
            })

        fam_counts = progress_data.get('fam_counts') or {0:0,1:0,2:0,3:0,4:0,5:0}
        fam_counts_str = {str(k): int(v or 0) for k, v in fam_counts.items()}

        return jsonify({
            'success': True,
            'score': progress_data.get('score'),
            'status': progress_data.get('status', 'not_started'),
            'fam_counts': fam_counts_str,
            'total_words': int(progress_data.get('total_words') or 0),
            'completed_at': progress_data.get('completed_at'),
            'last_updated': datetime.now(UTC).isoformat()
        })
        
    except Exception as e:
        print(f"Error getting custom level progress: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@custom_levels_bp.get('/api/custom-levels/<int:group_id>/progress')
@require_auth(optional=True)
def api_get_custom_group_progress(group_id):
    """Get progress data for all levels in a custom level group"""
    try:
        # Get user from Flask's g object (set by require_auth decorator)
        user = g.current_user
        user_id = user['id'] if user else None
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Get progress data from custom_level_progress table
        from server.db_progress_cache import get_custom_level_group_progress
        progress_data = get_custom_level_group_progress(user_id, group_id)
        
        # Convert to array format for easier frontend consumption
        levels = []
        for level_number, data in progress_data.items():
            fam_counts_str = {str(k): v for k, v in data.get('fam_counts', {}).items()}
            levels.append({
                'level': level_number,
                'score': data.get('score'),
                'status': data.get('status', 'not_started'),
                'fam_counts': fam_counts_str,
                'total_words': data.get('total_words', 0),
                'completed_at': data.get('completed_at'),
                'last_updated': str(data.get('last_updated', ''))
            })
        
        return jsonify({
            'success': True,
            'levels': levels
        })
        
    except Exception as e:
        print(f"Error getting custom group progress: {e}")
        import traceback
        traceback.print_exc()
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
        
        if not words:
            return jsonify({'success': True, 'enriched_count': 0, 'total_words': 0})
        
        # Filter out empty words
        words = [w.strip() for w in words if w and w.strip()]
        if not words:
            return jsonify({'success': True, 'enriched_count': 0, 'total_words': 0})
        
        # Check which words already exist (batch query)
        from server.db_config import get_database_config, get_db_connection, execute_query
        config = get_database_config()
        conn = get_db_connection()
        
        existing_words = set()
        try:
            if config['type'] == 'postgresql':
                # OPTIMIZATION: Use ANY with array instead of multiple OR conditions
                # This is much more efficient for PostgreSQL
                result = execute_query(conn, '''
                    SELECT word FROM words 
                    WHERE word = ANY(%s) AND language = %s AND native_language = %s
                ''', (words, language, native_language))
                for row in result.fetchall():
                    from server.db import _coerce_row_to_dict
                    row_dict = _coerce_row_to_dict(row, getattr(result, 'description', None))
                    if row_dict and row_dict.get('word'):
                        existing_words.add(row_dict['word'])
            else:
                # SQLite batch check
                cur = conn.cursor()
                placeholders = ','.join(['?'] * len(words))
                query = f'''
                    SELECT word FROM words 
                    WHERE word IN ({placeholders}) AND language = ? AND native_language = ?
                '''
                result = cur.execute(query, words + [language, native_language])
                for row in result.fetchall():
                    if isinstance(row, dict):
                        existing_words.add(row.get('word', ''))
                    elif isinstance(row, (list, tuple)) and len(row) > 0:
                        existing_words.add(row[0])
        finally:
            conn.close()
        
        # Filter out words that already exist
        words_to_enrich = [w for w in words if w not in existing_words]
        
        if not words_to_enrich:
            print(f"All {len(words)} words already exist, skipping enrichment")
            # Still generate audio for all words
            try:
                from server.services.tts import batch_ensure_tts_for_words
                sentence_contexts = {}
                if sentence_context:
                    for word in words:
                        sentence_contexts[word] = sentence_context
                
                audio_results = batch_ensure_tts_for_words(words, language, sentence_contexts)
                if audio_results:
                    from server.db_config import get_db_connection, execute_query
                    from datetime import datetime, UTC
                    conn = get_db_connection()
                    try:
                        # OPTIMIZATION: Batch update audio URLs instead of individual queries
                        words_with_audio = [(w, url) for w, url in audio_results.items() if url]
                        if words_with_audio:
                            if config['type'] == 'postgresql':
                                # Use batch UPDATE with unnest for PostgreSQL (more efficient)
                                words_list = [w for w, _ in words_with_audio]
                                urls_list = [url for _, url in words_with_audio]
                                execute_query(conn, '''
                                    UPDATE words 
                                    SET audio_url = data.url, updated_at = CURRENT_TIMESTAMP
                                    FROM unnest(%s::text[], %s::text[]) AS data(word, url)
                                    WHERE words.word = data.word 
                                      AND words.language = %s 
                                      AND words.native_language = %s
                                ''', (words_list, urls_list, language, native_language))
                                conn.commit()
                            else:
                                # SQLite batch update
                                cur = conn.cursor()
                                for word, audio_url in words_with_audio:
                                    cur.execute('''
                                        UPDATE words SET audio_url = ?, updated_at = ? 
                                        WHERE word = ? AND language = ? AND native_language = ?
                                    ''', (audio_url, datetime.now(UTC).isoformat(), word, language, native_language))
                                conn.commit()
                        print(f"✅ Generated and updated audio URLs for {len(words_with_audio)} words")
                    finally:
                        conn.close()
            except Exception as e:
                print(f"⚠️ Error generating audio: {e}")
            
            return jsonify({
                'success': True,
                'message': 'All words already enriched',
                'enriched_count': 0,
                'total_words': len(words)
            })
        
        # Use batch enrichment for words that need enrichment
        print(f"🔧 Batch enriching {len(words_to_enrich)} words (skipping {len(existing_words)} existing)")
        
        # Build sentence contexts dict
        sentence_contexts = {}
        if sentence_context:
            for word in words_to_enrich:
                sentence_contexts[word] = sentence_context
        
        # Use batch enrichment
        from server.services.llm import llm_enrich_words_batch
        enriched_results = llm_enrich_words_batch(words_to_enrich, language, native_language, sentence_contexts)
        
        # Store enriched words in database (batch insert)
        enriched_count = 0
        if enriched_results:
            from server.db_config import get_db_connection, execute_query
            import json
            conn = get_db_connection()
            try:
                for word, enriched_data in enriched_results.items():
                    if not enriched_data or not enriched_data.get('translation'):
                        continue
                    
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
                                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                    %s, %s, %s, %s, %s, %s
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
                        ''', (
                            insert_data['word'], insert_data['language'], insert_data['native_language'],
                            insert_data['translation'], insert_data['example'], insert_data['example_native'],
                            insert_data['lemma'], insert_data['pos'], insert_data['ipa'], insert_data['audio_url'],
                            insert_data['gender'], insert_data['plural'], insert_data['conj'], insert_data['comp'],
                            insert_data['synonyms'], insert_data['collocations'], insert_data['cefr'],
                            insert_data['freq_rank'], insert_data['tags'], insert_data['note'], insert_data['info']
                        ))
                        else:
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
                        
                        enriched_count += 1
                        
                        conn.commit()
                print(f"✅ Batch enriched and stored {enriched_count} words")
            except Exception as e:
                print(f"❌ Error storing enriched words: {e}")
                import traceback
                traceback.print_exc()
                conn.rollback()
            finally:
                conn.close()
                    
        # Generate audio for all words (including existing ones) in batch
        try:
            from server.services.tts import batch_ensure_tts_for_words
            sentence_contexts_all = {}
            if sentence_context:
                for word in words:
                    sentence_contexts_all[word] = sentence_context
            
            print(f"🎵 Generating audio for {len(words)} words in language '{language}'")
            audio_results = batch_ensure_tts_for_words(words, language, sentence_contexts_all)
            print(f"🎵 Audio generation completed: {len(audio_results)} results, {sum(1 for v in audio_results.values() if v)} successful")
            
            # Update audio URLs in database
            if audio_results:
                from server.db_config import get_db_connection, execute_query
                from datetime import datetime, UTC
                conn = get_db_connection()
                updated_count = 0
                try:
                    # OPTIMIZATION: Batch update audio URLs instead of individual queries
                    words_with_audio = [(w, url) for w, url in audio_results.items() if url]
                    if words_with_audio:
                        if config['type'] == 'postgresql':
                            # Use batch UPDATE with unnest for PostgreSQL
                            words_list = [w for w, _ in words_with_audio]
                            urls_list = [url for _, url in words_with_audio]
                            execute_query(conn, '''
                                UPDATE words 
                                SET audio_url = data.url, updated_at = CURRENT_TIMESTAMP
                                FROM unnest(%s::text[], %s::text[]) AS data(word, url)
                                WHERE words.word = data.word 
                                  AND words.language = %s 
                                  AND words.native_language = %s
                            ''', (words_list, urls_list, language, native_language))
                            conn.commit()
                            updated_count = len(words_with_audio)
                        else:
                            # SQLite batch update
                            cur = conn.cursor()
                            for word, audio_url in words_with_audio:
                                cur.execute('''
                                    UPDATE words SET audio_url = ?, updated_at = ? 
                                    WHERE word = ? AND language = ? AND native_language = ?
                                ''', (audio_url, datetime.now(UTC).isoformat(), word, language, native_language))
                            conn.commit()
                            updated_count = len(words_with_audio)
                    print(f"✅ Generated and updated audio URLs for {updated_count}/{len(audio_results)} words")
                except Exception as e:
                    print(f"❌ Error updating audio URLs: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    conn.close()
            else:
                print(f"⚠️ No audio results returned from batch_ensure_tts_for_words")
        except Exception as e:
            print(f"❌ Error generating audio for custom level words: {e}")
            import traceback
            traceback.print_exc()
        
        return jsonify({
            'success': True,
            'message': 'Words enriched',
            'enriched_count': enriched_count,
            'total_words': len(words)
        })
        
    except Exception as e:
        print(f"Error enriching custom level words: {e}")
        import traceback
        traceback.print_exc()
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
        word = (payload.get('word') or '').strip()
        
        # Check if answer is correct
        is_correct = answer == correct_answer

        # Update familiarity for authenticated users
        if user_id and word:
            language = None
            native_language = None
            try:
                group_data = get_custom_level_group(group_id, user_id)
            except Exception:
                group_data = None
            if group_data:
                language = group_data.get('language')
                native_language = group_data.get('native_language')
            try:
                level_data = get_custom_level(group_id, level_number, user_id)
            except Exception:
                level_data = None
            if level_data:
                language = language or level_data.get('language')
                native_language = native_language or level_data.get('native_language')
            if not native_language:
                try:
                    native_language = get_user_native_language(user_id)
                except Exception as e:
                    print(f"Error resolving native language for custom MC familiarity: {e}")
                    native_language = None
            if language and native_language:
                delta = 1 if is_correct else -1
                _adjust_user_word_familiarity(
                    user_id=user_id,
                    word=word,
                    language=language,
                    native_language=native_language,
                    delta=delta
                )
        
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


# Standard level endpoint removed - standard levels are deactivated

@words_bp.get('/api/words')
@require_auth(optional=True)
def api_words_list():
    # Get language filter from request
    language = request.args.get('language', '')
    
    # Get user from Flask's g object (set by require_auth decorator)
    user = g.current_user
    user_id = user['id'] if user else None
    
    # Get native language from header
    native_language = request.headers.get('X-Native-Language', 'en')
    
    print(f"DEBUG: api_words_list called with language={language}, user_id={user_id}, native_language={native_language}")
    
    if not language:
        return jsonify({'error': 'language required'}), 400
    
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        if config['type'] == 'postgresql':
            # PostgreSQL implementation - aggregate by user, language, native_language
            if user_id:
                # Authenticated user - get user-specific words with familiarity
                result = execute_query(conn, """
                    SELECT 
                        w.id,
                        w.word,
                        w.language,
                        w.native_language,
                        w.translation,
                        w.example,
                        w.example_native,
                        w.lemma,
                        w.pos,
                        w.ipa,
                        w.audio_url,
                        w.gender,
                        w.plural,
                        w.conj,
                        w.comp,
                        w.synonyms,
                        w.collocations,
                        w.cefr,
                        w.freq_rank,
                        w.tags,
                        w.note,
                        w.info,
                        w.created_at,
                        w.updated_at,
                        COALESCE(uwf.familiarity, 0) as familiarity,
                        COALESCE(uwf.seen_count, 0) as seen_count,
                        COALESCE(uwf.correct_count, 0) as correct_count
                    FROM words w
                    LEFT JOIN user_word_familiarity uwf ON w.id = uwf.word_id 
                        AND uwf.user_id = %s 
                        AND uwf.native_language = %s
                    WHERE w.language = %s 
                        AND w.native_language = %s
                    ORDER BY w.word
                """, (user_id, native_language, language, native_language))
            else:
                # Unauthenticated user - get all words without familiarity data
                result = execute_query(conn, """
                    SELECT 
                        w.id,
                        w.word,
                        w.language,
                        w.native_language,
                        w.translation,
                        w.example,
                        w.example_native,
                        w.lemma,
                        w.pos,
                        w.ipa,
                        w.audio_url,
                        w.gender,
                        w.plural,
                        w.conj,
                        w.comp,
                        w.synonyms,
                        w.collocations,
                        w.cefr,
                        w.freq_rank,
                        w.tags,
                        w.note,
                        w.info,
                        w.created_at,
                        w.updated_at,
                        0 as familiarity,
                        0 as seen_count,
                        0 as correct_count
                    FROM words w
                    WHERE w.language = %s 
                        AND w.native_language = %s
                    ORDER BY w.word
                """, (language, native_language))
            
            # Convert to list of dictionaries
            words = []
            for row in result.fetchall():
                word_obj = dict(row)
                
                # Parse JSON fields
                for field in ['conj', 'comp', 'synonyms', 'collocations', 'tags', 'info']:
                    if word_obj.get(field):
                        try:
                            word_obj[field] = json.loads(word_obj[field])
                        except Exception:
                            pass
                
                words.append(word_obj)
            
            print(f"DEBUG: Returning {len(words)} words from PostgreSQL for user_id={user_id}")
            return jsonify(words)
            
        else:
            # SQLite fallback - use existing logic
            if not user_id:
                # Not authenticated - get words from global database
                print("DEBUG: No user_id, getting words from global database")
                try:
                    # Get global database path
                    from server.multi_user_db import db_manager
                    global_db_path = db_manager.get_global_db_path(native_language)
                    
                    if not os.path.exists(global_db_path):
                        return jsonify([])
                    
                    conn_sqlite = sqlite3.connect(global_db_path)
                    conn_sqlite.row_factory = sqlite3.Row
                    cur = conn_sqlite.cursor()
                    
                    # Get all words for the target language
                    cur.execute("""
                        SELECT word, translation, word_hash
                        FROM words_global 
                        WHERE language = ?
                        ORDER BY word
                    """, (language,))
                    
                    global_words = cur.fetchall()
                    conn_sqlite.close()
                    
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
            else:
                # Authenticated user - use existing SQLite logic
                from server.db_multi_user import get_user_native_language, ensure_user_databases
                from server.multi_user_db import db_manager
                
                native_language = get_user_native_language(user_id)
                ensure_user_databases(user_id, native_language)
                
                # Continue with existing SQLite logic...
                # (keeping the existing complex logic for SQLite compatibility)
                return jsonify([])
        
    except Exception as e:
        print(f"Error loading user words: {e}")
        return jsonify({'error': str(e)}), 500

@words_bp.get('/api/words/learning')
@require_auth()
def api_words_learning():
    """Return words that the authenticated user is currently learning (familiarity < 5)."""
    user = g.current_user
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    user_id = user['id']
    language = request.args.get('language') or request.args.get('lang')
    if not language:
        return jsonify({'success': False, 'error': 'language parameter required'}), 400
    
    # Determine native language preference
    native_language = request.headers.get('X-Native-Language')
    if not native_language:
        native_language = user.get('native_language') or get_user_native_language(user_id) or 'en'
    
    # Familiarity range (defaults to "learning" words: 0-4, excluding mastered 5)
    def _parse_bound(value, default):
        try:
            return max(0, min(5, int(value)))
        except (ValueError, TypeError):
            return default
    
    min_fam = _parse_bound(request.args.get('min_familiarity'), 0)
    max_fam = _parse_bound(request.args.get('max_familiarity'), 4)
    if min_fam > max_fam:
        min_fam, max_fam = max_fam, min_fam
    max_fam = min(max_fam, 4)  # Exclude fully mastered by default
    
    # Pagination
    def _parse_positive_int(value, default, upper=None):
        try:
            parsed = int(value)
        except (ValueError, TypeError):
            return default
        parsed = max(0, parsed)
        if upper is not None:
            parsed = min(parsed, upper)
        return parsed
    
    limit = _parse_positive_int(request.args.get('limit'), 100, 500)
    if limit == 0:
        limit = 100
    offset = _parse_positive_int(request.args.get('offset'), 0)
    
    search_term = (request.args.get('q') or '').strip()
    
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'error': 'Failed to connect to database'}), 500
            
            stats = {'0': 0, '1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            total_count = 0
            rows = []
            
            if config['type'] == 'postgresql':
                filters = [
                    "uwf.user_id = %s",
                    "w.language = %s",
                    "(uwf.native_language = %s OR uwf.native_language IS NULL)",
                    "COALESCE(uwf.familiarity, 0) BETWEEN %s AND %s"
                ]
                params = [user_id, language, native_language, min_fam, max_fam]
                
                if search_term:
                    filters.append("(w.word ILIKE %s OR w.translation ILIKE %s OR w.example ILIKE %s)")
                    pattern = f"%{search_term}%"
                    params.extend([pattern, pattern, pattern])
                
                filter_clause = " AND ".join(filters)
                
                # Distribution counts
                dist_cursor = execute_query(conn, f"""
                    SELECT COALESCE(uwf.familiarity, 0) AS familiarity, COUNT(*) AS count
                    FROM user_word_familiarity uwf
                    INNER JOIN words w ON w.id = uwf.word_id
                    WHERE {filter_clause}
                    GROUP BY COALESCE(uwf.familiarity, 0)
                """, params)
                for crow in dist_cursor.fetchall():
                    # Handle both dict and tuple/list results
                    if isinstance(crow, dict):
                        fam_key = str(crow.get('familiarity', 0) or 0)
                        count = crow.get('count', 0) or 0
                    elif isinstance(crow, (list, tuple)) and len(crow) >= 2:
                        fam_key = str(crow[0] or 0)
                        count = crow[1] or 0
                    else:
                        continue
                    stats[fam_key] = count
                    total_count += count
                
                data_cursor = execute_query(conn, f"""
                    SELECT 
                        w.id AS word_id,
                        w.word,
                        w.translation,
                        w.language,
                        w.native_language,
                        w.ipa,
                        w.pos,
                        w.cefr,
                        w.example,
                        w.example_native,
                        w.audio_url,
                        COALESCE(uwf.familiarity, 0) AS familiarity,
                        COALESCE(uwf.seen_count, 0) AS seen_count,
                        COALESCE(uwf.correct_count, 0) AS correct_count,
                        COALESCE(uwf.updated_at, uwf.created_at) AS last_reviewed,
                        uwf.created_at,
                        uwf.user_comment
                    FROM user_word_familiarity uwf
                    INNER JOIN words w ON w.id = uwf.word_id
                    WHERE {filter_clause}
                    ORDER BY last_reviewed DESC NULLS LAST, COALESCE(uwf.seen_count, 0) DESC, w.word ASC
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])
                rows = data_cursor.fetchall()
            else:
                filters = [
                    "uwf.user_id = ?",
                    "w.language = ?",
                    "(uwf.native_language = ? OR uwf.native_language IS NULL)",
                    "COALESCE(uwf.familiarity, 0) BETWEEN ? AND ?"
                ]
                params = [user_id, language, native_language, min_fam, max_fam]
                
                if search_term:
                    filters.append("(LOWER(w.word) LIKE ? OR LOWER(w.translation) LIKE ? OR LOWER(COALESCE(w.example, '')) LIKE ?)")
                    pattern = f"%{search_term.lower()}%"
                    params.extend([pattern, pattern, pattern])
                
                filter_clause = " AND ".join(filters)
                
                dist_cursor = execute_query(conn, f"""
                    SELECT COALESCE(uwf.familiarity, 0) AS familiarity, COUNT(*) AS count
                    FROM user_word_familiarity uwf
                    INNER JOIN words w ON w.id = uwf.word_id
                    WHERE {filter_clause}
                    GROUP BY COALESCE(uwf.familiarity, 0)
                """, params)
                for crow in dist_cursor.fetchall():
                    # Handle both dict and tuple/list results
                    if isinstance(crow, dict):
                        fam_key = str(crow.get('familiarity', 0) or 0)
                        count = crow.get('count', 0) or 0
                    elif isinstance(crow, (list, tuple)) and len(crow) >= 2:
                        fam_key = str(crow[0] or 0)
                        count = crow[1] or 0
                    else:
                        continue
                    stats[fam_key] = count
                    total_count += count
                
                data_cursor = execute_query(conn, f"""
                    SELECT 
                        w.id AS word_id,
                        w.word,
                        w.translation,
                        w.language,
                        w.native_language,
                        w.ipa,
                        w.pos,
                        w.cefr,
                        w.example,
                        w.example_native,
                        w.audio_url,
                        COALESCE(uwf.familiarity, 0) AS familiarity,
                        COALESCE(uwf.seen_count, 0) AS seen_count,
                        COALESCE(uwf.correct_count, 0) AS correct_count,
                        COALESCE(uwf.updated_at, uwf.created_at) AS last_reviewed,
                        uwf.created_at,
                        uwf.user_comment
                    FROM user_word_familiarity uwf
                    INNER JOIN words w ON w.id = uwf.word_id
                    WHERE {filter_clause}
                    ORDER BY last_reviewed DESC, COALESCE(uwf.seen_count, 0) DESC, w.word ASC
                    LIMIT ? OFFSET ?
                """, params + [limit, offset])
                rows = data_cursor.fetchall()
            
            learning_words = []
            for row in rows:
                # Handle both dict and tuple/list results
                if isinstance(row, dict):
                    def accessor(key):
                        return row.get(key)
                elif isinstance(row, (list, tuple)):
                    # Map column names to indices based on SELECT order
                    column_map = {
                        'word_id': 0, 'word': 1, 'translation': 2, 'language': 3, 'native_language': 4,
                        'ipa': 5, 'pos': 6, 'cefr': 7, 'example': 8, 'example_native': 9,
                        'audio_url': 10, 'familiarity': 11, 'seen_count': 12, 'correct_count': 13,
                        'last_reviewed': 14, 'created_at': 15, 'user_comment': 16
                    }
                    def accessor(key):
                        idx = column_map.get(key, -1)
                        if idx >= 0 and idx < len(row):
                            return row[idx]
                        return None
                else:
                    def accessor(key):
                        return getattr(row, key, None)
                
                familiarity = accessor('familiarity') or 0
                last_reviewed = accessor('last_reviewed') or accessor('created_at')
                if last_reviewed and hasattr(last_reviewed, 'isoformat'):
                    last_reviewed = last_reviewed.isoformat()
                
                learning_words.append({
                    'word_id': accessor('word_id'),
                    'word': accessor('word'),
                    'translation': accessor('translation'),
                    'language': accessor('language'),
                    'native_language': accessor('native_language'),
                    'ipa': accessor('ipa'),
                    'pos': accessor('pos'),
                    'cefr': accessor('cefr'),
                    'example': accessor('example'),
                    'example_native': accessor('example_native'),
                    'audio_url': accessor('audio_url'),
                    'familiarity': familiarity,
                    'seen_count': accessor('seen_count') or 0,
                    'correct_count': accessor('correct_count') or 0,
                    'last_reviewed': last_reviewed,
                    'user_comment': accessor('user_comment')
                })
            
            return jsonify({
                'success': True,
                'words': learning_words,
                'total': total_count,
                'stats': {
                    'total': total_count,
                    'by_familiarity': stats
                },
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'returned': len(learning_words),
                    'has_more': (offset + len(learning_words)) < total_count
                }
            })
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as close_error:
                    print(f"⚠️ Error closing connection: {close_error}")
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error getting learning words: {e}")
        print(f"❌ Traceback: {error_trace}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'error_type': type(e).__name__
        }), 500

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
        # Get native language from header
        native_language = request.headers.get('X-Native-Language', 'en')
        
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        if config['type'] == 'postgresql':
            # PostgreSQL implementation - count only words with familiarity >= 1
            result = execute_query(conn, """
                SELECT COUNT(*) as count
                FROM user_word_familiarity uwf
                INNER JOIN words w ON w.id = uwf.word_id
                WHERE uwf.user_id = %s
                    AND uwf.native_language = %s
                    AND w.language = %s
                    AND w.native_language = %s
                    AND COALESCE(uwf.familiarity, 0) >= 1
            """, (user_id, native_language, language, native_language))
            
            row = result.fetchone()
            count = row['count'] if row else 0
            
            print(f"DEBUG: PostgreSQL word count for user_id={user_id}, language={language}, native_language={native_language}: {count}")
            return jsonify({'count': count})
            
        else:
            # SQLite fallback - use existing logic
            from server.db_multi_user import get_user_native_language, ensure_user_databases
            from server.multi_user_db import db_manager
            
            native_language = get_user_native_language(user_id)
            ensure_user_databases(user_id, native_language)
            
            db_path = db_manager.get_user_db_path(user_id, native_language)
            if not os.path.exists(db_path):
                return jsonify({'count': 0})
            
            conn_sqlite = sqlite3.connect(db_path)
            conn_sqlite.row_factory = sqlite3.Row
            cur = conn_sqlite.cursor()
            
            # Count words with familiarity >= 1 in local database for this language
            cur.execute("""
                SELECT COUNT(DISTINCT wl.word_hash) as count
                FROM words_local wl
                JOIN level_words lw ON lw.word_hashes LIKE '%' || wl.word_hash || '%'
                WHERE lw.language = ?
                  AND wl.familiarity >= 1
            """, (language,))
            
            row = cur.fetchone()
            conn_sqlite.close()
            
            # If no words found via level_words, count all words in local database
            if not row or row['count'] == 0:
                conn_sqlite = sqlite3.connect(db_path)
                conn_sqlite.row_factory = sqlite3.Row
                cur = conn_sqlite.cursor()
                
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM words_local
                    WHERE familiarity >= 1
                """)
                
                row = cur.fetchone()
                conn_sqlite.close()
            
            return jsonify({'count': row['count'] if row else 0})
        
    except Exception as e:
        print(f"Error counting user words: {e}")
        return jsonify({'count': 0})

@words_bp.get('/api/words/count_max')
def api_words_count_max():
    language = (request.args.get('language') or '').strip()
    cnt = count_words_fam5(language or None)
    return jsonify({'success': True, 'count': cnt})

@words_bp.get('/api/words/count_learned')
@require_auth(optional=True)
def api_words_count_learned():
    """Get count of learned words (familiarity = 5) for a specific language (user-specific)"""
    language = request.args.get('language', 'en')
    
    # Get user from Flask's g object (set by require_auth decorator)
    user = g.current_user
    user_id = user['id'] if user else None
    
    # Get native language from header
    native_language = request.headers.get('X-Native-Language', 'en')
    
    if not user_id:
        # Not authenticated - return 0
        return jsonify({'count': 0})
    
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        if config['type'] == 'postgresql':
            # PostgreSQL implementation - count learned words (familiarity = 5) for user, language, native_language
            result = execute_query(conn, """
                SELECT COUNT(*) as count
                FROM words w
                INNER JOIN user_word_familiarity uwf ON w.id = uwf.word_id 
                    AND uwf.user_id = %s 
                    AND uwf.native_language = %s
                    AND uwf.familiarity = 5
                WHERE w.language = %s 
                    AND w.native_language = %s
            """, (user_id, native_language, language, native_language))
            
            row = result.fetchone()
            count = row['count'] if row else 0
            
            print(f"DEBUG: PostgreSQL learned words count for user_id={user_id}, language={language}, native_language={native_language}: {count}")
            return jsonify({'count': count})
            
        else:
            # SQLite fallback - use existing logic for familiarity 5
            cnt = count_words_fam5(language or None)
            return jsonify({'count': cnt})
        
    except Exception as e:
        print(f"Error counting learned words: {e}")
        return jsonify({'count': 0})

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
@require_auth(optional=True)
def api_word_get():
    word = (request.args.get('word') or '').strip()
    language = (request.args.get('language') or '').strip()
    native_language_param = (request.args.get('native_language') or '').strip()
    if not word:
        return jsonify({'error': 'word required'}), 400
    
    # Get user context from middleware
    user_context = get_user_context()
    user_id = user_context['user_id']
    
    # For testing: if no user_id from auth, try to get from Authorization header
    if not user_id:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            # For testing purposes, assume user_id = 2 if Authorization header is present
            user_id = 2
            print(f"🔧 Using test user_id = 2 for /api/word endpoint")
    
    # Get native language from URL parameter, user context, or default
    native_language = native_language_param or user_context.get('native_language', 'en')
    
    # Get word data from existing PostgreSQL words table
    from server.db_config import get_database_config, get_db_connection, execute_query
    
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        result = None
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
            result = cur.execute('SELECT * FROM words WHERE word=? AND language=? AND native_language=?', (word, language, native_language))
            row = result.fetchone()
        
        if not row:
            # Return empty word data if not found
            return jsonify({
              'word': word, 'language': language, 'translation': '', 'example': '', 'example_native': '',
              'lemma': '', 'pos': '', 'ipa': '', 'audio_url': '', 'gender': 'none', 'plural': '',
              'conj': {}, 'comp': {}, 'synonyms': [], 'collocations': [], 'cefr': '', 'freq_rank': None, 'tags': [], 'note': '',
              'info': {}, 'familiarity': 0, 'seen_count': 0, 'correct_count': 0
            })
        
        # Handle both dict and tuple/list results
        if isinstance(row, dict):
            data = dict(row)
        elif isinstance(row, (list, tuple)):
            # Convert tuple/list to dict using cursor description
            if result and hasattr(result, 'description') and result.description:
                data = {result.description[i][0]: row[i] for i in range(min(len(row), len(result.description)))}
            else:
                # Fallback: try to get description from cursor
                try:
                    desc = None
                    if result:
                        desc = getattr(result, 'description', None)
                    if not desc and hasattr(conn, 'cursor'):
                        try:
                            temp_cursor = conn.cursor()
                            desc = getattr(temp_cursor, 'description', None)
                        except:
                            pass
                    if desc:
                        data = {desc[i][0]: row[i] for i in range(min(len(row), len(desc)))}
                    else:
                        # Last resort: use column names from words table schema
                        column_names = ['id', 'word', 'translation', 'language', 'native_language', 'ipa', 'pos', 
                                      'gender', 'plural', 'lemma', 'example', 'example_native', 'audio_url',
                                      'conj', 'comp', 'synonyms', 'collocations', 'cefr', 'freq_rank', 'tags', 
                                      'note', 'info', 'created_at', 'updated_at']
                        data = {column_names[i]: row[i] for i in range(min(len(row), len(column_names)))}
                except Exception as e:
                    print(f"⚠️ Warning: Error converting row to dict: {e}")
                    # If all else fails, create a minimal dict
                    data = {'word': row[1] if len(row) > 1 else '', 'language': row[3] if len(row) > 3 else '', 
                           'native_language': row[4] if len(row) > 4 else ''}
        else:
            # Try to convert using _coerce_row_to_dict
            from server.db import _coerce_row_to_dict
            data = _coerce_row_to_dict(row, getattr(result, 'description', None))
            if not data:
                data = {}
        
        # Parse JSON fields
        for json_field in ['conj', 'comp', 'synonyms', 'collocations', 'tags', 'info']:
            if data.get(json_field):
                try:
                    data[json_field] = json.loads(data[json_field]) if isinstance(data[json_field], str) else data[json_field]
                except (json.JSONDecodeError, TypeError):
                    data[json_field] = None
            else:
                data[json_field] = None
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error in api_word_get: {e}")
        print(f"❌ Traceback: {error_trace}")
        if conn:
            try:
                conn.close()
            except:
                pass
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass
    
    # Get user-specific familiarity data if authenticated
    is_authenticated = user_id is not None
    if user_id:
        try:
            # Get familiarity from PostgreSQL user_word_familiarity table
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
    
    # Always include familiarity fields in response
    # Keep user-specific familiarity data for authenticated users
    # For unauthenticated users, return default values
    if not is_authenticated:
        # Ensure default values are set for unauthenticated users
        data['familiarity'] = 0
        data['seen_count'] = 0
        data['correct_count'] = 0
        data['user_comment'] = ''
    
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


# --- Optimized batch word fetch endpoint with familiarity data ---
@words_bp.post('/api/words/batch')
@require_auth(optional=True)
def api_words_batch():
    """Fetch multiple words in single optimized query - includes user familiarity data"""
    payload = request.get_json(force=True) or {}
    words = payload.get('words') or []
    language = (payload.get('language') or '').strip()
    
    # Normalize input
    words = [str(w).strip() for w in words if str(w).strip()]
    if not words:
        return jsonify({'success': True, 'words': {}})
    
    try:
        user_context = get_user_context()
        user_id = user_context.get('user_id')
        native_language = user_context.get('native_language', 'en')
        
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            # Fetch words and familiarity data in optimized queries
            if config['type'] == 'postgresql':
                # Get words data
                result = execute_query(conn, '''
                    SELECT * FROM words 
                    WHERE word = ANY(%s) AND language = %s AND native_language = %s
                ''', (words, language, native_language))
                word_rows = result.fetchall()
                
                # Get familiarity data if authenticated
                familiarity_map = {}
                if user_id:
                    try:
                        fam_result = execute_query(conn, '''
                            SELECT word, familiarity, seen_count, correct_count, user_comment
                            FROM user_word_familiarity
                            WHERE user_id = %s AND word = ANY(%s) AND language = %s AND native_language = %s
                        ''', (user_id, words, language, native_language))
                        for row in fam_result.fetchall():
                            if isinstance(row, dict):
                                familiarity_map[row['word']] = {
                                    'familiarity': row.get('familiarity', 0) or 0,
                                    'seen_count': row.get('seen_count', 0) or 0,
                                    'correct_count': row.get('correct_count', 0) or 0,
                                    'user_comment': row.get('user_comment') or ''
                                }
                            else:
                                familiarity_map[row[0]] = {
                                    'familiarity': row[1] or 0,
                                    'seen_count': row[2] or 0,
                                    'correct_count': row[3] or 0,
                                    'user_comment': row[4] or ''
                                }
                    except Exception as e:
                        print(f"Error fetching familiarity data: {e}")
            else:
                # SQLite syntax
                cur = conn.cursor()
                placeholders = ','.join('?' for _ in words)
                result = cur.execute(
                    f'SELECT * FROM words WHERE word IN ({placeholders}) AND language=? AND native_language=?',
                    (*words, language, native_language)
                )
                word_rows = result.fetchall()
                
                # Get familiarity data if authenticated
                familiarity_map = {}
                if user_id:
                    try:
                        fam_result = cur.execute(
                            f'SELECT word, familiarity, seen_count, correct_count, user_comment FROM user_word_familiarity WHERE user_id=? AND word IN ({placeholders}) AND language=? AND native_language=?',
                            (user_id, *words, language, native_language)
                        )
                        for row in fam_result.fetchall():
                            if isinstance(row, dict):
                                familiarity_map[row['word']] = {
                                    'familiarity': row.get('familiarity', 0) or 0,
                                    'seen_count': row.get('seen_count', 0) or 0,
                                    'correct_count': row.get('correct_count', 0) or 0,
                                    'user_comment': row.get('user_comment') or ''
                                }
                            else:
                                familiarity_map[row[0]] = {
                                    'familiarity': row[1] or 0,
                                    'seen_count': row[2] or 0,
                                    'correct_count': row[3] or 0,
                                    'user_comment': row[4] or ''
                                }
                    except Exception as e:
                        print(f"Error fetching familiarity data: {e}")
            
            # Convert rows to dict format
            words_data = {}
            for row in word_rows:
                from server.db import _coerce_row_to_dict
                word_data = _coerce_row_to_dict(row, getattr(result, 'description', None))
                if not word_data:
                    continue
                
                # Parse JSON fields
                for json_field in ['conj', 'comp', 'synonyms', 'collocations', 'tags', 'info']:
                    if word_data.get(json_field):
                        try:
                            word_data[json_field] = json.loads(word_data[json_field]) if isinstance(word_data[json_field], str) else word_data[json_field]
                        except (json.JSONDecodeError, TypeError):
                            word_data[json_field] = None
                    else:
                        word_data[json_field] = None
                
                word = word_data.get('word')
                if word:
                    # Add familiarity data
                    if word in familiarity_map:
                        word_data.update(familiarity_map[word])
                    else:
                        word_data['familiarity'] = 0
                        word_data['seen_count'] = 0
                        word_data['correct_count'] = 0
                        word_data['user_comment'] = ''
                    
                    words_data[word] = word_data
            
            return jsonify({'success': True, 'words': words_data})
        finally:
            conn.close()
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error in api_words_batch: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
                result = cur.execute(f'SELECT * FROM words WHERE word IN ({placeholders}) AND language=? AND native_language=?', (*words, language, native_language))
                rows = result.fetchall()
            
            # Convert to dict with word as key
            word_data_map = {}
            for row in rows:
                # Handle both dict and tuple/list results
                if isinstance(row, dict):
                    word_data = dict(row)
                elif isinstance(row, (list, tuple)):
                    # Convert tuple/list to dict using cursor description
                    if result and hasattr(result, 'description') and result.description:
                        word_data = {result.description[i][0]: row[i] for i in range(min(len(row), len(result.description)))}
                    else:
                        # Fallback: try to get description from cursor
                        try:
                            desc = None
                            if result:
                                desc = getattr(result, 'description', None)
                            if not desc and hasattr(conn, 'cursor'):
                                try:
                                    temp_cursor = conn.cursor()
                                    desc = getattr(temp_cursor, 'description', None)
                                except:
                                    pass
                            if desc:
                                word_data = {desc[i][0]: row[i] for i in range(min(len(row), len(desc)))}
                            else:
                                # Last resort: use column names from words table schema
                                column_names = ['id', 'word', 'translation', 'language', 'native_language', 'ipa', 'pos', 
                                              'gender', 'plural', 'lemma', 'example', 'example_native', 'audio_url',
                                              'conj', 'comp', 'synonyms', 'collocations', 'cefr', 'freq_rank', 'tags', 
                                              'note', 'info', 'created_at', 'updated_at']
                                word_data = {column_names[i]: row[i] for i in range(min(len(row), len(column_names)))}
                        except Exception as e:
                            print(f"⚠️ Warning: Error converting row to dict: {e}")
                            # If all else fails, create a minimal dict
                            word_data = {'word': row[1] if len(row) > 1 else '', 'language': row[3] if len(row) > 3 else '', 
                                       'native_language': row[4] if len(row) > 4 else ''}
                else:
                    # Try to convert using _coerce_row_to_dict
                    from server.db import _coerce_row_to_dict
                    word_data = _coerce_row_to_dict(row, getattr(result, 'description', None))
                    if not word_data:
                        word_data = {}
                
                # Parse JSON fields
                for json_field in ['conj', 'comp', 'synonyms', 'collocations', 'tags', 'info']:
                    if word_data.get(json_field):
                        try:
                            word_data[json_field] = json.loads(word_data[json_field]) if isinstance(word_data[json_field], str) else word_data[json_field]
                        except (json.JSONDecodeError, TypeError):
                            word_data[json_field] = None
                    else:
                        word_data[json_field] = None
                
                if 'word' in word_data:
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
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error in get_many: {e}")
        print(f"❌ Traceback: {error_trace}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'error_type': type(e).__name__
        }), 500


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
                insert_values = (
                    insert_data['word'], insert_data['language'], insert_data['native_language'],
                    insert_data['translation'], insert_data['example'], insert_data['example_native'],
                    insert_data['lemma'], insert_data['pos'], insert_data['ipa'], insert_data['audio_url'],
                    insert_data['gender'], insert_data['plural'], insert_data['conj'], insert_data['comp'],
                    insert_data['synonyms'], insert_data['collocations'], insert_data['cefr'],
                    insert_data['freq_rank'], insert_data['tags'], insert_data['note'], insert_data['info']
                )
                execute_query(conn, '''
                    INSERT INTO words (
                        word, language, native_language, translation, example, example_native,
                        lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                        collocations, cefr, freq_rank, tags, note, info
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
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
                ''', insert_values)
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


@words_bp.post('/api/words/batch-update')
def api_words_batch_update():
    """Batch update multiple word familiarities in a single transaction for better performance"""
    try:
        payload = request.get_json(force=True) or {}
        updates = payload.get('updates', [])
        
        if not updates or not isinstance(updates, list):
            return jsonify({'success': False, 'error': 'updates array required'}), 400
        
        # Get user context
        user_context = get_user_context()
        user_id = user_context['user_id']
        is_authenticated = user_id is not None
        
        if not is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Get native language
        native_language = user_context.get('native_language', 'en')
        if request.headers.get('X-Native-Language'):
            native_language = request.headers.get('X-Native-Language')
        
        # Track affected levels for cache invalidation
        affected_levels = set()
        affected_groups = set()
        
        # Get level context from request body or Flask g object
        level_context = payload.get('level_context', {})
        if not level_context and hasattr(g, 'current_level_context'):
            level_context = g.current_level_context
        
        group_id = level_context.get('group_id')
        level_number = level_context.get('level_number')
        
        # Process all updates in a single transaction
        from server.db_config import get_database_config, get_db_connection
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            # Ensure all words exist first (batch)
            all_words = [(u.get('word', '').strip(), u.get('language', 'en')) for u in updates]
            unique_words = {}
            for word, lang in all_words:
                if word:
                    key = (word, lang)
                    if key not in unique_words:
                        unique_words[key] = word
            
            if unique_words:
                from server.db import ensure_words_exist
                for (word, lang), w in unique_words.items():
                    try:
                        ensure_words_exist([w], lang, native_language)
                    except Exception as e:
                        print(f"Error ensuring word '{w}' exists: {e}")
            
            # Get current familiarities before updating (for incremental cache updates)
            from server.db_multi_user import get_user_word_familiarity_by_word
            word_updates_for_cache = []  # List of (word, old_fam, new_fam, group_id, level_number)
            
            # Update all familiarities
            success_count = 0
            for update in updates:
                word = (update.get('word') or '').strip()
                language = update.get('language', 'en')
                new_familiarity = update.get('familiarity', 0)
                
                if not word:
                    continue
                
                try:
                    # Get current familiarity before update
                    current_row = get_user_word_familiarity_by_word(user_id, word, language, native_language)
                    old_familiarity = 0
                    if current_row:
                        old_familiarity = current_row.get('familiarity', 0) or 0
                    
                    # Update familiarity
                    success = update_user_word_familiarity_by_word(
                        user_id=user_id,
                        word=word,
                        language=language,
                        native_language=native_language,
                        familiarity=new_familiarity
                    )
                    
                    if success:
                        success_count += 1
                        
                        # Track affected levels and word updates for incremental cache
                        if group_id and level_number:
                            affected_groups.add(group_id)
                            affected_levels.add((group_id, level_number))
                            word_updates_for_cache.append((word, old_familiarity, new_familiarity, group_id, level_number))
                
                except Exception as e:
                    print(f"Error updating familiarity for '{word}': {e}")
                    continue
            
            conn.commit()
            
            # Smart cache invalidation - use incremental updates when possible
            if word_updates_for_cache:
                try:
                    from server.db_progress_cache import update_progress_cache_incremental
                    from collections import defaultdict
                    
                    # Group updates by (group_id, level_number)
                    updates_by_level = defaultdict(list)
                    for word, old_fam, new_fam, group_id, level_number in word_updates_for_cache:
                        updates_by_level[(group_id, level_number)].append((word, old_fam, new_fam))
                    
                    # Apply incremental updates for each affected level
                    for (group_id, level_number), word_updates in updates_by_level.items():
                        update_progress_cache_incremental(user_id, group_id, level_number, word_updates)
                    
                except Exception as e:
                    print(f"Error updating progress cache incrementally: {e}")
                    # Fallback to full refresh
                    try:
                        from server.db_progress_cache import refresh_custom_level_progress
                        for group_id, level_number in affected_levels:
                            refresh_custom_level_progress(user_id, group_id, level_number)
                    except Exception as e2:
                        print(f"Error refreshing progress cache: {e2}")
            elif affected_levels:
                # Fallback: full refresh if we don't have word update details
                try:
                    from server.db_progress_cache import refresh_custom_level_progress
                    for group_id, level_number in affected_levels:
                        refresh_custom_level_progress(user_id, group_id, level_number)
                except Exception as e:
                    print(f"Error refreshing progress cache: {e}")
            
            return jsonify({
                'success': True,
                'updated_count': success_count,
                'total_count': len(updates)
            })
        
        finally:
            conn.close()
    
    except Exception as e:
        print(f"Error in batch word update: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@words_bp.post('/api/words/adjust-familiarity')
def api_words_adjust_familiarity():
    """Adjust familiarity level for a word - PostgreSQL version"""
    try:
        # Get user context from middleware
        user_context = get_user_context()
        user_id = user_context['user_id']
        
        payload = request.get_json(force=True) or {}
        word = (payload.get('word') or '').strip().lower()  # Normalize to lowercase
        delta = payload.get('delta', 0)
        
        if not word:
            return jsonify({'success': False, 'error': 'word required'}), 400
        
        # Get current language from request
        language = request.args.get('language', 'en')
        
        if not user_id:
            # Not authenticated - return error
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Get native language from user context or header
        native_language = user_context.get('native_language') or request.headers.get('X-Native-Language', 'en')
        
        # Use PostgreSQL database
        from server.db_config import get_database_config, get_db_connection, execute_query
        
        config = get_database_config()
        if config['type'] != 'postgresql':
            return jsonify({'success': False, 'error': 'PostgreSQL required'}), 500
        
        conn = get_db_connection()
        
        try:
            # Get word_id from words table
            result = execute_query(conn, """
                SELECT id FROM words
                WHERE word = %s AND language = %s AND native_language = %s
                LIMIT 1
            """, (word, language, native_language))
            
            word_row = result.fetchone()
            if not word_row:
                return jsonify({'success': False, 'error': 'Word not found in database'}), 404
            
            word_id = word_row['id']
            
            # Get current familiarity from user_word_familiarity
            result = execute_query(conn, """
                SELECT familiarity FROM user_word_familiarity
                WHERE user_id = %s AND word_id = %s
                LIMIT 1
            """, (user_id, word_id))
            
            familiarity_row = result.fetchone()
            current_familiarity = familiarity_row['familiarity'] if familiarity_row else 0
            
            # Calculate new familiarity
            new_familiarity = max(0, min(5, current_familiarity + delta))
            
            # Update or insert familiarity
            if familiarity_row:
                # Update existing record
                execute_query(conn, """
                    UPDATE user_word_familiarity
                    SET familiarity = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND word_id = %s
                """, (new_familiarity, user_id, word_id))
            else:
                # Insert new record
                execute_query(conn, """
                    INSERT INTO user_word_familiarity (user_id, word_id, familiarity, created_at, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (user_id, word_id, new_familiarity))
            
            conn.commit()
            
            print(f"✅ Updated familiarity for '{word}' (user {user_id}): {current_familiarity} → {new_familiarity}")
            
            return jsonify({
                'success': True,
                'familiarity': new_familiarity,
                'delta': new_familiarity - current_familiarity,
                'authenticated': True
            })
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error adjusting familiarity: {e}")
        import traceback
        traceback.print_exc()
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
            from server.services.tts import batch_ensure_tts_for_words
            audio_results = batch_ensure_tts_for_words(words, language, sentence_contexts)
            
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
                    # Check if it's an S3 URL
                    if au.startswith('https://') and 's3' in au:
                        # S3 URL - assume it exists (S3 is reliable)
                        upd['audio_url'] = au
                        need_gen = False
                    elif au.startswith('/media/tts/'):
                        # Local path reference - check if it exists in S3
                        # Extract lang and filename from path
                        parts = au.strip('/').split('/')
                        if len(parts) == 4 and parts[0] == 'media' and parts[1] == 'tts':
                            lang_part, fname = parts[2], parts[3]
                            from server.services.s3_storage import tts_audio_exists, get_tts_audio_url
                            if tts_audio_exists(lang_part, fname, 'tts'):
                                upd['audio_url'] = get_tts_audio_url(lang_part, fname, 'tts')
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


# Standard level endpoint removed: @levels_bp.post('/api/level/ensure_topic')
# Standard level function removed: def api_level_ensure_topic():
# FALLBACK_SENTENCES removed - standard levels deactivated
# Standard level function removed: def api_level_start():
# Standard level function removed: def api_level_submit():
# Standard level function removed: def api_practice_grade():
# Standard level function removed: def api_level_stats_fs():
# Standard level endpoint removed: /api/level/<int:level>/words

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
# Standard level function removed: def api_levels_bulk_stats():
# Practice session function removed: def _custom_practice_sessions_path(lang: str) -> Path:
# Practice session function removed: def _load_custom_practice_sessions(lang: str) -> list:
# Practice session function removed: def _save_custom_practice_sessions(lang: str, sessions: list) -> None:
# Practice session function removed: def _create_custom_practice_session(lang: str, words: list, label: str, exclude_max: bool) -> int:
# Practice session function removed: def _get_custom_practice_session(lang: str, run_id: int) -> dict | None:
# Practice session function removed: def _update_custom_practice_session(lang: str, updated: dict | None, *, delete: bool = False) -> None:
# Standard level function removed: def api_level_unlock_words():
# Standard level function removed: def api_sync_user_data():
# Standard level function removed: def api_sync_words():
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

# Standard level endpoint removed: @practice_bp.post('/api/practice/start')
# Standard level function removed: def api_practice_start_fs():
# _ensure_course_dirs removed - standard levels deactivated
# Standard level function removed: def api_course_init():
# Standard level function removed: def api_levels_summary_fs():
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
        
        # Standard level file creation removed - standard levels are deactivated
        # Language validation still works, but no standard level files are created
        
        return jsonify({
            'success': True,
            'language_code': language_code,
            'language_name': ai_result.get('language_name', language_name),
            'message': f'Language {ai_result.get("language_name", language_name)} validated successfully (standard levels disabled)'
        })
        
    except Exception as e:
        print(f"Error validating language: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@levels_bp.get('/api/languages/list')
def api_languages_list():
    """List all available languages - returns only language codes, names are loaded from localization files"""
    try:
        # Standard levels are deactivated - return empty list or hardcoded list
        # Languages are now managed through localization system
        languages = []
        
        # Return empty list since standard levels are disabled
        # Languages can still be added through the localization system
        return jsonify({
            'success': True,
            'languages': languages,
            'message': 'Standard level groups are disabled. Use custom level groups instead.'
        })
        
    except Exception as e:
        print(f"Error listing languages: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ensure_all_languages_have_levels removed - standard levels are deactivated

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
        
        return jsonify({'success': True, 'languages': languages})
        
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
_register_debug_routes()

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

# Serve CSV file for direct access (generated from database)
@app.route('/localization_complete.csv')
def serve_csv():
    try:
        entries = get_all_localization_entries()
        rows = []
        language_fields = set()
        
        for entry in entries:
            entry_dict = dict(entry)
            rows.append(entry_dict)
            for key in entry_dict.keys():
                normalized_key = key.lower()
                if normalized_key in {'id', 'reference_key', 'description', 'language', 'language_code'}:
                    continue
                language_fields.add(key)
        
        ordered_languages = sorted(language_fields)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['KEY', 'DESCRIPTION', *ordered_languages])
        
        for entry in rows:
            reference_key = entry.get('reference_key', '')
            description = entry.get('description', '')
            row = [reference_key, description]
            for lang in ordered_languages:
                value = entry.get(lang, '')
                row.append(value if value is not None else '')
            writer.writerow(row)
        
        csv_data = output.getvalue()
        response = Response(csv_data, mimetype='text/csv; charset=utf-8')
        response.headers['Content-Disposition'] = 'attachment; filename=localization_complete.csv'
        return response
    except Exception as e:
        print(f"Error generating localization CSV from database: {e}")
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
        from server.db_config import get_database_config, execute_query
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
        from server.db_config import get_database_config, execute_query
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
        from server import postgres
        from urllib.parse import urlparse
        import os
        
        # Check if DATABASE_URL is set (PostgreSQL)
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            try:
                # Parse and connect to PostgreSQL
                parsed = urlparse(database_url)
                conn = postgres.connect(
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
        from server import postgres
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
        conn = postgres.connect(
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
        from server import postgres
        from urllib.parse import urlparse
        import os
        
        # Get DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({'success': False, 'error': 'DATABASE_URL not set'}), 400
        
        # Parse and connect
        parsed = urlparse(database_url)
        conn = postgres.connect(
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
        # Properly decode URL parameters
        word = request.args.get('word', '').strip()
        if word:
            # Decode URL encoding if present
            import urllib.parse
            word = urllib.parse.unquote(word)
        
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
        success = update_user_word_familiarity_by_word(
            user_id=user_id,
            word=word,
            language=language,
            native_language=native_language,
            familiarity=familiarity,
            user_comment=user_comment
        )
        
        # Also test reading the data back immediately
        read_back = get_user_word_familiarity_by_word(user_id, word, language, native_language)
        
        return jsonify({
            "success": success,
            "word": word,
            "user_id": user_id,
            "language": language,
            "native_language": native_language,
            "familiarity": familiarity,
            "user_comment": user_comment,
            "message": "Update successful" if success else "Update failed",
            "read_back": dict(read_back) if read_back else None
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
