import os
import pytest
from app.db.repository import SpatialDatabaseRepository
from app.core.config import settings


@pytest.fixture
def test_repo(tmp_path):
    test_db = str(tmp_path / "test_cityflow.db")
    repo = SpatialDatabaseRepository(db_path=test_db)
    repo.seed_from_json(settings.NETWORK_DATA_PATH)
    return repo


def test_database_initialization_and_seeding(test_repo):
    stats = test_repo.get_database_stats()
    assert stats["total_stops"] >= 35, "Should seed all transit stops"
    assert stats["total_routes"] >= 8, "Should seed all transit routes"
    assert stats["total_segments"] >= 50, "Should generate directional segments"
    assert stats["total_transfers"] >= 8, "Should seed transfer walk links"


def test_spatial_bbox_query(test_repo):
    # Bounding box covering Central Bengaluru (MG Road, Cubbon Park, Vidhana Soudha, Majestic)
    # Approx Lat: 12.96 to 12.99, Lon: 77.56 to 77.62
    stops = test_repo.find_stops_in_bbox(
        min_lat=12.96, min_lon=77.56, max_lat=12.99, max_lon=77.62
    )
    assert len(stops) >= 4
    stop_names = [s["name"] for s in stops]
    assert any("Majestic" in name for name in stop_names)
    assert any("MG Road" in name for name in stop_names)


def test_nearest_stops_spatial_search(test_repo):
    # Search nearest stops to Indiranagar Metro (12.9784, 77.6408)
    nearest = test_repo.find_nearest_stops(lat=12.9784, lon=77.6408, limit=3)
    assert len(nearest) >= 1
    closest_stop, dist = nearest[0]
    assert "Indiranagar" in closest_stop["name"]
    assert dist < 100.0, f"Expected distance < 100m, got {dist}m"


def test_stop_by_id_and_mode_filter(test_repo):
    stop = test_repo.get_stop_by_id("metro_majestic")
    assert stop is not None
    assert stop["name"] == "Nadaprabhu Kempegowda Majestic Metro"
    assert stop["mode"] == "metro"
    assert stop["is_transfer_hub"] == 1

    metro_stops = test_repo.list_stops(mode="metro")
    assert all(s["mode"] == "metro" for s in metro_stops)

    bus_stops = test_repo.list_stops(mode="bus")
    assert all(s["mode"] == "bus" for s in bus_stops)
