# Archived One-Time Files

This archive contains files that served one-time purposes and are no longer required for ongoing maintenance.

## Archive Information

- **Archive Date**: 20251117_143018
- **Total Files**: 35
- **Archive Location**: `archive_one_time_files/archive_20251117_143018`

## Contents

### Migrations

- `migrate_progress_cache.py`
- `migrate_topic_localizations.py`
- `add_topic_localizations.py`
- `add_topic_localizations_api.py`

### Imports

- `import_excel_localization.py`
- `import_words_from_json.py`

### Analysis Docs

- `A0_CEFR_FIX_COMPLETE.md`
- `A0_PERSISTENCE_FINAL_SOLUTION.md`
- `DEBUGGING_A0_PERSISTENCE.md`
- `DEPLOYMENT_FIXES.md`
- `EVALUATION_FIXES_FINAL.md`
- `EVALUATION_MIGRATION_SUMMARY.md`
- `LEVEL_LOADING_REDESIGN.md`
- `LEVEL_START_ANALYSIS.md`
- `LOG_ANALYSIS_ISSUES.md`
- `ONBOARDING_AUTO_IMPORT_FEATURE.md`
- `ONBOARDING_CRITICAL_FIX.md`
- `ONBOARDING_FIXES.md`
- `ONBOARDING_FIXES_V2.md`
- `ONBOARDING_FIXES_V3_FINAL.md`
- `PERFORMANCE_ANALYSIS.md`
- `PERFORMANCE_IMPLEMENTATION_SUMMARY.md`
- `PERFORMANCE_OPTIMIZATION_PLAN.md`
- `PERFORMANCE_OPTIMIZATION.md`
- `PRACTICE_ANALYSIS.md`
- `RAILWAY_MIGRATION_PLAN.md`
- `MIGRATE_TOPIC_LOCALIZATIONS.md`

### Setup Scripts

- `create_performance_indexes.py`
- `railway_create_indexes.py`
- `test_railway_migration.sh`
- `cleanup_redundant_files.py`

### Sql Files

- `create_test_user.sql`
- `create_user_word_familiarity_table.sql`

### Data Files

- `localization_complete.csv`

### Analysis Scripts

- `analyze_data_folder.py`

## Restore Instructions

If you need to restore any files:

1. Use the restore script: `./restore_archive.sh`
2. Or manually copy files from subdirectories back to the project root

## Warnings

- ℹ️  Running in local environment - migrations should be verified in production

## Original List

See `ONE_TIME_FILES_LIST.md` in the project root for the complete list and descriptions.

## Notes

- Migration scripts should only be restored if you need to run them again
- Analysis documents are kept for historical reference
- Import scripts can be restored if you need to re-import data
