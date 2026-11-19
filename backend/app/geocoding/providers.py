import hashlib
import asyncio
import time
from typing import Protocol
import httpx
from pydantic import ValidationError
from app.geocoding.models import Place

# Explicit search envelope, including Devanahalli, Anekal, Hoskote and Magadi outskirts.
BBOX = (77.15, 12.60, 78.00, 13.50)
ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"


def in_region(place: Place) -> bool:
    return BBOX[0] <= place.lon <= BBOX[2] and BBOX[1] <= place.lat <= BBOX[3]


class ProviderError(Exception):
    """Sanitized upstream failure; never includes URLs, queries or credentials."""


class RateLimited(ProviderError):
    def __init__(self, seconds=60):
        self.seconds = seconds
        super().__init__("Geocoding provider rate limited")


class GeocodingProvider(Protocol):
    name: str
    async def autocomplete(self, query: str, limit: int) -> list[Place]: ...


async def features(client: httpx.AsyncClient, url: str, params: dict) -> list:
    try:
        response = await client.get(url, params=params)
        if response.status_code == 429:
            try:
                seconds = min(3600, max(1, float(response.headers.get("Retry-After", "60"))))
            except ValueError:
                seconds = 60
            raise RateLimited(seconds)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("features"), list):
            raise ValueError("Invalid feature collection")
        return data["features"]
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        # Deliberately do not chain httpx exceptions: they contain the API key URL.
        raise ProviderError("Geocoding provider unavailable") from None


class GeoapifyAdapter:
    name = "geoapify"

    def __init__(self, client: httpx.AsyncClient, api_key: str):
        self.client, self.api_key = client, api_key
        self._gate = asyncio.Lock()
        self._next_request = 0.0
        self._cooldown_until = 0.0
        self._day = -1
        self._requests = 0

    async def autocomplete(self, query: str, limit: int) -> list[Place]:
        if not self.api_key:
            raise ProviderError("Geoapify is not configured")
        async with self._gate:
            now = time.monotonic()
            if now < self._cooldown_until:
                raise ProviderError("Geoapify temporarily rate limited")
            day = int(time.time() // 86400)
            if day != self._day:
                self._day, self._requests = day, 0
            if self._requests >= 3000:
                raise ProviderError("Local Geoapify daily budget reached")
            # Conservative 4 requests/sec per worker. Account-wide quotas require
            # deployment-level coordination; use one geocoding worker on Free.
            await asyncio.sleep(max(0, self._next_request - now))
            self._next_request = time.monotonic() + .25
            self._requests += 1
        try:
            items = await features(self.client, "https://api.geoapify.com/v1/geocode/autocomplete", {
            "text": query, "apiKey": self.api_key, "limit": limit, "lang": "en",
            "filter": "rect:" + ",".join(map(str, BBOX)),
            "bias": "proximity:77.5946,12.9716",
            })
        except RateLimited as exc:
            self._cooldown_until = time.monotonic() + exc.seconds
            raise
        results = []
        for item in items:
            try:
                p = item["properties"]
                if p.get("country_code", "in").lower() != "in":
                    continue
                rank = p.get("rank") or {}
                source = p.get("datasource") or {}
                place = Place(
                    place_id="geoapify:" + str(p["place_id"]),
                    name=p.get("name") or p.get("address_line1") or p["formatted"],
                    display_address=p["formatted"], lat=p["lat"], lon=p["lon"],
                    category=p.get("category") or p.get("result_type", "unknown"),
                    confidence=rank.get("confidence"),
                    street_confidence=rank.get("confidence_street_level"),
                    building_confidence=rank.get("confidence_building_level"),
                    provider=self.name, datasource=source,
                    attribution="Powered by Geoapify; " + ATTRIBUTION +
                        ("; " + str(source["attribution"]) if source.get("attribution") else ""),
                )
                if in_region(place):
                    results.append(place)
            except (KeyError, TypeError, ValueError, AttributeError, ValidationError):
                continue
        return results


class PhotonAdapter:
    name = "photon"

    def __init__(self, client: httpx.AsyncClient, base_url: str):
        self.client, self.base_url = client, base_url.rstrip("/")

    async def autocomplete(self, query: str, limit: int) -> list[Place]:
        if not self.base_url:
            raise ProviderError("Local Photon is not configured")
        items = await features(self.client, self.base_url + "/api", {
            "q": query, "limit": limit, "lang": "en", "lat": 12.9716, "lon": 77.5946,
            "bbox": ",".join(map(str, BBOX)), "countrycode": "IN",
        })
        results = []
        for item in items:
            try:
                p = item["properties"]
                if p.get("countrycode", "IN").upper() != "IN":
                    continue
                lon, lat = item["geometry"]["coordinates"][:2]
                address = ", ".join(str(p[k]) for k in
                    ("name", "housenumber", "street", "district", "city", "state", "postcode") if p.get(k))
                identity = f"{p.get('osm_type', '')}:{p.get('osm_id', '')}"
                if identity == ":":
                    identity = hashlib.sha256(f"{address}:{lat}:{lon}".encode()).hexdigest()[:24]
                place = Place(
                    place_id="photon:" + identity, name=p.get("name") or p.get("street") or address,
                    display_address=address, lat=lat, lon=lon,
                    category=p.get("osm_value") or p.get("type", "unknown"),
                    # Photon has no calibrated confidence; do not invent a probability.
                    provider=self.name, attribution=ATTRIBUTION,
                )
                if in_region(place):
                    results.append(place)
            except (KeyError, TypeError, ValueError, AttributeError, ValidationError):
                continue
        return results
