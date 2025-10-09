"""
Subset of :mod:`psycopg2.extras` implemented on top of psycopg 3.
"""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row
from psycopg.extras import execute_values as _execute_values

__all__ = ["RealDictCursor", "execute_values", "apply_real_dict_cursor"]


class RealDictCursor:
    """Placeholder class used as a cursor factory flag."""


execute_values = _execute_values


def apply_real_dict_cursor(conn: Any) -> None:
    """Configure a psycopg connection so cursors return mappings."""
    conn.row_factory = dict_row
