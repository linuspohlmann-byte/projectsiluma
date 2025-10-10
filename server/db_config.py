import os
import sqlite3
from urllib.parse import urlparse, unquote

try:
    import pg8000.dbapi as pg8000
    PG8000_AVAILABLE = True
except ImportError:
    pg8000 = None
    PG8000_AVAILABLE = False
    print("WARNING: pg8000 not available. PostgreSQL support disabled.")

# Maintain legacy constant names used elsewhere in the codebase
PSYCOPG2_AVAILABLE = PG8000_AVAILABLE
PSYCOPG2_EXECUTE_VALUES = None  # Not available with pg8000


def _is_sqlite_forced() -> bool:
    return os.getenv('FORCE_SQLITE') == '1'


def _build_sqlite_config() -> dict:
    return {
        'type': 'sqlite',
        'path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'polo.db')
    }


def _parse_database_url(database_url: str) -> dict:
    parsed = urlparse(database_url)
    if parsed.scheme not in {'postgres', 'postgresql'}:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")
    connect_kwargs: dict = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'database': (parsed.path[1:] if parsed.path else '') or None,
    }
    if parsed.username:
        connect_kwargs['user'] = unquote(parsed.username)
    if parsed.password:
        connect_kwargs['password'] = unquote(parsed.password)
    if parsed.query:
        # Allow extra options like sslmode
        for option in parsed.query.split('&'):
            if not option:
                continue
            key, _, value = option.partition('=')
            if key and value:
                connect_kwargs[key] = unquote(value)
    return connect_kwargs


def get_database_config():
    """Get database configuration based on environment"""
    if _is_sqlite_forced():
        return _build_sqlite_config()

    database_url = os.getenv('DATABASE_URL')
    if database_url and PSYCOPG2_AVAILABLE:
        try:
            connect_kwargs = _parse_database_url(database_url)
            # Attempt a quick connection to validate credentials
            test_conn = pg8000.connect(**connect_kwargs)
            test_conn.close()
            return {
                'type': 'postgresql',
                'url': database_url,
                'connect_kwargs': connect_kwargs
            }
        except Exception as exc:
            print(f"WARNING: PostgreSQL connection failed, falling back to SQLite: {exc}")
            return _build_sqlite_config()
    else:
        if database_url and not PSYCOPG2_AVAILABLE:
            print("WARNING: DATABASE_URL set but pg8000 not available. Using SQLite instead.")
        return _build_sqlite_config()


def get_db_connection():
    """Get database connection based on environment"""
    config = get_database_config()

    if config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
        try:
            connect_kwargs = config.get('connect_kwargs') or _parse_database_url(config['url'])
            conn = pg8000.connect(**connect_kwargs)
            # pg8000 defaults to autocommit False, keep explicit for clarity
            conn.autocommit = False
            return conn
        except Exception as exc:
            print(f"ERROR: Failed to connect to PostgreSQL with pg8000: {exc}")
            print(f"ERROR: DATABASE_URL: {config.get('url')}")
            print("Falling back to SQLite...")
            config = _build_sqlite_config()

    # SQLite (either primary or fallback)
    try:
        conn = sqlite3.connect(config['path'])
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as exc:
        print(f"ERROR: Failed to connect to SQLite: {exc}")
        print(f"ERROR: SQLite path: {config['path']}")
        raise exc


def _dict_row(cursor, row):
    if row is None:
        return None
    return {cursor.description[idx][0]: row[idx] for idx in range(len(row))}


def get_db_cursor(conn):
    """Get appropriate cursor for database type"""
    config = get_database_config()

    if config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
        cursor = conn.cursor()
        cursor.row_factory = _dict_row
        return cursor
    else:
        return conn.cursor()


def execute_query(conn, query, params=None):
    """Execute query with appropriate parameter style"""
    config = get_database_config()
    cursor = get_db_cursor(conn)

    if config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
        # pg8000 also uses %s for parameters
        if params:
            cursor.execute(query.replace('?', '%s'), params)
        else:
            cursor.execute(query.replace('?', '%s'))
    else:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

    return cursor


def get_lastrowid(cursor):
    """Get last inserted row ID"""
    config = get_database_config()

    if config['type'] == 'postgresql' and PSYCOPG2_AVAILABLE:
        if cursor.description:
            row = cursor.fetchone()
            if isinstance(row, dict):
                return row.get('id')
            elif row:
                return row[0]
        return None
    else:
        return cursor.lastrowid
