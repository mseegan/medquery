"""Run from the repo root: python scripts/seed_db.py [records-folder] [--no-memory]

The folder holds records.xlsx and the visit-note PDFs; it defaults to
RECORDS_DATA_DIR from .env. Unless --no-memory is given, the patient vector
store is rebuilt afterwards (this calls the Anthropic API to write summaries)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.seed import seed  # noqa: E402
from app.memory.indexing import rebuild_memory  # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    data_dir = args[0] if args else None
    seed(data_dir)
    if "--no-memory" not in sys.argv:
        imported, summaries = rebuild_memory(data_dir)
        print(f"Indexed {imported} imported records and {summaries} patient summaries.")


if __name__ == "__main__":
    main()
