from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_config

config = get_config()

_engine = None


def get_engine():
    """Get the engine for the database"""
    global _engine
    if _engine is None:
        _engine = create_engine(
            config.DATABASE_URL,
            echo=False,
            hide_parameters=True,
            pool_pre_ping=True,
        )
    return _engine


@contextmanager
def get_session():
    """Get a session for the database"""
    with Session(get_engine()) as session:
        yield session


def init_db():
    """Initialize the database and create all tables"""
    engine = get_engine()

    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS unaccent")

    SQLModel.metadata.create_all(engine)
