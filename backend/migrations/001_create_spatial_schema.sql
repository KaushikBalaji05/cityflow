-- =====================================================================
-- CityFlow Database Migration 001: Initial Spatial Schema
-- Target: PostgreSQL 16 + PostGIS 3.4
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Transit Stops (Bus stops, Metro stations)
CREATE TABLE IF NOT EXISTS transit_stops (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    mode VARCHAR(32) NOT NULL, -- 'bus', 'metro'
    line_name VARCHAR(128),
    platform_code VARCHAR(32),
    location GEOMETRY(Point, 4326) NOT NULL,
    is_wheelchair_accessible BOOLEAN DEFAULT FALSE,
    is_transfer_hub BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transit_stops_geom ON transit_stops USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_transit_stops_mode ON transit_stops(mode);

-- 2. Transit Routes (BMRCL Lines, BMTC Corridors)
CREATE TABLE IF NOT EXISTS transit_routes (
    id VARCHAR(64) PRIMARY KEY,
    short_name VARCHAR(64) NOT NULL,
    long_name VARCHAR(255) NOT NULL,
    mode VARCHAR(32) NOT NULL,
    agency VARCHAR(64) NOT NULL, -- 'BMTC', 'BMRCL'
    fare_tier VARCHAR(32) NOT NULL, -- 'ordinary', 'vajra_ac', 'metro_standard'
    headway_seconds INTEGER NOT NULL DEFAULT 360,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transit_routes_agency ON transit_routes(agency);

-- 3. Transit Segments (Directed connections between consecutive stops)
CREATE TABLE IF NOT EXISTS transit_segments (
    id VARCHAR(64) PRIMARY KEY,
    route_id VARCHAR(64) NOT NULL REFERENCES transit_routes(id) ON DELETE CASCADE,
    from_stop_id VARCHAR(64) NOT NULL REFERENCES transit_stops(id) ON DELETE CASCADE,
    to_stop_id VARCHAR(64) NOT NULL REFERENCES transit_stops(id) ON DELETE CASCADE,
    stop_sequence INTEGER NOT NULL,
    scheduled_travel_time_sec INTEGER NOT NULL,
    distance_meters DOUBLE PRECISION NOT NULL,
    base_fare DOUBLE PRECISION NOT NULL,
    geometry GEOMETRY(LineString, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transit_segments_route ON transit_segments(route_id, stop_sequence);
CREATE INDEX IF NOT EXISTS idx_transit_segments_from_to ON transit_segments(from_stop_id, to_stop_id);

-- 4. Precomputed Walking Transfer Edges between transit stops
CREATE TABLE IF NOT EXISTS transfer_edges (
    id VARCHAR(64) PRIMARY KEY,
    from_stop_id VARCHAR(64) NOT NULL REFERENCES transit_stops(id) ON DELETE CASCADE,
    to_stop_id VARCHAR(64) NOT NULL REFERENCES transit_stops(id) ON DELETE CASCADE,
    walking_distance_meters DOUBLE PRECISION NOT NULL,
    walking_duration_sec INTEGER NOT NULL,
    is_same_station BOOLEAN DEFAULT FALSE,
    geometry GEOMETRY(LineString, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transfer_edges_from ON transfer_edges(from_stop_id);
CREATE INDEX IF NOT EXISTS idx_transfer_edges_to ON transfer_edges(to_stop_id);

-- 5. Road Network Segments (for driving and auto-rickshaw routing)
CREATE TABLE IF NOT EXISTS road_segments (
    id VARCHAR(64) PRIMARY KEY,
    corridor_name VARCHAR(255) NOT NULL,
    road_type VARCHAR(64) NOT NULL, -- 'highway', 'primary', 'secondary', 'arterial'
    length_meters DOUBLE PRECISION NOT NULL,
    free_flow_speed_kmh DOUBLE PRECISION NOT NULL,
    base_traversal_time_sec INTEGER NOT NULL,
    geometry GEOMETRY(LineString, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_road_segments_geom ON road_segments USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_road_segments_corridor ON road_segments(corridor_name);
