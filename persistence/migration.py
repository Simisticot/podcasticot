import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def migrate(conn: sqlite3.Connection):
    conn.execute("""
        create table if not exists schema_version ( version text primary key)
                 """)
    applied = {row[0] for row in conn.execute("select version from schema_version")}
    migrations = sorted(Path(MIGRATIONS_DIR).glob("*.sql"))

    for migration in migrations:
        version = migration.stem
        if version in applied:
            continue
        sql = migration.read_text()
        with conn:
            conn.executescript(sql)
            conn.execute("insert into schema_version (version) values (?)", (version,))
