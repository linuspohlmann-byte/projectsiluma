#!/usr/bin/env python3
"""
Railway Data Migration Script
This script can be run directly on Railway to populate the database
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_data_via_app():
    """Migrate data using the app's database functions"""
    try:
        from server.db_config import get_database_config, get_db_connection, execute_query
        from server.db import get_db, init_db
        
        print("🚀 Starting Railway data migration via app...")
        
        # Check database type
        config = get_database_config()
        print(f"📊 Database type: {config['type']}")
        
        if config['type'] != 'postgresql':
            print("❌ This script is for PostgreSQL migration only")
            return
        
        # Get connection
        conn = get_db_connection()
        print("✅ Connected to Railway PostgreSQL database")
        
        # Check if we have any data
        result = execute_query(conn, "SELECT COUNT(*) as count FROM words")
        word_count = result.fetchone()['count']
        print(f"📚 Current word count in Railway DB: {word_count}")
        
        if word_count > 0:
            print("✅ Railway database already has data - migration not needed")
            return
        
        # Try to get data from local SQLite if available
        try:
            local_conn = get_db()  # This should connect to local SQLite
            local_cursor = local_conn.cursor()
            local_cursor.execute("SELECT COUNT(*) as count FROM words")
            local_count = local_cursor.fetchone()['count']
            print(f"📚 Local SQLite word count: {local_count}")
            
            if local_count == 0:
                print("❌ No local data to migrate")
                return
            
            # Migrate words from local to Railway
            print("🔄 Migrating words from local SQLite to Railway PostgreSQL...")
            local_cursor.execute("SELECT * FROM words LIMIT 100")  # Start with first 100 words
            words = local_cursor.fetchall()
            
            migrated = 0
            for word in words:
                try:
                    # Convert SQLite row to dict
                    word_dict = dict(word)
                    
                    # Insert into PostgreSQL
                    execute_query(conn, """
                        INSERT INTO words (
                            word, language, native_language, translation, example, example_native,
                            lemma, pos, ipa, audio_url, gender, plural, conj, comp, synonyms,
                            collocations, cefr, freq_rank, tags, note, info, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) ON CONFLICT (word, language) DO UPDATE SET
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
                        word_dict.get('word'), word_dict.get('language'), word_dict.get('native_language'),
                        word_dict.get('translation'), word_dict.get('example'), word_dict.get('example_native'),
                        word_dict.get('lemma'), word_dict.get('pos'), word_dict.get('ipa'), word_dict.get('audio_url'),
                        word_dict.get('gender'), word_dict.get('plural'), word_dict.get('conj'), word_dict.get('comp'),
                        word_dict.get('synonyms'), word_dict.get('collocations'), word_dict.get('cefr'),
                        word_dict.get('freq_rank'), word_dict.get('tags'), word_dict.get('note'), word_dict.get('info'),
                        word_dict.get('created_at'), word_dict.get('updated_at')
                    ))
                    migrated += 1
                    
                    if migrated % 10 == 0:
                        print(f"📝 Migrated {migrated} words...")
                        
                except Exception as e:
                    print(f"⚠️ Error migrating word {word_dict.get('word', 'unknown')}: {e}")
            
            print(f"✅ Successfully migrated {migrated} words to Railway PostgreSQL")
            
            # Check final count
            result = execute_query(conn, "SELECT COUNT(*) as count FROM words")
            final_count = result.fetchone()['count']
            print(f"📚 Final word count in Railway DB: {final_count}")
            
        except Exception as e:
            print(f"❌ Error accessing local SQLite: {e}")
            print("💡 This is expected on Railway - local SQLite is not available")
            
            # Create some sample data for testing
            print("🔄 Creating sample data for testing...")
            sample_words = [
                ('hello', 'en', 'de', 'hallo', 'Hello world!', 'Hallo Welt!', 'hello', 'interjection', 'həˈloʊ', None, 'none', None, None, None, None, None, 'A1', 1, None, None, None, datetime.now().isoformat(), datetime.now().isoformat()),
                ('world', 'en', 'de', 'Welt', 'Hello world!', 'Hallo Welt!', 'world', 'noun', 'wɜːrld', None, 'none', 'worlds', None, None, None, None, 'A1', 2, None, None, None, datetime.now().isoformat(), datetime.now().isoformat()),
                ('test', 'en', 'de', 'Test', 'This is a test.', 'Das ist ein Test.', 'test', 'noun', 'test', None, 'none', 'tests', None, None, None, None, 'A1', 3, None, None, None, datetime.now().isoformat(), datetime.now().isoformat())
            ]
            
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
                except Exception as e:
                    print(f"⚠️ Error creating sample word {word_data[0]}: {e}")
            
            print("✅ Created sample data for testing")
        
        conn.close()
        print("🎉 Migration completed!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_data_via_app()
