# Migration: Add New Topic Localizations

This migration adds localization entries for the new topic options (academic, family, immigration, culture, hobbies, healthcare, technology, romance, media) in all supported languages.

## What This Does

Adds PostgreSQL localization entries for:
- 9 new topic options (`topics.academic`, `topics.family`, etc.)
- 9 onboarding descriptions (`onboarding.topics.academic.desc`, etc.)
- All translations in 30+ languages

## How to Run

### Option 1: Via Railway CLI (Recommended)

```bash
railway run python3 migrate_topic_localizations.py
```

### Option 2: Via Railway Dashboard

1. Go to your Railway project
2. Open the service terminal
3. Run: `python3 migrate_topic_localizations.py`

### Option 3: Automatic on Next Deployment

The script can be integrated into the deployment process, or you can manually run it once after deployment.

## Verification

After running the migration, verify entries were added:

```bash
railway run python3 -c "
from server.db import get_localization_entry
print('Checking topics.academic:', get_localization_entry('topics.academic', 'de'))
print('Checking onboarding.topics.academic.desc:', get_localization_entry('onboarding.topics.academic.desc', 'de'))
"
```

## Languages Included

All entries include translations for:
- en, de, es, fr, it, pt, ru, tr, ka, nl, sv, no, da, fi, pl, cs, sk, hu, ro, bg, el, uk, zh, ja, ko, hi, ur, id, ms, th, vi, fa, ar, sw

## Notes

- The script uses `upsert_localization_entry` which will update existing entries if they already exist
- Safe to run multiple times
- Only works with PostgreSQL (not SQLite)

