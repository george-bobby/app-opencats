"""
Simple Teable API Client using aiohttp with cookie-based authentication
"""

import asyncio
import json
from typing import Any, Literal
from urllib.parse import urljoin

import aiohttp

from apps.teable.config.settings import settings
from common.logger import Logger


logger = Logger()


class TeableEntity:
    Literal["space", "base", "table", "record"]


class TeableAPIError(Exception):
    """Base exception for Teable API errors"""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class TeableAuthError(TeableAPIError):
    """Authentication related errors"""

    pass


class TeableClient:
    """
    Simple Teable API Client with cookie-based authentication
    Automatically logs in when first used.
    """

    def __init__(self, base_url: str | None = None, auto_login: bool = True):
        """
        Initialize Teable client

        Args:
            base_url: Base URL for Teable instance (defaults to settings.TEABLE_URL)
            auto_login: Whether to automatically login on first use (default: True)
        """
        self.base_url = base_url or settings.TEABLE_URL
        self._session: aiohttp.ClientSession | None = None
        self._logged_in = False
        self._auto_login = auto_login
        self._login_attempted = False
        self._login_lock = asyncio.Lock()

    async def __aenter__(self):
        """Async context manager entry"""
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def setup(self):
        """Initialize the session with cookie jar and optionally login"""
        if self._session is None:
            jar = aiohttp.CookieJar()
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                cookie_jar=jar,
                headers={
                    "User-Agent": "Teable-Python-Client/1.0",
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                },
            )

        # Auto-login if enabled and not already attempted
        if self._auto_login and not self._login_attempted:
            await self._ensure_logged_in()

    async def close(self):
        """Close the session"""
        if self._session:
            await self._session.close()
            self._session = None
            self._logged_in = False
            self._login_attempted = False
            self._login_lock = asyncio.Lock()

    async def _ensure_logged_in(self):
        """Ensure user is logged in, attempt login/signup if needed"""
        if self._logged_in:
            return

        async with self._login_lock:
            # Double-check after acquiring the lock
            if self._logged_in or self._login_attempted:
                return

            self._login_attempted = True

            try:
                # Try to login first
                await self.login()
            except TeableAuthError:
                logger.info("Login failed, attempting to create admin user...")
                try:
                    # Try to signup the admin user
                    await self.signup(
                        email=settings.TEABLE_ADMIN_EMAIL,
                        password=settings.TEABLE_ADMIN_PASSWORD,
                        default_space_name="Admin's Workspace",
                    )
                    # Now login with the newly created user
                    await self.login()
                except Exception as e:
                    raise TeableAuthError(f"Both login and signup failed: {e!s}")

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Make HTTP request to Teable API

        Args:
            method: HTTP method
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            TeableAPIError: For API errors
        """
        if not self._session:
            await self.setup()

        # Ensure we're logged in for non-auth endpoints
        if not endpoint.endswith(("/signin", "/signup")) and self._auto_login:
            await self._ensure_logged_in()

        url = urljoin(self.base_url.rstrip("/") + "/", endpoint.lstrip("/"))

        request_kwargs = {"params": params, **kwargs}

        if data is not None:
            request_kwargs["json"] = data

        try:
            async with self._session.request(method, url, **request_kwargs) as response:
                response_text = await response.text()

                # Try to parse JSON response
                try:
                    response_data = json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    response_data = {"message": response_text}

                if response.status in (200, 201):
                    return response_data
                elif response.status == 401:
                    self._logged_in = False
                    raise TeableAuthError("Authentication failed", response.status, response_data)
                elif response.status == 400:
                    error_msg = "Validation error"
                    if isinstance(response_data, dict) and "message" in response_data:
                        error_msg += f": {response_data['message']}"
                    raise TeableAPIError(error_msg, response.status, response_data)
                else:
                    # logger.info(f"Request data: {json.dumps(response_data, indent=2)}")
                    raise TeableAPIError(f"API error: {response.status} {response_data}", response.status, response_data)

        except aiohttp.ClientError as e:
            raise TeableAPIError(f"Network error: {e!s}")

    async def login(self, email: str | None = None, password: str | None = None) -> dict[str, Any]:
        """
        Login to Teable using email and password

        Args:
            email: User email (defaults to settings.TEABLE_ADMIN_EMAIL)
            password: User password (defaults to settings.TEABLE_ADMIN_PASSWORD)

        Returns:
            Login response data

        Raises:
            TeableAuthError: If login fails
        """
        email = email or settings.TEABLE_ADMIN_EMAIL
        password = password or settings.TEABLE_ADMIN_PASSWORD

        login_data = {"email": email, "password": password}

        try:
            logger.info(f"Attempting to login as: {email}")
            response = await self._request("POST", "/api/auth/signin", data=login_data)

            self._logged_in = True
            logger.info("✓ Login successful")
            return response

        except TeableAPIError as e:
            logger.fail(f"Login failed: {e}")
            self._logged_in = False
            raise TeableAuthError(f"Login failed: {e!s}")

    async def signup(
        self,
        email: str = settings.TEABLE_ADMIN_EMAIL,
        password: str = settings.TEABLE_ADMIN_PASSWORD,
        default_space_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Sign up a new user

        Args:
            email: User email
            password: User password
            default_space_name: Name for the default space

        Returns:
            Signup response data
        """
        if not default_space_name:
            username = email.split("@")[0]
            default_space_name = f"{username}'s space"

        signup_data = {
            "email": email,
            "password": password,
            "defaultSpaceName": default_space_name,
            "refMeta": {"query": ""},
        }

        try:
            logger.info(f"Attempting to sign up user: {email}")
            response = await self._request("POST", "/api/auth/signup", data=signup_data)
            logger.succeed("Signup successful")
            return response

        except TeableAPIError as e:
            logger.fail(f"Signup failed: {e}")
            raise

    async def get_current_user(self) -> dict[str, Any]:
        """
        Get current authenticated user information

        Returns:
            Current user data
        """
        return await self._request("GET", "/api/user/me")

    async def get_spaces(self) -> dict[str, Any]:
        """
        Get all spaces accessible to the current user

        Returns:
            Spaces data
        """
        return await self._request("GET", "/api/space")

    async def get_bases(self, space_id: str) -> dict[str, Any]:
        """
        Get all bases filtered by space

        Args:
            space_id: Space ID to filter bases

        Returns:
            Bases data
        """
        params = {"spaceId": space_id}
        return await self._request("GET", f"/api/space/{space_id}/base", params=params)

    async def get_tables(self, base_id: str) -> dict[str, Any]:
        """
        Get all tables in a base

        Args:
            base_id: ID of the base

        Returns:
            Tables data
        """
        return await self._request("GET", f"/api/base/{base_id}/table")

    async def get_records(
        self,
        table_id: str,
        take: int | None = 1000,
        skip: int | None = None,
        projection: list[str] | None = None,
        cell_format: str | None = None,
        field_key_type: str | None = None,
        view_id: str | None = None,
        ignore_view_query: str | None = None,
        filter_by_tql: str | None = None,
        filter: str | None = None,  # noqa: A002
        search: list[str] | None = None,
        filter_link_cell_candidate: list[str] | None = None,
        filter_link_cell_selected: list[str] | None = None,
        selected_record_ids: list[str] | None = None,
        order_by: str | None = None,
        group_by: str | None = None,
        collapsed_group_ids: str | None = None,
        query_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get records from a table with comprehensive filtering options

        Args:
            table_id: ID of the table
            take: Number of records per page (default: 1000)
            skip: Number of records to skip for pagination
            projection: List of field names to include in response
            cell_format: Format for cell values
            field_key_type: Type of field keys to use ("id" or "name")
            view_id: ID of the view to apply
            ignore_view_query: Whether to ignore view query
            filter_by_tql: TQL (Teable Query Language) filter expression
            filter: Additional filter string
            search: List of search terms
            filter_link_cell_candidate: List of link cell candidates to filter by
            filter_link_cell_selected: List of selected link cells to filter by
            selected_record_ids: List of specific record IDs to include
            order_by: Field to sort by
            group_by: Field to group by
            collapsed_group_ids: IDs of collapsed groups
            query_id: Query ID for saved queries

        Returns:
            Records data
        """
        params = {}

        if take:
            params["take"] = take
        if skip is not None:
            params["skip"] = skip
        if projection:
            params["projection"] = projection
        if cell_format:
            params["cellFormat"] = cell_format
        if field_key_type:
            params["fieldKeyType"] = field_key_type
        if view_id:
            params["viewId"] = view_id
        if ignore_view_query:
            params["ignoreViewQuery"] = ignore_view_query
        if filter_by_tql:
            params["filterByTql"] = filter_by_tql
        if filter:
            params["filter"] = filter
        if search:
            params["search"] = search
        if filter_link_cell_candidate:
            params["filterLinkCellCandidate"] = filter_link_cell_candidate
        if filter_link_cell_selected:
            params["filterLinkCellSelected"] = filter_link_cell_selected
        if selected_record_ids:
            params["selectedRecordIds"] = selected_record_ids
        if order_by:
            params["orderBy"] = order_by
        if group_by:
            params["groupBy"] = group_by
        if collapsed_group_ids:
            params["collapsedGroupIds"] = collapsed_group_ids
        if query_id:
            params["queryId"] = query_id

        return await self._request("GET", f"/api/table/{table_id}/record", params=params)

    @property
    def is_logged_in(self) -> bool:
        """Check if user is currently logged in"""
        return self._logged_in

    async def delete(self, entity: TeableEntity, _id: str) -> dict[str, Any]:
        return await self._request("DELETE", f"/api/{entity}/{_id}")

    async def create(self, entity: TeableEntity, data: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/api/{entity}", json=data)

    async def create_base(self, space_id: str, name: str) -> dict[str, Any]:
        """
        Create a new base in a space

        Args:
            space_id: ID of the space to create the base in
            name: Name of the base to create

        Returns:
            Base data
        """
        data = {"spaceId": space_id, "name": name}
        return await self._request("POST", "/api/base", json=data)

    async def create_table(
        self,
        base_id: str,
        name: str,
        fields: list[dict[str, Any]],
        records: list[dict[str, Any]] | None = None,
        views: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new table in a base

        Args:
            base_id: ID of the base to create the table in
            name: Name of the table to create
            views: List of view configurations
            fields: List of field configurations

        Returns:
            Table data
        """
        if views is None:
            views = [{"name": "Grid View", "type": "grid"}]
        data = {"name": name, "views": views, "fields": fields}
        if records:
            data["records"] = records

        # logger.info(json.dumps(data, indent=2))

        return await self._request("POST", f"/api/base/{base_id}/table/", json=data)

    async def assign_user_to_space(self, space_id: str, emails: list[str], role: str = "creator") -> dict[str, Any]:
        """
        Invite users to a space by email

        Args:
            space_id: ID of the space to invite to
            emails: List of email addresses to invite
            role: Role to assign, defaults to "creator"

        Returns:
            Response data
        """
        data = {"emails": emails, "role": role}
        return await self._request("POST", f"/api/space/{space_id}/invitation/email", data=data)

    async def upload_attachment(
        self,
        table_id: str,
        record_id: str,
        field_id: str,
        file_url: str,
    ) -> dict[str, Any]:
        """
        Upload an attachment to a specific field of a record using a file URL.

        Args:
            table_id: ID of the table
            record_id: ID of the record
            field_id: ID of the field
            file_url: URL of the file to upload
            token: Optional Bearer token for Authorization header

        Returns:
            Response data
        """
        # Use the standard _request method with JSON data
        endpoint = f"/api/table/{table_id}/record/{record_id}/{field_id}/uploadAttachment"
        data = {"fileUrl": file_url}

        return await self._request("POST", endpoint, data=data)

    async def get_fields(
        self,
        table_id: str,
        view_id: str | None = None,
        filter_hidden: bool | None = None,
        projection: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Get fields for a table

        Args:
            table_id: ID of the table
            view_id: Optional view ID to filter fields
            filter_hidden: Optional boolean to filter hidden fields
            projection: Optional list of field properties to return

        Returns:
            Dictionary containing field data
        """
        params = {}
        if view_id:
            params["viewId"] = view_id
        if filter_hidden is not None:
            params["filterHidden"] = str(filter_hidden).lower()
        if projection:
            params["projection"] = ",".join(projection)

        return await self._request("GET", f"/api/table/{table_id}/field", params=params)

    async def get_linked_records(
        self,
        table_id: str,
        field_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Get linked records for a specific field in a table

        Args:
            table_id: ID of the table
            field_id: ID of the link field
            params: Optional query parameters

        Returns:
            Dictionary containing linked record data
        """
        endpoint = f"/api/table/{table_id}/field/{field_id}/filter-link-records"
        return await self._request("GET", endpoint, params=params)

    async def add_field(
        self,
        table_id: str,
        name: str,
        field_type: str,
        options: dict[str, Any] | None = None,
        unique: bool | None = None,
        not_null: bool | None = None,
        description: str | None = None,
        lookup_options: dict[str, Any] | None = None,
        ai_config: dict[str, Any] | None = None,
        order: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add a new field to a table

        Args:
            table_id: ID of the table
            name: Name of the field
            field_type: Type of field (e.g. 'singleSelect', 'text', etc)
            options: Optional field options like formatting, choices etc
            unique: Optional boolean indicating if field values must be unique
            not_null: Optional boolean indicating if field is required
            description: Optional field description
            lookup_options: Optional lookup field configuration
            ai_config: Optional AI field configuration
            order: Optional field order configuration

        Returns:
            Dictionary containing the created field data
        """
        data = {
            "name": name,
            "type": field_type,
        }

        if options:
            data["options"] = options
        if unique is not None:
            data["unique"] = unique
        if not_null is not None:
            data["notNull"] = not_null
        if description:
            data["description"] = description
        if lookup_options:
            data["lookupOptions"] = lookup_options
        if ai_config:
            data["aiConfig"] = ai_config
        if order:
            data["order"] = order

        return await self._request("POST", f"/api/table/{table_id}/field", json=data)

    async def delete_record(self, table_id: str, record_ids: list[str]) -> dict[str, Any]:
        """
        Delete one or more records from a table

        Args:
            table_id: ID of the table
            record_ids: List of record IDs to delete

        Returns:
            Dictionary containing the deletion response
        """
        params = {"recordIds": record_ids}
        return await self._request("DELETE", f"/api/table/{table_id}/record", params=params)

    async def create_record(
        self,
        table_id: str,
        records: list[dict],
        field_key_type: str = "name",
        typecast: bool = True,
        order: dict | None = None,
    ) -> dict[str, Any]:
        """
        Create one or more records in a table

        Args:
            table_id: ID of the table
            records: List of record data dictionaries, each containing a "fields" key mapping field names to values
            field_key_type: Type of field keys to use ("id" or "name")
            typecast: Whether to automatically convert field values to the correct type
            order: Optional record ordering configuration with viewId, anchorId and position

        Returns:
            Dictionary containing the created record data
        """
        data = {
            "fieldKeyType": field_key_type,
            "typecast": typecast,
            "records": records,
        }

        if order:
            data["order"] = order

        return await self._request("POST", f"/api/table/{table_id}/record", json=data)

    async def update_record(
        self,
        table_id: str,
        record_id: str,
        record: dict[str, Any],
        field_key_type: str = "name",
        typecast: bool = True,
        order: dict | None = None,
    ) -> dict[str, Any]:
        """
        Update a record in a table

        Args:
            table_id: ID of the table
            record_id: ID of the record to update
            record: Record data dictionary containing a "fields" key mapping field names to values
            field_key_type: Type of field keys to use ("id" or "name")
            typecast: Whether to automatically convert field values to the correct type
            order: Optional record ordering configuration with viewId, anchorId and position

        Returns:
            Dictionary containing the updated record data
        """
        data = {
            "fieldKeyType": field_key_type,
            "typecast": typecast,
            "record": record,
        }

        if order:
            data["order"] = order

        return await self._request("PATCH", f"/api/table/{table_id}/record/{record_id}", json=data)


# Global client instance for reuse
_global_client: TeableClient | None = None


async def get_teable_client() -> TeableClient:
    """
    Get a global reusable client instance that automatically logs in

    Returns:
        TeableClient: Ready-to-use authenticated client
    """
    global _global_client

    if _global_client is None:
        _global_client = TeableClient()
        await _global_client.setup()

    return _global_client


async def close_global_client():
    """Close the global client if it exists"""
    global _global_client

    if _global_client:
        await _global_client.close()
        _global_client = None


class TeableClientManager:
    """Context manager for managing the global Teable client lifecycle"""

    async def __aenter__(self):
        """Initialize the global client"""
        return await get_teable_client()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the global client"""
        await close_global_client()


def get_teable_manager() -> TeableClientManager:
    """Get a context manager for the Teable client lifecycle"""
    return TeableClientManager()


# Helper functions for backward compatibility
async def create_authenticated_client() -> TeableClient:
    """
    Create and authenticate a Teable client

    Returns:
        Authenticated TeableClient instance
    """
    return await get_teable_client()


async def login_or_signup() -> TeableClient:
    """
    Get a client that automatically handles login/signup

    Returns:
        Authenticated TeableClient instance
    """
    return await get_teable_client()
