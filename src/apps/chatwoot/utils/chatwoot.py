from typing import Literal

import aiohttp

from apps.chatwoot.config.settings import settings
from common.logger import logger


class ChatwootClient:
    def __init__(
        self,
        base_url: str = settings.CHATWOOT_URL,
        email: str = settings.CHATWOOT_ADMIN_EMAIL,
        password: str = settings.CHATWOOT_ADMIN_PASSWORD,
    ):
        """
        Initialize a Chatwoot API client.

        Args:
            base_url: The base URL for the Chatwoot instance (e.g., 'http://localhost:3000')
            email: The email address for authentication (defaults to settings)
            password: The password for authentication (defaults to settings)
        """
        self.base_url = base_url.rstrip("/")
        self.session = None
        self.headers = {}
        self.access_token = None
        self.account_id = None
        self.user_id = None
        self.pubsub_token = None
        self.user_data = {}

        # Store credentials for auto-login
        self.email = email or getattr(settings, "CHATWOOT_EMAIL", None)
        self.password = password or getattr(settings, "CHATWOOT_PASSWORD", None)
        self._is_logged_in = False

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        # Auto-login if credentials are provided
        if self.email and self.password and not self._is_logged_in:
            await self.login(self.email, self.password)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def login(self, email: str | None = None, password: str | None = None) -> bool:
        """
        Login to Chatwoot API using email and password.

        Args:
            email: The email address for authentication, defaults to init value
            password: The password for authentication, defaults to init value

        Returns:
            bool: True if login was successful, False otherwise
        """
        # Use provided credentials or fall back to instance credentials
        email = email or self.email
        password = password or self.password

        if not email or not password:
            logger.error("Login failed: Email and password are required")
            return False

        if not self.session:
            self.session = aiohttp.ClientSession()

        url = f"{self.base_url}/auth/sign_in"
        payload = {"email": email, "password": password}

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    response_data = await response.json()
                    user_data = response_data.get("data", {})

                    # Store authentication data
                    self.access_token = user_data.get("access_token")
                    self.account_id = user_data.get("account_id")
                    self.user_id = user_data.get("id")
                    self.pubsub_token = user_data.get("pubsub_token")
                    self.user_data = user_data

                    # Set headers for future requests with account_id
                    self.headers = {
                        "api_access_token": self.access_token,
                        "Content-Type": "application/json",
                    }

                    self._is_logged_in = True
                    return True
                else:
                    response_text = await response.text()
                    logger.error(f"Login failed: {response.status} - {response_text}")
                    return False
        except Exception as e:
            logger.error(f"Login error: {e!s}")
            return False

    def get_api_url(self, endpoint: str) -> str:
        """
        Construct a proper API URL with the account_id if available.

        Args:
            endpoint: The API endpoint path

        Returns:
            str: The complete API URL
        """
        # Remove leading slashes for consistency
        endpoint = endpoint.lstrip("/")

        # If we have an account_id and the endpoint doesn't already include it
        if self.account_id and not endpoint.startswith(f"accounts/{self.account_id}"):
            # Add account_id to the path for account-specific endpoints
            return f"{self.base_url}/api/v1/accounts/{self.account_id}/{endpoint}"

        # For non-account endpoints or if account_id is not available
        return f"{self.base_url}/api/v1/{endpoint}"

    async def close(self):
        """Close the underlying HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def list_agents(self, page: int = 1):
        """List all agents in the current account.

        Returns:
            list: List of agent data dictionaries
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to list agents")

        url = self.get_api_url("agents")
        async with self.session.get(url, headers=self.headers, params={"page": page}) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.error(f"Failed to list agents: {response.status} - {response_text}")
                return []

    async def add_agent(self, name: str, email: str, role: str = "agent"):
        """Add a new agent to the current account.

        Args:
            name: The agent's full name
            email: The agent's email address
            role: The agent's role (default: "agent")

        Returns:
            dict: The created agent data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add an agent")

        url = self.get_api_url("agents")
        payload = {"name": name, "email": email, "role": role}

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.error(f"Failed to add agent: {response.status} - {response_text}")
                return None

    async def list_teams(self):
        """List all teams in the current account.

        Returns:
            list: List of team data dictionaries
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to list teams")

        url = self.get_api_url("teams")
        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.error(f"Failed to list teams: {response.status} - {response_text}")
                return []

    async def add_team(self, name: str, description: str, allow_auto_assign: bool = True):
        """Add a new team to the current account.

        Args:
            name: The team's name
            description: The team's description
            allow_auto_assign: Whether to allow auto-assignment of conversations (default: True)

        Returns:
            dict: The created team data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add a team")

        url = self.get_api_url("teams")
        payload = {
            "name": name,
            "description": description,
            "allow_auto_assign": allow_auto_assign,
        }

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.error(f"Failed to add team: {response.status} - {response_text}")
                return None

    async def delete_team(self, team_id: int) -> bool:
        """Delete a team from the current account.

        Args:
            team_id: The ID of the team to delete

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to delete a team")

        url = self.get_api_url(f"teams/{team_id}")
        async with self.session.delete(url, headers=self.headers) as response:
            if response.status == 200:
                return True
            else:
                response_text = await response.text()
                logger.error(f"Failed to delete team: {response.status} - {response_text}")
                return False

    async def add_team_members(self, team_id: int, user_ids: list[int]):
        """Add members to a team.

        Args:
            team_id: The ID of the team to add members to
            user_ids: List of user IDs to add to the team

        Returns:
            dict: The updated team data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add team members")

        url = self.get_api_url(f"teams/{team_id}/team_members")
        payload = {"user_ids": user_ids}

        async with self.session.patch(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.error(f"Failed to add team members: {response.status} - {response_text}")
                return None

    async def list_inboxes(self):
        """List all inboxes in the current account.

        Returns:
            list: List of inbox data dictionaries
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to list inboxes")

        url = self.get_api_url(f"accounts/{self.account_id}/inboxes")
        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data["payload"]
            else:
                response_text = await response.text()
                logger.error(f"Failed to list inboxes: {response.status} - {response_text}")
                return []

    async def add_inbox(
        self,
        config: dict,
    ):
        """Add an inbox to an account.

        Args:
            account_id: The ID of the account to add the inbox to
            name: The name of the inbox
            channel_type: The type of channel (e.g. "email", "sms")
            email: The email address for email channel type
            phone_number: The phone number for SMS channel type
            provider_config: Configuration for SMS provider (api_key, api_secret, etc)

        Returns:
            dict: The created inbox data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add an inbox")

        url = self.get_api_url(f"accounts/{self.account_id}/inboxes")
        payload = config

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.error(f"Failed to add inbox: {response.status} - {response_text}")
                return None

    async def update_inbox(self, inbox_id: int, config: dict):
        """Update an inbox configuration.

        Args:
            inbox_id: The ID of the inbox to update
            config: The configuration data to update (e.g., CSAT settings)

        Returns:
            dict: The updated inbox data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to update an inbox")

        url = self.get_api_url(f"accounts/{self.account_id}/inboxes/{inbox_id}")

        async with self.session.patch(url, headers=self.headers, json=config) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                logger.error(f"Failed to update inbox {inbox_id}: {response.status} - {response_text}")
                return None

    async def delete_inbox(self, inbox_id: int):
        """Delete an inbox from the current account.

        Args:
            inbox_id: The ID of the inbox to delete

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to delete an inbox")

        url = self.get_api_url(f"accounts/{self.account_id}/inboxes/{inbox_id}")
        async with self.session.delete(url, headers=self.headers) as response:
            if response.status == 200:
                return True

    async def add_inbox_members(self, inbox_id: int, user_ids: list[int]):
        """Add members to an inbox.

        Args:
            inbox_id: The ID of the inbox to add members to
            user_ids: List of user IDs to add as members

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add inbox members")

        url = self.get_api_url(f"accounts/{self.account_id}/inbox_members")
        payload = {"inbox_id": inbox_id, "user_ids": user_ids}

        async with self.session.patch(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                return True
            else:
                response_text = await response.text()
                logger.error(f"Failed to add inbox members: {response.status} - {response_text}")
                logger.error(f"Payload: {payload}")
                return False

    async def list_labels(self):
        """List all labels in the current account."""
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to list labels")

        url = self.get_api_url("labels")
        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data["payload"]
            else:
                response_text = await response.text()
                logger.error(f"Failed to list labels: {response.status} - {response_text}")
                return []

    async def add_label(
        self,
        title: str,
        description: str = "",
        color: str | None = None,
        show_on_sidebar: bool = True,
    ) -> dict | None:
        """Add a new label to the current account.

        Args:
            title: The title of the label
            color: The color of the label in hex format (e.g., "#8F876D")
            description: Optional description of the label
            show_on_sidebar: Whether to show the label in the sidebar

        Returns:
            dict | None: The created label data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add a label")

        url = self.get_api_url("labels")
        payload = {
            "title": title,
            "color": color,
            "description": description,
            "show_on_sidebar": show_on_sidebar,
        }

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                logger.error(f"Failed to add label: {response.status} - {response_text}")
            return None

    async def delete_label(self, label_id: int):
        """Delete a label from the current account."""
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to delete a label")

        url = self.get_api_url(f"labels/{label_id}")
        async with self.session.delete(url, headers=self.headers) as response:
            if response.status == 200:
                return True
            else:
                response_text = await response.text()
                logger.error(f"Failed to delete label: {response.status} - {response_text}")
                return False

    async def add_custom_attribute(
        self,
        payload: dict,
    ) -> dict | None:
        """Add a new custom attribute definition to the current account.

        Args:
            attribute_display_name: The display name of the attribute
            attribute_description: Optional description of the attribute
            attribute_model: The model type (0 for conversation)
            attribute_display_type: The display type (7 for text)
            attribute_key: The key for the attribute (defaults to display_name)
            attribute_values: List of possible values for the attribute
            regex_pattern: Optional regex pattern for validation
            regex_cue: Optional regex cue for validation

        Returns:
            dict | None: The created attribute data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add a custom attribute")

        url = self.get_api_url("custom_attribute_definitions")

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                logger.error(f"Failed to add custom attribute: {response.status} - {response_text}")
            return None

    async def list_canned_responses(self):
        """List all canned responses in the current account.

        Returns:
            list: List of canned response data dictionaries
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to list canned responses")

        url = self.get_api_url("canned_responses")
        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                logger.error(f"Failed to list canned responses: {response.status} - {response_text}")
                return []

    async def add_canned_response(
        self,
        short_code: str,
        content: str,
    ) -> dict | None:
        """Add a new canned response to the current account.

        Args:
            short_code: The short code identifier for the canned response
            content: The content/text of the canned response

        Returns:
            dict | None: The created canned response data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add a canned response")

        url = self.get_api_url("canned_responses")
        payload = {"short_code": short_code, "content": content}

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                logger.error(f"Failed to add canned response: {response.status} - {response_text}")
            return None

    async def delete_canned_response(self, canned_response_id: int):
        """Delete a canned response from the current account.

        Args:
            canned_response_id: The ID of the canned response to delete

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to delete a canned response")

        url = self.get_api_url(f"canned_responses/{canned_response_id}")
        async with self.session.delete(url, headers=self.headers) as response:
            if response.status == 200:
                return True
            else:
                response_text = await response.text()
                logger.error(f"Failed to delete canned response: {response.status} - {response_text}")
                return False

    async def list_contacts(self, page: int = 1):
        """List all contacts in the current account.

        Returns:
            list: List of contact data dictionaries
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to list contacts")

        url = self.get_api_url("contacts")
        async with self.session.get(url, headers=self.headers, params={"page": page}) as response:
            if response.status == 200:
                data = await response.json()
                return data["payload"]
            else:
                response_text = await response.text()
                logger.error(f"Failed to list contacts: {response.status} - {response_text}")
                return []

    async def add_contact(self, contact: dict):
        """Add a new contact to the current account.

        Args:
            name: The name of the contact
            email: Optional email address of the contact
            phone_number: Optional phone number of the contact

        Returns:
            dict | None: The created contact data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add a contact")

        url = self.get_api_url("contacts")
        payload = contact

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                logger.error(f"Failed to add contact: {response.status} - {response_text}")
            return None

    async def delete_contact(self, contact_id: int):
        """Delete a contact from the current account.

        Args:
            contact_id: The ID of the contact to delete

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to delete a contact")

        url = self.get_api_url(f"contacts/{contact_id}")
        async with self.session.delete(url, headers=self.headers) as response:
            if response.status == 200:
                return True

    async def list_macros(self):
        """List all macros in the current account.

        Returns:
            list: List of macro data dictionaries
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to list macros")

        url = self.get_api_url("macros")
        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                data = await response.json()
                return data["payload"]
            else:
                response_text = await response.text()
                logger.error(f"Failed to list macros: {response.status} - {response_text}")
                return []

    async def add_macro(self, macro: dict):
        url = self.get_api_url("macros")
        async with self.session.post(url, headers=self.headers, json=macro) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                logger.error(f"Failed to add macro: {response.status} - {response_text}")
                return None

    async def delete_macro(self, macro_id: int):
        """Delete a macro from the current account.

        Args:
            macro_id: The ID of the macro to delete

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to delete a macro")

        url = self.get_api_url(f"macros/{macro_id}")
        async with self.session.delete(url, headers=self.headers) as response:
            if response.status == 200:
                return True
            else:
                response_text = await response.text()
                logger.error(f"Failed to delete macro: {response.status} - {response_text}")
                return False

    async def list_conversations(self, page: int = 1):
        """List all conversations in the current account.

        Returns:
            list: List of conversation data dictionaries
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to list conversations")

        url = self.get_api_url("conversations")
        async with self.session.get(url, headers=self.headers, params={"page": page}) as response:
            if response.status == 200:
                data = await response.json()
                logger.info(data)
                return data["data"]["payload"]
            else:
                response_text = await response.text()
                logger.error(f"Failed to list conversations: {response.status} - {response_text}")
                return []

    async def add_conversation(
        self,
        inbox_id: int,
        contact_id: int,
        assignee_id: int,
        source_id: str | None = None,
        mail_subject: str | None = None,
    ):
        """Add a new conversation to the current account.

        Args:
            message_content: The content of the message
            inbox_id: The ID of the inbox
            contact_id: The ID of the contact
            source_id: The source ID of the conversation
            assignee_id: The ID of the assignee
            mail_subject: Optional subject of the mail

        Returns:
            dict: The created conversation data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add a conversation")

        url = self.get_api_url("conversations")
        data = {
            "inbox_id": inbox_id,
            "contact_id": contact_id,
            "source_id": source_id,
            "assignee_id": assignee_id,
        }

        if mail_subject:
            data["additional_attributes"] = {"mail_subject": mail_subject}

        async with self.session.post(url, headers=self.headers, json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                raise Exception(f"Failed to add conversation: {response.status} - {response_text}")

    async def set_conversation_status(
        self,
        conversation_id: int,
        status: Literal["open", "resolved"],
        snoozed_until: str | None = None,
    ):
        """Set the status of a conversation.

        Args:
            conversation_id: The ID of the conversation to update
            status: The new status ("open" or "resolved")
            snoozed_until: Optional timestamp for when to unsnooze the conversation

        Returns:
            dict | None: The updated conversation data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to set conversation status")

        url = self.get_api_url(f"conversations/{conversation_id}/toggle_status")
        payload = {"status": status, "snoozed_until": snoozed_until}

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                raise Exception(f"Failed to set conversation status: {response.status} - {response_text}")

    async def add_conversation_message(
        self,
        conversation_id: int,
        message: str,
        message_type: Literal["incoming", "outgoing"],
        private: bool = False,
        created_at: int | None = None,
    ):
        """Add a message to a conversation.

        Args:
            conversation_id: The ID of the conversation to add the message to
            message: The content of the message
            message_type: The type of message (incoming or outgoing)
            private: Whether the message is private (default: False)
            created_at: Optional timestamp for when the message was created

        Returns:
            dict | None: The created message data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add conversation message")

        url = self.get_api_url(f"conversations/{conversation_id}/messages")
        data = {
            "content": message,
            "private": private,
        }
        if message_type == "incoming":
            data["message_type"] = 0

        if created_at:
            data = created_at

        async with self.session.post(url, headers=self.headers, json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                raise Exception(f"Failed to add conversation message: {response.status} - {response_text}")

    async def update_conversation_last_seen(
        self,
        conversation_id: int,
    ):
        """Update the last seen timestamp for a conversation.

        Args:
            conversation_id: The ID of the conversation to update

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to update conversation last seen")

        url = self.get_api_url(f"conversations/{conversation_id}/update_last_seen")

        async with self.session.post(url, headers=self.headers) as response:
            if response.status == 200:
                return True
            else:
                response_text = await response.text()
                logger.error(f"Failed to update conversation last seen: {response.status} - {response_text}")
                return False

    async def assign_conversation_to_team(
        self,
        conversation_id: int,
        team_id: int,
    ) -> bool:
        """Assign a conversation to a team.

        Args:
            conversation_id: The ID of the conversation to assign
            team_id: The ID of the team to assign the conversation to

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to assign conversation to team")

        url = self.get_api_url(f"conversations/{conversation_id}/assignments")
        data = {"team_id": team_id}

        async with self.session.post(url, headers=self.headers, json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                raise Exception(f"Failed to assign conversation to team: {response.status} - {response_text}")

    async def set_conversation_priority(
        self,
        conversation_id: int,
        priority: Literal["low", "medium", "high", "urgent"] | None,
    ) -> bool:
        """Set the priority of a conversation.

        Args:
            conversation_id: The ID of the conversation to update
            priority: The priority level to set (low, medium, high, urgent) or None to remove priority

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to set conversation priority")

        url = self.get_api_url(f"conversations/{conversation_id}/toggle_priority")
        data = {"priority": priority}

        async with self.session.post(url, headers=self.headers, json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                raise Exception(f"Failed to set conversation priority: {response.status} - {response_text}")

    async def add_conversation_labels(
        self,
        conversation_id: int,
        labels: list[str],
    ) -> bool:
        """Add labels to a conversation.

        Args:
            conversation_id: The ID of the conversation to add labels to
            labels: List of label names to add to the conversation

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add conversation labels")

        url = self.get_api_url(f"conversations/{conversation_id}/labels")
        data = {"labels": labels}

        async with self.session.post(url, headers=self.headers, json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                raise Exception(f"Failed to add conversation labels: {response.status} - {response_text}")

    async def list_campaigns(self) -> list:
        """List all campaigns for the account.

        Returns:
            list: List of campaign objects if successful, empty list otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to list campaigns")

        url = self.get_api_url("campaigns")

        async with self.session.get(url, headers=self.headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                logger.error(f"Failed to list campaigns: {response.status} - {response_text}")
                return []

    async def add_campaign(
        self,
        campaign: dict,
    ) -> dict | None:
        """Add a new campaign.

        Args:
            campaign: Dictionary containing campaign details with fields:
                - title: Campaign title
                - message: Campaign message
                - inbox_id: ID of the inbox
                - sender_id: ID of the sender
                - enabled: Whether campaign is enabled
                - trigger_only_during_business_hours: Whether to trigger only during business hours
                - trigger_rules: Dictionary with trigger rules like url and time_on_page

        Returns:
            dict: Campaign object if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add campaign")

        url = self.get_api_url("campaigns")

        async with self.session.post(url, headers=self.headers, json=campaign) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                logger.error(f"Failed to add campaign: {response.status} - {response_text}")
                return None

    async def delete_campaign(self, campaign_id: int) -> bool:
        """Delete a campaign.

        Args:
            campaign_id: The ID of the campaign to delete

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to delete campaign")

        url = self.get_api_url(f"campaigns/{campaign_id}")

        async with self.session.delete(url, headers=self.headers) as response:
            if response.status == 200:
                return True
            else:
                response_text = await response.text()
                logger.error(f"Failed to delete campaign: {response.status} - {response_text}")
                return False

    async def add_automation_rule(
        self,
        name: str,
        description: str,
        event_name: str,
        conditions: list[dict],
        actions: list[dict],
    ) -> dict | None:
        """Add a new automation rule to the current account.

        Args:
            name: The name of the automation rule
            description: The description of the automation rule
            event_name: The event that triggers the rule (e.g., "message_created")
            conditions: List of condition dictionaries with fields:
                - attribute_key: The attribute to check (e.g., "message_type")
                - filter_operator: The operator to use (e.g., "equal_to")
                - values: List of values to compare against
                - query_operator: The logical operator ("and" or "or")
                - custom_attribute_type: Type of custom attribute (empty string if not custom)
            actions: List of action dictionaries with fields:
                - action_name: The action to perform (e.g., "assign_agent")
                - action_params: List of parameters for the action

        Returns:
            dict | None: The created automation rule data if successful, None otherwise
        """
        if not self._is_logged_in:
            raise RuntimeError("Must be logged in to add automation rule")

        url = self.get_api_url("automation_rules")
        payload = {
            "name": name,
            "description": description,
            "event_name": event_name,
            "conditions": conditions,
            "actions": actions,
        }

        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                response_text = await response.text()
                logger.error(f"Failed to add automation rule: {response.status} - {response_text}")
                return None
