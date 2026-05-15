#!/bin/bash
# Restore script for archived one-time files
# Generated on 20251117_143018
# 
# This script restores all archived files to their original locations.
# Use with caution - only restore if you need these files again.

ARCHIVE_DIR="archive_one_time_files/archive_20251117_143018"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔄 Restoring archived files from $ARCHIVE_DIR"
echo ""

# Category: migrations
echo "Restoring migrate_progress_cache.py..."
mv "$ARCHIVE_DIR/migrations/migrate_progress_cache.py" "$ROOT_DIR/migrate_progress_cache.py"
echo "Restoring migrate_topic_localizations.py..."
mv "$ARCHIVE_DIR/migrations/migrate_topic_localizations.py" "$ROOT_DIR/migrate_topic_localizations.py"
echo "Restoring add_topic_localizations.py..."
mv "$ARCHIVE_DIR/migrations/add_topic_localizations.py" "$ROOT_DIR/add_topic_localizations.py"
echo "Restoring add_topic_localizations_api.py..."
mv "$ARCHIVE_DIR/migrations/add_topic_localizations_api.py" "$ROOT_DIR/add_topic_localizations_api.py"

# Category: imports
echo "Restoring import_excel_localization.py..."
mv "$ARCHIVE_DIR/imports/import_excel_localization.py" "$ROOT_DIR/import_excel_localization.py"
echo "Restoring import_words_from_json.py..."
mv "$ARCHIVE_DIR/imports/import_words_from_json.py" "$ROOT_DIR/import_words_from_json.py"

# Category: analysis_docs
echo "Restoring A0_CEFR_FIX_COMPLETE.md..."
mv "$ARCHIVE_DIR/analysis_docs/A0_CEFR_FIX_COMPLETE.md" "$ROOT_DIR/A0_CEFR_FIX_COMPLETE.md"
echo "Restoring A0_PERSISTENCE_FINAL_SOLUTION.md..."
mv "$ARCHIVE_DIR/analysis_docs/A0_PERSISTENCE_FINAL_SOLUTION.md" "$ROOT_DIR/A0_PERSISTENCE_FINAL_SOLUTION.md"
echo "Restoring DEBUGGING_A0_PERSISTENCE.md..."
mv "$ARCHIVE_DIR/analysis_docs/DEBUGGING_A0_PERSISTENCE.md" "$ROOT_DIR/DEBUGGING_A0_PERSISTENCE.md"
echo "Restoring DEPLOYMENT_FIXES.md..."
mv "$ARCHIVE_DIR/analysis_docs/DEPLOYMENT_FIXES.md" "$ROOT_DIR/DEPLOYMENT_FIXES.md"
echo "Restoring EVALUATION_FIXES_FINAL.md..."
mv "$ARCHIVE_DIR/analysis_docs/EVALUATION_FIXES_FINAL.md" "$ROOT_DIR/EVALUATION_FIXES_FINAL.md"
echo "Restoring EVALUATION_MIGRATION_SUMMARY.md..."
mv "$ARCHIVE_DIR/analysis_docs/EVALUATION_MIGRATION_SUMMARY.md" "$ROOT_DIR/EVALUATION_MIGRATION_SUMMARY.md"
echo "Restoring LEVEL_LOADING_REDESIGN.md..."
mv "$ARCHIVE_DIR/analysis_docs/LEVEL_LOADING_REDESIGN.md" "$ROOT_DIR/LEVEL_LOADING_REDESIGN.md"
echo "Restoring LEVEL_START_ANALYSIS.md..."
mv "$ARCHIVE_DIR/analysis_docs/LEVEL_START_ANALYSIS.md" "$ROOT_DIR/LEVEL_START_ANALYSIS.md"
echo "Restoring LOG_ANALYSIS_ISSUES.md..."
mv "$ARCHIVE_DIR/analysis_docs/LOG_ANALYSIS_ISSUES.md" "$ROOT_DIR/LOG_ANALYSIS_ISSUES.md"
echo "Restoring ONBOARDING_AUTO_IMPORT_FEATURE.md..."
mv "$ARCHIVE_DIR/analysis_docs/ONBOARDING_AUTO_IMPORT_FEATURE.md" "$ROOT_DIR/ONBOARDING_AUTO_IMPORT_FEATURE.md"
echo "Restoring ONBOARDING_CRITICAL_FIX.md..."
mv "$ARCHIVE_DIR/analysis_docs/ONBOARDING_CRITICAL_FIX.md" "$ROOT_DIR/ONBOARDING_CRITICAL_FIX.md"
echo "Restoring ONBOARDING_FIXES.md..."
mv "$ARCHIVE_DIR/analysis_docs/ONBOARDING_FIXES.md" "$ROOT_DIR/ONBOARDING_FIXES.md"
echo "Restoring ONBOARDING_FIXES_V2.md..."
mv "$ARCHIVE_DIR/analysis_docs/ONBOARDING_FIXES_V2.md" "$ROOT_DIR/ONBOARDING_FIXES_V2.md"
echo "Restoring ONBOARDING_FIXES_V3_FINAL.md..."
mv "$ARCHIVE_DIR/analysis_docs/ONBOARDING_FIXES_V3_FINAL.md" "$ROOT_DIR/ONBOARDING_FIXES_V3_FINAL.md"
echo "Restoring PERFORMANCE_ANALYSIS.md..."
mv "$ARCHIVE_DIR/analysis_docs/PERFORMANCE_ANALYSIS.md" "$ROOT_DIR/PERFORMANCE_ANALYSIS.md"
echo "Restoring PERFORMANCE_IMPLEMENTATION_SUMMARY.md..."
mv "$ARCHIVE_DIR/analysis_docs/PERFORMANCE_IMPLEMENTATION_SUMMARY.md" "$ROOT_DIR/PERFORMANCE_IMPLEMENTATION_SUMMARY.md"
echo "Restoring PERFORMANCE_OPTIMIZATION_PLAN.md..."
mv "$ARCHIVE_DIR/analysis_docs/PERFORMANCE_OPTIMIZATION_PLAN.md" "$ROOT_DIR/PERFORMANCE_OPTIMIZATION_PLAN.md"
echo "Restoring PERFORMANCE_OPTIMIZATION.md..."
mv "$ARCHIVE_DIR/analysis_docs/PERFORMANCE_OPTIMIZATION.md" "$ROOT_DIR/PERFORMANCE_OPTIMIZATION.md"
echo "Restoring PRACTICE_ANALYSIS.md..."
mv "$ARCHIVE_DIR/analysis_docs/PRACTICE_ANALYSIS.md" "$ROOT_DIR/PRACTICE_ANALYSIS.md"
echo "Restoring RAILWAY_MIGRATION_PLAN.md..."
mv "$ARCHIVE_DIR/analysis_docs/RAILWAY_MIGRATION_PLAN.md" "$ROOT_DIR/RAILWAY_MIGRATION_PLAN.md"
echo "Restoring MIGRATE_TOPIC_LOCALIZATIONS.md..."
mv "$ARCHIVE_DIR/analysis_docs/MIGRATE_TOPIC_LOCALIZATIONS.md" "$ROOT_DIR/MIGRATE_TOPIC_LOCALIZATIONS.md"

# Category: setup_scripts
echo "Restoring create_performance_indexes.py..."
mv "$ARCHIVE_DIR/setup_scripts/create_performance_indexes.py" "$ROOT_DIR/create_performance_indexes.py"
echo "Restoring railway_create_indexes.py..."
mv "$ARCHIVE_DIR/setup_scripts/railway_create_indexes.py" "$ROOT_DIR/railway_create_indexes.py"
echo "Restoring test_railway_migration.sh..."
mv "$ARCHIVE_DIR/setup_scripts/test_railway_migration.sh" "$ROOT_DIR/test_railway_migration.sh"
echo "Restoring cleanup_redundant_files.py..."
mv "$ARCHIVE_DIR/setup_scripts/cleanup_redundant_files.py" "$ROOT_DIR/cleanup_redundant_files.py"

# Category: sql_files
echo "Restoring create_test_user.sql..."
mv "$ARCHIVE_DIR/sql_files/create_test_user.sql" "$ROOT_DIR/create_test_user.sql"
echo "Restoring create_user_word_familiarity_table.sql..."
mv "$ARCHIVE_DIR/sql_files/create_user_word_familiarity_table.sql" "$ROOT_DIR/create_user_word_familiarity_table.sql"

# Category: data_files
echo "Restoring localization_complete.csv..."
mv "$ARCHIVE_DIR/data_files/localization_complete.csv" "$ROOT_DIR/localization_complete.csv"

# Category: analysis_scripts
echo "Restoring analyze_data_folder.py..."
mv "$ARCHIVE_DIR/analysis_scripts/analyze_data_folder.py" "$ROOT_DIR/analyze_data_folder.py"

echo "✅ Restore complete!"
echo ""
echo "⚠️  Note: You may need to run migrations again if restoring migration scripts."
