#!/usr/bin/env python3
"""
Analyze the data/ folder to determine what's still needed vs redundant.
"""

import os
from pathlib import Path

def analyze_data_folder():
    """Analyze the data folder structure and usage."""
    
    data_dir = Path('data')
    if not data_dir.exists():
        print("❌ data/ folder does not exist")
        return
    
    print("=" * 70)
    print("DATA FOLDER ANALYSIS")
    print("=" * 70)
    print()
    
    # Check what's in the data folder
    total_size = 0
    language_dirs = []
    user_dirs = []
    other_dirs = []
    
    for item in data_dir.iterdir():
        if not item.is_dir():
            continue
            
        size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
        total_size += size
        
        if item.name == 'users':
            user_dirs.append((item, size))
        elif item.name.startswith('__'):
            other_dirs.append((item, size))
        else:
            language_dirs.append((item, size))
    
    print(f"📊 Total size: {total_size / (1024*1024):.2f} MB")
    print()
    
    # Analyze language directories
    print("=" * 70)
    print("LANGUAGE DIRECTORIES (Standard Course Levels)")
    print("=" * 70)
    print()
    print("✅ STILL NEEDED - These contain standard course level JSON files")
    print("   Used by: _read_level(), _write_level(), _list_levels()")
    print("   Endpoints: /api/levels/bulk-stats, /api/levels/summary")
    print()
    
    for lang_dir, size in sorted(language_dirs):
        level_count = len(list((lang_dir / 'levels').glob('*.json'))) if (lang_dir / 'levels').exists() else 0
        course_exists = (lang_dir / 'course.json').exists()
        practice_exists = (lang_dir / 'practice_sessions.json').exists()
        
        print(f"  📁 {lang_dir.name}/")
        print(f"     Size: {size / 1024:.2f} KB")
        print(f"     Levels: {level_count} JSON files")
        print(f"     course.json: {'✅' if course_exists else '❌'}")
        print(f"     practice_sessions.json: {'✅' if practice_exists else '❌'}")
        print()
    
    # Analyze user directories
    print("=" * 70)
    print("USER DIRECTORIES")
    print("=" * 70)
    print()
    
    if user_dirs:
        user_dir, user_size = user_dirs[0]
        user_count = len([d for d in user_dir.iterdir() if d.is_dir() and d.name.startswith('user_')])
        total_user_files = sum(1 for f in user_dir.rglob('*.json') if f.is_file())
        
        print(f"  📁 {user_dir.name}/")
        print(f"     Size: {user_size / 1024:.2f} KB")
        print(f"     Users: {user_count}")
        print(f"     Total JSON files: {total_user_files}")
        print()
        print("  ⚠️  PARTIALLY NEEDED - User-specific level modifications")
        print("     Used by: _read_level(lang, level, user_id)")
        print("     Endpoints: /api/level/start (for user-specific level content)")
        print("     Note: User progress is stored in PostgreSQL, but user-specific")
        print("           level content modifications are still stored here")
        print()
    else:
        print("  ✅ No user directories found")
        print()
    
    # Analyze other directories
    print("=" * 70)
    print("OTHER DIRECTORIES")
    print("=" * 70)
    print()
    
    if other_dirs:
        print("  ⚠️  POTENTIALLY REDUNDANT:")
        print()
        for other_dir, size in other_dirs:
            file_count = sum(1 for f in other_dir.rglob('*') if f.is_file())
            print(f"  📁 {other_dir.name}/")
            print(f"     Size: {size / 1024:.2f} KB")
            print(f"     Files: {file_count}")
            print()
            print("     ❓ Check if this is a temporary/test directory")
            print()
    else:
        print("  ✅ No suspicious directories found")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("✅ KEEP:")
    print("   - data/{lang}/levels/*.json (standard course levels)")
    print("   - data/{lang}/course.json (course metadata)")
    print("   - data/{lang}/practice_sessions.json (practice sessions)")
    print("   - data/users/user_{id}/{lang}/levels/*.json (user-specific level modifications)")
    print()
    print("❓ REVIEW:")
    print("   - data/__add_course__/ (check if this is a temporary/test directory)")
    print()
    print("❌ REMOVE:")
    print("   - Nothing identified as completely redundant")
    print()
    print("=" * 70)
    print("NOTE: The data/ folder is still actively used for standard course levels.")
    print("      Custom levels are stored in PostgreSQL, but standard levels are")
    print("      still stored as JSON files in the data/ folder.")
    print("=" * 70)

if __name__ == '__main__':
    analyze_data_folder()

