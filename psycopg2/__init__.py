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


def connect(*args: Any, **kwargs: Any):
    """
    Thin wrapper around :func:`psycopg.connect` that honours the ``cursor_factory``
    kwarg expected by psycopg2 callers. Rows default to dictionaries so existing
    code keeps working without further changes.
    """
    cursor_factory = kwargs.pop("cursor_factory", None)
    conn = psycopg.connect(*args, **kwargs)

    # Default to dict-like rows for compatibility with psycopg2 RealDictCursor.
    conn.row_factory = dict_row

    if cursor_factory is extras.RealDictCursor:
        extras.apply_real_dict_cursor(conn)

    return conn
