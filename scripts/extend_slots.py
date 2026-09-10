"""Top up rolling AppointmentSlot availability further into the future,
without a full reseed (which would wipe existing bookings). Idempotent.

Run from the repo root: python scripts/extend_slots.py [--start-date YYYY-MM-DD] [--days N]
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.availability import generate_slots
from app.db.database import get_session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, default=None)
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    with get_session() as session:
        created = generate_slots(session, start_date=args.start_date, num_business_days=args.days)
    print(f"Created {len(created)} new appointment slot(s).")


if __name__ == "__main__":
    main()
