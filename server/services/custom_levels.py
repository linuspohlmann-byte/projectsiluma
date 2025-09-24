"""
Custom Level Groups Service
Handles creation and management of user-defined level groups with AI-generated content
"""

import json
import sqlite3
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from server.db import get_db, upsert_word_row
from server.services.llm import llm_generate_sentences, suggest_topic, suggest_level_title, cefr_norm, llm_enrich_word, llm_enrich_words_batch
from server.services.tts import ensure_tts_for_word, ensure_tts_for_sentence, batch_ensure_tts_for_sentences, batch_ensure_tts_for_words

def create_custom_level_group(user_id: int, language: str, native_language: str, 
                            group_name: str, context_description: str, 
                            cefr_level: str = 'A1', num_levels: int = 10) -> Optional[int]:
    """Create a new custom level group"""
    conn = get_db()
    try:
        now = datetime.now(UTC).isoformat()
        cursor = conn.execute('''
            INSERT INTO custom_level_groups 
            (user_id, language, native_language, group_name, context_description, 
             cefr_level, num_levels, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, language, native_language, group_name, context_description, 
              cefr_level, num_levels, now, now))
        
        group_id = cursor.lastrowid
        conn.commit()
        return group_id
    except Exception as e:
        print(f"Error creating custom level group: {e}")
        return None
    finally:
        conn.close()

def generate_custom_levels(group_id: int, language: str, native_language: str, 
                          context_description: str, cefr_level: str, num_levels: int) -> bool:
    """Generate AI-powered levels for a custom level group with full content pre-loading"""
    try:
        print(f"🎯 Starting enhanced level generation for group {group_id} with {num_levels} levels")
        
        # Ultra-fast generation with maximum batch optimization
        print("⚡ Using ultra-fast batch generation...")
        
        # Step 1: Generate topics sequentially for story progression, then titles in parallel
        print("📚 Generating topics sequentially for story progression...")
        topics = []
        titles = []
        
        # Generate topics sequentially to build story progression
        for i in range(1, num_levels + 1):
            # Get previous topics for story context
            previous_topics = [topic for _, topic in topics]
            
            topic = suggest_topic(language, native_language, cefr_level, context_description, i, previous_topics)
            topics.append((i, topic))
            print(f"✅ Generated topic for level {i}: {topic}")
        
        # Generate titles sequentially for story progression
        print("📝 Generating titles sequentially for story progression...")
        
        for i, topic in topics:
            # Get all topics and previous titles for story context in title generation
            all_topics = [t for _, t in topics]
            previous_titles = [t for _, t in titles]
            title = suggest_level_title(language, native_language, topic, i, cefr_level, context_description, all_topics, previous_titles)
            titles.append((i, title))
            print(f"✅ Generated title for level {i}: {title}")
        
        # Sort by level number
        topics.sort(key=lambda x: x[0])
        titles.sort(key=lambda x: x[0])
        
        # Step 2: Generate all sentences in parallel
        print("📝 Generating all sentences in parallel...")
        all_sentences = []
        all_words = set()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            sentence_futures = {}
            
            for level_num, topic in topics:
                future = executor.submit(llm_generate_sentences, language, native_language, 5, topic, cefr_level, f"Level {level_num}")
                sentence_futures[future] = level_num
            
            # Collect sentences and extract words
            for future in as_completed(sentence_futures):
                level_num = sentence_futures[future]
                sentences = future.result()
                if sentences:
                    all_sentences.append((level_num, sentences))
                    print(f"✅ Generated {len(sentences)} sentences for level {level_num}")
                    
                    # Extract words for batch enrichment
                    for sentence_data in sentences:
                        if isinstance(sentence_data, dict):
                            words = sentence_data.get('words', [])
                            for word in words:
                                if word and word.strip():
                                    all_words.add(word.strip().lower())
        
        # Sort sentences by level
        all_sentences.sort(key=lambda x: x[0])
        
        # Step 3: Batch enrich all words at once
        print(f"📚 Batch enriching {len(all_words)} unique words...")
        word_hashes = batch_enrich_words_for_custom_levels(list(all_words), language, native_language, [])
        
        # Step 4: Create and save all levels
        print("💾 Creating all levels...")
        for i, (level_num, sentences) in enumerate(all_sentences):
            level_content = create_level_content(
                level_num, titles[i][1], topics[i][1], 
                sentences, context_description, word_hashes, language, native_language
            )
            
            save_custom_level(group_id, level_num, titles[i][1], topics[i][1], level_content)
            print(f"✅ Saved level {level_num} to database")
        
        print(f"🎉 Ultra-fast generation complete: {num_levels} levels!")
        return True
        
    except Exception as e:
        print(f"Error generating custom levels: {e}")
        return False

def generate_custom_levels_original(group_id: int, language: str, native_language: str, 
                                  context_description: str, cefr_level: str, num_levels: int) -> bool:
    """Original implementation of custom level generation (kept for reference)"""
    try:
        print(f"🎯 Starting original level generation for group {group_id} with {num_levels} levels")
        
        # Generate topics for each level sequentially for story progression
        topics = []
        for i in range(1, num_levels + 1):
            try:
                # Get previous topics for story context
                previous_topics = topics.copy()
                topic = suggest_topic(language, native_language, cefr_level, context_description, i, previous_topics)
                topics.append(topic)
                print(f"✅ Generated topic for level {i}: {topic}")
            except Exception as e:
                print(f"Error generating topic for level {i}: {e}")
                # Fallback topic
                topics.append(f"{context_description} - Level {i}")
        
        # Collect all sentences and words for batch processing
        all_sentences = []
        all_words = set()
        level_data = []
        
        # Generate levels with coherent story-based titles
        for i, topic in enumerate(topics, 1):
            try:
                # Get previous titles for uniqueness
                previous_titles = [t for _, t in titles]
                level_title = suggest_level_title(
                    language, native_language, topic, i, cefr_level, 
                    context_description, topics, previous_titles
                )
                titles.append((i, level_title))
                print(f"✅ Generated title for level {i}: {level_title}")
            except Exception as e:
                print(f"Error generating level title for level {i}: {e}")
                # Fallback title
                level_title = f"{context_description} - Level {i}"
                titles.append((i, level_title))
            
            # Generate sentences for this level
            try:
                sentences = llm_generate_sentences(
                    target_lang=language,
                    native_lang=native_language,
                    n=5,
                    topic=topic,
                    cefr=cefr_level
                )
                print(f"✅ Generated {len(sentences)} sentences for level {i}")
            except Exception as e:
                print(f"Error generating sentences for level {i}: {e}")
                # Fallback sentences
                sentences = [
                    {"sentence": f"Hello, this is level {i} about {topic}.", "translation": f"Hallo, das ist Level {i} über {topic}.", "words": ["hello", "level", "about"]},
                    {"sentence": f"Let's learn about {topic} in {language}.", "translation": f"Lass uns über {topic} in {language} lernen.", "words": ["learn", "about"]},
                    {"sentence": f"This is a practice sentence for {topic}.", "translation": f"Das ist ein Übungssatz für {topic}.", "words": ["practice", "sentence"]},
                    {"sentence": f"Welcome to level {i} of {context_description}.", "translation": f"Willkommen zu Level {i} von {context_description}.", "words": ["welcome", "level"]},
                    {"sentence": f"Keep practicing {topic} to improve your skills.", "translation": f"Übe weiter {topic}, um deine Fähigkeiten zu verbessern.", "words": ["practice", "improve", "skills"]}
                ]
            
            # Store level data for later processing
            level_info = {
                "level_number": i,
                "title": level_title,
                "topic": topic,
                "sentences": sentences
            }
            level_data.append(level_info)
            
            # Collect all sentences and words for batch processing
            for sentence_data in sentences:
                if isinstance(sentence_data, dict):
                    text_target = sentence_data.get('sentence', '')
                    all_sentences.append(text_target)
                    words = sentence_data.get('words', [])
                    for word in words:
                        if word and word.strip():
                            all_words.add(word.strip().lower())
                else:
                    text_target = str(sentence_data)
                    all_sentences.append(text_target)
                    words = text_target.split()
                    for word in words:
                        if word and word.strip():
                            all_words.add(word.strip().lower())
        
        print(f"📊 Collected {len(all_sentences)} sentences and {len(all_words)} unique words for batch processing")
        
        # Batch process all content
        print("🎵 Starting batch audio generation...")
        batch_generate_audio_for_custom_levels(all_sentences, all_words, language, native_language)
        
        print("📚 Starting batch word enrichment...")
        word_hashes = batch_enrich_words_for_custom_levels(list(all_words), language, native_language, all_sentences)
        
        # Now create the actual levels with all enriched content
        print("💾 Creating levels with enriched content...")
        for level_info in level_data:
            i = level_info["level_number"]
            level_title = level_info["title"]
            topic = level_info["topic"]
            sentences = level_info["sentences"]
            
            # Create level content using helper function
            level_content = create_level_content(i, level_title, topic, sentences, context_description, word_hashes, language, native_language)
            
            # Save level to database
            try:
                save_custom_level(group_id, i, level_title, topic, level_content)
                print(f"✅ Saved level {i} to database")
            except Exception as e:
                print(f"Error saving level {i} to database: {e}")
                # Continue with other levels even if one fails
        
        print(f"🎉 Successfully generated {num_levels} levels with full content for group {group_id}")
        return True
    except Exception as e:
        print(f"Error generating custom levels: {e}")
        return False

def save_custom_level(group_id: int, level_number: int, title: str, topic: str, content: Dict[str, Any]) -> bool:
    """Save a custom level to the database"""
    conn = get_db()
    try:
        now = datetime.now(UTC).isoformat()
        conn.execute('''
            INSERT INTO custom_levels 
            (group_id, level_number, title, topic, content, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (group_id, level_number, title, topic, json.dumps(content, ensure_ascii=False), now, now))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving custom level: {e}")
        return False
    finally:
        conn.close()

def get_custom_level_groups(user_id: int, language: str = None, native_language: str = None) -> List[Dict[str, Any]]:
    """Get custom level groups for a user with optional language and native_language filtering"""
    conn = get_db()
    try:
        # Build query based on provided filters
        query = "SELECT * FROM custom_level_groups WHERE user_id = ?"
        params = [user_id]
        
        if language:
            query += " AND language = ?"
            params.append(language)
        
        if native_language:
            query += " AND native_language = ?"
            params.append(native_language)
        
        query += " ORDER BY created_at DESC"
        
        cursor = conn.execute(query, params)
        
        groups = []
        for row in cursor.fetchall():
            groups.append(dict(row))
        
        return groups
    except Exception as e:
        print(f"Error getting custom level groups: {e}")
        return []
    finally:
        conn.close()

def get_custom_level_group(group_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific custom level group"""
    conn = get_db()
    try:
        cursor = conn.execute('''
            SELECT * FROM custom_level_groups 
            WHERE id = ? AND user_id = ?
        ''', (group_id, user_id))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"Error getting custom level group: {e}")
        return None
    finally:
        conn.close()

def get_custom_level(group_id: int, level_number: int, user_id: int = None) -> Optional[Dict[str, Any]]:
    """Get a specific custom level with optimized word hash handling"""
    conn = get_db()
    try:
        # First check if the group exists and belongs to the user (if user_id provided)
        if user_id:
            cursor = conn.execute('''
                SELECT id FROM custom_level_groups 
                WHERE id = ? AND user_id = ?
            ''', (group_id, user_id))
            if not cursor.fetchone():
                return None
        
        cursor = conn.execute('''
            SELECT * FROM custom_levels 
            WHERE group_id = ? AND level_number = ?
        ''', (group_id, level_number))
        
        row = cursor.fetchone()
        if row:
            level_data = dict(row)
            level_data['content'] = json.loads(level_data['content'])
            
            # Ensure word hashes exist for Multi-User-DB compatibility
            group_info = get_custom_level_group(group_id, user_id) if user_id else None
            if group_info:
                level_data['content'] = ensure_custom_level_word_hashes(
                    level_data['content'], 
                    group_info['language'], 
                    group_info['native_language']
                )
            
            return level_data
        return None
    except Exception as e:
        print(f"Error getting custom level: {e}")
        return None
    finally:
        conn.close()

def get_custom_levels_for_group(group_id: int) -> List[Dict[str, Any]]:
    """Get all levels for a custom level group with optimized word hash handling"""
    conn = get_db()
    try:
        cursor = conn.execute('''
            SELECT * FROM custom_levels 
            WHERE group_id = ?
            ORDER BY level_number
        ''', (group_id,))
        
        levels = []
        
        # Get group info for language/native_language
        group_info = get_custom_level_group(group_id, None)
        
        for row in cursor.fetchall():
            level_data = dict(row)
            level_data['content'] = json.loads(level_data['content'])
            
            # Ensure word hashes exist for Multi-User-DB compatibility
            if group_info:
                level_data['content'] = ensure_custom_level_word_hashes(
                    level_data['content'], 
                    group_info['language'], 
                    group_info['native_language']
                )
            
            levels.append(level_data)
        
        return levels
    except Exception as e:
        print(f"Error getting custom levels: {e}")
        return []
    finally:
        conn.close()

def delete_custom_level_group(group_id: int, user_id: int) -> bool:
    """Delete a custom level group and all its levels"""
    conn = get_db()
    try:
        # Verify ownership
        cursor = conn.execute('''
            SELECT id FROM custom_level_groups 
            WHERE id = ? AND user_id = ?
        ''', (group_id, user_id))
        
        if not cursor.fetchone():
            return False
        
        # Delete group (levels will be deleted by CASCADE)
        conn.execute('''
            DELETE FROM custom_level_groups 
            WHERE id = ? AND user_id = ?
        ''', (group_id, user_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting custom level group: {e}")
        return False
    finally:
        conn.close()

def update_custom_level_group(group_id: int, user_id: int, **kwargs) -> bool:
    """Update a custom level group"""
    conn = get_db()
    try:
        # Build update query dynamically
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in ['group_name', 'context_description', 'cefr_level', 'num_levels', 'status']:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return True
        
        updates.append("updated_at = ?")
        values.append(datetime.now(UTC).isoformat())
        values.extend([group_id, user_id])
        
        conn.execute(f'''
            UPDATE custom_level_groups 
            SET {', '.join(updates)}
            WHERE id = ? AND user_id = ?
        ''', values)
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating custom level group: {e}")
        return False
    finally:
        conn.close()

def batch_generate_audio_for_custom_levels(sentences: List[str], words: set, language: str, native_language: str) -> None:
    """Batch generate audio for all sentences and words in custom levels using optimized batch processing"""
    try:
        print(f"🎵 Batch generating audio for {len(sentences)} sentences and {len(words)} words...")
        
        # Create sentence context mapping for words
        word_sentence_contexts = {}
        for word in words:
            if word and word.strip():
                for sentence in sentences:
                    if word.lower() in sentence.lower():
                        word_sentence_contexts[word] = sentence
                        break
        
        # Batch generate audio for sentences
        sentence_audio_results = batch_ensure_tts_for_sentences(sentences, language)
        sentence_audio_count = sum(1 for url in sentence_audio_results.values() if url)
        
        # Batch generate audio for words
        word_audio_results = batch_ensure_tts_for_words(list(words), language, word_sentence_contexts)
        word_audio_count = sum(1 for url in word_audio_results.values() if url)
        
        print(f"🎵 Batch audio generation complete: {sentence_audio_count} sentences, {word_audio_count} words")
        
    except Exception as e:
        print(f"Error in batch audio generation: {e}")

def batch_enrich_words_for_custom_levels(words: List[str], language: str, native_language: str, sentence_contexts: List[str]) -> Dict[str, str]:
    """Batch enrich all words with translations, POS, IPA, and other metadata using optimized batch processing
    
    Returns:
        Dict[str, str]: Mapping of word -> word_hash for successfully enriched words
    """
    try:
        print(f"📚 Batch enriching {len(words)} words with metadata for Multi-User-DB...")
        
        # Create sentence context mapping for words
        word_sentence_contexts = {}
        for word in words:
            if word and word.strip():
                for sentence in sentence_contexts:
                    if word.lower() in sentence.lower():
                        word_sentence_contexts[word] = sentence
                        break
        
        # Import Multi-User DB manager
        from server.multi_user_db import db_manager
        
        # Check which words already exist in Multi-User-DB
        words_to_enrich = []
        existing_word_hashes = {}
        
        for word in words:
            if not word or not word.strip():
                continue
                
            word = word.strip()
            word_hash = db_manager.generate_word_hash(word, language, native_language)
            
            # Check if word already exists in global Multi-User-DB
            existing_data = db_manager.get_global_word_data(native_language, [word_hash])
            if existing_data and existing_data.get(word_hash, {}).get('translation'):
                # Word already exists in Multi-User-DB
                existing_word_hashes[word] = word_hash
                print(f"⏭️ Word '{word}' already exists in Multi-User-DB")
            else:
                words_to_enrich.append(word)
        
        print(f"📊 Found {len(existing_word_hashes)} existing words, {len(words_to_enrich)} words to enrich")
        
        # Use batch enrichment function for new words only
        enriched_results = {}
        if words_to_enrich:
            enriched_results = llm_enrich_words_batch(words_to_enrich, language, native_language, word_sentence_contexts)
        
        # Store enriched words directly in Multi-User-DB
        new_word_hashes = {}
        enriched_count = 0
        
        for word, enrichment_data in enriched_results.items():
            if enrichment_data and enrichment_data.get('translation'):
                try:
                    # Store directly in Multi-User-DB
                    word_hash = db_manager.add_word_to_global(word, language, native_language, enrichment_data)
                    if word_hash:
                        new_word_hashes[word] = word_hash
                        enriched_count += 1
                        print(f"✅ Stored enriched word '{word}' in Multi-User-DB")
                    
                    # Also store in old DB for backward compatibility
                    from server.db import upsert_word_row
                    upsert_word_row({
                        'word': word,
                        'language': language,
                        'native_language': native_language,
                        'translation': enrichment_data.get('translation', ''),
                        'pos': enrichment_data.get('pos', ''),
                        'ipa': enrichment_data.get('ipa', ''),
                        'example': enrichment_data.get('example', ''),
                        'example_native': enrichment_data.get('example_native', ''),
                        'synonyms': enrichment_data.get('synonyms', []),
                        'collocations': enrichment_data.get('collocations', []),
                        'gender': enrichment_data.get('gender', 'none'),
                        'familiarity': 0
                    })
                    
                except Exception as e:
                    print(f"❌ Error storing enriched word '{word}' in Multi-User-DB: {e}")
        
        # Combine existing and new word hashes
        all_word_hashes = {**existing_word_hashes, **new_word_hashes}
        
        print(f"📚 Batch word enrichment complete: {enriched_count} new words enriched, {len(all_word_hashes)} total words available")
        
        return all_word_hashes
        
    except Exception as e:
        print(f"Error in batch word enrichment: {e}")
        return {}

def generate_custom_level_word_hashes(custom_level_content: Dict[str, Any], language: str, native_language: str) -> Dict[str, str]:
    """Generate word hashes for all words in a custom level"""
    try:
        from server.multi_user_db import db_manager
        
        word_hashes = {}
        
        # Extract words from level items
        for item in custom_level_content.get('items', []):
            for word in item.get('words', []):
                if word and word.strip():
                    word = word.strip().lower()
                    if word not in word_hashes:
                        word_hash = db_manager.generate_word_hash(word, language, native_language)
                        word_hashes[word] = word_hash
        
        return word_hashes
        
    except Exception as e:
        print(f"Error generating word hashes for custom level: {e}")
        return {}

def ensure_custom_level_word_hashes(custom_level_content: Dict[str, Any], language: str, native_language: str) -> Dict[str, Any]:
    """Ensure custom level content has word hashes, generate if missing"""
    try:
        # Check if word_hashes already exist
        if 'word_hashes' not in custom_level_content or not custom_level_content['word_hashes']:
            # Generate word hashes
            word_hashes = generate_custom_level_word_hashes(custom_level_content, language, native_language)
            custom_level_content['word_hashes'] = word_hashes
            print(f"✅ Generated {len(word_hashes)} word hashes for custom level")
        else:
            print(f"✅ Custom level already has {len(custom_level_content['word_hashes'])} word hashes")
        
        return custom_level_content
        
    except Exception as e:
        print(f"Error ensuring word hashes for custom level: {e}")
        return custom_level_content

def unlock_custom_level_words_for_user(user_id: int, group_id: int, course_language: str, native_language: str) -> bool:
    """Unlock all words from a custom level group for a specific user"""
    try:
        print(f"🔓 Unlocking custom level words for user {user_id}, group {group_id}")
        
        # Import Multi-User DB manager
        from server.multi_user_db import db_manager
        
        # Ensure user databases exist
        db_manager.ensure_user_database(user_id, native_language)
        
        # Get all levels for this group
        levels = get_custom_levels_for_group(group_id)
        
        all_word_hashes = set()
        
        # Collect all word hashes from all levels
        for level in levels:
            content = level.get('content', {})
            word_hashes = content.get('word_hashes', {})
            all_word_hashes.update(word_hashes.values())
        
        if not all_word_hashes:
            print(f"⚠️ No word hashes found for custom level group {group_id}")
            return False
        
        # Unlock all words for user
        success = db_manager.unlock_words_for_level(
            user_id, native_language, 1, language, list(all_word_hashes)
        )
        
        if success:
            print(f"✅ Successfully unlocked {len(all_word_hashes)} words for user {user_id}")
        else:
            print(f"❌ Failed to unlock words for user {user_id}")
        
        return success
        
    except Exception as e:
        print(f"Error unlocking custom level words for user {user_id}: {e}")
        return False

def migrate_existing_custom_levels_to_multi_user() -> Dict[str, Any]:
    """Migrate all existing custom levels to Multi-User-DB compatibility"""
    try:
        print("🔄 Starting migration of existing custom levels to Multi-User-DB...")
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        
        # Get all custom level groups
        cursor = conn.execute("SELECT * FROM custom_level_groups ORDER BY id")
        groups = cursor.fetchall()
        
        migration_stats = {
            'groups_processed': 0,
            'levels_processed': 0,
            'words_migrated': 0,
            'errors': []
        }
        
        for group in groups:
            try:
                group_id = group['id']
                language = group['language']
                native_language = group['native_language']
                
                print(f"📁 Processing custom level group {group_id}: {group['group_name']} ({language} -> {native_language})")
                
                # Get all levels for this group
                cursor = conn.execute("SELECT * FROM custom_levels WHERE group_id = ? ORDER BY level_number", (group_id,))
                levels = cursor.fetchall()
                
                all_words = set()
                
                # Collect all words from all levels
                for level in levels:
                    try:
                        content = json.loads(level['content'])
                        
                        # Extract words from level items
                        for item in content.get('items', []):
                            for word in item.get('words', []):
                                if word and word.strip():
                                    all_words.add(word.strip().lower())
                        
                        migration_stats['levels_processed'] += 1
                        
                    except Exception as e:
                        error_msg = f"Error processing level {level['level_number']} in group {group_id}: {e}"
                        print(f"❌ {error_msg}")
                        migration_stats['errors'].append(error_msg)
                
                if all_words:
                    print(f"📚 Found {len(all_words)} unique words in group {group_id}")
                    
                    # Migrate words to Multi-User-DB
                    word_hashes = batch_enrich_words_for_custom_levels(
                        list(all_words), language, native_language, []
                    )
                    
                    migration_stats['words_migrated'] += len(word_hashes)
                    
                    # Update level content with word hashes
                    for level in levels:
                        try:
                            content = json.loads(level['content'])
                            
                            # Ensure word hashes exist
                            content = ensure_custom_level_word_hashes(content, language, native_language)
                            
                            # Update level in database
                            conn.execute(
                                "UPDATE custom_levels SET content = ? WHERE id = ?",
                                (json.dumps(content, ensure_ascii=False), level['id'])
                            )
                            
                        except Exception as e:
                            error_msg = f"Error updating level {level['level_number']} in group {group_id}: {e}"
                            print(f"❌ {error_msg}")
                            migration_stats['errors'].append(error_msg)
                
                migration_stats['groups_processed'] += 1
                print(f"✅ Completed migration for group {group_id}")
                
            except Exception as e:
                error_msg = f"Error processing group {group['id']}: {e}"
                print(f"❌ {error_msg}")
                migration_stats['errors'].append(error_msg)
        
        # Commit all changes
        conn.commit()
        conn.close()
        
        print(f"🎉 Migration completed!")
        print(f"📊 Stats: {migration_stats['groups_processed']} groups, {migration_stats['levels_processed']} levels, {migration_stats['words_migrated']} words")
        
        if migration_stats['errors']:
            print(f"⚠️ {len(migration_stats['errors'])} errors occurred during migration")
            for error in migration_stats['errors']:
                print(f"   - {error}")
        
        return migration_stats
        
    except Exception as e:
        print(f"❌ Critical error during custom level migration: {e}")
        return {
            'groups_processed': 0,
            'levels_processed': 0,
            'words_migrated': 0,
            'errors': [f"Critical error: {e}"]
        }

def generate_custom_levels_ultra_fast(group_id: int, language: str, native_language: str, 
                                     context_description: str, cefr_level: str, num_levels: int) -> bool:
    """Ultra-fast custom level generation with maximum batch optimization"""
    try:
        print(f"⚡ Starting ultra-fast level generation for group {group_id} with {num_levels} levels")
        
        # Step 1: Batch generate ALL topics at once
        print("📝 Batch generating all topics...")
        topics_batch = batch_generate_topics(language, native_language, cefr_level, context_description, num_levels)
        if not topics_batch:
            print("❌ Failed to generate topics batch")
            return False
        
        # Step 2: Batch generate ALL titles at once
        print("🏷️ Batch generating all titles...")
        titles_batch = batch_generate_titles(language, native_language, cefr_level, topics_batch, context_description)
        if not titles_batch:
            print("❌ Failed to generate titles batch")
            return False
        
        # Step 3: Batch generate ALL sentences at once
        print("📝 Batch generating all sentences...")
        sentences_batch = batch_generate_all_sentences(language, native_language, cefr_level, topics_batch, num_levels)
        if not sentences_batch:
            print("❌ Failed to generate sentences batch")
            return False
        
        # Step 4: Batch translate ALL sentences at once
        print("🌐 Batch translating all sentences...")
        translations_batch = batch_translate_all_sentences(sentences_batch, language, native_language)
        
        # Step 5: Extract and batch enrich ALL words at once
        print("📚 Batch extracting and enriching all words...")
        all_words = extract_all_words_from_sentences(sentences_batch)
        word_hashes = batch_enrich_words_for_custom_levels(all_words, language, native_language, sentences_batch)
        
        # Step 6: Create all levels with enriched content
        print("💾 Creating all levels with enriched content...")
        for i in range(1, num_levels + 1):
            level_content = create_level_content(
                i, titles_batch[i-1], topics_batch[i-1], 
                sentences_batch[i-1], context_description, word_hashes, language, native_language
            )
            
            # Add translations to level content
            if i-1 < len(translations_batch):
                for j, item in enumerate(level_content.get('items', [])):
                    if j < len(translations_batch[i-1]):
                        item['text_native_ref'] = translations_batch[i-1][j]
            
            # Save level to database
            save_custom_level(group_id, i, titles_batch[i-1], topics_batch[i-1], level_content)
            print(f"✅ Saved level {i} to database")
        
        print(f"🎉 Ultra-fast generation complete: {num_levels} levels in record time!")
        return True
        
    except Exception as e:
        print(f"❌ Error in ultra-fast generation: {e}")
        return False

def generate_custom_levels_optimized(group_id: int, language: str, native_language: str, 
                                   context_description: str, cefr_level: str, num_levels: int) -> bool:
    """Optimized version of custom level generation with parallel processing for large groups"""
    try:
        print(f"🚀 Starting optimized level generation for group {group_id} with {num_levels} levels")
        
        # For large groups (>15 levels), use ultra-fast processing
        if num_levels > 15:
            return generate_custom_levels_async(group_id, language, native_language, 
                                              context_description, cefr_level, num_levels)
        
        # For smaller groups, use regular processing but with optimizations
        return generate_custom_levels_parallel(group_id, language, native_language, 
                                             context_description, cefr_level, num_levels)
        
    except Exception as e:
        print(f"Error in optimized custom level generation: {e}")
        return False

def generate_custom_levels_parallel(group_id: int, language: str, native_language: str, 
                                  context_description: str, cefr_level: str, num_levels: int) -> bool:
    """Parallel version of custom level generation with optimized batch processing"""
    try:
        print(f"⚡ Starting parallel level generation for group {group_id}")
        
        # Generate topics for each level sequentially for story progression
        topics = []
        for i in range(1, num_levels + 1):
            try:
                # Get previous topics for story context
                previous_topics = topics.copy()
                topic = suggest_topic(language, native_language, cefr_level, context_description, i, previous_topics)
                topics.append(topic)
                print(f"✅ Generated topic for level {i}: {topic}")
            except Exception as e:
                print(f"Error generating topic for level {i}: {e}")
                topics.append(f"{context_description} - Level {i}")
        
        # Collect all data for batch processing
        all_sentences = []
        all_words = set()
        level_data = []
        
        # Generate levels with sequential title generation for story progression
        level_titles = {}
        for i, topic in enumerate(topics, 1):
            try:
                # Get previous titles for uniqueness
                previous_titles = [level_titles.get(j, "") for j in range(1, i)]
                level_title = suggest_level_title(
                    language, native_language, topic, i, cefr_level, 
                    context_description, topics, previous_titles
                )
                level_titles[i] = level_title
                print(f"✅ Generated title for level {i}: {level_title}")
            except Exception as e:
                print(f"Error generating level title for level {i}: {e}")
                level_titles[i] = f"{context_description} - Level {i}"
        
        # Generate sentences with parallel processing
        with ThreadPoolExecutor(max_workers=2) as executor:
            sentence_futures = {}
            for i, topic in enumerate(topics, 1):
                future = executor.submit(
                    llm_generate_sentences,
                    target_lang=language,
                    native_lang=native_language,
                    n=5,
                    topic=topic,
                    cefr=cefr_level
                )
                sentence_futures[future] = i
            
            # Collect sentences as they complete
            for future in as_completed(sentence_futures):
                level_num = sentence_futures[future]
                try:
                    sentences = future.result()
                    level_title = level_titles.get(level_num, f"{context_description} - Level {level_num}")
                    
                    level_info = {
                        "level_number": level_num,
                        "title": level_title,
                        "topic": topics[level_num - 1],
                        "sentences": sentences
                    }
                    level_data.append(level_info)
                    
                    # Collect words and sentences
                    for sentence_data in sentences:
                        if isinstance(sentence_data, dict):
                            text_target = sentence_data.get('sentence', '')
                            all_sentences.append(text_target)
                            words = sentence_data.get('words', [])
                            for word in words:
                                if word and word.strip():
                                    all_words.add(word.strip().lower())
                    
                    print(f"✅ Generated {len(sentences)} sentences for level {level_num}")
                    
                except Exception as e:
                    print(f"Error generating sentences for level {level_num}: {e}")
                    # Add fallback data
                    level_info = {
                        "level_number": level_num,
                        "title": level_titles.get(level_num, f"{context_description} - Level {level_num}"),
                        "topic": topics[level_num - 1],
                        "sentences": []
                    }
                    level_data.append(level_info)
        
        # Sort level data by level number
        level_data.sort(key=lambda x: x["level_number"])
        
        print(f"📊 Collected {len(all_sentences)} sentences and {len(all_words)} unique words for batch processing")
        
        # Parallel batch processing
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit audio generation
            audio_future = executor.submit(
                batch_generate_audio_for_custom_levels,
                all_sentences, all_words, language, native_language
            )
            
            # Submit word enrichment
            enrichment_future = executor.submit(
                batch_enrich_words_for_custom_levels,
                list(all_words), language, native_language, all_sentences
            )
            
            # Wait for both to complete
            audio_future.result()
            word_hashes = enrichment_future.result()
        
        # Create levels with enriched content
        print("💾 Creating levels with enriched content...")
        for level_info in level_data:
            i = level_info["level_number"]
            level_title = level_info["title"]
            topic = level_info["topic"]
            sentences = level_info["sentences"]
            
            # Create level content
            level_content = create_level_content(i, level_title, topic, sentences, context_description, word_hashes, language, native_language)
            
            # Save level to database
            try:
                save_custom_level(group_id, i, level_title, topic, level_content)
                print(f"✅ Saved level {i} to database")
            except Exception as e:
                print(f"Error saving level {i} to database: {e}")
        
        print(f"🎉 Successfully generated {num_levels} levels with parallel processing for group {group_id}")
        return True
        
    except Exception as e:
        print(f"Error in parallel custom level generation: {e}")
        return False

def generate_custom_levels_async(group_id: int, language: str, native_language: str, 
                               context_description: str, cefr_level: str, num_levels: int) -> bool:
    """Async version for very large custom level groups (>15 levels)"""
    try:
        print(f"🔄 Starting async level generation for large group {group_id} with {num_levels} levels")
        
        # For very large groups, we'll create a background task
        # This is a placeholder for future async implementation
        # For now, we'll use the parallel version but with more conservative settings
        
        print("⚠️ Large group detected - using conservative parallel processing")
        return generate_custom_levels_parallel(group_id, language, native_language, 
                                             context_description, cefr_level, num_levels)
        
    except Exception as e:
        print(f"Error in async custom level generation: {e}")
        return False

def create_level_content(level_number: int, title: str, topic: str, sentences: List[Dict], 
                        context_description: str, word_hashes: Dict[str, str], 
                        language: str = "", native_language: str = "") -> Dict[str, Any]:
    """Helper function to create level content structure"""
    
    level_content = {
        "items": [],
        "meta": {
            "level": level_number,
            "section": context_description,
            "theme": topic,
            "title": title
        },
        "language": "",
        "level": level_number,
        "title": title,
        "section": context_description,
        "topic": topic,
        "runs": [],
        "fam_counts": {
            "0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0
        },
        "word_hashes": {}
    }
    
    # Process sentences into items
    for idx, sentence_data in enumerate(sentences, 1):
        if isinstance(sentence_data, dict):
            text_target = sentence_data.get('sentence', '')
            text_native_ref = sentence_data.get('translation', '')
            words = sentence_data.get('words', [])
        else:
            text_target = str(sentence_data)
            text_native_ref = ""
            words = text_target.split()
        
        # Generate translation if missing
        if not text_native_ref and text_target:
            try:
                from server.services.llm import llm_translate_batch
                # Use the correct native language and source language
                translations = llm_translate_batch([text_target], native_language, language)
                if translations and len(translations) > 0:
                    text_native_ref = translations[0]
                    print(f"Translated '{text_target}' to '{text_native_ref}' (from {language} to {native_language})")
            except Exception as e:
                print(f"Error generating translation for '{text_target}': {e}")
        
        item = {
            "idx": idx,
            "text_target": text_target,
            "text_native_ref": text_native_ref,
            "words": words
        }
        level_content["items"].append(item)
        
        # Collect word hashes for this level
        for word in words:
            if word in word_hashes:
                level_content["word_hashes"][word] = word_hashes[word]
    
    return level_content
