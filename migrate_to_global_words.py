#!/usr/bin/env python3
"""
Migration script to create global_words table and migrate existing data
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

def get_database_connection():
    """Get PostgreSQL database connection"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise Exception('DATABASE_URL environment variable not set')
    
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def create_global_words_table():
    """Create the global_words table"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        
        print("Creating global_words table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_words (
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
        print("Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_global_words_word_hash ON global_words(word_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_global_words_word_lang ON global_words(word, target_language);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_global_words_native_lang ON global_words(native_language);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_global_words_target_lang ON global_words(target_language);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_global_words_created_at ON global_words(created_at);")
        
        # Create trigger function and trigger
        print("Creating trigger function...")
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
            DROP TRIGGER IF EXISTS trigger_update_global_words_updated_at ON global_words;
            CREATE TRIGGER trigger_update_global_words_updated_at
                BEFORE UPDATE ON global_words
                FOR EACH ROW
                EXECUTE FUNCTION update_global_words_updated_at();
        """)
        
        conn.commit()
        print("✅ global_words table created successfully")
        
    except Exception as e:
        print(f"❌ Error creating global_words table: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def migrate_existing_words():
    """Migrate existing words from old tables to global_words"""
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        
        # Check if old words table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'words'
            );
        """)
        old_table_exists = cursor.fetchone()[0]
        
        if not old_table_exists:
            print("ℹ️ No old words table found - skipping migration")
            return
        
        print("Migrating existing words to global_words table...")
        
        # Get all words from old table
        cursor.execute("SELECT * FROM words")
        old_words = cursor.fetchall()
        
        migrated_count = 0
        skipped_count = 0
        
        for word_row in old_words:
            try:
                word_data = dict(word_row)
                
                # Generate word hash
                import hashlib
                word = word_data['word'].lower().strip()
                target_language = word_data.get('language', 'en')
                native_language = 'en'  # Default native language for migration
                
                content = f"{word}|{target_language}|{native_language}"
                word_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                
                # Prepare data for insertion
                insert_data = {
                    'word': word,
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
                    'conj': word_data.get('conj'),
                    'comp': word_data.get('comp'),
                    'synonyms': word_data.get('synonyms'),
                    'collocations': word_data.get('collocations'),
                    'cefr': word_data.get('cefr'),
                    'freq_rank': word_data.get('freq_rank'),
                    'tags': word_data.get('tags'),
                    'note': word_data.get('note'),
                    'word_hash': word_hash
                }
                
                # Insert or update in global_words table
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
                
                migrated_count += 1
                
            except Exception as e:
                print(f"⚠️ Error migrating word {word_data.get('word', 'unknown')}: {e}")
                skipped_count += 1
                continue
        
        conn.commit()
        print(f"✅ Migration completed: {migrated_count} words migrated, {skipped_count} skipped")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def main():
    """Main migration function"""
    print("🚀 Starting migration to global_words table...")
    
    try:
        # Step 1: Create the table
        create_global_words_table()
        
        # Step 2: Migrate existing data
        migrate_existing_words()
        
        print("🎉 Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
