import json
import math
import os
import sqlite3
from typing import List, Dict, Optional, Tuple, Any

from app.routing.graph import haversine_distance_meters


class SpatialDatabaseRepository:
    """
    Spatial database repository supporting SQLite with R-Tree spatial indexing
    for local development/testing, and standard SQL queries compatible with PostgreSQL/PostGIS.
    """

    def __init__(self, db_path: str = "cityflow.db"):
        self.db_path = db_path
        self._init_database()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Transit Stops
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transit_stops (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    line_name TEXT,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    is_transfer_hub INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. SQLite R*Tree Spatial Index for fast spatial bounding box & nearest neighbor queries
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS idx_stops_spatial USING rtree(
                    rowid,
                    min_lon, max_lon,
                    min_lat, max_lat
                );
            """)

            # 3. Transit Routes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transit_routes (
                    id TEXT PRIMARY KEY,
                    short_name TEXT NOT NULL,
                    long_name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    agency TEXT NOT NULL,
                    fare_tier TEXT NOT NULL,
                    headway_seconds INTEGER NOT NULL DEFAULT 360,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. Transit Segments
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transit_segments (
                    id TEXT PRIMARY KEY,
                    route_id TEXT NOT NULL,
                    from_stop_id TEXT NOT NULL,
                    to_stop_id TEXT NOT NULL,
                    stop_sequence INTEGER NOT NULL,
                    scheduled_travel_time_sec INTEGER NOT NULL,
                    distance_meters REAL NOT NULL,
                    base_fare REAL NOT NULL,
                    FOREIGN KEY (route_id) REFERENCES transit_routes(id),
                    FOREIGN KEY (from_stop_id) REFERENCES transit_stops(id),
                    FOREIGN KEY (to_stop_id) REFERENCES transit_stops(id)
                );
            """)

            # 5. Transfer Edges
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transfer_edges (
                    id TEXT PRIMARY KEY,
                    from_stop_id TEXT NOT NULL,
                    to_stop_id TEXT NOT NULL,
                    walking_distance_meters REAL NOT NULL,
                    walking_duration_sec INTEGER NOT NULL,
                    is_same_station INTEGER DEFAULT 0,
                    FOREIGN KEY (from_stop_id) REFERENCES transit_stops(id),
                    FOREIGN KEY (to_stop_id) REFERENCES transit_stops(id)
                );
            """)

            # 6. Road Network Segments
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS road_segments (
                    id TEXT PRIMARY KEY,
                    corridor_name TEXT NOT NULL,
                    road_type TEXT NOT NULL,
                    length_meters REAL NOT NULL,
                    free_flow_speed_kmh REAL NOT NULL,
                    base_traversal_time_sec INTEGER NOT NULL
                );
            """)

            conn.commit()

    def seed_from_json(self, json_path: str):
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"JSON seed file not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Insert stops & populate R-Tree
            for idx, stop in enumerate(data.get("stops", []), start=1):
                cursor.execute("""
                    INSERT OR REPLACE INTO transit_stops (id, name, mode, line_name, lat, lon, is_transfer_hub)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    stop["id"],
                    stop["name"],
                    stop["mode"],
                    stop.get("line"),
                    stop["lat"],
                    stop["lon"],
                    1 if stop.get("transfer_hub") else 0
                ))

                # Update R-Tree index (bounding point)
                cursor.execute("""
                    DELETE FROM idx_stops_spatial WHERE rowid = ?;
                """, (idx,))
                cursor.execute("""
                    INSERT INTO idx_stops_spatial (rowid, min_lon, max_lon, min_lat, max_lat)
                    VALUES (?, ?, ?, ?, ?);
                """, (idx, stop["lon"], stop["lon"], stop["lat"], stop["lat"]))

            # Insert routes
            for route in data.get("transit_routes", []):
                cursor.execute("""
                    INSERT OR REPLACE INTO transit_routes (id, short_name, long_name, mode, agency, fare_tier, headway_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    route["id"],
                    route.get("short_name", route["id"][:8]),
                    route["name"],
                    route["mode"],
                    route["agency"],
                    route["fare_tier"],
                    route["headway_seconds"]
                ))

                # Insert segments
                stops = route.get("stops", [])
                seg_times = route.get("segment_travel_times", [])
                for i in range(len(stops) - 1):
                    from_id = stops[i]
                    to_id = stops[i + 1]
                    dur = seg_times[i] if i < len(seg_times) else 180
                    seg_id = f"{route['id']}_{i}_{from_id}_{to_id}"
                    cursor.execute("""
                        INSERT OR REPLACE INTO transit_segments
                        (id, route_id, from_stop_id, to_stop_id, stop_sequence, scheduled_travel_time_sec, distance_meters, base_fare)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (seg_id, route["id"], from_id, to_id, i, dur, 1200.0, 10.0))

            # Insert transfer edges
            for edge in data.get("transfer_edges", []):
                edge_id = f"trans_{edge['from_stop']}_{edge['to_stop']}"
                cursor.execute("""
                    INSERT OR REPLACE INTO transfer_edges
                    (id, from_stop_id, to_stop_id, walking_distance_meters, walking_duration_sec, is_same_station)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    edge_id,
                    edge["from_stop"],
                    edge["to_stop"],
                    edge["distance_meters"],
                    edge["walking_duration_sec"],
                    1 if edge.get("is_same_station") else 0
                ))

            conn.commit()

    def get_stop_by_id(self, stop_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM transit_stops WHERE id = ?;", (stop_id,)).fetchone()
            return dict(row) if row else None

    def list_stops(self, mode: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM transit_stops WHERE 1=1"
        params: List[Any] = []
        if mode:
            query += " AND mode = ?"
            params.append(mode)
        if search:
            query += " AND (name LIKE ? OR line_name LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY name ASC;"

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def find_stops_in_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> List[Dict[str, Any]]:
        """
        Uses R-Tree spatial index to find all stops within a geographical bounding box.
        """
        sql = """
            SELECT s.*
            FROM transit_stops s
            JOIN idx_stops_spatial i ON s.rowid = i.rowid
            WHERE i.min_lon >= ? AND i.max_lon <= ?
              AND i.min_lat >= ? AND i.max_lat <= ?;
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql, (min_lon, max_lon, min_lat, max_lat)).fetchall()
            return [dict(r) for r in rows]

    def find_nearest_stops(
        self, lat: float, lon: float, limit: int = 5, max_dist_meters: float = 3000.0
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Finds the nearest stops to a coordinate with distance in meters.
        """
        # Convert max_dist to approximate bounding box delta (~111 km per degree)
        lat_delta = max_dist_meters / 111000.0
        lon_delta = max_dist_meters / (111000.0 * math.cos(math.radians(lat)))

        candidates = self.find_stops_in_bbox(
            lat - lat_delta, lon - lon_delta, lat + lat_delta, lon + lon_delta
        )
        if not candidates:
            # Fallback to scanning all stops if bounding box is too tight
            candidates = self.list_stops()

        results = []
        for stop in candidates:
            dist = haversine_distance_meters(lat, lon, stop["lat"], stop["lon"])
            if dist <= max_dist_meters:
                results.append((stop, dist))

        results.sort(key=lambda x: x[1])
        return results[:limit]

    def get_database_stats(self) -> Dict[str, int]:
        with self.get_connection() as conn:
            c = conn.cursor()
            stops_count = c.execute("SELECT COUNT(*) FROM transit_stops;").fetchone()[0]
            routes_count = c.execute("SELECT COUNT(*) FROM transit_routes;").fetchone()[0]
            segments_count = c.execute("SELECT COUNT(*) FROM transit_segments;").fetchone()[0]
            transfers_count = c.execute("SELECT COUNT(*) FROM transfer_edges;").fetchone()[0]
            return {
                "total_stops": stops_count,
                "total_routes": routes_count,
                "total_segments": segments_count,
                "total_transfers": transfers_count
            }
