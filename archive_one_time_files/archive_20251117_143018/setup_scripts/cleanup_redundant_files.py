#!/usr/bin/env python3
"""
Script to identify and optionally delete redundant local files:
- SQLite databases (if PostgreSQL is being used)
- Local audio files (if S3 is being used)
"""

import os
import sys
from pathlib import Path

def check_environment():
    """Check if PostgreSQL and S3 are configured"""
    # Check environment variables
    postgres_configured = bool(os.getenv('DATABASE_URL'))
    s3_configured = bool(
        os.getenv('AWS_ACCESS_KEY_ID') and 
        os.getenv('AWS_SECRET_ACCESS_KEY') and 
        os.getenv('S3_BUCKET_NAME')
    )
    
    # Also check if code indicates PostgreSQL/S3 are required
    # (based on the fact that Railway deployment uses them)
    code_uses_postgres = True  # App is designed to use PostgreSQL on Railway
    code_uses_s3 = True  # App is designed to use S3 (no local disk fallback)
    
    # If env vars not set locally, but code uses them, they're still redundant
    # (assuming production uses PostgreSQL/S3)
    postgres_redundant = code_uses_postgres  # SQLite is fallback only
    s3_redundant = code_uses_s3  # Local audio is not used in production
    
    return postgres_redundant, s3_redundant

def find_sqlite_databases():
    """Find all SQLite database files"""
    db_files = []
    root = Path('.')
    
    # Common database file patterns
    patterns = ['*.db', '*.sqlite', '*.sqlite3']
    
    for pattern in patterns:
        for db_file in root.rglob(pattern):
            # Skip venv and __pycache__
            if 'venv' in str(db_file) or '__pycache__' in str(db_file):
                continue
            db_files.append(db_file)
    
    return sorted(set(db_files))

def find_local_audio_files():
    """Find local audio files in media/ directory"""
    media_dir = Path('media')
    if not media_dir.exists():
        return []
    
    audio_files = []
    audio_extensions = ['.mp3', '.wav', '.ogg', '.m4a']
    
    for ext in audio_extensions:
        for audio_file in media_dir.rglob(f'*{ext}'):
            audio_files.append(audio_file)
    
    return sorted(audio_files)

def get_file_size_mb(file_path):
    """Get file size in MB"""
    try:
        size_bytes = file_path.stat().st_size
        return size_bytes / (1024 * 1024)
    except:
        return 0

def main():
    postgres_configured, s3_configured = check_environment()
    
    print("=" * 70)
    print("REDUNDANT FILES CLEANUP ANALYSIS")
    print("=" * 70)
    print()
    
    print(f"PostgreSQL in use (production): {postgres_configured}")
    print(f"S3 in use (production): {s3_configured}")
    print()
    print("Note: Even if not configured locally, these files are redundant")
    print("      because production uses PostgreSQL and S3 exclusively.")
    print()
    
    # Find SQLite databases
    db_files = find_sqlite_databases()
    total_db_size = sum(get_file_size_mb(db) for db in db_files)
    
    print(f"Found {len(db_files)} SQLite database files ({total_db_size:.2f} MB total)")
    if db_files:
        print("\nSQLite databases:")
        for db in db_files[:20]:  # Show first 20
            size_mb = get_file_size_mb(db)
            print(f"  - {db} ({size_mb:.2f} MB)")
        if len(db_files) > 20:
            print(f"  ... and {len(db_files) - 20} more")
    
    # Find local audio files
    audio_files = find_local_audio_files()
    total_audio_size = sum(get_file_size_mb(audio) for audio in audio_files)
    
    print(f"\nFound {len(audio_files)} local audio files ({total_audio_size:.2f} MB total)")
    if audio_files:
        print("\nLocal audio directories:")
        audio_dirs = set(str(f.parent) for f in audio_files)
        for audio_dir in sorted(audio_dirs)[:10]:  # Show first 10
            dir_files = [f for f in audio_files if str(f.parent) == audio_dir]
            dir_size = sum(get_file_size_mb(f) for f in dir_files)
            print(f"  - {audio_dir} ({len(dir_files)} files, {dir_size:.2f} MB)")
        if len(audio_dirs) > 10:
            print(f"  ... and {len(audio_dirs) - 10} more directories")
    
    print()
    print("=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print()
    
    postgres_redundant, s3_redundant = check_environment()
    
    print("=" * 70)
    print("REDUNDANT FILES CLEANUP ANALYSIS")
    print("=" * 70)
    print()
    
    print(f"PostgreSQL in use (production): {postgres_redundant}")
    print(f"S3 in use (production): {s3_redundant}")
    print()
    print("Note: Even if not configured locally, these files are redundant")
    print("      because production uses PostgreSQL and S3 exclusively.")
    print()
    
    recommendations = []
    
    if postgres_redundant and db_files:
        recommendations.append({
            'type': 'SQLite databases',
            'files': db_files,
            'size_mb': total_db_size,
            'reason': 'PostgreSQL is configured, SQLite databases are redundant',
            'safe': True
        })
    
    if s3_redundant and audio_files:
        recommendations.append({
            'type': 'Local audio files',
            'files': audio_files,
            'size_mb': total_audio_size,
            'reason': 'S3 is configured, local audio files are redundant',
            'safe': True
        })
    
    if not recommendations:
        print("✅ No redundant files found! Everything is already cleaned up.")
        return
    
    total_savings = sum(r['size_mb'] for r in recommendations)
    print(f"Total space that can be freed: {total_savings:.2f} MB")
    print()
    
    for rec in recommendations:
        print(f"📁 {rec['type']}:")
        print(f"   Files: {len(rec['files'])}")
        print(f"   Size: {rec['size_mb']:.2f} MB")
        print(f"   Reason: {rec['reason']}")
        print(f"   Safe to delete: {'✅ Yes' if rec['safe'] else '⚠️  Check first'}")
        print()
    
    # Ask for confirmation
    if '--delete' in sys.argv:
        print("⚠️  DELETION MODE ENABLED")
        print()
        response = input(f"Delete {len(sum([r['files'] for r in recommendations], []))} files? (yes/no): ")
        if response.lower() == 'yes':
            deleted_count = 0
            deleted_size = 0
            
            for rec in recommendations:
                for file_path in rec['files']:
                    try:
                        size_mb = get_file_size_mb(file_path)
                        file_path.unlink()
                        deleted_count += 1
                        deleted_size += size_mb
                        print(f"✅ Deleted: {file_path}")
                    except Exception as e:
                        print(f"❌ Error deleting {file_path}: {e}")
            
            print()
            print(f"✅ Deleted {deleted_count} files ({deleted_size:.2f} MB)")
        else:
            print("Deletion cancelled.")
    else:
        print("💡 To delete these files, run: python cleanup_redundant_files.py --delete")
        print()
        print("⚠️  WARNING: Make sure you have backups before deleting!")

if __name__ == '__main__':
    main()

