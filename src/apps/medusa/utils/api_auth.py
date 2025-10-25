import base64
import json
from typing import Any

import aiohttp
import requests

from apps.medusa.config.settings import settings
from common.logger import logger


class MedusaAuth:
    """Handles authentication with Medusa API."""

    def __init__(self, base_url: str = settings.MEDUSA_API_URL):
        self.base_url = base_url
        self.admin_email = settings.MEDUSA_ADMIN_EMAIL
        self.admin_password = settings.MEDUSA_ADMIN_PASSWORD
        self.session_token: str | None = None
        self.user_data: dict[str, Any] | None = None

    def _decode_token(self, token: str | None) -> dict[str, Any]:
        """Decode JWT token payload."""
        if not token:
            return {}

        try:
            token_parts = token.split(".")
            if len(token_parts) >= 2:
                payload = token_parts[1]
                payload += "=" * (4 - len(payload) % 4)
                decoded_payload = base64.b64decode(payload)
                return json.loads(decoded_payload)
        except Exception as e:
            logger.debug(f"Could not decode token payload: {e}")
        return {}

    def authenticate_sync(self) -> dict[str, Any]:
        """Authenticate synchronously with Medusa API."""
        logger.info("Authenticating with Medusa API...")

        auth_url = f"{self.base_url}/auth/user/emailpass"
        payload = {"email": self.admin_email, "password": self.admin_password}
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(auth_url, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                auth_data = response.json()

                if "token" in auth_data:
                    self.session_token = auth_data["token"]
                    self.user_data = self._decode_token(self.session_token)

                logger.info("Authentication successful")
                return auth_data
            else:
                error_msg = f"Authentication failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f": {error_data}"
                except Exception:
                    error_msg += f": {response.text}"

                logger.error(error_msg)
                raise Exception(error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during authentication: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def authenticate_async(self) -> dict[str, Any]:
        """Authenticate asynchronously with Medusa API."""
        logger.info("Authenticating with Medusa API...")

        auth_url = f"{self.base_url}/auth/user/emailpass"
        payload = {"email": self.admin_email, "password": self.admin_password}
        headers = {"Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as session, session.post(auth_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    auth_data = await response.json()

                    if "token" in auth_data:
                        self.session_token = auth_data["token"]
                        self.user_data = self._decode_token(self.session_token)

                    logger.info("Authentication successful")
                    return auth_data
                else:
                    error_text = await response.text()
                    error_msg = f"Authentication failed with status {response.status}: {error_text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

        except aiohttp.ClientError as e:
            error_msg = f"Network error during authentication: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def get_auth_headers(self) -> dict[str, str]:
        """Get authorization headers for API requests."""
        headers = {"Content-Type": "application/json"}

        if self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"

        return headers

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.user_data is not None

    def get_user_info(self) -> dict[str, Any] | None:
        """Get authenticated user information."""
        return self.user_data

    def test_connection(self) -> bool:
        """Test connection to Medusa API."""
        logger.info("Testing connection to Medusa API...")

        try:
            health_url = f"{self.base_url}/health"
            response = requests.get(health_url, timeout=10)

            if response.status_code == 200:
                logger.info("Connection to Medusa API successful")
                return True
            else:
                logger.error(f"Connection test failed with status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def logout(self):
        """Clear authentication session."""
        self.session_token = None
        self.user_data = None
        logger.info("Logged out successfully")


class BaseMedusaAPI:
    """Base class for Medusa API operations with session management."""

    def __init__(self):
        self.base_url = settings.MEDUSA_API_URL
        self.auth: MedusaAuth | None = None
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Enter async context manager."""
        self.auth = await authenticate_async()
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        if self.session:
            await self.session.close()


def authenticate() -> MedusaAuth:
    """Synchronous authentication helper."""
    auth = MedusaAuth()
    auth.authenticate_sync()
    return auth


async def authenticate_async() -> MedusaAuth:
    """Asynchronous authentication helper."""
    auth = MedusaAuth()
    await auth.authenticate_async()
    return auth


def get_medusa_base_url() -> str:
    """Get Medusa API base URL."""
    return settings.MEDUSA_API_URL


def get_medusa_auth_headers() -> dict[str, str]:
    """Get Medusa API authentication headers.

    Note: This creates a new auth session each time.
    For better performance, use MedusaAPIUtils context manager instead.
    """
    auth = MedusaAuth()
    auth.authenticate_sync()
    return auth.get_auth_headers()
