#!/usr/bin/env python3
"""
Import words from JSON level files into local SQLite database
This prepares the local database for migration to Railway
"""

import os
import json
import sqlite3
from datetime import datetime, UTC
from typing import List, Dict, Set

def get_db_connection():
    """Get SQLite database connection"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'polo.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def extract_words_from_level(level_file: str) -> List[str]:
    """Extract unique words from a level JSON file"""
    try:
        with open(level_file, 'r', encoding='utf-8') as f:
            level_data = json.load(f)
        
        words = set()
        
        # Extract words from sentences
        if 'sentences' in level_data:
            for sentence in level_data['sentences']:
                if 'words' in sentence:
                    words.update(sentence['words'])
        
        # Extract words from word lists
        if 'words' in level_data:
            words.update(level_data['words'])
        
        return list(words)
    except Exception as e:
        print(f"Error reading {level_file}: {e}")
        return []

def import_words_for_language(language: str, conn: sqlite3.Connection) -> int:
    """Import all words for a specific language"""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', language)
    
    if not os.path.exists(data_dir):
        print(f"Language directory not found: {data_dir}")
        return 0
    
    all_words = set()
    
    # Process all level files
    levels_dir = os.path.join(data_dir, 'levels')
    if os.path.exists(levels_dir):
        for level_file in os.listdir(levels_dir):
            if level_file.endswith('.json'):
                level_path = os.path.join(levels_dir, level_file)
                words = extract_words_from_level(level_path)
                all_words.update(words)
                print(f"Level {level_file}: {len(words)} words")
    
    # Import words into database
    imported_count = 0
    cursor = conn.cursor()
    
    for word in all_words:
        if word and word.strip():
            try:
                # Check if word already exists
                cursor.execute(
                    "SELECT id FROM words WHERE word = ? AND language = ?",
                    (word.strip(), language)
                )
                
                if not cursor.fetchone():
                    # Insert new word
                    cursor.execute("""
                        INSERT INTO words (word, language, native_language, translation, pos, ipa, 
                                         example, example_native, synonyms, collocations, gender, 
                                         familiarity, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        word.strip(),
                        language,
                        'en',  # Default native language
                        '',    # Will be enriched later
                        '',    # Will be enriched later
                        '',    # Will be enriched later
                        '',    # Will be enriched later
                        '',    # Will be enriched later
                        '[]',  # Empty JSON array
                        '[]',  # Empty JSON array
                        'none',
                        0,     # Default familiarity
                        datetime.now(UTC).isoformat(),
                        datetime.now(UTC).isoformat()
                    ))
                    imported_count += 1
            except Exception as e:
                print(f"Error importing word '{word}': {e}")
    
    conn.commit()
    return imported_count

def create_test_user_with_data(conn: sqlite3.Connection) -> int:
    """Create a test user with sample progress data"""
    cursor = conn.cursor()
    
    # Create test user
    test_user_id = None
    try:
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, native_language, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            'test_user',
            'test@example.com',
            'hashed_password',  # In real app, this would be properly hashed
            'en',
            datetime.now(UTC).isoformat(),
            datetime.now(UTC).isoformat()
        ))
        test_user_id = cursor.lastrowid
        print(f"Created test user with ID: {test_user_id}")
    except Exception as e:
        print(f"Error creating test user: {e}")
        return 0
    
    # Create sample progress data
    progress_count = 0
    languages = ['de', 'fr', 'es', 'it', 'pt', 'ru', 'tr', 'pl', 'ka', 'ar', 'hi', 'zh', 'ja', 'ko']
    
    for language in languages:
        for level in range(1, 11):  # First 10 levels
            try:
                cursor.execute("""
                    INSERT INTO user_progress (user_id, language, level, status, score, 
                                             completed_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    test_user_id,
                    language,
                    level,
                    'completed' if level <= 5 else 'in_progress',
                    85 + (level * 2),  # Sample scores
                    datetime.now(UTC).isoformat() if level <= 5 else None,
                    datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat()
                ))
                progress_count += 1
            except Exception as e:
                print(f"Error creating progress for {language} level {level}: {e}")
    
    conn.commit()
    return progress_count

def main():
    """Main function to import words and create test data"""
    print("🚀 Starting word import and test data creation...")
    
    conn = get_db_connection()
    
    try:
        # Get all available languages
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        languages = [d for d in os.listdir(data_dir) 
                    if os.path.isdir(os.path.join(data_dir, d)) and d != 'users']
        
        print(f"Found {len(languages)} languages: {', '.join(languages)}")
        
        total_imported = 0
        
        # Import words for each language
        for language in languages:
            print(f"\n📚 Importing words for {language}...")
            imported = import_words_for_language(language, conn)
            total_imported += imported
            print(f"✅ Imported {imported} words for {language}")
        
        print(f"\n📊 Total words imported: {total_imported}")
        
        # Create test user with progress data
        print(f"\n👤 Creating test user with progress data...")
        progress_count = create_test_user_with_data(conn)
        print(f"✅ Created test user with {progress_count} progress entries")
        
        # Show database statistics
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM words")
        word_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_progress")
        progress_count = cursor.fetchone()[0]
        
        print(f"\n📈 Database Statistics:")
        print(f"   Words: {word_count}")
        print(f"   Users: {user_count}")
        print(f"   Progress entries: {progress_count}")
        
        print(f"\n✅ Import completed successfully!")
        print(f"   Ready for Railway migration")
        
    except Exception as e:
        print(f"❌ Error during import: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()

