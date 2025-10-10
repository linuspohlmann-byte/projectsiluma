"""
Subset of :mod:`psycopg2.extras` implemented on top of psycopg 3.
"""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

__all__ = ["RealDictCursor", "execute_values", "apply_real_dict_cursor"]


class RealDictCursor:
    """Placeholder class used as a cursor factory flag."""


def execute_values(cur, sql, argslist, template=None, page_size=100):
    """
    Simplified execute_values compatible helper.
    Executes batched INSERT/UPSERT statements using repeated execute calls.
    """
    if not argslist:
        return
    if template is None:
        template = "(" + ", ".join(["%s"] * len(argslist[0])) + ")"
    for chunk_start in range(0, len(argslist), page_size):
        chunk = argslist[chunk_start:chunk_start + page_size]
        values_sql = ", ".join([template] * len(chunk))
        params: list[Any] = []
        for row in chunk:
            params.extend(row)
        statement = sql.replace("VALUES %s", f"VALUES {values_sql}")
        cur.execute(statement, params)


def apply_real_dict_cursor(conn: Any) -> None:
    """Configure a psycopg connection so cursors return mappings."""
    conn.row_factory = dict_row
