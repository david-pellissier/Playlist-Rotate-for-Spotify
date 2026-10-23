from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import env


class Base(DeclarativeBase):
    pass


env.database_path.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{env.database_path}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _configure_sqlite(connection, _):
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=DELETE")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
