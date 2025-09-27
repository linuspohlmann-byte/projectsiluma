#!/usr/bin/env python3
"""
WSGI entry point for Railway hosting
"""

import os
import sys
import threading
import time

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Set environment variables for production
os.environ.setdefault('FLASK_ENV', 'production')

def periodic_sync():
    """Periodic synchronization of user data"""
    try:
        from server.db_config import get_database_config
        config = get_database_config()
        
        # Only run sync for SQLite (not PostgreSQL on Railway)
        if config['type'] == 'sqlite':
            from server.db import get_db
            from server.db_multi_user import get_user_native_language
            from server.services.user_data import migrate_user_data_structure
            
            # Get all active users
            conn = get_db()
            try:
                users = conn.execute("SELECT id FROM users WHERE is_active = 1").fetchall()
                for user in users:
                    user_id = user['id']
                    try:
                        # Ensure user databases exist and are synced
                        native_lang = get_user_native_language(user_id)
                        if native_lang:
                            from server.db_multi_user import ensure_user_databases
                            ensure_user_databases(user_id, native_lang)
                            
                            # Migrate user data if needed
                            migrate_user_data_structure(user_id)
                    except Exception as user_error:
                        print(f"Error syncing user {user_id}: {user_error}")
            finally:
                conn.close()
        else:
            print("PostgreSQL detected - skipping periodic sync")
    except Exception as e:
        print(f"Error in periodic sync: {e}")

def start_background_sync():
    """Start background synchronization thread"""
    try:
        # Check database type first
        from server.db_config import get_database_config
        config = get_database_config()
        
        print(f"🚀 Starting ProjectSiluma with {config['type']} database...")
        
        # Initialize the main database
        from server.db import init_db
        init_db()
        print("✅ Main database initialized")
        
        # Only run sync for SQLite (PostgreSQL doesn't need it)
        if config['type'] == 'sqlite':
            from server.database_sync import sync_databases_on_startup
            sync_databases_on_startup()
            print("✅ Database sync completed")
            
            # Start periodic sync thread only for SQLite
            def sync_worker():
                while True:
                    time.sleep(300)  # 5 minutes
                    periodic_sync()
            
            sync_thread = threading.Thread(target=sync_worker, daemon=True)
            sync_thread.start()
            print("🔄 Periodic sync started (every 5 minutes)")
        else:
            print("✅ PostgreSQL detected - no sync needed")
        
    except Exception as e:
        print(f"Warning: Could not start background sync: {e}")
        # Try to initialize database anyway
        try:
            from server.db import init_db
            init_db()
            print("✅ Database initialized as fallback")
        except Exception as db_error:
            print(f"❌ Database initialization failed: {db_error}")

try:
    # Import the Flask app
    from app import app
    
    # Configure app for Railway
    try:
        from config_railway import RailwayConfig
        app.config.from_object(RailwayConfig)
        RailwayConfig.init_app(app)
        print("✅ Railway configuration loaded")
    except Exception as config_error:
        print(f"⚠️  Warning: Could not load Railway config: {config_error}")
    
    # Add CORS support for Railway
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    
    # Add OPTIONS handler for CORS preflight requests
    @app.route('/<path:path>', methods=['OPTIONS'])
    def handle_options(path):
        return '', 200
    
    # Start background sync for Railway
    start_background_sync()
    
    # This is the WSGI application that Railway will use
    application = app
    
    # For local testing
    if __name__ == "__main__":
        port = int(os.environ.get('PORT', 5000))
        app.run(debug=False, host='0.0.0.0', port=port)
        
except Exception as e:
    # Log the error for debugging
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logging.error(f"Failed to import Flask app: {e}")
    raise
