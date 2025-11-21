#!/usr/bin/env python3
"""
Cleanup script for word duplicates in PostgreSQL words table.

This script:
1. Identifies duplicate words (same normalized word, language, native_language)
2. Updates user_word_familiarity to point to canonical entry
3. Merges duplicate user_word_familiarity entries
4. Removes duplicate word entries

Can be run as standalone script or imported as module.
"""

import os
import sys
from typing import Dict, List, Tuple, Any
from collections import defaultdict

# Add parent directory to path to import server modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.db import normalize_word
from server.db_config import get_database_config, get_db_connection, execute_query


def find_duplicates(conn) -> List[Dict[str, Any]]:
    """
    Find duplicate words by normalizing all words and grouping by normalized form.
    Returns list of duplicate groups with canonical entry identified.
    """
    print("🔍 Scanning for duplicate words...")
    
    # Get all words
    result = execute_query(conn, """
        SELECT id, word, language, native_language, created_at, updated_at,
               translation, example, lemma, pos, ipa, audio_url
        FROM words
        ORDER BY created_at
    """)
    
    all_words = result.fetchall()
    print(f"📊 Found {len(all_words)} total words in database")
    
    # Group by normalized word + language + native_language
    groups: Dict[Tuple[str, str, str], List[Dict]] = defaultdict(list)
    
    for word_row in all_words:
        word = word_row['word']
        language = word_row['language'] or ''
        native_language = word_row['native_language'] or ''
        
        normalized = normalize_word(word)
        if not normalized:
            continue
        
        key = (normalized, language, native_language)
        groups[key].append(word_row)
    
    # Find groups with duplicates
    duplicates = []
    for key, word_list in groups.items():
        if len(word_list) > 1:
            # Identify canonical entry (oldest or most complete)
            canonical = select_canonical_entry(word_list)
            duplicates.append({
                'normalized_word': key[0],
                'language': key[1],
                'native_language': key[2],
                'entries': word_list,
                'canonical_id': canonical['id'],
                'canonical_word': canonical['word']
            })
    
    print(f"🔍 Found {len(duplicates)} duplicate groups")
    return duplicates


def select_canonical_entry(entries: List[Dict]) -> Dict:
    """
    Select canonical entry from duplicate group.
    Prefers entry with:
    1. Oldest created_at
    2. Most complete data (non-null fields)
    """
    if not entries:
        return None
    
    # Sort by created_at (oldest first)
    sorted_entries = sorted(entries, key=lambda x: x.get('created_at', ''))
    
    # Score entries by completeness
    def completeness_score(entry):
        score = 0
        if entry.get('translation'):
            score += 1
        if entry.get('example'):
            score += 1
        if entry.get('lemma'):
            score += 1
        if entry.get('pos'):
            score += 1
        if entry.get('ipa'):
            score += 1
        if entry.get('audio_url'):
            score += 1
        return score
    
    # Find entry with highest completeness among oldest entries
    oldest_entries = [e for e in sorted_entries if e.get('created_at') == sorted_entries[0].get('created_at')]
    canonical = max(oldest_entries, key=completeness_score)
    
    return canonical


def update_user_word_familiarity(conn, duplicate_groups: List[Dict]) -> Dict[str, int]:
    """
    Update user_word_familiarity to point to canonical entries.
    Also merges duplicate entries for same user.
    Returns statistics.
    """
    stats = {
        'updated_references': 0,
        'merged_entries': 0,
        'errors': 0
    }
    
    print("🔄 Updating user_word_familiarity references...")
    
    for group in duplicate_groups:
        canonical_id = group['canonical_id']
        duplicate_ids = [e['id'] for e in group['entries'] if e['id'] != canonical_id]
        
        if not duplicate_ids:
            continue
        
        for dup_id in duplicate_ids:
            try:
                # First, check if there are duplicate user_word_familiarity entries
                # (same user, different word_ids pointing to duplicates)
                result = execute_query(conn, """
                    SELECT u1.user_id, u1.word_id as canonical_word_id, u2.word_id as dup_word_id,
                           u1.familiarity as fam1, u2.familiarity as fam2,
                           u1.seen_count as seen1, u2.seen_count as seen2,
                           u1.correct_count as corr1, u2.correct_count as corr2
                    FROM user_word_familiarity u1
                    JOIN user_word_familiarity u2 ON u1.user_id = u2.user_id
                    WHERE u1.word_id = %s AND u2.word_id = %s
                """, (canonical_id, dup_id))
                
                merge_candidates = result.fetchall()
                
                # Merge duplicate entries for same user
                for merge_cand in merge_candidates:
                    user_id = merge_cand['user_id']
                    # Update canonical entry with merged values
                    execute_query(conn, """
                        UPDATE user_word_familiarity
                        SET familiarity = GREATEST(%s, %s),
                            seen_count = %s + %s,
                            correct_count = %s + %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND word_id = %s
                    """, (
                        merge_cand['fam1'], merge_cand['fam2'],
                        merge_cand['seen1'], merge_cand['seen2'],
                        merge_cand['corr1'], merge_cand['corr2'],
                        user_id, canonical_id
                    ))
                    
                    # Delete duplicate entry
                    execute_query(conn, """
                        DELETE FROM user_word_familiarity
                        WHERE user_id = %s AND word_id = %s
                    """, (user_id, dup_id))
                    
                    stats['merged_entries'] += 1
                
                # Update all remaining references to point to canonical
                result = execute_query(conn, """
                    UPDATE user_word_familiarity
                    SET word_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE word_id = %s
                """, (canonical_id, dup_id))
                
                updated_count = result.rowcount if hasattr(result, 'rowcount') else 0
                stats['updated_references'] += updated_count
                
            except Exception as e:
                print(f"❌ Error updating references for word_id {dup_id}: {e}")
                stats['errors'] += 1
    
    print(f"✅ Updated {stats['updated_references']} references, merged {stats['merged_entries']} duplicate entries")
    return stats


def remove_duplicates(conn, duplicate_groups: List[Dict]) -> int:
    """
    Remove duplicate word entries, keeping only canonical ones.
    Returns number of deleted entries.
    """
    print("🗑️  Removing duplicate word entries...")
    
    deleted_count = 0
    
    for group in duplicate_groups:
        canonical_id = group['canonical_id']
        duplicate_ids = [e['id'] for e in group['entries'] if e['id'] != canonical_id]
        
        for dup_id in duplicate_ids:
            try:
                # Verify no references remain (should be updated already)
                result = execute_query(conn, """
                    SELECT COUNT(*) as count
                    FROM user_word_familiarity
                    WHERE word_id = %s
                """, (dup_id,))
                
                ref_count = result.fetchone()['count']
                
                if ref_count > 0:
                    print(f"⚠️  Warning: word_id {dup_id} still has {ref_count} references, skipping deletion")
                    continue
                
                # Delete duplicate entry
                execute_query(conn, """
                    DELETE FROM words
                    WHERE id = %s
                """, (dup_id,))
                
                deleted_count += 1
                
            except Exception as e:
                print(f"❌ Error deleting word_id {dup_id}: {e}")
    
    print(f"✅ Deleted {deleted_count} duplicate word entries")
    return deleted_count


def run_cleanup(dry_run: bool = False) -> Dict[str, Any]:
    """
    Run complete cleanup process.
    Returns statistics dictionary.
    """
    config = get_database_config()
    if config['type'] != 'postgresql':
        print("❌ This script only works with PostgreSQL")
        return {'error': 'Only PostgreSQL supported'}
    
    conn = get_db_connection()
    
    try:
        # Find duplicates
        duplicate_groups = find_duplicates(conn)
        
        if not duplicate_groups:
            print("✅ No duplicates found!")
            return {
                'duplicates_found': 0,
                'updated_references': 0,
                'merged_entries': 0,
                'deleted_entries': 0
            }
        
        # Print summary
        total_duplicates = sum(len(g['entries']) - 1 for g in duplicate_groups)
        print(f"\n📋 Summary:")
        print(f"   - {len(duplicate_groups)} duplicate groups")
        print(f"   - {total_duplicates} duplicate entries to remove")
        
        if dry_run:
            print("\n🔍 DRY RUN - No changes will be made")
            return {
                'dry_run': True,
                'duplicates_found': len(duplicate_groups),
                'total_duplicate_entries': total_duplicates
            }
        
        # Update user_word_familiarity
        # PostgreSQL autocommit is off by default, so we're already in a transaction
        try:
            familiarity_stats = update_user_word_familiarity(conn, duplicate_groups)
            
            # Remove duplicates
            deleted_count = remove_duplicates(conn, duplicate_groups)
            
            conn.commit()
            print("\n✅ Cleanup completed successfully!")
            
            return {
                'duplicates_found': len(duplicate_groups),
                'total_duplicate_entries': total_duplicates,
                'updated_references': familiarity_stats['updated_references'],
                'merged_entries': familiarity_stats['merged_entries'],
                'deleted_entries': deleted_count,
                'errors': familiarity_stats['errors']
            }
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error during cleanup, rolling back: {e}")
            raise
            
    finally:
        conn.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Cleanup word duplicates in PostgreSQL')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()
    
    try:
        stats = run_cleanup(dry_run=args.dry_run)
        print("\n📊 Final Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

