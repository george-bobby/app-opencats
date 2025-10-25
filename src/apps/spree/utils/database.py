from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Connection, Pool

from apps.spree.config.settings import settings
from common.logger import Logger


logger = Logger()


class AsyncPGClient:
    """AsyncPG client with connection pooling for efficient connection reuse."""

    def __init__(self):
        self._pool: Pool | None = None
        self._connection_string = self._build_connection_string()

    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from settings."""
        return f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.APP_POSTGRES_HOST}:{settings.APP_POSTGRES_PORT}/{settings.POSTGRES_DB}"

    async def initialize_pool(self, min_size: int = 5, max_size: int = 20, command_timeout: int = 60, server_settings: dict | None = None) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            logger.warning("Pool already initialized")
            return

        try:
            self._pool = await asyncpg.create_pool(
                self._connection_string,
                min_size=min_size,
                max_size=max_size,
                command_timeout=command_timeout,
                server_settings=server_settings or {"application_name": "spree_app", "timezone": "UTC"},
            )
            logger.info(f"Database pool initialized with {min_size}-{max_size} connections")
        except Exception as e:
            logger.fail(f"Failed to initialize database pool: {e}")
            raise

    async def close_pool(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.succeed("Database pool closed")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Connection, None]:
        """Get a connection from the pool using context manager."""
        if self._pool is None:
            raise RuntimeError("Pool not initialized. Call initialize_pool() first.")

        async with self._pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                logger.fail(f"Database operation failed: {e}")
                raise

    async def execute(self, query: str, *args) -> str:
        """Execute a query and return the result."""
        async with self.get_connection() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list:
        """Fetch multiple rows from a query."""
        async with self.get_connection() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> asyncpg.Record | None:
        """Fetch a single row from a query."""
        async with self.get_connection() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """Fetch a single value from a query."""
        async with self.get_connection() as conn:
            return await conn.fetchval(query, *args)

    async def executemany(self, query: str, args_list: list) -> None:
        """Execute a query multiple times with different arguments."""
        async with self.get_connection() as conn:
            await conn.executemany(query, args_list)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Connection, None]:
        """Start a database transaction."""
        async with self.get_connection() as conn, conn.transaction():
            yield conn

    async def health_check(self) -> bool:
        """Check if the database connection is healthy."""
        try:
            async with self.get_connection() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.fail(f"Database health check failed: {e}")
            return False

    @property
    def pool_stats(self) -> dict:
        """Get connection pool statistics."""
        if self._pool is None:
            return {"status": "not_initialized"}

        return {
            "status": "active",
            "size": self._pool.get_size(),
            "max_size": self._pool.get_max_size(),
            "min_size": self._pool.get_min_size(),
            "idle_size": self._pool.get_idle_size(),
        }


# Create a singleton instance
db_client = AsyncPGClient()


# Convenience functions for common operations
async def init_db(min_size: int = 5, max_size: int = 20, command_timeout: int = 60) -> None:
    """Initialize the database connection pool."""
    await db_client.initialize_pool(min_size=min_size, max_size=max_size, command_timeout=command_timeout)


async def close_db() -> None:
    """Close the database connection pool."""
    await db_client.close_pool()


# Context manager for database lifecycle
@asynccontextmanager
async def database_lifespan(min_size: int = 5, max_size: int = 20, command_timeout: int = 60) -> AsyncGenerator[AsyncPGClient, None]:
    """Context manager for database lifecycle management."""
    await init_db(min_size, max_size, command_timeout)
    try:
        yield db_client
    finally:
        await close_db()
