#!/usr/bin/env python3
"""
Create a test user for local development
"""
import os
import sys

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Set environment to use SQLite for local development
os.environ.setdefault('FLASK_ENV', 'development')
if not os.environ.get('DATABASE_URL'):
    # Force SQLite for local development
    os.environ['DATABASE_URL'] = ''

# Mock postgres module if pg8000 is not available
import sys
class MockPostgres:
    class RealDictCursor:
        pass

if 'server.postgres' not in sys.modules:
    try:
        from server import postgres
    except RuntimeError:
        # PostgreSQL not available, mock it
        import types
        mock_postgres = types.ModuleType('server.postgres')
        mock_postgres.RealDictCursor = type('RealDictCursor', (), {})
        sys.modules['server.postgres'] = mock_postgres

from server.db import init_db, get_user_by_username
from server.services.auth import register_user

def create_test_user(username='testuser', email='test@example.com', password='password123'):
    """Create a test user for local development"""
    try:
        # Initialize database
        print("🔧 Initializing database...")
        init_db()
        print("✅ Database initialized")
        
        # Check if user already exists
        existing_user = get_user_by_username(username)
        if existing_user:
            print(f"⚠️  User '{username}' already exists!")
            print(f"   User ID: {existing_user.get('id') if isinstance(existing_user, dict) else existing_user['id']}")
            print(f"   Email: {existing_user.get('email') if isinstance(existing_user, dict) else existing_user['email']}")
            return False
        
        # Create user
        print(f"👤 Creating user '{username}'...")
        result = register_user(username, email, password)
        
        if result['success']:
            print(f"✅ User created successfully!")
            print(f"   Username: {username}")
            print(f"   Email: {email}")
            print(f"   Password: {password}")
            print(f"   User ID: {result.get('user_id')}")
            print(f"   Session Token: {result.get('session_token')}")
            return True
        else:
            print(f"❌ Failed to create user: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Create a test user for local development')
    parser.add_argument('--username', default='testuser', help='Username (default: testuser)')
    parser.add_argument('--email', default='test@example.com', help='Email (default: test@example.com)')
    parser.add_argument('--password', default='password123', help='Password (default: password123)')
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("🚀 Creating test user for local development")
    print("=" * 50)
    
    success = create_test_user(args.username, args.email, args.password)
    
    if success:
        print("=" * 50)
        print("✅ Test user created! You can now log in with:")
        print(f"   Username: {args.username}")
        print(f"   Password: {args.password}")
        print("=" * 50)
    else:
        print("=" * 50)
        print("❌ Failed to create test user")
        print("=" * 50)
        sys.exit(1)

