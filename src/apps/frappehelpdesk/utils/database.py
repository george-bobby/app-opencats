from contextlib import asynccontextmanager
from typing import Any

import aiomysql
from aiomysql import Connection, Cursor, Pool

from apps.frappehelpdesk.config.settings import settings
from common.logger import logger


class AsyncMariaDBClient:
    """Async MariaDB/MySQL client with connection pooling for Frappe Helpdesk."""

    def __init__(
        self,
        host: str = settings.MYSQL_HOST,
        port: int = settings.MYSQL_PORT,
        user: str = settings.MYSQL_USER,
        password: str = settings.MYSQL_PASSWORD,
        database: str | None = None,
        charset: str = "utf8mb4",
        autocommit: bool = True,
        minsize: int = 1,
        maxsize: int = 10,
        pool_recycle: int = 3600,
        **kwargs,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database  # Will be auto-detected if None
        self.charset = charset
        self.autocommit = autocommit
        self.minsize = minsize
        self.maxsize = maxsize
        self.pool_recycle = pool_recycle
        self.kwargs = kwargs
        self._pool: Pool | None = None

    async def _get_first_underscore_database(self) -> str:
        """Get the first database whose name starts with underscore."""
        # Create a temporary connection without specifying database
        temp_conn = await aiomysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            charset=self.charset,
        )

        try:
            cursor = await temp_conn.cursor()
            try:
                # Get all databases that start with underscore
                await cursor.execute("SHOW DATABASES LIKE '\\_%'")
                databases = await cursor.fetchall()

                if not databases:
                    raise RuntimeError("No databases found with names starting with '_'")

                # Return the first database name (remove the tuple wrapper)
                first_db = databases[0][0]
                return first_db

            finally:
                await cursor.close()
        finally:
            temp_conn.close()

    async def get_available_databases(self) -> list[str]:
        """Get all databases whose names start with underscore."""
        # Create a temporary connection without specifying database
        temp_conn = await aiomysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            charset=self.charset,
        )

        try:
            cursor = await temp_conn.cursor()
            try:
                # Get all databases that start with underscore
                await cursor.execute("SHOW DATABASES LIKE '\\_%'")
                databases = await cursor.fetchall()
                return [db[0] for db in databases]
            finally:
                await cursor.close()
        finally:
            temp_conn.close()

    async def connect(self) -> None:
        """Initialize the connection pool."""
        try:
            # Auto-detect database if not specified
            if self.database is None:
                self.database = await self._get_first_underscore_database()

            self._pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                charset=self.charset,
                autocommit=self.autocommit,
                minsize=self.minsize,
                maxsize=self.maxsize,
                pool_recycle=self.pool_recycle,
                **self.kwargs,
            )
        except Exception as e:
            logger.error(f"Failed to connect to MariaDB: {e}")
            raise

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            logger.info("Disconnected from MariaDB database")

    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        conn: Connection = await self._pool.acquire()
        try:
            yield conn
        finally:
            self._pool.release(conn)

    @asynccontextmanager
    async def get_cursor(self, cursor_class=None):
        """Get a cursor with automatic connection management."""
        async with self.get_connection() as conn:
            if cursor_class is None:
                cursor: Cursor = await conn.cursor()
            else:
                cursor: Cursor = await conn.cursor(cursor_class)
            try:
                yield cursor
            finally:
                await cursor.close()

    async def execute(
        self,
        query: str,
        params: tuple | list | dict | None = None,
        fetch: bool = False,
        fetchall: bool = False,
        fetchone: bool = False,
    ) -> Any | None:
        """Execute a query with optional fetching."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(query, params)

                if fetchall:
                    return await cursor.fetchall()
                elif fetchone:
                    return await cursor.fetchone()
                elif fetch:
                    return await cursor.fetchall()

                return cursor.rowcount
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                logger.error(f"Query: {query}")
                logger.error(f"Params: {params}")
                raise

    async def execute_many(self, query: str, params_list: list[tuple | list | dict]) -> int:
        """Execute the same query with multiple parameter sets."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.executemany(query, params_list)
                return cursor.rowcount
            except Exception as e:
                logger.error(f"Batch query execution failed: {e}")
                logger.error(f"Query: {query}")
                raise

    async def fetch_all(self, query: str, params: tuple | list | dict | None = None) -> list[tuple]:
        """Fetch all results from a SELECT query."""
        return await self.execute(query, params, fetchall=True)

    async def fetch_one(self, query: str, params: tuple | list | dict | None = None) -> tuple | None:
        """Fetch one result from a SELECT query."""
        return await self.execute(query, params, fetchone=True)

    async def fetch_dict_all(self, query: str, params: tuple | list | dict | None = None) -> list[dict[str, Any]]:
        """Fetch all results as dictionaries."""
        async with self.get_cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, params)
            return await cursor.fetchall()

    async def fetch_dict_one(self, query: str, params: tuple | list | dict | None = None) -> dict[str, Any] | None:
        """Fetch one result as a dictionary."""
        async with self.get_cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, params)
            return await cursor.fetchone()

    async def insert(self, table: str, data: dict[str, Any]) -> int:
        """Insert a single record and return the last insert ID."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        async with self.get_cursor() as cursor:
            await cursor.execute(query, list(data.values()))
            return cursor.lastrowid

    async def insert_many(self, table: str, data_list: list[dict[str, Any]]) -> int:
        """Insert multiple records."""
        if not data_list:
            return 0

        columns = ", ".join(data_list[0].keys())
        placeholders = ", ".join(["%s"] * len(data_list[0]))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        params_list = [list(data.values()) for data in data_list]
        return await self.execute_many(query, params_list)

    async def update(
        self,
        table: str,
        data: dict[str, Any],
        where_clause: str,
        where_params: tuple | list | None = None,
    ) -> int:
        """Update records in a table."""
        set_clause = ", ".join([f"{key} = %s" for key in data])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

        params = list(data.values())
        if where_params:
            params.extend(where_params if isinstance(where_params, list | tuple) else [where_params])

        return await self.execute(query, params)

    async def delete(
        self,
        table: str,
        where_clause: str,
        where_params: tuple | list | None = None,
    ) -> int:
        """Delete records from a table."""
        query = f"DELETE FROM {table} WHERE {where_clause}"
        return await self.execute(query, where_params)

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        query = """
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
        """
        result = await self.fetch_one(query, (self.database, table_name))
        return result[0] > 0 if result else False

    async def get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        """Get column information for a table."""
        query = """
        SELECT column_name, data_type, is_nullable, column_default, column_key
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """
        return await self.fetch_dict_all(query, (self.database, table_name))

    async def get_frappe_doctype_list(self, doctype: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Get a list of documents from a Frappe doctype table."""
        table_name = f"tab{doctype.replace(' ', '')}"
        query = f"SELECT * FROM `{table_name}` WHERE docstatus != 2 ORDER BY creation DESC LIMIT %s OFFSET %s"
        return await self.fetch_dict_all(query, (limit, offset))

    async def get_frappe_doc(self, doctype: str, name: str) -> dict[str, Any] | None:
        """Get a single Frappe document by name."""
        table_name = f"tab{doctype.replace(' ', '')}"
        query = f"SELECT * FROM `{table_name}` WHERE name = %s AND docstatus != 2"
        return await self.fetch_dict_one(query, (name,))

    async def create_frappe_doc(self, doctype: str, data: dict[str, Any]) -> str:
        """Create a new Frappe document."""
        table_name = f"tab{doctype.replace(' ', '')}"

        # Add default Frappe fields if not present
        frappe_defaults = {
            "docstatus": 0,
            "idx": 0,
            "creation": "NOW()",
            "modified": "NOW()",
            "modified_by": "Administrator",
            "owner": "Administrator",
        }

        for key, value in frappe_defaults.items():
            if key not in data:
                data[key] = value

        return await self.insert(table_name, data)

    async def start_transaction(self):
        """Start a transaction context manager."""
        return TransactionContext(self)


class TransactionContext:
    """Transaction context manager for MariaDB operations."""

    def __init__(self, client: AsyncMariaDBClient):
        self.client = client
        self.connection: Connection | None = None

    async def __aenter__(self):
        if not self.client._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        self.connection = await self.client._pool.acquire()
        await self.connection.begin()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                await self.connection.commit()
            else:
                await self.connection.rollback()
        finally:
            if self.connection:
                self.client._pool.release(self.connection)

    async def execute(self, query: str, params: tuple | list | dict | None = None):
        """Execute a query within the transaction."""
        cursor = await self.connection.cursor()
        try:
            await cursor.execute(query, params)
            return cursor.rowcount
        finally:
            await cursor.close()

    async def fetch_all(self, query: str, params: tuple | list | dict | None = None):
        """Fetch all results within the transaction."""
        cursor = await self.connection.cursor()
        try:
            await cursor.execute(query, params)
            return await cursor.fetchall()
        finally:
            await cursor.close()


# Factory function to create and connect MariaDB client
async def create_mariadb_client(
    host: str = settings.MYSQL_HOST,
    port: int = settings.MYSQL_PORT,
    user: str = settings.MYSQL_USER,
    password: str = settings.MYSQL_PASSWORD,
    database: str | None = None,  # Auto-detect if None
    **kwargs,
) -> AsyncMariaDBClient:
    """Factory function to create and connect MariaDB client."""
    client = AsyncMariaDBClient(host=host, port=port, user=user, password=password, database=database, **kwargs)
    await client.connect()
    return client


# Example usage
if __name__ == "__main__":

    async def example():
        # Create client (uses settings from config.py by default)
        client = await create_mariadb_client()

        try:
            # Check if connected
            logger.info("Testing MariaDB connection...")

            # Example: Get list of help desk tickets
            tickets = await client.get_frappe_doctype_list("HD Ticket", limit=10)
            logger.info(f"Found {len(tickets)} help desk tickets")

            # Example: Get a specific ticket
            if tickets:
                ticket_name = tickets[0].get("name")
                ticket = await client.get_frappe_doc("HD Ticket", ticket_name)
                logger.info(f"Retrieved ticket: {ticket.get('subject', 'No subject')}")

            # Example: Create a new ticket (demo)
            # new_ticket_data = {
            #     "name": "NEW-TICKET-001",
            #     "subject": "Test ticket from async client",
            #     "description": "This is a test ticket created via async MariaDB client",
            #     "status": "Open",
            #     "priority": "Medium"
            # }
            # ticket_id = await client.create_frappe_doc("HD Ticket", new_ticket_data)
            # logger.info(f"Created new ticket with ID: {ticket_id}")

            # Transaction example
            async with client.start_transaction() as tx:
                await tx.execute("SELECT COUNT(*) FROM `tabHD Ticket`")
                # More transactional operations...

        finally:
            await client.disconnect()

    # Run example (uncomment to test)
    # asyncio.run(example())
