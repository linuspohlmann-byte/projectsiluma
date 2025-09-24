import os
import sqlite3
from urllib.parse import urlparse

# Conditional import for PostgreSQL
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("WARNING: psycopg2 not available. PostgreSQL support disabled.")

def get_database_config():
    """Get database configuration based on environment"""
    # Check if we're in production (Railway)
    if os.getenv('DATABASE_URL') and PSYCOPG2_AVAILABLE:
        # Production: Try PostgreSQL first, fallback to SQLite if it fails
        try:
            # Test PostgreSQL connection
            parsed = urlparse(os.getenv('DATABASE_URL'))
            test_conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password
            )
            test_conn.close()
            return {
                'type': 'postgresql',
                'url': os.getenv('DATABASE_URL')
            }
        except Exception as e:
            print(f"WARNING: PostgreSQL connection failed, falling back to SQLite: {e}")
            return {
                'type': 'sqlite',
                'path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'polo.db')
            }
    else:
        # Development: Use SQLite
        if os.getenv('DATABASE_URL') and not PSYCOPG2_AVAILABLE:
            print("WARNING: DATABASE_URL set but psycopg2 not available. Using SQLite instead.")
        return {
            'type': 'sqlite',
            'path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'polo.db')
        }

def get_db_connection():
    """Get database connection based on environment"""
    config = get_database_config()
    
    if config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
        try:
            # Parse DATABASE_URL
            parsed = urlparse(config['url'])
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],  # Remove leading slash
                user=parsed.username,
                password=parsed.password,
                cursor_factory=RealDictCursor  # This makes rows behave like dicts
            )
            conn.autocommit = False  # Use explicit transactions for better control
            return conn
        except Exception as e:
            print(f"ERROR: Failed to connect to PostgreSQL: {e}")
            print(f"ERROR: DATABASE_URL: {config['url']}")
            # Fallback to SQLite if PostgreSQL fails
            print("Falling back to SQLite...")
            config['type'] = 'sqlite'
            config['path'] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'polo.db')
    
    # SQLite (either primary or fallback)
    try:
        conn = sqlite3.connect(config['path'])
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"ERROR: Failed to connect to SQLite: {e}")
        print(f"ERROR: SQLite path: {config['path']}")
        raise e

def get_db_cursor(conn):
    """Get appropriate cursor for database type"""
    config = get_database_config()
    
    if config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
        return conn.cursor(cursor_factory=RealDictCursor)
    else:
        return conn.cursor()

def execute_query(conn, query, params=None):
    """Execute query with appropriate parameter style"""
    config = get_database_config()
    cursor = get_db_cursor(conn)
    
    if config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
        # PostgreSQL uses %s for parameters
        if params:
            cursor.execute(query.replace('?', '%s'), params)
        else:
            cursor.execute(query.replace('?', '%s'))
    else:
        # SQLite uses ? for parameters
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
    
    return cursor

def get_lastrowid(cursor):
    """Get last inserted row ID"""
    config = get_database_config()
    
    if config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
        return cursor.fetchone()['id'] if cursor.description else None
    else:
        return cursor.lastrowid
