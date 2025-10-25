import typing as t

import asyncpg

from apps.supabase.config.settings import settings


class PostgresClient:
    """
    Asynchronous PostgreSQL client using asyncpg with connection pooling.
    """

    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self._dsn = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.LOCAL_POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

    async def __aenter__(self):
        if self.pool is None:
            self.pool = await asyncpg.create_pool(dsn=self._dsn, min_size=1, max_size=10)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def execute(self, query: str, *args) -> str:
        """
        Execute a SQL command (INSERT, UPDATE, DELETE, etc.).
        Returns the status string.
        """
        if self.pool is None:
            raise RuntimeError("Connection pool is not initialized. Use 'async with PostgresClient()'.")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        """
        Execute a SELECT query and return all results as a list of asyncpg.Record.
        """
        if self.pool is None:
            raise RuntimeError("Connection pool is not initialized. Use 'async with PostgresClient()'.")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> asyncpg.Record | None:
        """
        Execute a SELECT query and return a single row (or None).
        """
        if self.pool is None:
            raise RuntimeError("Connection pool is not initialized. Use 'async with PostgresClient()'.")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args) -> t.Any:
        """
        Execute a SELECT query and return a single value (first column of the first row).
        """
        if self.pool is None:
            raise RuntimeError("Connection pool is not initialized. Use 'async with PostgresClient()'.")
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
