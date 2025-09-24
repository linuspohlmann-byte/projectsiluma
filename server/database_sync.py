"""Utilities to keep legacy and multi-user databases aligned at startup."""

from __future__ import annotations

import json
import sqlite3
from typing import Set

from .db import DB_PATH
from .db_multi_user import ensure_user_databases
from .multi_user_db import db_manager


DEFAULT_NATIVE_LANGUAGE = "en"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_native_language_column(conn: sqlite3.Connection) -> None:
    columns: Set[str] = {
        row["name"] for row in conn.execute("PRAGMA table_info(users)")
    }
    if "native_language" not in columns:
        conn.execute(
            f"ALTER TABLE users ADD COLUMN native_language TEXT DEFAULT '{DEFAULT_NATIVE_LANGUAGE}'"
        )
        conn.commit()
    conn.execute(
        "UPDATE users SET native_language = ? WHERE native_language IS NULL OR native_language = ''",
        (DEFAULT_NATIVE_LANGUAGE,),
    )
    conn.commit()


def _ensure_user_settings(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT id, settings, native_language FROM users"
    ).fetchall()
    for row in rows:
        native_language = row["native_language"] or DEFAULT_NATIVE_LANGUAGE
        settings_raw = row["settings"]
        try:
            settings = json.loads(settings_raw) if settings_raw else {}
        except json.JSONDecodeError:
            settings = {}
        if not isinstance(settings, dict):
            settings = {"value": settings}
        if settings.get("native_language") != native_language:
            settings["native_language"] = native_language
            cur.execute(
                "UPDATE users SET settings = ?, native_language = ? WHERE id = ?",
                (json.dumps(settings), native_language, row["id"]),
            )
    conn.commit()


def _ensure_global_databases(conn: sqlite3.Connection) -> Set[str]:
    languages: Set[str] = set()
    rows = conn.execute(
        "SELECT DISTINCT native_language FROM words WHERE native_language IS NOT NULL AND native_language <> ''"
    ).fetchall()
    for row in rows:
        languages.add(row["native_language"])
    if not languages:
        languages.add(DEFAULT_NATIVE_LANGUAGE)
    for lang in languages:
        db_manager.ensure_global_database(lang)
    return languages


def _ensure_user_databases(conn: sqlite3.Connection, languages: Set[str]) -> None:
    rows = conn.execute(
        "SELECT id, native_language FROM users WHERE is_active = 1"
    ).fetchall()
    for row in rows:
        native_language = row["native_language"] or DEFAULT_NATIVE_LANGUAGE
        if native_language not in languages:
            db_manager.ensure_global_database(native_language)
            languages.add(native_language)
        ensure_user_databases(row["id"], native_language)


def sync_databases_on_startup() -> None:
    """Ensure both legacy and multi-user databases are ready for requests."""
    conn = _get_connection()
    try:
        _ensure_native_language_column(conn)
        _ensure_user_settings(conn)
        languages = _ensure_global_databases(conn)
        _ensure_user_databases(conn, languages)
    finally:
        conn.close()
