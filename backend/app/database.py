from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base


connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.connect() as connection:
            connection.execute(text("PRAGMA journal_mode=WAL"))
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(monitors)").all()
            }
            if "render_wait_ms" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE monitors ADD COLUMN render_wait_ms INTEGER NOT NULL DEFAULT 1500"
                )
                connection.commit()
            profile_columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(pushover_profiles)").all()
            }
            if "device_names_json" not in profile_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE pushover_profiles ADD COLUMN device_names_json TEXT NOT NULL DEFAULT '[]'"
                )
                connection.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_session() -> Session:
    return SessionLocal()
