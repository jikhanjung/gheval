"""Simple migration runner for GHEval database."""

import os
import importlib.util
from peewee import SqliteDatabase

from GhCommons import get_db_path


def get_migration_files():
    """Get sorted list of migration files."""
    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    files = []
    for f in sorted(os.listdir(migrations_dir)):
        if f.endswith(".py") and not f.startswith("__"):
            files.append(os.path.join(migrations_dir, f))
    return files


def ensure_migration_table(db):
    """Create migration tracking table if it doesn't exist."""
    db.execute_sql("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL UNIQUE,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)


def get_applied_migrations(db):
    """Get set of already-applied migration names."""
    cursor = db.execute_sql("SELECT name FROM _migrations")
    return {row[0] for row in cursor.fetchall()}


def run_migrations(db_path=None):
    """Run all pending migrations."""
    if db_path is None:
        db_path = get_db_path()

    db = SqliteDatabase(db_path)
    db.connect()
    db.execute_sql("PRAGMA foreign_keys = ON")

    ensure_migration_table(db)
    applied = get_applied_migrations(db)

    for filepath in get_migration_files():
        name = os.path.basename(filepath)
        if name in applied:
            continue

        print(f"Applying migration: {name}")
        spec = importlib.util.spec_from_file_location(name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        module.migrate(db)
        db.execute_sql("INSERT INTO _migrations (name) VALUES (?)", (name,))
        print(f"  Applied: {name}")

    db.close()
    print("All migrations applied.")


if __name__ == "__main__":
    run_migrations()
