import sys
import sqlite3
import structlog

log = structlog.get_logger(__name__)


def migrate(sqlite_path: str, pg_url: str):
    from sqlalchemy import create_engine, text
    import app.models
    from app.models import Base

    log.info("connecting_sqlite", path=sqlite_path)
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    log.info("connecting_postgres", url=pg_url.rpartition("@")[2])
    pg_engine = create_engine(pg_url)
    Base.metadata.create_all(pg_engine)

    tables = [row[0] for row in sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    log.info("tables_found", count=len(tables), tables=tables)

    pg_conn = pg_engine.connect()
    total_rows = 0

    for table in tables:
        rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            log.info("table_skipped", table=table, reason="empty")
            continue

        columns = rows[0].keys()
        for row in rows:
            values = {col: row[col] for col in columns}
            if "id" in values:
                values.pop("id", None)
            if values:
                try:
                    pg_conn.execute(text(f"INSERT INTO {table} ({','.join(values.keys())}) VALUES ({','.join(':' + k for k in values.keys())})"), values)
                except Exception as e:
                    log.warning("row_skip", table=table, error=str(e))
        pg_conn.commit()
        total_rows += len(rows)
        log.info("table_migrated", table=table, rows=len(rows))

    for table in tables:
        try:
            pg_conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table}"))
            pg_conn.commit()
        except Exception:
            pass

    pg_conn.close()
    sqlite_conn.close()
    log.info("migration_complete", total_rows=total_rows)


if __name__ == "__main__":
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else "data/face_scan.db"
    pg_url = sys.argv[2] if len(sys.argv) > 2 else "postgresql+psycopg2://face:password@localhost:5432/facedb"
    migrate(sqlite_path, pg_url)