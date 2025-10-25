import time
import uuid
from pathlib import Path

import aiohttp

from apps.mattermost.config.settings import settings
from common.logger import logger


class MattermostClient:
    def __init__(
        self,
        base_url: str = settings.MATTERMOST_URL,
        username: str = settings.MATTERMOST_OWNER_USERNAME,
        password: str = settings.MATTERMOST_PASSWORD,
    ):
        """
        Initialize a Mattermost API client.
        """
        self.base_url = base_url.rstrip("/")
        self.session = None
        self.headers = {}
        self.token = None

        # Store credentials for auto-login
        self.username = username
        self.password = password
        self._is_logged_in = False

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        # Auto-login if credentials are provided
        if self.username and self.password and not self._is_logged_in:
            await self.login(self.username, self.password)
        elif self.token and not self._is_logged_in:
            # Use access token for authentication
            self.access_token = self.token
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            self._is_logged_in = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.logout()

    async def login(self, username: str | None = None, password: str | None = None) -> bool:
        """
        Login to Mattermost API using username and password.

        Args:
            username: The username for authentication, defaults to init value
            password: The password for authentication, defaults to init value

        Returns:
            bool: True if login was successful, False otherwise
        """
        # Use provided credentials or fall back to instance credentials
        username = username or self.username
        password = password or self.password

        if not username or not password:
            logger.warning("Login failed: Username and password are required")
            return False

        if not self.session:
            self.session = aiohttp.ClientSession()

        url = f"{self.base_url}/api/v4/users/login"
        payload = {"login_id": username, "password": password}

        try:
            async with self.session.post(url, headers=self.headers, json=payload) as response:
                if response.status == 200:
                    # Extract token from response headers
                    token = response.headers.get("Token")
                    if token:
                        self.access_token = token
                        self.headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        }

                    # Parse user data from response
                    user_data = await response.json()
                    self.user_id = user_data.get("id")
                    self.user_data = user_data

                    self._is_logged_in = True
                    return True
                else:
                    response_text = await response.text()
                    logger.warning(f"Login failed: {response.status} - {response_text}")
                    return False
        except Exception as e:
            logger.warning(f"Login error: {e!s}")
            return False

    async def logout(self):
        """
        Logout from Mattermost API.

        This method clears the session and headers, effectively logging out the user.
        """
        if not self._is_logged_in:
            logger.warning("Logout called but not logged in")
            return

        url = self.get_api_url("users/logout")

        try:
            async with self.session.post(url, headers=self.headers) as response:
                if response.status in [200, 201, 204]:
                    self.headers = {}
                    self.token = None
                    self._is_logged_in = False
                else:
                    response_text = await response.text()
                    logger.fail(f"Logout failed: {response.status} - {response_text}")
            if self.session:
                await self.session.close()
                self.session = None
        except Exception as e:
            logger.fail(f"Logout error: {e!s}")

    async def get_user_token(self, username: str, password: str) -> str | None:
        """
        Get a user token for authentication.

        Args:
            username: The username for authentication
            password: The password for authentication

        Returns:
            str: Token if successful, None otherwise
        """
        if not username or not password:
            logger.fail("Get token failed: Username and password are required")
            return None

        if not self.session:
            self.session = aiohttp.ClientSession()

        url = f"{self.base_url}/api/v4/users/login"
        payload = {"login_id": username, "password": password}

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    # Extract token from response headers
                    token = response.headers.get("Token")
                    return token
                else:
                    response_text = await response.text()
                    logger.fail(f"Failed to get token: {response.status} - {response_text}")
                    return None
        except Exception as e:
            logger.fail(f"Error getting token: {e!s}")
            return None

    def get_api_url(self, endpoint: str) -> str:
        """
        Construct a proper API URL.

        Args:
            endpoint: The API endpoint path

        Returns:
            str: The complete API URL
        """
        # Remove leading slashes for consistency
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/api/v4/{endpoint}"

    async def close(self):
        """Close the underlying HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    # CRUD Operations with automatic authentication
    async def create_team(self, name: str, display_name: str):
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add a team")

        url = self.get_api_url("teams")
        payload = {"name": name, "display_name": display_name, "type": "O"}

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to add team: {response.status} - {response_text}")
                return None

    async def create_user(self, user_data: dict):
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to create a user")

        url = self.get_api_url("users")

        # Prepare payload with required fields
        payload = {
            "email": user_data["email"],
            "username": user_data["username"],
            "first_name": user_data["first_name"],
            "last_name": user_data["last_name"],
            "password": user_data["password"],
            "roles": user_data.get("roles", "system_user"),
        }

        # Add optional fields if provided
        if "nickname" in user_data:
            payload["nickname"] = user_data["nickname"]
        if "position" in user_data:
            payload["position"] = user_data["position"]

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()

                # Upload avatar if provided
                if user_data.get("avatar"):
                    await self.upload_user_avatar(data["id"], user_data["avatar"])

                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to create user {user_data['username']}: {response.status} - {response_text}")
                return None

    async def upload_user_avatar(self, user_id: str, avatar_path: str):
        """
        Upload an avatar for a user.

        Args:
            user_id: The ID of the user
            avatar_path: Path to the avatar image file

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to upload avatar")

        url = self.get_api_url(f"users/{user_id}/image")

        try:
            # Create multipart form data

            data = aiohttp.FormData()
            data.add_field("image", open(avatar_path, "rb"), filename=f"avatar_{user_id}.jpg", content_type="image/jpeg")  # noqa: PTH123, SIM115

            # Prepare headers for multipart upload
            headers = {"Authorization": self.headers["Authorization"]}

            async with self.session.post(url, headers=headers, data=data) as response:
                if response.status in [200, 201]:
                    return True
                else:
                    response_text = await response.text()
                    logger.fail(f"Failed to upload avatar for user {user_id}: {response.status} - {response_text}")
                    return False
        except Exception as e:
            logger.fail(f"Error uploading avatar for user {user_id}: {e}")
            return False

    async def update_site_configuration(self, config_data: dict):
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to update site configuration")

        url = self.get_api_url("config")

        # First, get the current configuration to avoid clearing existing settings
        try:
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    current_config = await response.json()
                else:
                    logger.warning("Could not fetch current configuration, using defaults")
                    current_config = {}
        except Exception as e:
            logger.warning(f"Could not fetch current configuration: {e}")
            current_config = {}

        # Prepare payload with site configuration, preserving existing settings
        payload = {
            "ServiceSettings": {
                **current_config.get("ServiceSettings", {}),
                "SiteURL": config_data.get("site_url", "https://chat.vertexon.io"),
                "EnableSignUpWithEmail": config_data.get("enable_signup", False),
                "EnableOpenServer": config_data.get("enable_open_server", False),
            },
            "TeamSettings": {
                **current_config.get("TeamSettings", {}),
                "SiteName": config_data.get("site_name", "Vertexon Solutions"),
                "CompanyName": config_data.get("company_name", "Vertexon Solutions"),
                "MaxUsersPerTeam": config_data.get("max_users_per_team", 100),
            },
            "EmailSettings": {
                **current_config.get("EmailSettings", {}),
                "EnableSignUpWithEmail": config_data.get("enable_signup", False),
                "EnableSignInWithEmail": True,
                "EnableSignInWithUsername": True,
            },
        }

        async with self.session.put(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                logger.info(f"Updated site configuration: {config_data.get('site_name', 'Unknown')}")
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to update site configuration: {response.status} - {response_text}")
                return None

    async def update_integration_settings(self, integration_data: dict):
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to update integration settings")

        url = self.get_api_url("config")

        # First, get the current configuration to avoid clearing existing settings
        try:
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    current_config = await response.json()
                else:
                    logger.warning("Could not fetch current configuration, using defaults")
                    current_config = {}
        except Exception as e:
            logger.warning(f"Could not fetch current configuration: {e}")
            current_config = {}

        # Prepare payload with integration settings, preserving existing settings
        payload = {
            "ServiceSettings": {
                **current_config.get("ServiceSettings", {}),
                "EnableIncomingWebhooks": integration_data.get("incoming_webhooks", True),
                "EnableOutgoingWebhooks": integration_data.get("outgoing_webhooks", True),
                "EnableBotAccountCreation": integration_data.get("bot_accounts", True),
                "EnableCommands": integration_data.get("slash_commands", False),
                "EnableOAuthServiceProvider": integration_data.get("oauth_applications", False),
            }
        }

        async with self.session.put(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                logger.info("Updated integration settings")
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to update integration settings: {response.status} - {response_text}")
                return None

    async def update_email_settings(self, email_data: dict):
        """
        Update email settings in Mattermost.

        Args:
            email_data: Dictionary containing email settings:
                       - smtp_server: SMTP server address
                       - smtp_port: SMTP port number
                       - smtp_username: SMTP username
                       - smtp_password: SMTP password
                       - smtp_security: SMTP security type (STARTTLS, TLS, etc.)
                       - feedback_email: Feedback email address
                       - feedback_name: Feedback email name

        Returns:
            dict: Configuration data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                config = await client.update_email_settings({
                    "smtp_server": "smtp.vertexon.io",
                    "smtp_port": 587,
                    "smtp_username": "noreply@vertexon.io",
                    "smtp_password": "password123",
                    "smtp_security": "STARTTLS"
                })
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to update email settings")

        url = self.get_api_url("config")

        # First, get the current configuration to avoid clearing existing settings
        try:
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    current_config = await response.json()
                else:
                    logger.warning("Could not fetch current configuration, using defaults")
                    current_config = {}
        except Exception as e:
            logger.warning(f"Could not fetch current configuration: {e}")
            current_config = {}

        # Prepare payload with email settings, preserving existing settings
        payload = {
            "EmailSettings": {
                **current_config.get("EmailSettings", {}),
                "EnableSignUpWithEmail": True,
                "EnableSignInWithEmail": True,
                "EnableSignInWithUsername": True,
                "SMTPUsername": email_data.get("smtp_username", ""),
                "SMTPPassword": email_data.get("smtp_password", ""),
                "SMTPServer": email_data.get("smtp_server", ""),
                "SMTPPort": str(email_data.get("smtp_port", 587)),
                "ConnectionSecurity": email_data.get("smtp_security", "STARTTLS"),
                "FeedbackName": email_data.get("feedback_name", "Vertexon Solutions"),
                "FeedbackEmail": email_data.get("feedback_email", "noreply@vertexon.io"),
                "EnableEmailBatching": True,
                "EmailBatchingBufferSize": 256,
                "EmailBatchingInterval": 30,
            }
        }

        async with self.session.put(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                logger.info(f"Updated email settings for {email_data.get('smtp_server', 'Unknown')}")
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to update email settings: {response.status} - {response_text}")
                return None

    async def update_complete_configuration(self, config_data: dict):
        """
        Update complete Mattermost configuration in a single API call.

        This method fetches the current configuration and updates it with new settings,
        ensuring no existing settings are cleared.

        Args:
            config_data: Dictionary containing all configuration settings:
                        - site_configuration: Site URL, name, company details
                        - email_settings: SMTP configuration
                        - integration_settings: Webhooks, bots, security settings
                        - authentication: Authentication method settings

        Returns:
            dict: Configuration data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                config = await client.update_complete_configuration({
                    "site_configuration": {...},
                    "email_settings": {...},
                    "integration_settings": {...}
                })
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to update configuration")

        url = self.get_api_url("config")

        # First, get the current configuration
        try:
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    current_config = await response.json()
                    logger.succeed("Successfully fetched current configuration")
                else:
                    logger.fail(f"Failed to fetch current configuration: {response.status}")
                    return None
        except Exception as e:
            logger.fail(f"Error fetching current configuration: {e}")
            return None

        # Prepare complete payload by merging current config with new settings
        payload = current_config.copy()

        # Update ServiceSettings
        if "ServiceSettings" not in payload:
            payload["ServiceSettings"] = {}

        service_settings = payload["ServiceSettings"]
        site_config = config_data.get("site_configuration", {})
        integration_config = config_data.get("integration_settings", {})

        service_settings.update(
            {
                "SiteURL": site_config.get("site_url", service_settings.get("SiteURL", "https://chat.vertexon.io")),
                "EnableSignUpWithEmail": site_config.get("enable_signup", False),
                "EnableOpenServer": site_config.get("enable_open_server", False),
                "EnableIncomingWebhooks": integration_config.get("incoming_webhooks", True),
                "EnableOutgoingWebhooks": integration_config.get("outgoing_webhooks", True),
                "EnableBotAccountCreation": integration_config.get("bot_accounts", True),
                "EnableCommands": integration_config.get("slash_commands", False),
                "EnableOAuthServiceProvider": integration_config.get("oauth_applications", False),
            }
        )

        # Update TeamSettings
        if "TeamSettings" not in payload:
            payload["TeamSettings"] = {}

        team_settings = payload["TeamSettings"]
        team_settings.update(
            {
                "SiteName": site_config.get("site_name", "Vertexon Solutions"),
                "CompanyName": site_config.get("company_name", "Vertexon Solutions"),
                "MaxUsersPerTeam": site_config.get("max_users_per_team", 100),
            }
        )

        # Update EmailSettings
        if "EmailSettings" not in payload:
            payload["EmailSettings"] = {}

        email_settings = payload["EmailSettings"]
        email_config = config_data.get("email_settings", {})

        email_settings.update(
            {
                "EnableSignUpWithEmail": site_config.get("enable_signup", False),
                "EnableSignInWithEmail": True,
                "EnableSignInWithUsername": True,
                "SMTPUsername": email_config.get("smtp_username", ""),
                "SMTPPassword": email_config.get("smtp_password", ""),
                "SMTPServer": email_config.get("smtp_server", ""),
                "SMTPPort": str(email_config.get("smtp_port", 587)),
                "ConnectionSecurity": email_config.get("smtp_security", "STARTTLS"),
                "FeedbackName": email_config.get("feedback_name", "Vertexon Solutions"),
                "FeedbackEmail": email_config.get("feedback_email", "noreply@vertexon.io"),
                "EnableEmailBatching": True,
                "EmailBatchingBufferSize": 256,
                "EmailBatchingInterval": 30,
            }
        )

        # Send the complete configuration update
        async with self.session.put(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                logger.succeed("Successfully updated complete configuration")
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to update configuration: {response.status} - {response_text}")
                return None

    async def create_channel(self, team_id: str, channel_data: dict):
        """
        Create a new channel in a specific team.

        Args:
            team_id: The ID of the team to create the channel in
            channel_data: Dictionary containing channel information:
                         - name: Channel name (e.g., "product-roadmap")
                         - display_name: Human-readable display name
                         - type: Channel type ("O" for open, "P" for private)
                         - description: Channel description

        Returns:
            dict: Channel data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                channel = await client.create_channel(
                    team_id="team123",
                    channel_data={
                        "name": "product-roadmap",
                        "display_name": "Product Roadmap",
                        "type": "O",
                        "description": "Product roadmap discussions"
                    }
                )
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to create a channel")

        url = self.get_api_url("channels")

        # Prepare payload with required fields
        payload = {
            "team_id": team_id,
            "name": channel_data["name"],
            "display_name": channel_data["display_name"],
            "type": channel_data["channel_type"],  # "O" for open, "P" for private
        }

        # Add optional description if provided
        if "description" in channel_data:
            payload["header"] = channel_data["description"]

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to create channel {channel_data['name']}: {response.status} - {response_text}")
                return None

    async def get_teams(self):
        """
        Get all teams

        Args:
            None
        Returns:
            list: List of teams if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get team information")

        url = self.get_api_url("teams")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to get teams: {response.status} - {response_text}")
                return None

    async def get_team_by_name(self, team_name: str):
        """
        Get team by name

        Args:
            team_name: str
        Returns:
            dict: team info, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get team information")

        url = self.get_api_url(f"teams/name/{team_name}")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to get teams: {response.status} - {response_text}")
                return None

    async def get_team_members(self, team_id: str):
        """
        Get all teams

        Args:
            None
        Returns:
            list: List of teams if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get team information")

        url = self.get_api_url(f"teams/{team_id}/members")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to get teams: {response.status} - {response_text}")
                return None

    async def get_team_channels(self, team_id: str):
        """
        Get all channels for a specific team

        Args:
            team_id: str - The team ID
        Returns:
            list: List of channels for the team if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get team channels")

        url = self.get_api_url(f"teams/{team_id}/channels")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.debug(f"Failed to get channels for team {team_id}: {response.status} - {response_text}")
                return None

    async def get_channels(self):
        """
        Get list of channels

        Args:
            None
        Returns:
            list: List of channels if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get channel information")

        url = self.get_api_url("channels?per_page=1000")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to get channels: {response.status} - {response_text}")
                return None

    async def get_channel_by_name(self, team_id: str, channel_name: str):
        """
        Get channel by name

        Args:
            channel_name: str
        Returns:
            dict: channel info, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get channel information")

        url = self.get_api_url(f"teams/{team_id}/channels/name/{channel_name}")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to get channel: {response.status} - {response_text}")
                return None

    async def delete_channel(self, channel_id: str):
        """
        Delete a channel by ID.

        Args:
            channel_id: The ID of the channel to delete

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to delete a channel")

        url = self.get_api_url(f"channels/{channel_id}")

        async with self.session.delete(url, headers=self.headers) as response:
            if response.status in [200, 201, 204]:
                return True
            else:
                response_text = await response.text()
                logger.fail(f"Failed to delete channel {channel_id}: {response.status} - {response_text}")
                return False

    async def archive_channel(self, channel_id: str) -> bool:
        """
        Archive (soft delete) a channel by ID.

        This maps to DELETE /api/v4/channels/{channel_id} which archives the
        channel in Mattermost.

        Args:
            channel_id: The ID of the channel to archive

        Returns:
            bool: True if successful, False otherwise
        """
        return await self.delete_channel(channel_id)

    async def archive_channel_by_name(self, team_id: str, channel_name: str) -> bool:
        """
        Archive a channel by its name within a team.

        Args:
            team_id: The ID of the team that owns the channel
            channel_name: The unique handle/name of the channel

        Returns:
            bool: True if archived, False otherwise
        """
        channel = await self.get_channel_by_name(team_id, channel_name)
        if not channel or not channel.get("id"):
            logger.fail(f"Channel not found: {channel_name}")
            return False
        return await self.archive_channel(channel["id"])

    async def get_channel_members(self, channel_id: str):
        """
        Get list of channel memebers

        Args:
            None
        Returns:
            list: List of channel members if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get channel members")

        url = self.get_api_url(f"channels/{channel_id}/members?per_page=1000")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to get channel members: {response.status} - {response_text}")
                return None

    async def get_users(self) -> list[dict]:
        """
        Get all users

        Args:
            None
        Returns:
            list: List of users if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get users")

        url = self.get_api_url("users?per_page=1000")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to get users: {response.status} - {response_text}")
                return None

    async def get_user_by_username(self, username: str) -> dict | None:
        """
        Get user by username.

        Args:
            username: The username of the user to retrieve

        Returns:
            dict: User data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get user information")

        url = self.get_api_url(f"users/username/{username}")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to get user {username}: {response.status} - {response_text}")
                return None

    async def add_user_to_channel(self, channel_id: str, user_ids: list[str]):
        """
        Add a user to a channel.

        Args:
            channel_id: The ID of the channel
            user_id: The ID of the user to add

        Returns:
            dict: Channel member data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add user to channel")

        url = self.get_api_url(f"channels/{channel_id}/members")

        payload = {"user_ids": user_ids}

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to add user {user_ids} to channel {channel_id}: {response.status} - {response_text}")
                return None

    async def add_user_to_team(self, team_id: str, user_id: str):
        """
        Add a user to a team.

        Args:
            team_id: The ID of the team
            user_id: The ID of the user to add

        Returns:
            dict: Team member data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add user to team")

        url = self.get_api_url(f"teams/{team_id}/members")

        payload = {
            "team_id": team_id,
            "user_id": user_id,
        }

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to add user {user_id} to team {team_id}: {response.status} - {response_text}")
                return None

    async def create_post(self, post_data: dict):
        """
        Create a new post in a channel.

        Args:
            post_data: Dictionary containing post information:
                      - channel_id: The ID of the channel
                      - message: The message content
                      - user_id: The ID of the user posting the message
                      - create_at: Optional timestamp in milliseconds
                      - root_id: Optional root post ID for thread replies
                      - file_ids: Optional list of file IDs to attach
                      - pending_post_id: Optional pending post ID for UI tracking
                      - props: Optional props dictionary for additional metadata

        Returns:
            dict: Post data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                post = await client.create_post({
                    "channel_id": "channel123",
                    "message": "Hello, world!",
                    "user_id": "user456",
                    "create_at": 1640995200000  # Optional timestamp
                })
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to create a post")

        url = self.get_api_url("posts")

        # Prepare payload with required fields
        payload = {
            "channel_id": post_data["channel_id"],
            "message": post_data["message"],
        }

        if "user_id" in post_data:
            payload["user_id"] = post_data["user_id"]

        # Add optional fields
        if "root_id" in post_data:
            payload["root_id"] = post_data["root_id"]

        if "file_ids" in post_data:
            payload["file_ids"] = post_data["file_ids"]

        if "pending_post_id" in post_data:
            payload["pending_post_id"] = post_data["pending_post_id"]

        # Use get() method for cleaner code
        payload["props"] = post_data.get("props", {"disable_group_highlight": True})
        payload["create_at"] = post_data.get("create_at", 0)

        # Add metadata field
        payload["metadata"] = post_data.get("metadata", {})

        # Add reply_count for consistency with UI
        payload["reply_count"] = 0

        # Set update_at timestamp
        payload["update_at"] = int(time.time() * 1000)

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data
            elif response.status == 403:
                # Permission error - don't log as failure since it's expected behavior
                response_text = await response.text()
                # logger.debug(f"Permission denied for post creation: {response.status} - {response_text}")
                return None
            else:
                response_text = await response.text()
                logger.fail(f"Failed to create post: {response.status} - {response_text}")
                return None

    async def create_direct_channel(self, user_ids: list[str]) -> dict | None:
        """
        Create a new direct channel (1-on-1) or group direct channel (up to 7 members).

        Args:
            user_ids: List of user IDs to create a direct channel with (2-7 users)

        Returns:
            dict: Channel data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to create a direct channel")

        if len(user_ids) < 2 or len(user_ids) > 7:
            logger.fail(f"Direct channel requires 2-7 users, got {len(user_ids)}")
            return None

        # Use different endpoints for different channel types
        url = self.get_api_url("channels/direct") if len(user_ids) == 2 else self.get_api_url("channels/group")

        # For both direct and group channels, Mattermost expects just the array of user IDs
        payload = user_ids

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to create direct channel: {response.status} - {response_text}")
                return None

    async def create_reaction(
        self,
        post_id: str,
        user_id: str,
        emoji_name: str,
    ):
        """
        Create a reaction on a post.

        Args:
            post_id: The ID of the post to react to
            user_id: The ID of the user creating the reaction
            emoji_name: The emoji name (e.g., "thumbsup", "heart", "smile")
        Returns:
            dict: Reaction data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                reaction = await client.create_reaction(
                    post_id="post123",
                    user_id="user456",
                    emoji_name="thumbsup"
                )
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to create a reaction")

        url = self.get_api_url("reactions")

        payload = {
            "user_id": user_id,
            "post_id": post_id,
            "emoji_name": emoji_name,
        }

        await self.session.close()

        self.session = aiohttp.ClientSession()

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.debug(f"Failed to create reaction {emoji_name}: {response.status} - {response_text}")
                return None

    async def pin_post(self, post_id: str):
        """
        Pin a post to the channel.

        Args:
            post_id: The ID of the post to pin

        Returns:
            dict: Pin data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                pin = await client.pin_post("post123")
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to pin a post")

        url = self.get_api_url(f"posts/{post_id}/pin")

        async with self.session.post(url, headers=self.headers) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to pin post: {response.status} - {response_text}")
                return None

    async def get_posts_for_channel(self, channel_id: str, page: int = 0, per_page: int = 60):
        """
        Get posts for a specific channel.

        Args:
            channel_id: The ID of the channel
            page: Page number (0-based)
            per_page: Number of posts per page (max 200)

        Returns:
            dict: Posts data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                posts = await client.get_posts_for_channel("channel123", page=0, per_page=60)
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to get posts")

        url = self.get_api_url(f"channels/{channel_id}/posts")
        params = {
            "page": page,
            "per_page": min(per_page, 200),  # Mattermost max is 200
        }

        async with self.session.get(url, headers=self.headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to get posts: {response.status} - {response_text}")
                return None

    async def update_channel_header(self, channel_id: str, header: str):
        """
        Update the header (description) of a channel.

        Args:
            channel_id: The ID of the channel
            header: The new header text for the channel

        Returns:
            dict: Updated channel data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                updated_channel = await client.update_channel_header("channel123", "New header text")
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to update channel header")

        url = self.get_api_url(f"channels/{channel_id}/patch")
        payload = {"header": header}

        async with self.session.put(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.debug(f"Failed to update channel header: {response.status} - {response_text}")
                return None

    async def set_channel_member_roles(self, channel_id: str, user_id: str, is_admin: bool = True):
        """
        Set a channel member's roles (admin/user).

        Args:
            channel_id: The ID of the channel
            user_id: The ID of the user to update
            is_admin: Whether to set the user as admin (True) or regular user (False)

        Returns:
            dict: Updated member data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                # Set user as channel admin
                result = await client.set_channel_member_roles("channel123", "user456", is_admin=True)

                # Set user as regular channel member
                result = await client.set_channel_member_roles("channel123", "user456", is_admin=False)
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to update channel member roles")

        url = self.get_api_url(f"channels/{channel_id}/members/{user_id}/schemeRoles")
        payload = {
            "scheme_user": True,  # Always true for channel members
            "scheme_admin": is_admin,  # True for admin, False for regular user
        }

        async with self.session.put(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.fail(f"Failed to update channel member roles: {response.status} - {response_text}")
                return None

    async def set_user_preferences(self, user_id: str, preferences: list[dict]):
        """
        Set user preferences to control channel visibility and behavior in the UI.

        This API call is used to set user preferences like showing direct channels,
        channel open times, and other UI-related settings.

        Args:
            user_id: The ID of the user whose preferences to set
            preferences: List of preference objects with user_id, category, name, and value

        Returns:
            dict: Response data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                preferences = [
                    {
                        "user_id": "user123",
                        "category": "direct_channel_show",
                        "name": "channel456",
                        "value": "true"
                    },
                    {
                        "user_id": "user123",
                        "category": "channel_open_time",
                        "name": "channel456",
                        "value": "1757475065977"
                    }
                ]
                result = await client.set_user_preferences("user123", preferences)
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to set user preferences")

        url = self.get_api_url(f"users/{user_id}/preferences")

        async with self.session.put(url, headers=self.headers, json=preferences) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                raise RuntimeError(f"Failed to set user preferences: {response.status} - {response_text}")

    async def show_direct_channel(self, user_id: str, channel_id: str, other_user_id: str | None = None):
        """
        Convenience method to show a direct channel in the UI.

        This sets the user preferences to make a direct channel visible
        and sets the channel open time to current timestamp.

        Args:
            user_id: The ID of the user who should see the channel
            channel_id: The ID of the direct channel to show
            other_user_id: The ID of the other user in the direct channel (required for direct_channel_show)

        Returns:
            dict: Response data if successful, None otherwise

        Example:
            ```python
            async with MattermostClient() as client:
                result = await client.show_direct_channel("user123", "channel456", "user789")
            ```
        """
        if not other_user_id:
            # If other_user_id not provided, try to get it from channel members
            channel_members = await self.get_channel_members(channel_id)
            if channel_members:
                # Find the other user (not the current user)
                for member in channel_members:
                    if member["user_id"] != user_id:
                        other_user_id = member["user_id"]
                        break

        if not other_user_id:
            raise RuntimeError("Could not determine other user ID for direct channel")

        preferences = [
            # For direct channels, direct_channel_show uses the OTHER user's ID as the name
            {"user_id": user_id, "category": "direct_channel_show", "name": other_user_id, "value": "true"},
            # channel_open_time uses the channel ID as the name
            {
                "user_id": user_id,
                "category": "channel_open_time",
                "name": channel_id,
                "value": str(int(time.time() * 1000)),  # Current timestamp in milliseconds
            },
        ]

        return await self.set_user_preferences(user_id, preferences)

    async def upload_file(self, channel_id: str, file_path: str, filename: str | None = None, client_id: str | None = None):
        """
        Upload a file to Mattermost and return file information.

        Args:
            channel_id: The ID of the channel to upload to
            file_path: Path to the file to upload
            filename: Optional custom filename (defaults to basename of file_path)
            client_id: Optional client ID for tracking uploads

        Returns:
            dict: File information if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                file_info = await client.upload_file("channel123", "/path/to/file.pdf")
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to upload files")

        url = self.get_api_url("files")

        if not filename:
            filename = Path(file_path).name

        try:
            # Create multipart form data
            data = aiohttp.FormData()
            data.add_field("channel_id", channel_id)

            # Add client_id if provided (used by Mattermost UI for tracking)
            if client_id:
                data.add_field("client_ids", client_id)

            # Read the entire file into memory first to avoid I/O issues
            file_content = Path(file_path).read_bytes()
            data.add_field("files", file_content, filename=filename)

            # Prepare headers for multipart upload (don't set Content-Type, let aiohttp handle it)
            headers = {"Authorization": self.headers["Authorization"]}

            async with self.session.post(url, headers=headers, data=data) as response:
                if response.status in [200, 201]:
                    response_data = await response.json()
                    # logger.debug(f"Successfully uploaded file {filename} to channel {channel_id}")
                    return response_data
                else:
                    response_text = await response.text()
                    logger.debug(f"Failed to upload file {filename}: {response.status} - {response_text}")
                    return None

        except Exception as e:
            logger.debug(f"Error uploading file {filename}: {e}")
            return None

    async def upload_file_data(self, channel_id: str, file_data: bytes, filename: str, client_id: str | None = None):
        """
        Upload binary file data directly to Mattermost without writing to disk.

        Args:
            channel_id: The ID of the channel to upload to
            file_data: Binary data of the file
            filename: Name of the file
            client_id: Optional client ID for tracking uploads

        Returns:
            dict: File information if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                file_data = b"\\x00" * 1024  # 1KB of null bytes
                file_info = await client.upload_file_data("channel123", file_data, "test.txt")
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to upload files")

        url = self.get_api_url("files")

        try:
            # Create multipart form data
            data = aiohttp.FormData()
            data.add_field("channel_id", channel_id)

            # Add client_id if provided (used by Mattermost UI for tracking)
            if client_id:
                data.add_field("client_ids", client_id)

            # Add file data directly
            data.add_field("files", file_data, filename=filename)

            # Prepare headers for multipart upload (don't set Content-Type, let aiohttp handle it)
            headers = {"Authorization": self.headers["Authorization"]}

            async with self.session.post(url, headers=headers, data=data) as response:
                if response.status in [200, 201]:
                    response_data = await response.json()
                    # logger.debug(f"Successfully uploaded file {filename} to channel {channel_id}")
                    return response_data
                else:
                    response_text = await response.text()
                    logger.debug(f"Failed to upload file {filename}: {response.status} - {response_text}")
                    return None

        except Exception as e:
            logger.debug(f"Error uploading file {filename}: {e}")
            return None

    async def create_post_with_files(self, channel_id: str, message: str = "", file_paths: list[str] | None = None, user_id: str | None = None, root_id: str | None = None) -> dict | None:
        """
        Upload files and create a post with those files attached in one operation.

        Args:
            channel_id: The ID of the channel to post to
            message: The message content (can be empty for file-only posts)
            file_paths: List of file paths to upload and attach
            user_id: Optional user ID for the post
            root_id: Optional root post ID for thread replies

        Returns:
            dict: Post data if successful, None otherwise

        Raises:
            RuntimeError: If not logged in to Mattermost

        Example:
            ```python
            async with MattermostClient() as client:
                post = await client.create_post_with_files(
                    channel_id="channel123",
                    message="Check out these files:",
                    file_paths=["/path/to/file1.pdf", "/path/to/file2.jpg"],
                    user_id="user456"
                )
            ```
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to create post with files")

        file_ids = []

        # Upload files first if any are provided
        if file_paths:
            for file_path in file_paths:
                client_id = str(uuid.uuid4())
                file_info = await self.upload_file(channel_id, file_path, client_id=client_id)
                if file_info and "file_infos" in file_info:
                    # Extract file ID from the response
                    for file_data in file_info["file_infos"]:
                        if "id" in file_data:
                            file_ids.append(file_data["id"])
                else:
                    logger.warning(f"Failed to upload file: {file_path}")
                    return None

        # Create post data
        post_data = {
            "channel_id": channel_id,
            "message": message,
        }

        if user_id:
            post_data["user_id"] = user_id
            # Generate pending post ID for UI tracking
            post_data["pending_post_id"] = f"{user_id}:{int(time.time() * 1000)}"

        if root_id:
            post_data["root_id"] = root_id

        if file_ids:
            post_data["file_ids"] = file_ids

        # Create the post with attached files
        return await self.create_post(post_data)

    async def create_group_dm_channel(self, user_ids: list[str]) -> dict | None:
        """Create a group direct message channel with multiple users.

        Args:
            user_ids: List of Mattermost user IDs to include in the group DM

        Returns:
            Channel data if successful, None otherwise
        """
        try:
            async with self.session.post(f"{self.base_url}/api/v4/channels/group", headers=self.headers, json=user_ids) as response:
                if response.status == 201:
                    channel_data = await response.json()
                    logger.debug(f"Successfully created group DM channel: {channel_data.get('id')}")
                    return channel_data
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create group DM channel: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Error creating group DM channel: {e}")
            return None
