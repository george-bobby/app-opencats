import time
import typing as t

import aiohttp
import requests

from apps.odooproject.config.settings import settings
from common.logger import logger


class OdooClient:
    """
    Asynchronous JSON-RPC client for interacting with Odoo API.
    """

    def __init__(self):
        """
        Initialize the Odoo JSON-RPC client.

        Args:
            url: Base URL of Odoo instance (e.g., "http://localhost:8069")
            db: Database name
            username: Odoo username for auto-authentication
            password: Odoo password for auto-authentication
        """
        self.url = settings.ODOO_URL
        self.db = settings.ODOO_DB
        self.username = settings.ODOO_USERNAME
        self.password = settings.ODOO_PASSWORD
        self.uid = None
        self.session = None
        self.headers = {
            "Content-Type": "application/json",
        }
        self._is_authenticated = False

    async def __aenter__(self):
        """Context manager entry point to create the aiohttp session."""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point to close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _ensure_session(self):
        """Ensure an aiohttp session exists."""
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers)
            return True  # Session was created
        return False  # Session already existed

    async def _ensure_authenticated(self):
        """Ensure the client is authenticated before making API calls."""
        if not self._is_authenticated:
            await self.authenticate(self.username, self.password)

    async def authenticate(self, username: str | None = None, password: str | None = None) -> int:
        """
        Authenticate with Odoo and store the user ID.

        Args:
            username: Odoo username (defaults to the one provided in constructor)
            password: Odoo password (defaults to the one provided in constructor)

        Returns:
            User ID if authentication successful

        Raises:
            Exception: If authentication fails
        """
        # Use provided credentials or fall back to instance attributes
        username = username or self.username
        password = password or self.password

        if not username or not password:
            raise Exception("Username and password are required for authentication")

        created_session = await self._ensure_session()

        endpoint = f"{self.url}/jsonrpc"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "common",
                "method": "login",
                "args": [self.db, username, password],
            },
            "id": 1,
        }

        async with self.session.post(endpoint, json=payload) as response:
            result = await response.json()

        if created_session and not self.session._in_context:
            await self.session.close()
            self.session = None

        if "error" in result:
            raise Exception(f"Authentication failed: {result['error']}")

        if not result.get("result"):
            raise Exception("Authentication failed: Invalid username or password")

        self.uid = result["result"]
        self.password = password
        self._is_authenticated = True

        return self.uid

    async def execute_kw(self, model: str, method: str, args: list | None = None, kwargs: dict | None = None) -> t.Any:
        """
        Execute a method on an Odoo model using execute_kw.

        Args:
            model: Odoo model name (e.g., "stock.picking")
            method: Method to call (e.g., "search_read")
            args: Positional arguments for the method
            kwargs: Keyword arguments for the method

        Returns:
            Result from the Odoo API

        Raises:
            Exception: If the API call fails
        """
        # Auto-authenticate if needed
        await self._ensure_authenticated()

        created_session = await self._ensure_session()

        args = args or []
        kwargs = kwargs or {}

        # Prepend authentication parameters to args
        auth_args = [self.db, self.uid, self.password, model, method]
        full_args = [*auth_args, args]
        if kwargs:
            full_args.append(kwargs)

        endpoint = f"{self.url}/jsonrpc"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": "object", "method": "execute_kw", "args": full_args},
            "id": 2,
        }

        # logger.info(f"Payload: {json.dumps(payload, indent=4)}")

        async with self.session.post(endpoint, json=payload) as response:
            result = await response.json()

        if created_session and not self.session._in_context:
            await self.session.close()
            self.session = None

        if "error" in result:
            if "data" in result["error"] and "message" in result["error"]["data"]:
                message = result["error"]["data"]["message"]
            raise Exception(message or "Unknown error")

        return result.get("result")

    async def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order: str | None = None,
    ) -> list[dict]:
        """
        Convenience method for search_read operations.

        Args:
            model: Odoo model name
            domain: Search domain (e.g., [('state', '=', 'done')])
            fields: List of fields to fetch
            limit: Maximum number of records
            offset: Number of records to skip
            order: Sorting order (e.g., "id desc")

        Returns:
            List of records matching the criteria
        """

        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order

        return await self.execute_kw(model, "search_read", [domain or []], kwargs)

    async def create(self, model: str, values: dict | list[dict]) -> int:
        """
        Create a new record in the specified model.

        Args:
            model: Odoo model name
            values: Field values for the new record

        Returns:
            ID of the newly created record
        """

        args = values if isinstance(values, list) else [values]
        return await self.execute_kw(model, "create", args)

    async def write(self, model: str, ids: int | list[int], values: dict) -> bool:
        """
        Update existing records.

        Args:
            model: Odoo model name
            ids: Record ID or list of record IDs to update
            values: Field values to update

        Returns:
            True if successful
        """

        ids_list = [ids] if isinstance(ids, int) else ids
        return await self.execute_kw(model, "write", [ids_list, values])

    async def unlink(self, model: str, ids: int | list[int]) -> bool:
        """
        Delete records from the specified model.

        Args:
            model: Odoo model name
            ids: Record ID or list of record IDs to delete

        Returns:
            True if successful
        """

        ids_list = [ids] if isinstance(ids, int) else ids

        return await self.execute_kw(model, "unlink", [ids_list])


def create_odoo_db():
    """Create a new Odoo database using credentials from settings"""

    # Now create the database
    url = f"{settings.ODOO_URL}/web/database/create"

    # Form data matching the curl command
    form_data = {
        "master_pwd": "admin",
        "name": settings.ODOO_DB,
        "login": settings.ODOO_USERNAME,
        "password": settings.ODOO_PASSWORD,
        "phone": "",
        "lang": "en_US",
        "country_code": "",
    }

    cookies = {
        "session_id": "Q22sIIC0XqS-RO4xszKuJCCfuBvMxO5Y-EqBYNfBO1p8lxCcGJeBpwzads_Z3_jpUtdf0EU7GNfJPyPcg5Q7",
        "cids": "1",
        "tz": "Asia/Saigon",
    }

    # Headers matching the curl command
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "DNT": "1",
        "Origin": settings.ODOO_URL,
        "Referer": f"{settings.ODOO_URL}/web/database/selector",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Not.A/Brand";v="99", "Chromium";v="136"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }

    try:
        logger.info(f"Creating database '{settings.ODOO_DB}' at {settings.ODOO_URL}...")
        response = requests.post(url, data=form_data, headers=headers, cookies=cookies)

        if response.status_code == 200:
            response_text = response.text
            if "oe_login_form" in response_text:
                logger.info(f"Database '{settings.ODOO_DB}' created successfully!")
                logger.info(f"Access URL: {settings.ODOO_URL}")
                logger.info(f"Admin login: {settings.ODOO_USERNAME}")
                logger.info(f"Admin password: {settings.ODOO_PASSWORD}")
                logger.info("----- Ready to seed data -----")
            else:
                logger.info("Database creation may have failed. Check the response.")
                logger.info(f"Response status: {response.status_code}")
        else:
            logger.info(f"Failed to create database. HTTP status: {response.status_code}")
            logger.info(f"Error response: {response.text[:500]}...")

    except Exception as e:
        logger.error(f"Error creating database: {e!s}")


def check_odoo_status():
    """Check if Odoo server is accessible"""
    url = f"{settings.ODOO_URL}/web/database/selector"
    max_retries = 30
    retry_delay = 2

    logger.info(f"Checking Odoo status at {settings.ODOO_URL}...")

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                response_text = response.text
                if "database" in response_text.lower():
                    return True

        except Exception:
            pass

        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    return False
