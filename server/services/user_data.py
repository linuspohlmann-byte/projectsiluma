import os
import json
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, Any, Optional

from ..db import (
    get_user_progress, update_user_progress, get_user_familiarity_counts,
    get_user_word_familiarity, update_user_word_familiarity, get_db
)

# Base directory for user data
USER_DATA_DIR = Path(__file__).parent.parent.parent / 'data' / 'users'

def ensure_user_directory(user_id: int) -> Path:
    """Ensure user directory exists and return path"""
    user_dir = USER_DATA_DIR / f"user_{user_id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def get_user_progress_file(user_id: int, language: str) -> Path:
    """Get path to user progress file for a specific language"""
    user_dir = ensure_user_directory(user_id)
    progress_dir = user_dir / 'progress'
    progress_dir.mkdir(parents=True, exist_ok=True)
    return progress_dir / f"{language}.json"

def get_user_settings_file(user_id: int) -> Path:
    """Get path to user settings file"""
    user_dir = ensure_user_directory(user_id)
    return user_dir / 'settings.json'

def get_user_stats_file(user_id: int) -> Path:
    """Get path to user stats file"""
    user_dir = ensure_user_directory(user_id)
    return user_dir / 'stats.json'

def get_user_word_familiarity_file(user_id: int, language: str) -> Path:
    """Get path to user word familiarity file for a specific language"""
    user_dir = ensure_user_directory(user_id)
    fam_dir = user_dir / 'word_familiarity'
    fam_dir.mkdir(parents=True, exist_ok=True)
    return fam_dir / f"{language}.json"

def get_user_level_runs_file(user_id: int, language: str, level: int) -> Path:
    """Get path to user level runs file for a specific language and level"""
    user_dir = ensure_user_directory(user_id)
    runs_dir = user_dir / 'level_runs' / language
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir / f"level_{level}.json"

def load_user_progress(user_id: int, language: str) -> Dict[str, Any]:
    """Load user progress for a specific language from file system"""
    progress_file = get_user_progress_file(user_id, language)
    
    if not progress_file.exists():
        return {
            'language': language,
            'levels': {},
            'total_score': 0,
            'levels_completed': 0,
            'last_updated': None
        }
    
    try:
        with progress_file.open('r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            'language': language,
            'levels': {},
            'total_score': 0,
            'levels_completed': 0,
            'last_updated': None
        }

def save_user_progress(user_id: int, language: str, progress_data: Dict[str, Any]):
    """Save user progress for a specific language to file system"""
    progress_file = get_user_progress_file(user_id, language)
    
    # Add timestamp
    progress_data['last_updated'] = datetime.now(UTC).isoformat()
    
    try:
        with progress_file.open('w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Error saving user progress: {e}")

def load_user_settings(user_id: int) -> Dict[str, Any]:
    """Load user settings from file system"""
    settings_file = get_user_settings_file(user_id)
    
    if not settings_file.exists():
        return {
            'theme': 'light',
            'language': 'en',
            'notifications': True,
            'sound_enabled': True,
            'auto_play_audio': False,
            'difficulty_preference': 'adaptive',
            'native_language': 'de'
        }
    
    try:
        with settings_file.open('r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            'theme': 'light',
            'language': 'en',
            'notifications': True,
            'sound_enabled': True,
            'auto_play_audio': False,
            'difficulty_preference': 'adaptive',
            'native_language': 'de'
        }

def save_user_settings(user_id: int, settings: Dict[str, Any]):
    """Save user settings to file system"""
    settings_file = get_user_settings_file(user_id)
    
    try:
        with settings_file.open('w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Error saving user settings: {e}")

def load_user_stats(user_id: int) -> Dict[str, Any]:
    """Load user statistics from file system"""
    stats_file = get_user_stats_file(user_id)
    
    if not stats_file.exists():
        return {
            'total_study_time': 0,
            'words_learned': 0,
            'levels_completed': 0,
            'streak_days': 0,
            'last_study_date': None,
            'achievements': [],
            'created_at': datetime.now(UTC).isoformat()
        }
    
    try:
        with stats_file.open('r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            'total_study_time': 0,
            'words_learned': 0,
            'levels_completed': 0,
            'streak_days': 0,
            'last_study_date': None,
            'achievements': [],
            'created_at': datetime.now(UTC).isoformat()
        }

def save_user_stats(user_id: int, stats: Dict[str, Any]):
    """Save user statistics to file system"""
    stats_file = get_user_stats_file(user_id)
    
    try:
        with stats_file.open('w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Error saving user stats: {e}")

def load_user_word_familiarity(user_id: int, language: str) -> Dict[str, Any]:
    """Load user word familiarity for a specific language from file system"""
    fam_file = get_user_word_familiarity_file(user_id, language)
    
    if not fam_file.exists():
        return {
            'language': language,
            'words': {},
            'last_updated': None
        }
    
    try:
        with fam_file.open('r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            'language': language,
            'words': {},
            'last_updated': None
        }

def save_user_word_familiarity(user_id: int, language: str, fam_data: Dict[str, Any]):
    """Save user word familiarity for a specific language to file system"""
    fam_file = get_user_word_familiarity_file(user_id, language)
    
    # Add timestamp
    fam_data['last_updated'] = datetime.now(UTC).isoformat()
    
    try:
        with fam_file.open('w', encoding='utf-8') as f:
            json.dump(fam_data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Error saving user word familiarity: {e}")

def load_user_level_runs(user_id: int, language: str, level: int) -> Dict[str, Any]:
    """Load user level runs for a specific language and level from file system"""
    runs_file = get_user_level_runs_file(user_id, language, level)
    
    if not runs_file.exists():
        return {
            'user_id': user_id,
            'language': language,
            'level': level,
            'runs': [],
            'last_updated': None
        }
    
    try:
        with runs_file.open('r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            'user_id': user_id,
            'language': language,
            'level': level,
            'runs': [],
            'last_updated': None
        }

def save_user_level_runs(user_id: int, language: str, level: int, runs_data: Dict[str, Any]):
    """Save user level runs for a specific language and level to file system"""
    runs_file = get_user_level_runs_file(user_id, language, level)
    
    # Add timestamp
    runs_data['last_updated'] = datetime.now(UTC).isoformat()
    
    try:
        with runs_file.open('w', encoding='utf-8') as f:
            json.dump(runs_data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Error saving user level runs: {e}")

def update_user_level_progress(user_id: int, language: str, level: int, status: str, score: float = None):
    """Update user level progress in both database and file system"""
    # Update database
    update_user_progress(user_id, language, level, status, score)
    
    # Update file system
    progress_data = load_user_progress(user_id, language)
    
    if 'levels' not in progress_data:
        progress_data['levels'] = {}
    
    level_key = str(level)
    progress_data['levels'][level_key] = {
        'status': status,
        'score': score,
        'completed_at': datetime.now(UTC).isoformat() if status == 'completed' else None,
        'updated_at': datetime.now(UTC).isoformat()
    }
    
    # Update totals
    if status == 'completed':
        progress_data['levels_completed'] = len([l for l in progress_data['levels'].values() if l['status'] == 'completed'])
        if score is not None:
            progress_data['total_score'] = sum(l.get('score', 0) for l in progress_data['levels'].values() if l.get('score') is not None)
    
    save_user_progress(user_id, language, progress_data)

def get_user_level_progress(user_id: int, language: str) -> Dict[str, Any]:
    """Get user level progress for a language"""
    return load_user_progress(user_id, language)

def update_user_word_familiarity(user_id: int, word: str, language: str, familiarity: int):
    """Update user word familiarity for a specific word and language"""
    # Update database
    from ..db import get_db
    conn = get_db()
    cursor = conn.execute("""
        SELECT id FROM words 
        WHERE word = ? AND (language = ? OR ? = "")
    """, (word, language, language))
    word_row = cursor.fetchone()
    conn.close()
    
    if word_row:
        word_id = word_row[0]
        update_user_word_familiarity(user_id, word_id, familiarity)
    
    # Update file system
    fam_data = load_user_word_familiarity(user_id, language)
    
    if 'words' not in fam_data:
        fam_data['words'] = {}
    
    fam_data['words'][word] = {
        'familiarity': familiarity,
        'updated_at': datetime.now(UTC).isoformat()
    }
    
    save_user_word_familiarity(user_id, language, fam_data)

def add_user_level_run(user_id: int, language: str, level: int, run_data: Dict[str, Any]):
    """Add a new level run for a user"""
    runs_data = load_user_level_runs(user_id, language, level)
    
    if 'runs' not in runs_data:
        runs_data['runs'] = []
    
    # Add run data with timestamp
    run_data['created_at'] = datetime.now(UTC).isoformat()
    runs_data['runs'].append(run_data)
    
    save_user_level_runs(user_id, language, level, runs_data)

def get_user_familiarity_counts_fs(user_id: int, language: str) -> Dict[str, int]:
    """Get familiarity counts for a user from file system"""
    fam_data = load_user_word_familiarity(user_id, language)
    
    counts = {str(i): 0 for i in range(6)}
    
    for word, data in fam_data.get('words', {}).items():
        familiarity = data.get('familiarity', 0)
        if 0 <= familiarity <= 5:
            counts[str(familiarity)] += 1
    
    return counts

def migrate_user_data_structure(user_id: int) -> bool:
    """
    Migrate user data to the new structure.
    This should be called for existing users.
    """
    try:
        user_dir = ensure_user_directory(user_id)
        
        # Create progress directory structure
        progress_dir = user_dir / 'progress'
        progress_dir.mkdir(parents=True, exist_ok=True)
        
        # Create word familiarity directory structure
        fam_dir = user_dir / 'word_familiarity'
        fam_dir.mkdir(parents=True, exist_ok=True)
        
        # Create level runs directory structure
        runs_dir = user_dir / 'level_runs'
        runs_dir.mkdir(parents=True, exist_ok=True)
        
        # Migrate existing progress data from database
        from ..db import get_user_progress
        db_progress = get_user_progress(user_id)
        
        for row in db_progress:
            language = row['language']
            
            # Create progress file for this language
            progress_file = progress_dir / f"{language}.json"
            if not progress_file.exists():
                progress_data = {
                    'language': language,
                    'levels': {},
                    'total_score': 0,
                    'levels_completed': 0,
                    'last_updated': datetime.now(UTC).isoformat()
                }
                
                level_key = str(row['level'])
                progress_data['levels'][level_key] = {
                    'status': row['status'],
                    'score': row['score'],
                    'completed_at': row['completed_at'],
                    'updated_at': row['updated_at']
                }
                
                if row['status'] == 'completed':
                    progress_data['levels_completed'] = 1
                    if row['score'] is not None:
                        progress_data['total_score'] = row['score']
                
                save_user_progress(user_id, language, progress_data)
        
        # Create empty word familiarity files for all languages the user has progress in
        languages = set(row['language'] for row in db_progress)
        for language in languages:
            fam_file = fam_dir / f"{language}.json"
            if not fam_file.exists():
                fam_data = {
                    'language': language,
                    'words': {},
                    'last_updated': datetime.now(UTC).isoformat()
                }
                save_user_word_familiarity(user_id, language, fam_data)
        
        # Create level runs directory structure for each language
        for language in languages:
            lang_runs_dir = runs_dir / language
            lang_runs_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Migration completed for user {user_id}")
        return True
        
    except Exception as e:
        print(f"Error migrating user data for user {user_id}: {e}")
        return False

def get_user_directory_structure(user_id: int) -> Dict[str, Any]:
    """Get user directory structure for debugging/admin purposes"""
    user_dir = ensure_user_directory(user_id)
    
    structure = {
        'user_id': user_id,
        'base_path': str(user_dir),
        'exists': user_dir.exists(),
        'files': [],
        'directories': []
    }
    
    if user_dir.exists():
        for item in user_dir.rglob('*'):
            relative_path = item.relative_to(user_dir)
            if item.is_file():
                structure['files'].append(str(relative_path))
            elif item.is_dir():
                structure['directories'].append(str(relative_path))
    
    return structure

def cleanup_global_user_data():
    """
    Remove global user data files that should not exist.
    This should be called after migration.
    """
    try:
        # Remove global level files from users directory
        global_levels_dir = USER_DATA_DIR / 'levels'
        if global_levels_dir.exists():
            print(f"Removing global levels directory: {global_levels_dir}")
            import shutil
            shutil.rmtree(global_levels_dir)
        
        print("Global user data cleanup completed")
        return True
        
    except Exception as e:
        print(f"Error cleaning up global user data: {e}")
        return False
