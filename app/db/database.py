from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

engine = create_engine(f"sqlite:///{settings.db_path}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(engine)


def reset_db() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
