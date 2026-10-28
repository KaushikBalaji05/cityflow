# CityFlow API Reference

The CityFlow REST API provides high-performance spatial querying, multimodal routing, and live mobility analytics for Bengaluru.

- **Base URL:** `http://localhost:8000/api/v1`
- **Interactive OpenAPI Documentation:** `http://localhost:8000/api/v1/docs`
- **ReDoc:** `http://localhost:8000/api/v1/redoc`

---

## 1. System & Health

### `GET /api/v1/health`
Returns the operational health of the application, active graph topology metrics, and database status.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "service": "CityFlow API",
  "version": "1.0.0",
  "environment": "development",
  "transit_graph": {
    "total_stops": 41,
    "total_routes": 12,
    "total_transfers": 10
  }
}
```

---

## 2. Spatial Stops & Search

### `GET /api/v1/stops`
Lists transit stops in Bengaluru, with optional filtering by mode (`metro` or `bus`) and text search.

**Query Parameters:**
- `mode` (string, optional): `'metro'` | `'bus'`
- `search` (string, optional): Case-insensitive name substring

**Response:** `200 OK`
```json
[
  {
    "id": "metro_indiranagar",
    "name": "Indiranagar Metro Station",
    "mode": "metro",
    "line": "Purple Line",
    "lat": 12.9784,
    "lon": 77.6408,
    "transfer_hub": false
  }
]
```

### `GET /api/v1/search`
Searches for transit stations, bus stops, and key interchanges matching a query string.

**Query Parameters:**
- `q` (string, required): Search query term (e.g. `Whitefield`, `Silk Board`, `Majestic`)

---

## 3. Multimodal Journey Planning

### `POST /api/v1/plan`
Computes and ranks feasible multimodal journeys between an origin and destination coordinate pair.

**Request Body:**
```json
{
  "origin": {
    "lat": 12.9784,
    "lon": 77.6408,
    "name": "Indiranagar Metro"
  },
  "destination": {
    "lat": 12.9698,
    "lon": 77.7499,
    "name": "Whitefield Kadugodi"
  },
  "allowed_modes": ["walk", "bus", "metro", "drive"],
  "objective": "fastest"
}
```

**Supported Objectives:**
- `fastest`: Minimizes total elapsed journey duration.
- `lowest_cost`: Minimizes financial fare in ₹ INR.
- `least_walking`: Minimizes total pedestrian walk distance.
- `fewest_transfers`: Minimizes number of vehicle changes.
- `balanced`: Multi-criteria weighted cost function.

**Response:** `200 OK`
```json
{
  "origin": { "lat": 12.9784, "lon": 77.6408, "name": "Indiranagar Metro" },
  "destination": { "lat": 12.9698, "lon": 77.7499, "name": "Whitefield Kadugodi" },
  "query_timestamp": "2026-10-29T01:30:00Z",
  "journeys": [
    {
      "journey_id": "single_metro_pur_metro_indiranagar",
      "objective": "fastest",
      "summary": "Metro: Namma Metro Purple Line (Eastbound)",
      "total_duration_sec": 1250,
      "total_walking_duration_sec": 0,
      "total_walking_distance_meters": 0.0,
      "total_waiting_time_sec": 150,
      "total_transfers": 0,
      "estimated_fare_inr": 35.0,
      "modes_used": ["walk", "metro"],
      "legs": [
        {
          "leg_index": 0,
          "mode": "metro",
          "route_name": "Namma Metro Purple Line (Eastbound)",
          "from_stop_name": "Indiranagar Metro Station",
          "to_stop_name": "Whitefield (Kadugodi) Metro Station",
          "duration_sec": 1100,
          "distance_meters": 13400.0,
          "waiting_time_sec": 150,
          "estimated_fare_inr": 35.0,
          "polyline": [[77.6408, 12.9784], [77.7499, 12.9698]],
          "assumptions": ["Scheduled headway: 5 mins", "Official fare tier: metro_standard"]
        }
      ],
      "is_live_adjusted": false,
      "assumptions": ["Direct public transit route with zero vehicle interchanges."]
    }
  ],
  "routing_metadata": {
    "direct_distance_meters": 11842.1,
    "candidate_count": 8,
    "objective": "fastest"
  }
}
```

---

## 4. Error Handling
The API follows standard RFC 7807 error responses:
- `400 Bad Request`: Invalid coordinates or missing mandatory fields.
- `422 Unprocessable Entity`: Schema validation errors (handled automatically by Pydantic).
- `500 Internal Server Error`: Computation or database access faults with diagnostic message.
