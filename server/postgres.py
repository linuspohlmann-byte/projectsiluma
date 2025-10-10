"""PostgreSQL helper built on pg8000, mimicking the tiny subset of psycopg2 used by the app."""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlparse, unquote

try:
    import pg8000.dbapi as pg8000
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise RuntimeError("pg8000 must be installed to use server.postgres") from exc

Error = pg8000.DatabaseError
OperationalError = pg8000.OperationalError
ProgrammingError = pg8000.ProgrammingError


class RealDictCursorType:
    """Sentinel type used to request dict rows (mirrors psycopg2.extras.RealDictCursor)."""


RealDictCursor = RealDictCursorType


def _parse_dsn(dsn: str) -> dict[str, Any]:
    parsed = urlparse(dsn)
    if parsed.scheme not in {'postgres', 'postgresql'}:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")
    connect_kwargs: dict[str, Any] = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'database': (parsed.path[1:] if parsed.path else '') or None,
    }
    if parsed.username:
        connect_kwargs['user'] = unquote(parsed.username)
    if parsed.password:
        connect_kwargs['password'] = unquote(parsed.password)
    if parsed.query:
        for option in parsed.query.split('&'):
            if not option:
                continue
            key, _, value = option.partition('=')
            if key and value:
                connect_kwargs[key] = unquote(value)
    return connect_kwargs


def _dict_row_factory(cursor, row):
    if row is None:
        return None
    return {cursor.description[idx][0]: row[idx] for idx in range(len(row))}


class CursorWrapper:
    def __init__(self, cursor, dict_rows: bool = False):
        self._cursor = cursor
        if dict_rows:
            self._cursor.row_factory = _dict_row_factory

    def execute(self, query: str, params: Iterable | None = None):
        if params is not None:
            self._cursor.execute(query, params)
        else:
            self._cursor.execute(query)
        return self

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def close(self) -> None:
        self._cursor.close()

    def __getattr__(self, item):  # pragma: no cover - passthrough for rarely used attrs
        return getattr(self._cursor, item)


class ConnectionWrapper:
    def __init__(self, conn, default_cursor_factory=None):
        self._conn = conn
        self._default_cursor_factory = default_cursor_factory

    def cursor(self, cursor_factory=None):
        requested_factory = cursor_factory or self._default_cursor_factory
        dict_rows = requested_factory is RealDictCursor
        if requested_factory not in (None, RealDictCursor):
            raise TypeError("Unsupported cursor_factory requested")
        return CursorWrapper(self._conn.cursor(), dict_rows=dict_rows)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):  # pragma: no cover
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover
        return self._conn.__exit__(exc_type, exc, tb)

    def __getattr__(self, item):  # pragma: no cover
        return getattr(self._conn, item)


def connect(dsn: str | None = None, **kwargs) -> ConnectionWrapper:
    cursor_factory = kwargs.pop('cursor_factory', None)
    if dsn:
        connect_kwargs = _parse_dsn(dsn)
        connect_kwargs.update(kwargs)
    else:
        connect_kwargs = kwargs
    conn = pg8000.connect(**connect_kwargs)
    conn.autocommit = False
    return ConnectionWrapper(conn, default_cursor_factory=cursor_factory)
