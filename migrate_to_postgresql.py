#!/usr/bin/env python3
"""
Migration script to convert SQLite database to PostgreSQL
Run this script after setting up PostgreSQL in Railway
"""

import os
import sys
import sqlite3
import psycopg2
from urllib.parse import urlparse
from datetime import datetime

def get_sqlite_connection():
    """Get SQLite connection"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'polo.db')
    if not os.path.exists(db_path):
        print(f"❌ SQLite database not found at {db_path}")
        return None
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_postgresql_connection():
    """Get PostgreSQL connection"""
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
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        return None

def create_postgresql_tables(pg_conn):
    """Create PostgreSQL tables"""
    cursor = pg_conn.cursor()
    
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
    
    # Create user_progress table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            language VARCHAR(10) NOT NULL,
            native_language VARCHAR(10) NOT NULL,
            level INTEGER NOT NULL,
            status VARCHAR(50) DEFAULT 'not_started',
            score REAL,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, language, native_language, level)
        )
    """)
    
    # Create user_word_familiarity table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_word_familiarity (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            word_id INTEGER NOT NULL,
            familiarity INTEGER DEFAULT 0,
            seen_count INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, word_id)
        )
    """)
    
    # Create words table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id SERIAL PRIMARY KEY,
            word VARCHAR(255) NOT NULL,
            language VARCHAR(10) NOT NULL,
            translation TEXT,
            pronunciation VARCHAR(255),
            part_of_speech VARCHAR(50),
            gender VARCHAR(10),
            example_sentence TEXT,
            example_translation TEXT,
            synonyms TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create level_runs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS level_runs (
            id SERIAL PRIMARY KEY,
            level INTEGER NOT NULL,
            target_language VARCHAR(10) NOT NULL,
            native_language VARCHAR(10) NOT NULL,
            cefr_level VARCHAR(10) NOT NULL,
            topic VARCHAR(100) NOT NULL,
            words TEXT NOT NULL,
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
    
    print("✅ PostgreSQL tables created successfully")

def migrate_data(sqlite_conn, pg_conn):
    """Migrate data from SQLite to PostgreSQL"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Migrate users
    print("🔄 Migrating users...")
    sqlite_cursor.execute("SELECT * FROM users")
    users = sqlite_cursor.fetchall()
    
    for user in users:
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
    
    print(f"✅ Migrated {len(users)} users")
    
    # Migrate user_sessions
    print("🔄 Migrating user sessions...")
    sqlite_cursor.execute("SELECT * FROM user_sessions")
    sessions = sqlite_cursor.fetchall()
    
    for session in sessions:
        pg_cursor.execute("""
            INSERT INTO user_sessions (id, user_id, session_token, created_at, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                session_token = EXCLUDED.session_token,
                expires_at = EXCLUDED.expires_at
        """, (
            session['id'], session['user_id'], session['session_token'],
            session['created_at'], session['expires_at']
        ))
    
    print(f"✅ Migrated {len(sessions)} sessions")
    
    # Migrate user_progress
    print("🔄 Migrating user progress...")
    sqlite_cursor.execute("SELECT * FROM user_progress")
    progress = sqlite_cursor.fetchall()
    
    for prog in progress:
        pg_cursor.execute("""
            INSERT INTO user_progress (id, user_id, language, native_language, level, status, score, completed_at, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, language, native_language, level) DO UPDATE SET
                status = EXCLUDED.status,
                score = EXCLUDED.score,
                completed_at = EXCLUDED.completed_at,
                updated_at = EXCLUDED.updated_at
        """, (
            prog['id'], prog['user_id'], prog['language'], prog['native_language'],
            prog['level'], prog['status'], prog['score'], prog['completed_at'],
            prog['created_at'], prog['updated_at']
        ))
    
    print(f"✅ Migrated {len(progress)} progress records")
    
    # Migrate words
    print("🔄 Migrating words...")
    sqlite_cursor.execute("SELECT * FROM words")
    words = sqlite_cursor.fetchall()
    
    for word in words:
        pg_cursor.execute("""
            INSERT INTO words (id, word, language, translation, pronunciation, part_of_speech, gender, example_sentence, example_translation, synonyms, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                word = EXCLUDED.word,
                translation = EXCLUDED.translation,
                pronunciation = EXCLUDED.pronunciation,
                part_of_speech = EXCLUDED.part_of_speech,
                gender = EXCLUDED.gender,
                example_sentence = EXCLUDED.example_sentence,
                example_translation = EXCLUDED.example_translation,
                synonyms = EXCLUDED.synonyms,
                updated_at = EXCLUDED.updated_at
        """, (
            word['id'], word['word'], word['language'], word['translation'],
            word['pronunciation'], word['part_of_speech'], word['gender'],
            word['example_sentence'], word['example_translation'], word['synonyms'],
            word['created_at'], word['updated_at']
        ))
    
    print(f"✅ Migrated {len(words)} words")
    
    # Update sequences
    print("🔄 Updating PostgreSQL sequences...")
    pg_cursor.execute("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))")
    pg_cursor.execute("SELECT setval('user_sessions_id_seq', (SELECT MAX(id) FROM user_sessions))")
    pg_cursor.execute("SELECT setval('user_progress_id_seq', (SELECT MAX(id) FROM user_progress))")
    pg_cursor.execute("SELECT setval('words_id_seq', (SELECT MAX(id) FROM words))")
    
    print("✅ Migration completed successfully!")

def main():
    """Main migration function"""
    print("🚀 Starting SQLite to PostgreSQL migration...")
    
    # Check if we're in production
    if not os.getenv('DATABASE_URL'):
        print("❌ This script should be run in production with DATABASE_URL set")
        return
    
    # Get connections
    sqlite_conn = get_sqlite_connection()
    if not sqlite_conn:
        return
    
    pg_conn = get_postgresql_connection()
    if not pg_conn:
        sqlite_conn.close()
        return
    
    try:
        # Create tables
        create_postgresql_tables(pg_conn)
        
        # Migrate data
        migrate_data(sqlite_conn, pg_conn)
        
        print("🎉 Migration completed successfully!")
        print("📝 Next steps:")
        print("1. Update your app to use PostgreSQL")
        print("2. Test the application")
        print("3. Remove SQLite dependency")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    main()
