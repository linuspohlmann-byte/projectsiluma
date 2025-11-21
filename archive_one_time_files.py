#!/usr/bin/env python3
"""
Script to safely archive one-time purpose files.

This script:
1. Verifies that migrations have been completed
2. Creates an archive folder with organized structure
3. Moves files to the archive
4. Creates a manifest and restore script
5. Provides verification and rollback capabilities
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# List of files to archive (from ONE_TIME_FILES_LIST.md)
FILES_TO_ARCHIVE = {
    'migrations': [
        'migrate_progress_cache.py',
        'migrate_topic_localizations.py',
        'add_topic_localizations.py',
        'add_topic_localizations_api.py',
    ],
    'imports': [
        'import_excel_localization.py',
        'import_words_from_json.py',
    ],
    'analysis_docs': [
        'A0_CEFR_FIX_COMPLETE.md',
        'A0_PERSISTENCE_FINAL_SOLUTION.md',
        'DEBUGGING_A0_PERSISTENCE.md',
        'DEPLOYMENT_FIXES.md',
        'EVALUATION_FIXES_FINAL.md',
        'EVALUATION_MIGRATION_SUMMARY.md',
        'LEVEL_LOADING_REDESIGN.md',
        'LEVEL_START_ANALYSIS.md',
        'LOG_ANALYSIS_ISSUES.md',
        'ONBOARDING_AUTO_IMPORT_FEATURE.md',
        'ONBOARDING_CRITICAL_FIX.md',
        'ONBOARDING_FIXES.md',
        'ONBOARDING_FIXES_V2.md',
        'ONBOARDING_FIXES_V3_FINAL.md',
        'PERFORMANCE_ANALYSIS.md',
        'PERFORMANCE_IMPLEMENTATION_SUMMARY.md',
        'PERFORMANCE_OPTIMIZATION_PLAN.md',
        'PERFORMANCE_OPTIMIZATION.md',
        'PRACTICE_ANALYSIS.md',
        'RAILWAY_MIGRATION_PLAN.md',
        'MIGRATE_TOPIC_LOCALIZATIONS.md',
    ],
    'setup_scripts': [
        'create_performance_indexes.py',
        'railway_create_indexes.py',
        'test_railway_migration.sh',
        'cleanup_redundant_files.py',
    ],
    'sql_files': [
        'create_test_user.sql',
        'create_user_word_familiarity_table.sql',
    ],
    'data_files': [
        'localization_complete.csv',
    ],
    'analysis_scripts': [
        'analyze_data_folder.py',
    ],
}

ARCHIVE_BASE = Path('archive_one_time_files')
ARCHIVE_DATE = datetime.now().strftime('%Y%m%d_%H%M%S')
ARCHIVE_DIR = ARCHIVE_BASE / f'archive_{ARCHIVE_DATE}'


def verify_migrations() -> Tuple[bool, List[str]]:
    """
    Verify that critical migrations have been completed.
    Returns (all_verified, warnings)
    """
    warnings = []
    all_verified = True
    
    print("🔍 Verifying migrations...")
    print("=" * 70)
    
    # Check if we're using PostgreSQL (production)
    database_url = os.getenv('DATABASE_URL')
    is_postgresql = database_url and 'postgresql' in database_url.lower()
    
    if is_postgresql:
        print("✅ PostgreSQL database detected (production environment)")
        
        # Try to verify migrations by checking for tables/features
        try:
            from server.db_config import get_db_connection, get_database_config
            from server.db import get_localization_entry
            
            config = get_database_config()
            if config.get('type') == 'postgresql':
                conn = get_db_connection()
                try:
                    # Check for custom_level_progress table (migrate_progress_cache.py)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'custom_level_progress'
                        )
                    """)
                    has_progress_table = cursor.fetchone()[0]
                    
                    if has_progress_table:
                        print("✅ custom_level_progress table exists (migrate_progress_cache.py completed)")
                    else:
                        warnings.append("⚠️  custom_level_progress table not found - migrate_progress_cache.py may not have run")
                        all_verified = False
                    
                    # Check for topic localizations (migrate_topic_localizations.py)
                    test_key = 'topics.academic'
                    test_entry = get_localization_entry(test_key, conn=conn)
                    if test_entry:
                        print("✅ Topic localizations exist (migrate_topic_localizations.py completed)")
                    else:
                        warnings.append("⚠️  Topic localizations not found - migrate_topic_localizations.py may not have run")
                    
                    # Check for user_word_familiarity table
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'user_word_familiarity'
                        )
                    """)
                    has_fam_table = cursor.fetchone()[0]
                    
                    if has_fam_table:
                        print("✅ user_word_familiarity table exists (create_user_word_familiarity_table.sql completed)")
                    else:
                        warnings.append("⚠️  user_word_familiarity table not found - create_user_word_familiarity_table.sql may not have run")
                    
                    cursor.close()
                finally:
                    conn.close()
        except Exception as e:
            warnings.append(f"⚠️  Could not verify migrations: {e}")
            print(f"⚠️  Migration verification skipped: {e}")
    else:
        print("ℹ️  SQLite database detected (local development)")
        print("   Migration verification skipped for local environment")
        warnings.append("ℹ️  Running in local environment - migrations should be verified in production")
    
    print("=" * 70)
    return all_verified, warnings


def create_archive_structure():
    """Create the archive directory structure"""
    print(f"\n📁 Creating archive structure: {ARCHIVE_DIR}")
    
    # Create main archive directory
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories for organization
    for category in FILES_TO_ARCHIVE.keys():
        (ARCHIVE_DIR / category).mkdir(exist_ok=True)
    
    print(f"✅ Archive structure created")


def archive_files() -> Dict[str, List[str]]:
    """
    Move files to archive.
    Returns dict of {category: [archived_files]}
    """
    archived = {category: [] for category in FILES_TO_ARCHIVE.keys()}
    not_found = []
    errors = []
    
    print(f"\n📦 Archiving files...")
    print("=" * 70)
    
    for category, files in FILES_TO_ARCHIVE.items():
        print(f"\n📂 Category: {category}")
        for filename in files:
            source = Path(filename)
            if source.exists():
                try:
                    dest = ARCHIVE_DIR / category / filename
                    shutil.move(str(source), str(dest))
                    archived[category].append(filename)
                    print(f"  ✅ {filename}")
                except Exception as e:
                    errors.append(f"{filename}: {e}")
                    print(f"  ❌ {filename}: {e}")
            else:
                not_found.append(filename)
                print(f"  ⚠️  {filename} (not found, skipping)")
    
    print("=" * 70)
    
    if not_found:
        print(f"\n⚠️  {len(not_found)} files not found (may have been deleted already):")
        for f in not_found:
            print(f"  - {f}")
    
    if errors:
        print(f"\n❌ {len(errors)} errors occurred:")
        for e in errors:
            print(f"  - {e}")
    
    return archived


def create_manifest(archived: Dict[str, List[str]], warnings: List[str]):
    """Create a manifest file documenting what was archived"""
    manifest = {
        'archive_date': ARCHIVE_DATE,
        'archive_path': str(ARCHIVE_DIR),
        'files_archived': {
            category: files for category, files in archived.items() if files
        },
        'total_files': sum(len(files) for files in archived.values()),
        'warnings': warnings,
        'restore_instructions': 'See restore_archive.sh for restore instructions'
    }
    
    manifest_path = ARCHIVE_DIR / 'manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n📄 Manifest created: {manifest_path}")
    return manifest


def create_restore_script(archived: Dict[str, List[str]]):
    """Create a restore script to move files back if needed"""
    restore_script = ARCHIVE_DIR / 'restore_archive.sh'
    
    script_content = f"""#!/bin/bash
# Restore script for archived one-time files
# Generated on {ARCHIVE_DATE}
# 
# This script restores all archived files to their original locations.
# Use with caution - only restore if you need these files again.

ARCHIVE_DIR="{ARCHIVE_DIR}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔄 Restoring archived files from $ARCHIVE_DIR"
echo ""

"""
    
    for category, files in archived.items():
        if files:
            script_content += f"# Category: {category}\n"
            for filename in files:
                script_content += f'echo "Restoring {filename}..."\n'
                script_content += f'mv "$ARCHIVE_DIR/{category}/{filename}" "$ROOT_DIR/{filename}"\n'
            script_content += "\n"
    
    script_content += """echo "✅ Restore complete!"
echo ""
echo "⚠️  Note: You may need to run migrations again if restoring migration scripts."
"""
    
    with open(restore_script, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(restore_script, 0o755)
    
    print(f"📜 Restore script created: {restore_script}")


def create_readme(manifest: Dict):
    """Create a README in the archive explaining what's here"""
    readme_path = ARCHIVE_DIR / 'README.md'
    
    readme_content = f"""# Archived One-Time Files

This archive contains files that served one-time purposes and are no longer required for ongoing maintenance.

## Archive Information

- **Archive Date**: {ARCHIVE_DATE}
- **Total Files**: {manifest['total_files']}
- **Archive Location**: `{ARCHIVE_DIR}`

## Contents

"""
    
    for category, files in manifest['files_archived'].items():
        if files:
            readme_content += f"### {category.replace('_', ' ').title()}\n\n"
            for filename in files:
                readme_content += f"- `{filename}`\n"
            readme_content += "\n"
    
    readme_content += """## Restore Instructions

If you need to restore any files:

1. Use the restore script: `./restore_archive.sh`
2. Or manually copy files from subdirectories back to the project root

## Warnings

"""
    
    if manifest['warnings']:
        for warning in manifest['warnings']:
            readme_content += f"- {warning}\n"
    else:
        readme_content += "- No warnings\n"
    
    readme_content += f"""
## Original List

See `ONE_TIME_FILES_LIST.md` in the project root for the complete list and descriptions.

## Notes

- Migration scripts should only be restored if you need to run them again
- Analysis documents are kept for historical reference
- Import scripts can be restored if you need to re-import data
"""
    
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print(f"📖 README created: {readme_path}")


def main():
    """Main archiving process"""
    print("=" * 70)
    print("ARCHIVE ONE-TIME FILES")
    print("=" * 70)
    print()
    
    # Step 1: Verify migrations
    all_verified, warnings = verify_migrations()
    
    if not all_verified and warnings:
        print("\n⚠️  WARNING: Some migrations may not be complete!")
        print("   Review the warnings above before proceeding.")
        response = input("\nContinue with archiving anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Archiving cancelled.")
            return
    
    # Step 2: Create archive structure
    create_archive_structure()
    
    # Step 3: Archive files
    archived = archive_files()
    
    total_archived = sum(len(files) for files in archived.values())
    if total_archived == 0:
        print("\n⚠️  No files were archived. They may have already been moved or deleted.")
        return
    
    # Step 4: Create manifest
    manifest = create_manifest(archived, warnings)
    
    # Step 5: Create restore script
    create_restore_script(archived)
    
    # Step 6: Create README
    create_readme(manifest)
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ ARCHIVING COMPLETE")
    print("=" * 70)
    print(f"\n📊 Summary:")
    print(f"   - Files archived: {total_archived}")
    print(f"   - Archive location: {ARCHIVE_DIR}")
    print(f"   - Manifest: {ARCHIVE_DIR / 'manifest.json'}")
    print(f"   - Restore script: {ARCHIVE_DIR / 'restore_archive.sh'}")
    print(f"\n💡 Next steps:")
    print(f"   1. Review the archived files in: {ARCHIVE_DIR}")
    print(f"   2. Test your application to ensure everything still works")
    print(f"   3. Commit the changes (archive folder and removed files)")
    print(f"   4. If needed, restore files using: {ARCHIVE_DIR / 'restore_archive.sh'}")
    print()


if __name__ == '__main__':
    import sys
    
    # Check for dry-run mode
    if '--dry-run' in sys.argv:
        print("🔍 DRY RUN MODE - No files will be moved")
        print("=" * 70)
        print("\nFiles that would be archived:")
        total = 0
        for category, files in FILES_TO_ARCHIVE.items():
            print(f"\n{category}:")
            for filename in files:
                exists = Path(filename).exists()
                status = "✅" if exists else "❌ (not found)"
                print(f"  {status} {filename}")
                if exists:
                    total += 1
        print(f"\nTotal files to archive: {total}")
        sys.exit(0)
    
    main()

