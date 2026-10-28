import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.db.repository import SpatialDatabaseRepository


def run_seed():
    db_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cityflow.db")
    print(f"Initializing spatial database at: {db_file}")
    repo = SpatialDatabaseRepository(db_path=db_file)

    network_path = settings.NETWORK_DATA_PATH
    print(f"Seeding network data from: {network_path}")
    repo.seed_from_json(network_path)

    stats = repo.get_database_stats()
    print("Database seeding completed successfully!")
    print(f"  - Stops seeded:     {stats['total_stops']}")
    print(f"  - Routes seeded:    {stats['total_routes']}")
    print(f"  - Segments seeded:  {stats['total_segments']}")
    print(f"  - Transfers seeded: {stats['total_transfers']}")


if __name__ == "__main__":
    run_seed()
