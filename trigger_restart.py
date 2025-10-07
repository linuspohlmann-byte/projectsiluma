#!/usr/bin/env python3
"""
Simple script to trigger Railway restart and database fix
"""

import os
import sys

def main():
    print("🚀 Triggering Railway restart...")
    
    # This file will be deleted after execution to trigger a restart
    if os.path.exists(__file__):
        try:
            os.remove(__file__)
            print("✅ Restart trigger file deleted - Railway should restart")
        except Exception as e:
            print(f"⚠️ Could not delete restart trigger: {e}")
    
    # Also try to run the database fix directly
    try:
        from emergency_fix import emergency_database_fix
        print("🔧 Running database fix directly...")
        success = emergency_database_fix()
        if success:
            print("✅ Database fix completed successfully!")
        else:
            print("⚠️ Database fix failed")
    except Exception as e:
        print(f"⚠️ Could not run database fix: {e}")

if __name__ == "__main__":
    main()
