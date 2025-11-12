#!/usr/bin/env python3
"""
Create performance indexes on Railway (PostgreSQL).
This script connects to Railway's PostgreSQL database and creates all necessary indexes.
Run this locally with DATABASE_URL set to your Railway database URL.
"""

import os
import sys

# Check if DATABASE_URL is set
if not os.getenv('DATABASE_URL'):
    print("❌ Error: DATABASE_URL environment variable not set")
    print("   Set it to your Railway PostgreSQL connection string")
    print("   Example: export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
    sys.exit(1)

# Import after checking DATABASE_URL
from create_performance_indexes import create_performance_indexes

if __name__ == '__main__':
    print("🚀 Creating performance indexes on Railway PostgreSQL database...")
    print("=" * 60)
    success = create_performance_indexes()
    if success:
        print("\n✅ Performance indexes created successfully!")
        print("   Your app should now be significantly faster!")
    else:
        print("\n⚠️  Some indexes may have failed. Check errors above.")
        sys.exit(1)

