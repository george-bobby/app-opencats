from typing import Any

import asyncpg

from apps.odooproject.config.settings import settings


class AsyncPostgresClient:
    """Async Postgres client using asyncpg."""

    _pool: asyncpg.Pool | None = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """Get or create the connection pool."""
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                user=settings.POSTGRES_USERNAME,
                password=settings.POSTGRES_PASSWORD,
                database=settings.POSTGRES_DATABASE,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                min_size=5,
                max_size=20,
            )
        return cls._pool

    @classmethod
    async def close_pool(cls) -> None:
        """Close the connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    async def execute(cls, query: str, *args) -> str:
        """Execute a query that doesn't return rows."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def fetch(cls, query: str, *args) -> list[dict[str, Any]]:
        """Execute a query and return all results as dictionaries."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    @classmethod
    async def fetchrow(cls, query: str, *args) -> dict[str, Any] | None:
        """Execute a query and return the first result as a dictionary."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    @classmethod
    async def fetchval(cls, query: str, *args) -> Any:
        """Execute a query and return a single value."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    @classmethod
    async def get_non_admin_users(cls) -> list[dict[str, Any]]:
        """Get all users where email is not admin"""
        query = "SELECT * FROM users WHERE email != $1"
        return await cls.fetch(query, "admin")
