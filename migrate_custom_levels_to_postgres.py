#!/usr/bin/env python3
"""
Migrate custom level groups (and related data) from local SQLite to PostgreSQL.

Usage:
    DATABASE_URL=postgres://user:pass@host:5432/dbname python3 migrate_custom_levels_to_postgres.py
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Iterable, Optional

from server import postgres
from server.postgres import ConnectionWrapper, RealDictCursor


SQLITE_CANDIDATES: tuple[str, ...] = (
    "polo.db",
    os.path.join("server", "siluma.db"),
    os.path.join("data", "siluma.db"),
    "siluma.db",
)


@dataclass
class SQLiteSource:
    path: str
    connection: sqlite3.Connection


@dataclass
class PostgresTarget:
    url: str
    connection: "ConnectionWrapper"


def find_sqlite_database() -> Optional[SQLiteSource]:
    """Locate the first available SQLite database and return an open connection."""
    for candidate in SQLITE_CANDIDATES:
        if os.path.exists(candidate):
            conn = sqlite3.connect(candidate)
            conn.row_factory = sqlite3.Row
            print(f"📁 Using SQLite database: {candidate}")
            return SQLiteSource(path=candidate, connection=conn)
    return None


def connect_postgres() -> Optional[PostgresTarget]:
    """Open a PostgreSQL connection using DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set. Aborting migration.")
        return None

    conn = postgres.connect(database_url, cursor_factory=RealDictCursor)
    conn.autocommit = False
    print("✅ Connected to PostgreSQL target.")
    return PostgresTarget(url=database_url, connection=conn)


def ensure_tables(target: PostgresTarget) -> None:
    """Create required tables if they do not yet exist."""
    with target.connection.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_level_groups (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                language VARCHAR(10) NOT NULL,
                native_language VARCHAR(10) NOT NULL,
                group_name VARCHAR(255) NOT NULL,
                context_description TEXT NOT NULL,
                cefr_level VARCHAR(10) DEFAULT 'A1',
                num_levels INTEGER DEFAULT 10,
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, language, group_name)
            );
        """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_levels (
                id SERIAL PRIMARY KEY,
                group_id INTEGER NOT NULL,
                level_number INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                topic VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
                UNIQUE(group_id, level_number)
            );
        """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_level_group_ratings (
                id SERIAL PRIMARY KEY,
                group_id INTEGER NOT NULL REFERENCES custom_level_groups(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL,
                stars INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, user_id)
            );
        """
        )

    target.connection.commit()
    print("🔧 Ensured required tables exist on PostgreSQL.")


def _dict_rows(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def migrate_custom_level_groups(source: SQLiteSource, target: PostgresTarget) -> int:
    sqlite_cur = source.connection.cursor()
    sqlite_cur.execute("SELECT * FROM custom_level_groups ORDER BY id")
    groups = _dict_rows(sqlite_cur.fetchall())

    if not groups:
        print("ℹ️ No custom level groups found in SQLite.")
        return 0

    with target.connection.cursor() as cur:
        for group in groups:
            cur.execute(
                """
                INSERT INTO custom_level_groups (
                    id, user_id, language, native_language, group_name, context_description,
                    cefr_level, num_levels, status, created_at, updated_at
                ) VALUES (
                    %(id)s, %(user_id)s, %(language)s, %(native_language)s, %(group_name)s,
                    %(context_description)s, %(cefr_level)s, %(num_levels)s, %(status)s,
                    %(created_at)s, %(updated_at)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    language = EXCLUDED.language,
                    native_language = EXCLUDED.native_language,
                    group_name = EXCLUDED.group_name,
                    context_description = EXCLUDED.context_description,
                    cefr_level = EXCLUDED.cefr_level,
                    num_levels = EXCLUDED.num_levels,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at;
            """,
                group,
            )

    target.connection.commit()
    print(f"✅ Migrated {len(groups)} custom level groups.")
    return len(groups)


def migrate_custom_levels(source: SQLiteSource, target: PostgresTarget) -> int:
    sqlite_cur = source.connection.cursor()
    sqlite_cur.execute("SELECT * FROM custom_levels ORDER BY id")
    levels = _dict_rows(sqlite_cur.fetchall())

    if not levels:
        print("ℹ️ No custom levels found in SQLite.")
        return 0

    with target.connection.cursor() as cur:
        for level in levels:
            # Ensure content is stored as JSON string (guard against Python dicts)
            content = level.get("content")
            if isinstance(content, (dict, list)):
                level["content"] = json.dumps(content, ensure_ascii=False)

            cur.execute(
                """
                INSERT INTO custom_levels (
                    id, group_id, level_number, title, topic, content, created_at, updated_at
                ) VALUES (
                    %(id)s, %(group_id)s, %(level_number)s, %(title)s, %(topic)s,
                    %(content)s, %(created_at)s, %(updated_at)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    group_id = EXCLUDED.group_id,
                    level_number = EXCLUDED.level_number,
                    title = EXCLUDED.title,
                    topic = EXCLUDED.topic,
                    content = EXCLUDED.content,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at;
            """,
                level,
            )

    target.connection.commit()
    print(f"✅ Migrated {len(levels)} custom levels.")
    return len(levels)


def migrate_group_ratings(source: SQLiteSource, target: PostgresTarget) -> int:
    sqlite_cur = source.connection.cursor()

    try:
        sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom_level_group_ratings'")
        if not sqlite_cur.fetchone():
            print("ℹ️ custom_level_group_ratings table does not exist in SQLite. Skipping.")
            return 0

        sqlite_cur.execute("SELECT * FROM custom_level_group_ratings ORDER BY id")
    except sqlite3.Error as exc:
        print(f"⚠️ Could not query custom_level_group_ratings: {exc}")
        return 0

    ratings = _dict_rows(sqlite_cur.fetchall())
    if not ratings:
        print("ℹ️ No custom level ratings found in SQLite.")
        return 0

    with target.connection.cursor() as cur:
        for rating in ratings:
            cur.execute(
                """
                INSERT INTO custom_level_group_ratings (
                    id, group_id, user_id, stars, comment, created_at, updated_at
                ) VALUES (
                    %(id)s, %(group_id)s, %(user_id)s, %(stars)s, %(comment)s,
                    %(created_at)s, %(updated_at)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    group_id = EXCLUDED.group_id,
                    user_id = EXCLUDED.user_id,
                    stars = EXCLUDED.stars,
                    comment = EXCLUDED.comment,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at;
            """,
                rating,
            )

    target.connection.commit()
    print(f"✅ Migrated {len(ratings)} custom level ratings.")
    return len(ratings)


def sync_sequences(target: PostgresTarget) -> None:
    """Ensure sequences are in sync with the highest primary key values."""
    with target.connection.cursor() as cur:
        for table, sequence in (
            ("custom_level_groups", "custom_level_groups_id_seq"),
            ("custom_levels", "custom_levels_id_seq"),
            ("custom_level_group_ratings", "custom_level_group_ratings_id_seq"),
        ):
            try:
                cur.execute(
                    f"""
                    SELECT setval(
                        %s,
                        COALESCE((SELECT MAX(id) FROM {table}), 1)
                    );
                """,
                    (sequence,),
                )
            except postgres.Error as exc:
                print(f"⚠️ Could not advance sequence {sequence}: {exc}")

    target.connection.commit()
    print("🔁 PostgreSQL sequences synchronized.")


def main() -> None:
    source = find_sqlite_database()
    if not source:
        print("❌ Could not find a SQLite database. Nothing to migrate.")
        return

    target = connect_postgres()
    if not target:
        source.connection.close()
        return

    try:
        ensure_tables(target)
        migrate_custom_level_groups(source, target)
        migrate_custom_levels(source, target)
        migrate_group_ratings(source, target)
        sync_sequences(target)
        target.connection.commit()
        print("🎉 Custom level migration completed successfully.")
    except Exception as exc:
        target.connection.rollback()
        print(f"❌ Migration failed: {exc}")
        raise
    finally:
        source.connection.close()
        target.connection.close()


if __name__ == "__main__":
    main()
