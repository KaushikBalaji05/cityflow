import asyncio
import logging
from app.geocoding.models import SearchMeta, SearchResponse
from app.geocoding.providers import ProviderError
from app.geocoding.relevance import normalize, query_variants, rank_unique, suitable

logger = logging.getLogger(__name__)


class GeocodingService:
    def __init__(self, primary, fallback, cache, overall=.85, street=.65, building=.85, timeout=5):
        self.primary, self.fallback, self.cache = primary, fallback, cache
        self.thresholds = (overall, street, building)
        self.inflight = {}
        self.timeout = timeout

    async def _call(self, provider, query):
        try:
            return await asyncio.wait_for(provider.autocomplete(query, 10), self.timeout)
        except (TimeoutError, asyncio.TimeoutError):
            raise ProviderError("Geocoding provider timed out") from None

    async def autocomplete(self, query: str, limit: int = 6):
        normalized = normalize(query)
        if len(normalized) < 3:
            raise ValueError("Enter at least three searchable characters")
        # Policy version covers region, language, thresholds and provider result limit.
        key = f"v1:en:{self.thresholds}:{normalized}"
        if key not in self.inflight:
            if len(self.inflight) >= 100:
                raise ProviderError("Location search is busy")
            task = asyncio.create_task(self._search(normalized, key))
            self.inflight[key] = task
            task.add_done_callback(lambda t: (self.inflight.pop(key, None),
                                              t.exception() if not t.cancelled() else None))
        response = await asyncio.shield(self.inflight[key])
        return SearchResponse(results=response.results[:limit],
                              meta=response.meta.model_copy(update={"query": query}))

    async def _search(self, query, key):
        # Cache failures must not turn provider success into a user-facing error.
        resolved = None
        try:
            async with self.cache.session(key) as cache:
                cached = await cache.get(key)
                resolved = await self._resolve(query, cached)
                if not resolved.meta.cache_hit:
                    await cache.put(key, resolved.results)
            return resolved
        except ProviderError:
            raise
        except Exception:
            logger.warning("Geocoding cache unavailable; using providers without persistence")
            if resolved is not None:
                return resolved
            return await self._resolve(query, None)

    async def _resolve(self, query, cached):
        failed = 0
        primary = cached
        if primary is None:
            try:
                primary = await self._call(self.primary, query)
            except ProviderError:
                failed += 1
                primary = []
                logger.warning("Primary geocoder unavailable")
        fallback_triggered = not suitable(query, primary, *self.thresholds)
        candidates = list(primary)
        if fallback_triggered:
            try:
                candidates.extend(await self._call(self.fallback, query))
                for variant in query_variants(query):
                    try:
                        candidates.extend(await self._call(self.fallback, variant))
                    except ProviderError:
                        pass
            except ProviderError:
                failed += 1
                logger.warning("Fallback geocoder unavailable")
        if failed == 2:
            raise ProviderError("Location search temporarily unavailable")
        return SearchResponse(results=rank_unique(query, candidates), meta=SearchMeta(
            query=query, cache_hit=cached is not None, fallback_triggered=fallback_triggered,
            degraded=failed > 0))
