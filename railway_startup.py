#!/usr/bin/env python3
"""
Railway startup script with better error handling
"""
import os
import sys
import traceback

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = [
        'OPENAI_API_KEY',
        'DATABASE_URL'
    ]
    
    optional_vars = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 
        'S3_BUCKET_NAME'
    ]
    
    print("🔍 Checking environment variables...")
    
    missing_required = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_required.append(var)
        else:
            print(f"✅ {var}: Set")
    
    missing_optional = []
    for var in optional_vars:
        if not os.environ.get(var):
            missing_optional.append(var)
        else:
            print(f"✅ {var}: Set")
    
    if missing_required:
        print(f"❌ Missing required variables: {', '.join(missing_required)}")
        return False
    
    if missing_optional:
        print(f"⚠️ Missing optional S3 variables: {', '.join(missing_optional)}")
        print("S3 integration will be disabled, using local file storage")
    else:
        print("✅ S3 integration enabled")
    
    return True

def test_imports():
    """Test critical imports"""
    print("🔍 Testing imports...")
    
    try:
        import flask
        print("✅ Flask import successful")
    except Exception as e:
        print(f"❌ Flask import failed: {e}")
        return False
    
    try:
        import boto3
        print("✅ Boto3 import successful")
    except Exception as e:
        print(f"❌ Boto3 import failed: {e}")
        return False
    
    try:
        from server.services.s3_storage import s3_storage
        print("✅ S3 storage import successful")
    except Exception as e:
        print(f"❌ S3 storage import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        from server.services.tts import ensure_tts_for_word
        print("✅ TTS service import successful")
    except Exception as e:
        print(f"❌ TTS service import failed: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_database_connection():
    """Test database connection"""
    print("🔍 Testing database connection...")
    
    try:
        from server.db import get_db
        conn = get_db()
        conn.close()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Main startup check"""
    print("🚀 Railway Startup Diagnostics")
    print("=" * 50)
    
    # Check environment
    if not check_environment():
        print("❌ Environment check failed")
        sys.exit(1)
    
    # Test imports
    if not test_imports():
        print("❌ Import test failed")
        sys.exit(1)
    
    # Test database
    if not test_database_connection():
        print("❌ Database test failed")
        sys.exit(1)
    
    print("=" * 50)
    print("✅ All startup checks passed!")
    print("🚀 Starting Flask application...")

    # Start the actual app
    try:
        from app import app
        print("✅ Flask application module imported.", flush=True)
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
        print("⚠️ Flask application exited unexpectedly.", flush=True)
    except Exception as e:
        print(f"❌ Flask app startup failed: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
