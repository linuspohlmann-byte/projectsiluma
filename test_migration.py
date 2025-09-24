#!/usr/bin/env python3
"""
Test script to verify database migration works correctly
"""

import os
import sys
from server.db_config import get_database_config, get_db_connection

def test_database_connection():
    """Test database connection and configuration"""
    print("🔍 Testing database configuration...")
    
    config = get_database_config()
    print(f"📊 Database type: {config['type']}")
    
    if config['type'] == 'postgresql':
        print(f"🔗 PostgreSQL URL: {config['url'][:50]}...")
    else:
        print(f"📁 SQLite path: {config['path']}")
    
    try:
        conn = get_db_connection()
        print("✅ Database connection successful!")
        
        # Test basic query
        cursor = conn.cursor()
        if config['type'] == 'postgresql':
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
            print(f"🐘 PostgreSQL version: {version[0]}")
        else:
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()
            print(f"🗃️ SQLite version: {version[0]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_table_creation():
    """Test table creation"""
    print("\n🔨 Testing table creation...")
    
    try:
        from server.db import init_db
        init_db()
        print("✅ Tables created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Table creation failed: {e}")
        return False

def test_basic_operations():
    """Test basic database operations"""
    print("\n🧪 Testing basic operations...")
    
    try:
        from server.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        # Test insert
        config = get_database_config()
        if config['type'] == 'postgresql':
            cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id", 
                         ('test_user', 'test@example.com', 'test_hash'))
            user_id = cursor.fetchone()['id']
        else:
            cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", 
                         ('test_user', 'test@example.com', 'test_hash'))
            user_id = cursor.lastrowid
        
        print(f"✅ User created with ID: {user_id}")
        
        # Test select
        if config['type'] == 'postgresql':
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        else:
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        
        user = cursor.fetchone()
        print(f"✅ User retrieved: {user['username']}")
        
        # Test delete
        if config['type'] == 'postgresql':
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        else:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        
        print("✅ User deleted successfully!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Basic operations failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting database migration test...\n")
    
    # Test 1: Database connection
    if not test_database_connection():
        print("\n❌ Database connection test failed!")
        return False
    
    # Test 2: Table creation
    if not test_table_creation():
        print("\n❌ Table creation test failed!")
        return False
    
    # Test 3: Basic operations
    if not test_basic_operations():
        print("\n❌ Basic operations test failed!")
        return False
    
    print("\n🎉 All tests passed! Migration is working correctly!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
