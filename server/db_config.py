import os
import sqlite3

# Conditional import for PostgreSQL drivers
PSYCOPG2_AVAILABLE = False
PSYCOPG2_EXECUTE_VALUES = None
POSTGRES_DRIVER = None
USING_PSYCOPG3 = False

try:  # Prefer latest psycopg (v3) driver
    import psycopg
    from psycopg.rows import dict_row as _psycopg_dict_row
    from psycopg.extras import execute_values as _psycopg_execute_values

    POSTGRES_DRIVER = "psycopg"
    USING_PSYCOPG3 = True
    PSYCOPG2_AVAILABLE = True  # maintain legacy flag name for callers
    PSYCOPG2_EXECUTE_VALUES = _psycopg_execute_values
except ImportError:
    try:  # Fall back to psycopg2 if present
        import psycopg2  # type: ignore
        from psycopg2.extras import RealDictCursor, execute_values as psycopg2_execute_values

        POSTGRES_DRIVER = "psycopg2"
        USING_PSYCOPG3 = False
        PSYCOPG2_AVAILABLE = True
        PSYCOPG2_EXECUTE_VALUES = psycopg2_execute_values
    except ImportError:
        psycopg2 = None  # type: ignore
        POSTGRES_DRIVER = None
        USING_PSYCOPG3 = False
        PSYCOPG2_AVAILABLE = False
        PSYCOPG2_EXECUTE_VALUES = None
        print("WARNING: PostgreSQL driver not available. PostgreSQL support disabled.")


def _connect_postgres(url: str):
    """Create a PostgreSQL connection using the available driver."""
    if POSTGRES_DRIVER == "psycopg":
        conn = psycopg.connect(url)  # type: ignore[name-defined]
        conn.autocommit = False
        # Ensure all cursors return dict-like rows
        conn.row_factory = _psycopg_dict_row  # type: ignore[name-defined]
        return conn
    if POSTGRES_DRIVER == "psycopg2":
        conn = psycopg2.connect(url, cursor_factory=RealDictCursor)  # type: ignore[name-defined]
        conn.autocommit = False
        return conn
    raise RuntimeError("PostgreSQL driver is not available.")

def get_database_config():
    """Get database configuration based on environment"""
    # Explicit override for local development
    if os.getenv('FORCE_SQLITE') == '1':
        return {
            'type': 'sqlite',
            'path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'polo.db')
        }
    # Check if we're in production (Railway)
    database_url = os.getenv('DATABASE_URL')
    if database_url and PSYCOPG2_AVAILABLE:
        # Production: Try PostgreSQL first, fallback to SQLite if it fails
        try:
            # Test PostgreSQL connection
            test_conn = _connect_postgres(database_url)
            test_conn.close()
            return {
                'type': 'postgresql',
                'url': database_url
            }
        except Exception as e:
            print(f"WARNING: PostgreSQL connection failed, falling back to SQLite: {e}")
            return {
                'type': 'sqlite',
                'path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'polo.db')
            }
    else:
        # Development: Use SQLite
        if database_url and not PSYCOPG2_AVAILABLE:
            print("WARNING: DATABASE_URL set but no PostgreSQL driver available. Using SQLite instead.")
        return {
            'type': 'sqlite',
            'path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'polo.db')
        }

def get_db_connection():
    """Get database connection based on environment"""
    config = get_database_config()
    
    if config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
        try:
            return _connect_postgres(config['url'])
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
        if USING_PSYCOPG3:
            return conn.cursor()
        return conn.cursor(cursor_factory=RealDictCursor)  # type: ignore[arg-type,name-defined]
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
