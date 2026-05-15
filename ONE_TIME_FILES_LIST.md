# One-Time Purpose Files - No Longer Required

This document lists files that served a one-time purpose and are no longer required for the maintenance and usage of the application.

## Migration Scripts (One-Time Database Migrations)

These scripts were used to migrate data or create database structures once:

1. **`migrate_progress_cache.py`** - Migration script to create custom_level_progress table and populate initial data
2. **`migrate_topic_localizations.py`** - Migration script to add new topic localization entries (already run on Railway)
3. **`add_topic_localizations.py`** - Script to add localization entries for new topic options (duplicate of migrate_topic_localizations.py)
4. **`add_topic_localizations_api.py`** - Script to add localization entries via API (alternative method, no longer needed)

## One-Time Import Scripts

These scripts were used to import data once:

5. **`import_excel_localization.py`** - Script to import localization data from CSV/Excel files (one-time data import)
6. **`import_words_from_json.py`** - Script to import words from JSON level files into local SQLite database (pre-migration preparation)

## One-Time Analysis/Debugging Documents

These markdown files document one-time fixes, analyses, or debugging sessions:

7. **`A0_CEFR_FIX_COMPLETE.md`** - Documentation of a completed fix for A0 CEFR level
8. **`A0_PERSISTENCE_FINAL_SOLUTION.md`** - Final solution documentation for A0 persistence issue
9. **`DEBUGGING_A0_PERSISTENCE.md`** - Debugging notes for A0 persistence issue
10. **`DEPLOYMENT_FIXES.md`** - Documentation of one-time deployment fixes
11. **`EVALUATION_FIXES_FINAL.md`** - Final fixes documentation for evaluation feature
12. **`EVALUATION_MIGRATION_SUMMARY.md`** - Summary of evaluation migration (one-time)
13. **`LEVEL_LOADING_REDESIGN.md`** - Documentation of level loading redesign (completed)
14. **`LEVEL_START_ANALYSIS.md`** - Analysis document for level start events (one-time analysis)
15. **`LOG_ANALYSIS_ISSUES.md`** - One-time log analysis document
16. **`ONBOARDING_AUTO_IMPORT_FEATURE.md`** - Documentation of onboarding auto-import feature (completed)
17. **`ONBOARDING_CRITICAL_FIX.md`** - Critical fix documentation for onboarding (completed)
18. **`ONBOARDING_FIXES.md`** - Onboarding fixes documentation (superseded by later versions)
19. **`ONBOARDING_FIXES_V2.md`** - Onboarding fixes v2 documentation (superseded by v3)
20. **`ONBOARDING_FIXES_V3_FINAL.md`** - Final onboarding fixes documentation (completed)
21. **`PERFORMANCE_ANALYSIS.md`** - One-time performance analysis document
22. **`PERFORMANCE_IMPLEMENTATION_SUMMARY.md`** - Summary of performance implementation (completed)
23. **`PERFORMANCE_OPTIMIZATION_PLAN.md`** - Planning document for performance optimization (completed)
24. **`PERFORMANCE_OPTIMIZATION.md`** - Performance optimization documentation (completed)
25. **`PRACTICE_ANALYSIS.md`** - One-time analysis document for practice functionality
26. **`RAILWAY_MIGRATION_PLAN.md`** - Migration plan document (completed migration)
27. **`MIGRATE_TOPIC_LOCALIZATIONS.md`** - Documentation for topic localizations migration (completed)

## One-Time Setup Scripts

These scripts were used for initial setup or one-time configuration:

28. **`create_performance_indexes.py`** - Script to create database indexes (can be run multiple times, but indexes persist, so not needed regularly)
29. **`railway_create_indexes.py`** - Railway-specific version of index creation script (one-time setup)
30. **`test_railway_migration.sh`** - Test script for Railway migration (one-time testing)
31. **`cleanup_redundant_files.py`** - Script to identify and clean up redundant files (one-time cleanup)

## One-Time SQL Setup Files

These SQL files were used for one-time database setup:

32. **`create_test_user.sql`** - SQL script to create a test user (one-time setup)
33. **`create_user_word_familiarity_table.sql`** - SQL script to create user_word_familiarity table (one-time table creation)

## One-Time Data Files

34. **`localization_complete.csv`** - CSV file with complete localization data (already imported, no longer needed)

## Analysis/Utility Scripts (One-Time Use)

35. **`analyze_data_folder.py`** - Script to analyze data folder structure (one-time analysis)

## Notes

- **`railway_startup.py`** - This file may still be used by Railway for startup, so it should be kept
- **`pre_deploy_check.sh`** - This is used regularly before deployment, so it should be kept
- **`polo.db`** - This appears to be a local SQLite database file that may be redundant if using PostgreSQL in production, but should be verified before deletion
- Configuration files (`config_*.py`, `*.env` files) should be kept as they may be needed for different environments

## Summary

**Total: 35 files** that served one-time purposes and are no longer required for ongoing maintenance and usage of the application.

## ✅ ARCHIVED

**Status**: All files have been successfully archived on November 17, 2025.

**Archive Location**: `archive_one_time_files/archive_20251117_143018/`

**See**: `ARCHIVE_SUMMARY.md` for complete archive details and restore instructions.

These files have been safely moved to the archive folder and can be restored if needed using the restore script in the archive directory.

