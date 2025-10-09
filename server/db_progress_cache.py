#!/usr/bin/env python3
"""
Custom Level Progress Cache System
Optimized table for caching familiarity data per level per user
"""

from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
from .db_config import get_database_config, get_db_connection, execute_query

def create_custom_level_progress_table():
    """Create the custom_level_progress table for caching familiarity data"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            # PostgreSQL syntax - use cursor directly for better error handling
            cursor = conn.cursor()
            
            # Create table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_level_progress (
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
                    score REAL,
                    status VARCHAR(50) DEFAULT 'not_started',
                    completed_at TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                    UNIQUE(user_id, group_id, level_number)
                );
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user_group 
                ON custom_level_progress(user_id, group_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_custom_level_progress_last_updated 
                ON custom_level_progress(last_updated);
            """)
            
            # Commit the transaction
            conn.commit()
            print("✅ Custom level progress table created successfully in PostgreSQL")
            
        else:
            # SQLite syntax
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_level_progress (
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
                    score REAL,
                    status TEXT DEFAULT 'not_started',
                    completed_at TEXT,
                    last_updated TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                    UNIQUE(user_id, group_id, level_number)
                );
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user_group 
                ON custom_level_progress(user_id, group_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_custom_level_progress_last_updated 
                ON custom_level_progress(last_updated);
            """)
            
            conn.commit()
            
        print("✅ Custom level progress table created successfully")
        
    except Exception as e:
        print(f"❌ Error creating custom level progress table: {e}")
        import traceback
        traceback.print_exc()
        # Try to rollback if possible
        try:
            conn.rollback()
        except:
            pass
    finally:
        conn.close()

def update_custom_level_progress(user_id: int, group_id: int, level_number: int, 
                                familiarity_counts: Dict[int, int], score: float = None, 
                                status: str = None, completed_at: str = None) -> bool:
    """Update or insert custom level progress data"""
    try:
        config = get_database_config()
        conn = get_db_connection()
        
        # Calculate total words
        total_words = sum(familiarity_counts.values())
        
        now = datetime.now(UTC).isoformat()
        
        try:
            if config['type'] == 'postgresql':
                print(f"📝 cache: upsert row user={user_id} group={group_id} level={level_number} counts={familiarity_counts} score={score} status={status}")
                execute_query(conn, """
                    INSERT INTO custom_level_progress 
                    (user_id, group_id, level_number, total_words, 
                     familiarity_0, familiarity_1, familiarity_2, 
                     familiarity_3, familiarity_4, familiarity_5,
                     score, status, completed_at,
                     last_updated, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, group_id, level_number)
                    DO UPDATE SET
                        total_words = EXCLUDED.total_words,
                        familiarity_0 = EXCLUDED.familiarity_0,
                        familiarity_1 = EXCLUDED.familiarity_1,
                        familiarity_2 = EXCLUDED.familiarity_2,
                        familiarity_3 = EXCLUDED.familiarity_3,
                        familiarity_4 = EXCLUDED.familiarity_4,
                        familiarity_5 = EXCLUDED.familiarity_5,
                        score = COALESCE(EXCLUDED.score, custom_level_progress.score),
                        status = COALESCE(EXCLUDED.status, custom_level_progress.status),
                        completed_at = COALESCE(EXCLUDED.completed_at, custom_level_progress.completed_at),
                        last_updated = EXCLUDED.last_updated
                """, (
                    user_id, group_id, level_number, total_words,
                    familiarity_counts.get(0, 0),
                    familiarity_counts.get(1, 0),
                    familiarity_counts.get(2, 0),
                    familiarity_counts.get(3, 0),
                    familiarity_counts.get(4, 0),
                    familiarity_counts.get(5, 0),
                    score, status, completed_at,
                    now, now
                ))
                conn.commit()
            else:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO custom_level_progress 
                    (user_id, group_id, level_number, total_words, 
                     familiarity_0, familiarity_1, familiarity_2, 
                     familiarity_3, familiarity_4, familiarity_5,
                     score, status, completed_at,
                     last_updated, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, group_id, level_number, total_words,
                    familiarity_counts.get(0, 0),
                    familiarity_counts.get(1, 0),
                    familiarity_counts.get(2, 0),
                    familiarity_counts.get(3, 0),
                    familiarity_counts.get(4, 0),
                    familiarity_counts.get(5, 0),
                    score, status, completed_at,
                    now, now
                ))
                conn.commit()
            
            print(f"✅ Updated custom level progress: user={user_id}, group={group_id}, level={level_number}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating custom level progress: {e}")
            return False
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error in update_custom_level_progress: {e}")
        return False

def get_custom_level_progress(user_id: int, group_id: int, level_number: int) -> Optional[Dict[str, Any]]:
    """Get cached custom level progress data"""
    try:
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config['type'] == 'postgresql':
                result = execute_query(conn, """
                    SELECT total_words, familiarity_0, familiarity_1, familiarity_2,
                           familiarity_3, familiarity_4, familiarity_5, 
                           score, status, completed_at, last_updated
                    FROM custom_level_progress
                    WHERE user_id = %s AND group_id = %s AND level_number = %s
                """, (user_id, group_id, level_number))
                
                row = result.fetchone()
                if row:
                    return {
                        'total_words': row['total_words'],
                        'fam_counts': {
                            0: row['familiarity_0'],
                            1: row['familiarity_1'],
                            2: row['familiarity_2'],
                            3: row['familiarity_3'],
                            4: row['familiarity_4'],
                            5: row['familiarity_5']
                        },
                        'score': row['score'],
                        'status': row['status'],
                        'completed_at': row['completed_at'],
                        'last_updated': row['last_updated']
                    }
            else:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT total_words, familiarity_0, familiarity_1, familiarity_2,
                           familiarity_3, familiarity_4, familiarity_5,
                           score, status, completed_at, last_updated
                    FROM custom_level_progress
                    WHERE user_id = ? AND group_id = ? AND level_number = ?
                """, (user_id, group_id, level_number))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'total_words': row[0],
                        'fam_counts': {
                            0: row[1],
                            1: row[2],
                            2: row[3],
                            3: row[4],
                            4: row[5],
                            5: row[6]
                        },
                        'score': row[7],
                        'status': row[8],
                        'completed_at': row[9],
                        'last_updated': row[10]
                    }
            
            return None
            
        except Exception as e:
            print(f"❌ Error getting custom level progress: {e}")
            return None
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error in get_custom_level_progress: {e}")
        return None

def get_custom_level_group_progress(user_id: int, group_id: int) -> Dict[int, Dict[str, Any]]:
    """Get cached progress data for all levels in a group"""
    try:
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config['type'] == 'postgresql':
                result = execute_query(conn, """
                    SELECT level_number, total_words, familiarity_0, familiarity_1, familiarity_2,
                           familiarity_3, familiarity_4, familiarity_5,
                           score, status, completed_at, last_updated
                    FROM custom_level_progress
                    WHERE user_id = %s AND group_id = %s
                    ORDER BY level_number
                """, (user_id, group_id))
                
                progress_data = {}
                for row in result.fetchall():
                    progress_data[row['level_number']] = {
                        'total_words': row['total_words'],
                        'fam_counts': {
                            0: row['familiarity_0'],
                            1: row['familiarity_1'],
                            2: row['familiarity_2'],
                            3: row['familiarity_3'],
                            4: row['familiarity_4'],
                            5: row['familiarity_5']
                        },
                        'score': row['score'],
                        'status': row['status'],
                        'completed_at': row['completed_at'],
                        'last_updated': row['last_updated']
                    }
            else:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT level_number, total_words, familiarity_0, familiarity_1, familiarity_2,
                           familiarity_3, familiarity_4, familiarity_5,
                           score, status, completed_at, last_updated
                    FROM custom_level_progress
                    WHERE user_id = ? AND group_id = ?
                    ORDER BY level_number
                """, (user_id, group_id))
                
                progress_data = {}
                for row in cursor.fetchall():
                    progress_data[row[0]] = {
                        'total_words': row[1],
                        'fam_counts': {
                            0: row[2],
                            1: row[3],
                            2: row[4],
                            3: row[5],
                            4: row[6],
                            5: row[7]
                        },
                        'score': row[8],
                        'status': row[9],
                        'completed_at': row[10],
                        'last_updated': row[11]
                    }
            
            return progress_data
            
        except Exception as e:
            print(f"❌ Error getting custom level group progress: {e}")
            return {}
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error in get_custom_level_group_progress: {e}")
        return {}

def calculate_familiarity_counts_from_user_words(user_id: int, group_id: int, level_number: int) -> Dict[int, int]:
    """Calculate familiarity counts from user_word_familiarity table"""
    try:
        from .services.custom_levels import get_custom_levels_for_group
        
        # Get level content to extract words
        levels = get_custom_levels_for_group(group_id)
        print(f"🧮 cache: calculating counts for user={user_id} group={group_id} level={level_number}, levels_found={len(levels) if levels else 0}")
        level = next((l for l in levels if l['level_number'] == level_number), None)
        
        if not level or not level.get('content', {}).get('items'):
            print(f"🧮 cache: no level content found for group={group_id} level={level_number}")
            return {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        
        # Extract unique words from level content
        import re
        all_words = set()
        for item in level['content']['items']:
            words = item.get('words', [])
            for word in words:
                if word and word.strip():
                    # Remove trailing punctuation before adding (KEEP original case!)
                    clean_word = re.sub(r'[.!?,;:—–-]+$', '', word.strip())
                    if clean_word:
                        all_words.add(clean_word)
        
        print(f"🧮 cache: extracted {len(all_words)} unique words for group={group_id} level={level_number}")
        print(f"🧮 cache: sample words: {list(all_words)[:10]}")
        
        if not all_words:
            print(f"🧮 cache: no words extracted for group={group_id} level={level_number}")
            return {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        
        # Get familiarity data from user_word_familiarity table
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            familiarity_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            
            if config['type'] == 'postgresql':
                # Get word IDs for the words in this level
                words_list = list(all_words)
                placeholders = ','.join(['%s'] * len(words_list))
                
                print(f"🔍 cache: querying PostgreSQL for {len(words_list)} words, user={user_id}")
                
                result = execute_query(conn, f"""
                    SELECT w.word, uwf.familiarity
                    FROM words w
                    JOIN user_word_familiarity uwf ON w.id = uwf.word_id
                    WHERE uwf.user_id = %s AND w.word IN ({placeholders})
                """, [user_id] + words_list)
                
                found_word_list = []
                for row in result.fetchall():
                    familiarity = max(0, min(5, row['familiarity'] or 0))
                    familiarity_counts[familiarity] += 1
                    found_word_list.append(row['word'])
                
                print(f"🔍 cache: found {len(found_word_list)} words in user_word_familiarity table")
                print(f"🔍 cache: sample found words: {found_word_list[:5]}")
                
                # Count words not found in user_word_familiarity as unknown (0)
                found_words = sum(familiarity_counts.values())
                missing_words = len(all_words) - found_words
                if missing_words > 0:
                    familiarity_counts[0] += missing_words
                    print(f"🔍 cache: {missing_words} words not found in user_word_familiarity, marking as unknown (0)")
                print(f"🧮 cache: computed counts for group={group_id} level={level_number}: {familiarity_counts}")
                    
            else:
                # SQLite version
                cursor = conn.cursor()
                words_list = list(all_words)
                placeholders = ','.join(['?' for _ in words_list])
                
                cursor.execute(f"""
                    SELECT w.word, uwf.familiarity
                    FROM words w
                    JOIN user_word_familiarity uwf ON w.id = uwf.word_id
                    WHERE uwf.user_id = ? AND w.word IN ({placeholders})
                """, [user_id] + words_list)
                
                for row in cursor.fetchall():
                    familiarity = max(0, min(5, row[1] or 0))
                    familiarity_counts[familiarity] += 1
                
                # Count words not found in user_word_familiarity as unknown (0)
                found_words = sum(familiarity_counts.values())
                missing_words = len(all_words) - found_words
                if missing_words > 0:
                    familiarity_counts[0] += missing_words
            
            return familiarity_counts
            
        except Exception as e:
            print(f"❌ Error calculating familiarity counts: {e}")
            return {0: len(all_words), 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error in calculate_familiarity_counts_from_user_words: {e}")
        return {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

def refresh_custom_level_progress(user_id: int, group_id: int, level_number: int) -> bool:
    """Refresh cached progress data for a specific level"""
    try:
        # Calculate fresh familiarity counts
        familiarity_counts = calculate_familiarity_counts_from_user_words(user_id, group_id, level_number)
        
        # Update cache
        return update_custom_level_progress(user_id, group_id, level_number, familiarity_counts)
        
    except Exception as e:
        print(f"❌ Error refreshing custom level progress: {e}")
        return False

def refresh_custom_level_group_progress(user_id: int, group_id: int) -> bool:
    """Refresh cached progress data for all levels in a group"""
    try:
        from .services.custom_levels import get_custom_levels_for_group
        
        levels = get_custom_levels_for_group(group_id)
        success_count = 0
        
        for level in levels:
            if refresh_custom_level_progress(user_id, group_id, level['level_number']):
                success_count += 1
        
        print(f"✅ Refreshed progress for {success_count}/{len(levels)} levels in group {group_id}")
        return success_count > 0
        
    except Exception as e:
        print(f"❌ Error refreshing custom level group progress: {e}")
        return False

def complete_custom_level(user_id: int, group_id: int, level_number: int, score: float) -> bool:
    """Mark a custom level as completed with a score"""
    try:
        config = get_database_config()
        conn = get_db_connection()
        
        now = datetime.now(UTC).isoformat()
        
        # Normalize score to integer percent (0-100)
        try:
            if score is None:
                int_score = 0
            else:
                # If score looks like fraction 0..1 → convert to percent
                int_score = int(round(float(score) * 100)) if float(score) <= 1.1 else int(round(float(score)))
            int_score = max(0, min(100, int_score))
        except Exception:
            int_score = 0

        # Determine status based on integer percent
        status = 'completed' if int_score >= 60 else 'in_progress'
        
        try:
            if config['type'] == 'postgresql':
                execute_query(conn, """
                    INSERT INTO custom_level_progress 
                    (user_id, group_id, level_number, score, status, completed_at, last_updated, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, group_id, level_number)
                    DO UPDATE SET
                        score = EXCLUDED.score,
                        status = EXCLUDED.status,
                        completed_at = EXCLUDED.completed_at,
                        last_updated = EXCLUDED.last_updated
                """, (user_id, group_id, level_number, int_score, status, now, now, now))
                conn.commit()
            else:
                cursor = conn.cursor()
                # For SQLite, we need to check if row exists first
                cursor.execute("""
                    SELECT id FROM custom_level_progress 
                    WHERE user_id = ? AND group_id = ? AND level_number = ?
                """, (user_id, group_id, level_number))
                
                if cursor.fetchone():
                    # Update existing row
                    cursor.execute("""
                        UPDATE custom_level_progress 
                        SET score = ?, status = ?, completed_at = ?, last_updated = ?
                        WHERE user_id = ? AND group_id = ? AND level_number = ?
                    """, (int_score, status, now, now, user_id, group_id, level_number))
                else:
                    # Insert new row
                    cursor.execute("""
                        INSERT INTO custom_level_progress 
                        (user_id, group_id, level_number, score, status, completed_at, last_updated, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, group_id, level_number, int_score, status, now, now, now))
                
                conn.commit()
            
            print(f"✅ Marked level as completed: user={user_id}, group={group_id}, level={level_number}, score={score}")
            
            # Refresh the familiarity counts for this level
            refresh_custom_level_progress(user_id, group_id, level_number)
            
            return True
            
        except Exception as e:
            print(f"❌ Error completing custom level: {e}")
            return False
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error in complete_custom_level: {e}")
        return False
