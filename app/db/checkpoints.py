"""The SQLite file where LangGraph saves each conversation's state."""
import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import settings


def make_checkpointer() -> SqliteSaver:
    Path(settings.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(settings.checkpoint_db_path, check_same_thread=False))


def clear_checkpoints() -> None:
    """Forget every saved conversation. They hold patient ids, which are reused
    when the databases are reseeded."""
    path = Path(settings.checkpoint_db_path)
    if not path.exists():
        return
    with sqlite3.connect(path) as connection:
        for table in ("writes", "checkpoints"):
            try:
                connection.execute(f"DELETE FROM {table}")
            except sqlite3.OperationalError:
                pass  # table not created yet
