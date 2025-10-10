"""
Minimal compatibility layer exposing a psycopg2-like API backed by psycopg 3.

This allows the codebase to keep importing ``psycopg2`` even when the classic
binary wheel is unavailable on the deployment platform.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg import Error, OperationalError, ProgrammingError  # re-export common errors
from psycopg.rows import dict_row

from . import extras

__all__ = [
    "connect",
    "Error",
    "OperationalError",
    "ProgrammingError",
    "extras",
]


class _CompatConnection:
    """Minimal wrapper to emulate psycopg2 connection behaviour."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args: Any, **kwargs: Any):
        cursor_factory = kwargs.pop("cursor_factory", None)
        if cursor_factory is extras.RealDictCursor:
            kwargs["row_factory"] = dict_row
        elif cursor_factory is not None:
            raise TypeError("Unsupported cursor_factory requested in psycopg2 shim.")
        return self._conn.cursor(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._conn, item)

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._conn.__exit__(exc_type, exc, tb)

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "_conn":
            super().__setattr__(key, value)
        else:
            setattr(self._conn, key, value)


def connect(*args: Any, **kwargs: Any):
    """
    Thin wrapper around :func:`psycopg.connect` that honours the ``cursor_factory``
    kwarg expected by psycopg2 callers. Rows default to dictionaries so existing
    code keeps working without further changes.
    """
    cursor_factory = kwargs.pop("cursor_factory", None)
    conn = psycopg.connect(*args, **kwargs)

    if cursor_factory is extras.RealDictCursor:
        extras.apply_real_dict_cursor(conn)

    return _CompatConnection(conn)
