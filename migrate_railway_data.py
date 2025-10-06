#!/usr/bin/env python3
"""
Migration script to populate Railway PostgreSQL database with data from local SQLite
This script will:
1. Connect to local SQLite database
2. Connect to Railway PostgreSQL database
3. Migrate all data including words, users, progress, etc.
"""

import os
import sys
import sqlite3
import psycopg2
from urllib.parse import urlparse
from datetime import datetime
import json

def get_sqlite_connection():
    """Get SQLite connection to local database"""
    # Try different possible SQLite database locations
    possible_paths = [
        'polo.db',
        'data/siluma.db',
        'server/siluma.db',
        'siluma.db'
    ]
    
    for db_path in possible_paths:
        if os.path.exists(db_path):
            print(f"📁 Found SQLite database at: {db_path}")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn
    
    print("❌ No SQLite database found in expected locations")
    return None

def get_postgresql_connection():
    """Get PostgreSQL connection to Railway"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return None
    
    try:
        parsed = urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
        conn.autocommit = True
        print("✅ Connected to Railway PostgreSQL database")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        return None

def create_postgresql_tables(pg_conn):
    """Create PostgreSQL tables with correct schema"""
    cursor = pg_conn.cursor()
    
    print("🔧 Creating PostgreSQL tables...")
    
    # Create words table (main table for word data)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id SERIAL PRIMARY KEY,
            word VARCHAR(255) NOT NULL,
            language VARCHAR(10) NOT NULL,
            native_language VARCHAR(10),
            translation TEXT,
            example TEXT,
            example_native TEXT,
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
            cefr VARCHAR(10),
            freq_rank INTEGER,
            tags TEXT,
            note TEXT,
            info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create users table
    cursor.execute("""
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
        )
    """)
    
    # Create user_sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            session_token VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
    """)
    
    # Create level_runs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS level_runs (
            id SERIAL PRIMARY KEY,
            level INTEGER NOT NULL,
            items TEXT NOT NULL,
            user_translations TEXT,
            score REAL,
            topic VARCHAR(255),
            target_lang VARCHAR(10),
            native_lang VARCHAR(10),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create localization table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS localization (
            id SERIAL PRIMARY KEY,
            key VARCHAR(255) NOT NULL,
            language VARCHAR(10) NOT NULL,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(key, language)
        )
    """)
    
    # Create custom_level_groups table
    cursor.execute("""
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
        )
    """)
    
    # Create custom_levels table
    cursor.execute("""
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
        )
    """)
    
    print("✅ PostgreSQL tables created successfully")

def migrate_words(sqlite_conn, pg_conn):
    """Migrate words data"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    print("🔄 Migrating words...")
    
    # Get all words from SQLite
    sqlite_cursor.execute("SELECT * FROM words")
    words = sqlite_cursor.fetchall()
    
    migrated_count = 0
    for word in words:
        try:
            pg_cursor.execute("""
                INSERT INTO words (
                    id, word, language, native_language, translation, example, example_native,
                    lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                    collocations, cefr, freq_rank, tags, note, info, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (id) DO UPDATE SET
                    word = EXCLUDED.word,
                    language = EXCLUDED.language,
                    native_language = EXCLUDED.native_language,
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
                    updated_at = EXCLUDED.updated_at
            """, (
                word['id'], word['word'], word['language'], word.get('native_language'),
                word.get('translation'), word.get('example'), word.get('example_native'),
                word.get('lemma'), word.get('pos'), word.get('ipa'), word.get('audio_url'),
                word.get('gender'), word.get('plural'), word.get('conj'), word.get('comp'),
                word.get('synonyms'), word.get('collocations'), word.get('cefr'),
                word.get('freq_rank'), word.get('tags'), word.get('note'), word.get('info'),
                word.get('created_at'), word.get('updated_at')
            ))
            migrated_count += 1
        except Exception as e:
            print(f"⚠️ Error migrating word {word.get('word', 'unknown')}: {e}")
    
    print(f"✅ Migrated {migrated_count} words")

def migrate_users(sqlite_conn, pg_conn):
    """Migrate users data"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    print("🔄 Migrating users...")
    
    try:
        sqlite_cursor.execute("SELECT * FROM users")
        users = sqlite_cursor.fetchall()
        
        migrated_count = 0
        for user in users:
            try:
                pg_cursor.execute("""
                    INSERT INTO users (id, username, email, password_hash, created_at, last_login, is_active, settings, native_language)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        last_login = EXCLUDED.last_login,
                        settings = EXCLUDED.settings,
                        native_language = EXCLUDED.native_language
                """, (
                    user['id'], user['username'], user['email'], user['password_hash'],
                    user['created_at'], user['last_login'], user['is_active'],
                    user['settings'], user.get('native_language', 'en')
                ))
                migrated_count += 1
            except Exception as e:
                print(f"⚠️ Error migrating user {user.get('username', 'unknown')}: {e}")
        
        print(f"✅ Migrated {migrated_count} users")
    except Exception as e:
        print(f"⚠️ No users table found or error: {e}")

def migrate_level_runs(sqlite_conn, pg_conn):
    """Migrate level runs data"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    print("🔄 Migrating level runs...")
    
    try:
        sqlite_cursor.execute("SELECT * FROM level_runs")
        runs = sqlite_cursor.fetchall()
        
        migrated_count = 0
        for run in runs:
            try:
                pg_cursor.execute("""
                    INSERT INTO level_runs (id, level, items, user_translations, score, topic, target_lang, native_lang, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        level = EXCLUDED.level,
                        items = EXCLUDED.items,
                        user_translations = EXCLUDED.user_translations,
                        score = EXCLUDED.score,
                        topic = EXCLUDED.topic,
                        target_lang = EXCLUDED.target_lang,
                        native_lang = EXCLUDED.native_lang
                """, (
                    run['id'], run['level'], run['items'], run.get('user_translations'),
                    run.get('score'), run.get('topic'), run.get('target_lang'),
                    run.get('native_lang'), run.get('created_at')
                ))
                migrated_count += 1
            except Exception as e:
                print(f"⚠️ Error migrating level run {run.get('id', 'unknown')}: {e}")
        
        print(f"✅ Migrated {migrated_count} level runs")
    except Exception as e:
        print(f"⚠️ No level_runs table found or error: {e}")

def update_sequences(pg_conn):
    """Update PostgreSQL sequences"""
    cursor = pg_conn.cursor()
    
    print("🔄 Updating PostgreSQL sequences...")
    
    try:
        cursor.execute("SELECT setval('words_id_seq', COALESCE((SELECT MAX(id) FROM words), 1))")
        cursor.execute("SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1))")
        cursor.execute("SELECT setval('level_runs_id_seq', COALESCE((SELECT MAX(id) FROM level_runs), 1))")
        cursor.execute("SELECT setval('localization_id_seq', COALESCE((SELECT MAX(id) FROM localization), 1))")
        cursor.execute("SELECT setval('custom_level_groups_id_seq', COALESCE((SELECT MAX(id) FROM custom_level_groups), 1))")
        cursor.execute("SELECT setval('custom_levels_id_seq', COALESCE((SELECT MAX(id) FROM custom_levels), 1))")
        print("✅ Sequences updated successfully")
    except Exception as e:
        print(f"⚠️ Error updating sequences: {e}")

def main():
    """Main migration function"""
    print("🚀 Starting Railway PostgreSQL data migration...")
    
    # Get connections
    sqlite_conn = get_sqlite_connection()
    if not sqlite_conn:
        print("❌ Could not connect to SQLite database")
        return
    
    pg_conn = get_postgresql_connection()
    if not pg_conn:
        sqlite_conn.close()
        print("❌ Could not connect to PostgreSQL database")
        return
    
    try:
        # Create tables
        create_postgresql_tables(pg_conn)
        
        # Migrate data
        migrate_words(sqlite_conn, pg_conn)
        migrate_users(sqlite_conn, pg_conn)
        migrate_level_runs(sqlite_conn, pg_conn)
        
        # Update sequences
        update_sequences(pg_conn)
        
        print("🎉 Migration completed successfully!")
        print("📝 Next steps:")
        print("1. Test the application")
        print("2. Verify data is accessible")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    main()
