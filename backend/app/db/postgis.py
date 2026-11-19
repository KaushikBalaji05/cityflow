"""PostGIS stop access, constrained to stops actually present in the routing graph."""
NEAREST_SQL = """
SELECT id, ST_Distance(location::geography,
       ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography) AS distance
FROM transit_stops
WHERE ST_DWithin(location::geography,
      ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)
  AND mode = ANY(%s) AND id = ANY(%s)
ORDER BY distance
"""


class PostgisStopLookup:
    def __init__(self, network, url):
        self.network = network
        self.url = url.replace("postgresql+asyncpg://", "postgresql://")

    def __call__(self, lat, lon, max_distance_meters, allowed_modes, limit=6):
        import psycopg
        # Do not silently expand radius or substitute different coordinates.
        with psycopg.connect(self.url, connect_timeout=3) as conn:
            conn.execute("SET LOCAL statement_timeout = '3000ms'")
            rows = conn.execute(NEAREST_SQL, (lon, lat, lon, lat, max_distance_meters,
                                            allowed_modes, list(self.network.stops))).fetchall()
        candidates = [(self.network.stops[stop_id], float(distance)) for stop_id, distance in rows]
        # Preserve the existing mode balance so buses do not crowd out rail.
        selected = []
        for mode in allowed_modes:
            selected.extend([p for p in candidates if p[0]["mode"] == mode][:max(1, limit // len(allowed_modes))])
        ids = {p[0]["id"] for p in selected}
        selected.extend(p for p in candidates if p[0]["id"] not in ids)
        return sorted(selected[:limit], key=lambda p: p[1])
