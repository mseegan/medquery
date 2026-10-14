"""Run from the repo root: python scripts/seed_db.py [records-folder]

The folder holds records.xlsx and the visit-note PDFs; it defaults to
RECORDS_DATA_DIR from .env."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.seed import seed  # noqa: E402

if __name__ == "__main__":
    seed(sys.argv[1] if len(sys.argv) > 1 else None)
