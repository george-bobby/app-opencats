"""API utilities for OpenCATS - HTTP form submissions and session management."""

import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import aiohttp

from apps.opencats.config.settings import settings
from common.logger import logger


class OpenCATSAPIUtils:
    """API utilities for OpenCATS form submissions and session management."""

    def __init__(self):
        self.base_url = settings.OPENCATS_API_URL
        self.session = None
        self.cookies = None

    async def __aenter__(self):
        logger.info("Initializing OpenCATS API utilities...")
        self.session = aiohttp.ClientSession()
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def authenticate(self) -> bool:
        """Authenticate with OpenCATS and maintain session."""
        try:
            login_url = urljoin(self.base_url, "/index.php?m=login&a=attemptLogin")
            login_data = {
                "username": settings.OPENCATS_ADMIN_EMAIL,
                "password": settings.OPENCATS_ADMIN_PASSWORD,
            }

            if settings.OPENCATS_SITE_NAME:
                login_data["siteName"] = settings.OPENCATS_SITE_NAME

            async with self.session.post(login_url, data=login_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, allow_redirects=True) as response:
                if response.status == 200:
                    # Store cookies for subsequent requests
                    self.cookies = response.cookies
                    logger.info("✅ Successfully authenticated with OpenCATS")
                    return True
                else:
                    logger.error(f"❌ Authentication failed with status: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"❌ Authentication error: {e!s}")
            return False

    async def submit_form(self, endpoint: str, form_data: dict[str, Any]) -> dict[str, Any] | None:
        """Submit a form to OpenCATS and return response data."""
        try:
            url = urljoin(self.base_url, endpoint)

            # Ensure postback is included
            if "postback" not in form_data:
                form_data["postback"] = "postback"

            async with self.session.post(url, data=form_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, cookies=self.cookies, allow_redirects=True) as response:
                response_text = await response.text()

                result = {"status_code": response.status, "url": str(response.url), "content": response_text, "entity_id": None}

                # Try to extract entity ID from redirect URL
                if response.status in [200, 302]:
                    entity_id = self._extract_entity_id_from_url(str(response.url))
                    if not entity_id:
                        entity_id = self._extract_entity_id_from_content(response_text)
                    result["entity_id"] = entity_id

                return result

        except Exception as e:
            logger.error(f"❌ Form submission error: {e!s}")
            return None

    async def ajax_request(self, function: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Submit an AJAX request to OpenCATS."""
        try:
            url = urljoin(self.base_url, "/ajax.php")

            # Add function parameter
            ajax_data = {"f": function, **data}

            async with self.session.post(url, data=ajax_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, cookies=self.cookies) as response:
                response_text = await response.text()

                return {"status_code": response.status, "content": response_text}

        except Exception as e:
            logger.error(f"❌ AJAX request error: {e!s}")
            return None

    async def get_latest_entity_id(self, module: str, entity_type: str) -> int | None:
        """Get the latest entity ID from a module listing page."""
        try:
            url = urljoin(self.base_url, f"/index.php?m={module}")

            async with self.session.get(url, cookies=self.cookies) as response:
                if response.status == 200:
                    content = await response.text()
                    return self._extract_latest_entity_id(content, entity_type)

        except Exception as e:
            logger.error(f"❌ Error getting latest entity ID: {e!s}")

        return None

    def _extract_entity_id_from_url(self, url: str) -> int | None:
        """Extract entity ID from URL parameters."""
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)

            # Common ID parameter patterns
            id_patterns = ["companyID", "contactID", "candidateID", "jobOrderID", "savedListID", "eventID", "calendarEventID"]

            for pattern in id_patterns:
                if pattern in query_params:
                    return int(query_params[pattern][0])

        except (ValueError, IndexError, KeyError):
            pass

        return None

    def _extract_entity_id_from_content(self, content: str) -> int | None:
        """Extract entity ID from HTML content."""
        try:
            # Look for ID patterns in the HTML content
            id_patterns = [
                r"companyID[=:](\d+)",
                r"contactID[=:](\d+)",
                r"candidateID[=:](\d+)",
                r"jobOrderID[=:](\d+)",
                r"savedListID[=:](\d+)",
                r"eventID[=:](\d+)",
                r"calendarEventID[=:](\d+)",
            ]

            for pattern in id_patterns:
                match = re.search(pattern, content)
                if match:
                    return int(match.group(1))

        except (ValueError, AttributeError):
            pass

        return None

    def _extract_latest_entity_id(self, content: str, entity_type: str) -> int | None:
        """Extract the latest entity ID from listing page content."""
        try:
            # Map entity types to ID patterns
            pattern_map = {
                "company": r"companyID=(\d+)",
                "contact": r"contactID=(\d+)",
                "candidate": r"candidateID=(\d+)",
                "joborder": r"jobOrderID=(\d+)",
                "event": r"eventID=(\d+)",
                "list": r"savedListID=(\d+)",
            }

            pattern = pattern_map.get(entity_type)
            if not pattern:
                return None

            matches = re.findall(pattern, content)
            if matches:
                # Return the highest ID (most recent)
                return max(int(match) for match in matches)

        except (ValueError, TypeError):
            pass

        return None
