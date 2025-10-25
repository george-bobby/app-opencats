"""API utilities for OpenCATS - HTTP form submissions and session management."""

import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import aiohttp
from tenacity import retry, stop_after_attempt, wait_fixed

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

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
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

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
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

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
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

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
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

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_all_items(self, endpoint) -> list[dict[str, Any]]:
        """Get all items from a specific endpoint using AJAX listing."""
        try:
            # Map endpoint to AJAX function
            function_map = {
                "candidates": "lists:getCandidatesList",
                "companies": "lists:getCompaniesList", 
                "contacts": "lists:getContactsList",
                "joborders": "lists:getJobOrdersList",
            }
            
            # Extract endpoint name from enum
            endpoint_name = endpoint.name.lower() if hasattr(endpoint, 'name') else str(endpoint).lower()
            function = function_map.get(endpoint_name)
            
            if not function:
                logger.warning(f"⚠️ No AJAX function mapped for endpoint: {endpoint_name}")
                return []
                
            # Make AJAX request to get all items
            result = await self.ajax_request(function, {})
            
            if result and result.get("status_code") == 200:
                # Parse response content to extract items
                content = result.get("content", "")
                items = self._extract_items_from_listing(content, endpoint_name)
                logger.info(f"✅ Retrieved {len(items)} {endpoint_name}")
                return items
            else:
                logger.warning(f"⚠️ Failed to retrieve {endpoint_name}: {result}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error retrieving all {endpoint_name}: {e!s}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_item(self, endpoint, item_id: int) -> dict[str, Any] | None:
        """Get a specific item by ID."""
        try:
            # Map endpoint to view URL pattern
            url_map = {
                "candidates": f"/index.php?m=candidates&a=show&candidateID={item_id}",
                "companies": f"/index.php?m=companies&a=show&companyID={item_id}",
                "contacts": f"/index.php?m=contacts&a=show&contactID={item_id}",
                "joborders": f"/index.php?m=joborders&a=show&jobOrderID={item_id}",
            }
            
            endpoint_name = endpoint.name.lower() if hasattr(endpoint, 'name') else str(endpoint).lower()
            url_path = url_map.get(endpoint_name)
            
            if not url_path:
                logger.warning(f"⚠️ No URL pattern mapped for endpoint: {endpoint_name}")
                return None
                
            url = urljoin(self.base_url, url_path)
            
            async with self.session.get(url, cookies=self.cookies) as response:
                if response.status == 200:
                    content = await response.text()
                    item = self._extract_item_from_view(content, endpoint_name, item_id)
                    return item
                else:
                    logger.warning(f"⚠️ Failed to get {endpoint_name} ID {item_id}: status {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error getting {endpoint_name} ID {item_id}: {e!s}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def update_item(self, endpoint, item_id: int, update_data: dict[str, Any]) -> bool:
        """Update an item using form submission."""
        try:
            # Map endpoint to edit URL pattern and form data
            endpoint_name = endpoint.name.lower() if hasattr(endpoint, 'name') else str(endpoint).lower()
            
            url_map = {
                "candidates": f"/index.php?m=candidates&a=edit&candidateID={item_id}",
                "companies": f"/index.php?m=companies&a=edit&companyID={item_id}", 
                "contacts": f"/index.php?m=contacts&a=edit&contactID={item_id}",
                "joborders": f"/index.php?m=joborders&a=edit&jobOrderID={item_id}",
            }
            
            url_path = url_map.get(endpoint_name)
            
            if not url_path:
                logger.warning(f"⚠️ No update URL pattern mapped for endpoint: {endpoint_name}")
                return False
                
            # Prepare form data with ID and updates
            form_data = {
                f"{endpoint_name[:-1]}ID": item_id,  # Remove 's' from endpoint name
                **update_data
            }
            
            result = await self.submit_form(url_path, form_data)
            
            if result and result.get("status_code") == 200:
                logger.info(f"✅ Updated {endpoint_name} ID {item_id}")
                return True
            else:
                logger.warning(f"⚠️ Failed to update {endpoint_name} ID {item_id}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error updating {endpoint_name} ID {item_id}: {e!s}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def delete_item(self, endpoint, item_id: int) -> bool:
        """Delete an item using AJAX request."""
        try:
            # Map endpoint to AJAX delete function
            function_map = {
                "candidates": "candidates:delete",
                "companies": "companies:delete",
                "contacts": "contacts:delete", 
                "joborders": "joborders:delete",
            }
            
            endpoint_name = endpoint.name.lower() if hasattr(endpoint, 'name') else str(endpoint).lower()
            function = function_map.get(endpoint_name)
            
            if not function:
                logger.warning(f"⚠️ No delete function mapped for endpoint: {endpoint_name}")
                return False
                
            # Prepare delete data
            delete_data = {
                f"{endpoint_name[:-1]}ID": item_id  # Remove 's' from endpoint name
            }
            
            result = await self.ajax_request(function, delete_data)
            
            if result and result.get("status_code") == 200:
                logger.info(f"✅ Deleted {endpoint_name} ID {item_id}")
                return True
            else:
                logger.warning(f"⚠️ Failed to delete {endpoint_name} ID {item_id}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error deleting {endpoint_name} ID {item_id}: {e!s}")
            return False

    def _extract_items_from_listing(self, content: str, endpoint_name: str) -> list[dict[str, Any]]:
        """Extract items from listing page HTML content."""
        items = []
        try:
            # This is a simplified parser - in a real implementation,
            # you'd want to use a proper HTML parser like BeautifulSoup
            # For now, we'll extract basic info using regex
            
            if endpoint_name == "candidates":
                # Look for candidate table rows with IDs
                pattern = r'candidateID=(\d+).*?>(.*?)<'
                matches = re.findall(pattern, content, re.DOTALL)
                for candidate_id, name_html in matches:
                    # Extract name from HTML (simplified)
                    name_match = re.search(r'>([^<]+)</a>', name_html)
                    if name_match:
                        names = name_match.group(1).split()
                        items.append({
                            "candidateID": int(candidate_id),
                            "firstName": names[0] if names else "",
                            "lastName": " ".join(names[1:]) if len(names) > 1 else ""
                        })
                        
            elif endpoint_name == "companies":
                pattern = r'companyID=(\d+).*?>(.*?)<'
                matches = re.findall(pattern, content, re.DOTALL)
                for company_id, name_html in matches:
                    name_match = re.search(r'>([^<]+)</a>', name_html)
                    if name_match:
                        items.append({
                            "companyID": int(company_id),
                            "name": name_match.group(1).strip()
                        })
                        
            elif endpoint_name == "contacts":
                pattern = r'contactID=(\d+).*?>(.*?)<'
                matches = re.findall(pattern, content, re.DOTALL)
                for contact_id, name_html in matches:
                    name_match = re.search(r'>([^<]+)</a>', name_html)
                    if name_match:
                        names = name_match.group(1).split()
                        items.append({
                            "contactID": int(contact_id),
                            "firstName": names[0] if names else "",
                            "lastName": " ".join(names[1:]) if len(names) > 1 else ""
                        })
                        
            elif endpoint_name == "joborders":
                pattern = r'jobOrderID=(\d+).*?>(.*?)<'
                matches = re.findall(pattern, content, re.DOTALL)
                for job_id, title_html in matches:
                    title_match = re.search(r'>([^<]+)</a>', title_html)
                    if title_match:
                        items.append({
                            "jobOrderID": int(job_id),
                            "title": title_match.group(1).strip()
                        })
                        
        except Exception as e:
            logger.error(f"❌ Error parsing {endpoint_name} listing: {e!s}")
            
        return items

    def _extract_item_from_view(self, content: str, endpoint_name: str, item_id: int) -> dict[str, Any] | None:
        """Extract item details from view page HTML content."""
        try:
            # Simplified extraction - in a real implementation, use proper HTML parsing
            item = {f"{endpoint_name[:-1]}ID": item_id}
            
            if endpoint_name == "candidates":
                # Extract candidate details
                name_match = re.search(r'<h2[^>]*>([^<]+)</h2>', content)
                if name_match:
                    names = name_match.group(1).split()
                    item.update({
                        "firstName": names[0] if names else "",
                        "lastName": " ".join(names[1:]) if len(names) > 1 else ""
                    })
                    
            elif endpoint_name == "companies":
                # Extract company details
                name_match = re.search(r'<h2[^>]*>([^<]+)</h2>', content)
                if name_match:
                    item["name"] = name_match.group(1).strip()
                    
            # Add more extraction logic for other endpoints as needed
            
            return item
            
        except Exception as e:
            logger.error(f"❌ Error parsing {endpoint_name} view: {e!s}")
            return None
