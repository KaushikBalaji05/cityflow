"""Separate Geoapify-only cache. Photon content never enters this database."""
import hashlib
import json
import asyncio
from contextlib import asynccontextmanager
from app.geocoding.models import Place


class NullCache:
    @asynccontextmanager
    async def session(self, key):
        yield self

    async def get(self, key):
        return None

    async def put(self, key, places):
        pass


class PostgresCache:
    def __init__(self, url: str, ttl: int):
        self.url = url.replace("postgresql+asyncpg://", "postgresql://")
        self.ttl = ttl

    @asynccontextmanager
    async def session(self, key):
        import psycopg
        # Transaction-scoped lock also coalesces requests across backend workers.
        lock = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
        # Psycopg sync connections are thread-safe. Offload all I/O so native
        # Windows Proactor loops work too (psycopg.AsyncConnection requires Selector).
        conn = await asyncio.to_thread(psycopg.connect, self.url, connect_timeout=3)
        try:
            await asyncio.to_thread(conn.execute, "SET LOCAL statement_timeout = '15000ms'")
            await asyncio.to_thread(conn.execute, "SELECT pg_advisory_xact_lock(%s)", (lock,))
            yield CacheTransaction(conn, self.ttl)
            await asyncio.to_thread(conn.commit)
        except BaseException:
            await asyncio.to_thread(conn.rollback)
            raise
        finally:
            await asyncio.to_thread(conn.close)


class CacheTransaction:
    def __init__(self, conn, ttl):
        self.conn, self.ttl = conn, ttl

    async def get(self, key):
        def read():
            return self.conn.execute(
                "SELECT results FROM geocoding_cache WHERE normalized_query=%s "
                "AND provider='geoapify' AND expires_at > now()", (key,)).fetchone()
        row = await asyncio.to_thread(read)
        if not row:
            return None
        places = [Place.model_validate(p) for p in row[0]]
        return [p for p in places if p.provider == "geoapify"]

    async def put(self, key, places):
        eligible = [p.model_dump() for p in places if p.provider == "geoapify"]
        if not eligible:
            return
        await asyncio.to_thread(self.conn.execute,
            "INSERT INTO geocoding_cache (normalized_query,provider,results,expires_at) "
            "VALUES (%s,'geoapify',%s::jsonb,now()+%s * interval '1 second') "
            "ON CONFLICT (normalized_query,provider) DO UPDATE SET results=excluded.results, "
            "created_at=now(),expires_at=excluded.expires_at",
            (key, json.dumps(eligible), self.ttl))
